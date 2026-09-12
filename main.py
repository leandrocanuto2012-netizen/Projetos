import traceback
import re
from datetime import datetime
import httpx
import mysql.connector
from mysql.connector import pooling
from fastapi import FastAPI, HTTPException, Request
import uvicorn
import os
import time


#  1. CONFIGURAOES GLOBAIS - AJUSTE AQUI SEUS DADOS

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'root123'),
    'port': int(os.getenv('DB_PORT', '13306')),
    'database': os.getenv('DB_NAME', 'bot_carteira_db'),
    'connection_timeout': int(os.getenv('DB_CONNECTION_TIMEOUT', '5')),
}

EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL', 'http://localhost:8890')
EVOLUTION_TOKEN = os.getenv('EVOLUTION_TOKEN', '1C5F3BBD6A06-4030-944F-78D365077AB1')
INSTANCE_NAME = os.getenv('EVOLUTION_INSTANCE', 'consultoria de crédito')
ID_GRUPO_CORRETORES = os.getenv(
    'CORRETORES_GROUP_ID', '9EE45C1B5E22-4654-A30B-E9C1D4D5E583.us'
)

LIMITE_ALTO_CREDITO = 200000.00  # Valor a partir do qual exige 2º proponente


#  2. INICIALIZAÇÃO E ROTINA DE CRIAÇÃO AUTOMÁTICA DO BANCO DE DADOS

print("[1/5] Verificando e estruturando Banco de Dados MySQL...")
db_pool = None
ultimo_erro = None
for tentativa in range(1, 11):
    try:
        tmp_conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
        )
        tmp_cursor = tmp_conn.cursor()
        tmp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
        tmp_cursor.close()
        tmp_conn.close()
        db_pool = pooling.MySQLConnectionPool(
            pool_name='mypool', pool_size=10, **DB_CONFIG
        )
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS controle_sessao (
                remetente VARCHAR(100) NOT NULL,
                estado VARCHAR(100) NOT NULL,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (remetente)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads_credito (
                id INT AUTO_INCREMENT PRIMARY KEY,
                remetente VARCHAR(100) NOT NULL UNIQUE,
                celular VARCHAR(30),
                lgpd_autorizado VARCHAR(10),
                nome_completo VARCHAR(255),
                email VARCHAR(255),
                cpf VARCHAR(14),
                data_nascimento VARCHAR(10),
                estado_civil VARCHAR(50),
                nome_completo_companheiro VARCHAR(255),
                cpf_companheiro VARCHAR(14),
                renda_mensal DECIMAL(12,2),
                valor_solicitado DECIMAL(12,2),
                compor_renda VARCHAR(10),
                nome_2_proponente VARCHAR(255),
                cpf_2_proponente VARCHAR(14),
                cep_garantia VARCHAR(10),
                logradouro_garantia VARCHAR(255),
                bairro_garantia VARCHAR(150),
                cidade_garantia VARCHAR(150),
                estado_garantia VARCHAR(2),
                doc_comprovante_renda TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Banco de dados disponível.")
        break
    except mysql.connector.Error as err:
        ultimo_erro = err
        print(f"Banco indisponível (tentativa {tentativa}/10): {err}")
        if tentativa < 10:
            time.sleep(3)

if db_pool is None:
    raise RuntimeError(f"Não foi possível conectar ao MySQL após 10 tentativas: {ultimo_erro}")
    
 #  3. MÁQUINA DE ESTADOS - FLUXO DE PERGUNTAS

FLUXO_CADASTRO =[
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": " *Termo de Privacidade (LGPD):* Para prosseguirmos com a sua simulação de crédito, precisamos coletar alguns dados pessoais e financeiros. Você autoriza o tratamento dos seus dados estritamente para esta finalidade?\n\nDigite:\n*1* - Sim, eu autorizo\n*2* - Não autorizo"},
    {"id": 1, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": " Digite seu *Nome Completo*:"},
    {"id": 2, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": " Digite seu *E-mail* principal:"},
    {"id": 3, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "🪪 Digite seu *CPF* (apenas números):"},
    {"id": 4, "estado": "AGUARDANDO_NASCIMENTO", "campo": "data_nascimento", "pergunta": " Digite sua *Data de Nascimento* (Formato: DD/MM/AAAA):"},
    {"id": 5, "estado": "AGUARDANDO_ESTADO_CIVIL", "campo": "estado_civil", "pergunta": " Qual o seu *Estado Civil*?\n\nDigite o número da opção:\n*1* - Solteiro(a)\n*2* - Casado(a)\n*3* - União Estável\n*4* - Divorciado(a)\n*5* - Viúvo(a)"},
    {"id": 6, "estado": "AGUARDANDO_NOME_CONJUGE", "campo": "nome_completo_companheiro", "pergunta": " Digite o *Nome Completo do seu Cônjuge/Companheiro*: "},
    {"id": 7, "estado": "AGUARDANDO_CPF_CONJUGE", "campo": "cpf_companheiro", "pergunta": " Digite o *CPF do seu Cônjuge* (apenas números):"},
    {"id": 8, "estado": "AGUARDANDO_RENDA", "campo": "renda_mensal", "pergunta": " Qual é a sua *Renda Mensal* bruta atual? (Ex: 3500)"},
    {"id": 9, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": " Qual o *Valor do Crédito* que você deseja solicitar? (Ex: 250000)"},
    {"id": 10, "estado": "AGUARDANDO_NOME_2_PROPONENTE", "campo": "nome_2_proponente", "pergunta": " Como o valor solicitado é alto, é necessário compor renda. Digite o *Nome Completo do 2º Proponente*:"},
    {"id": 11, "estado": "AGUARDANDO_CPF_2_PROPONENTE", "campo": "cpf_2_proponente", "pergunta": " Digite o *CPF do 2º Proponente* (apenas números):"},
    {"id": 12, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": " Agora, digite o *CEP do imóvel* que será utilizado como garantia (apenas números):"},
    {"id": 13, "estado": "AGUARDANDO_DOCUMENTO", "campo": "doc_comprovante_renda", "pergunta": " Para finalizar, envie um *documento ou foto* contendo a sua comprovação de renda (Holerite, Extrato ou IR) diretamente aqui pelo chat:"}
]

MAPA_ESTADOS = {p["estado"]: p for p in FLUXO_CADASTRO}


#  4. FUNÇÕES DE VALIDAÇÃO E INTEGRAÇÕES EXTERNAS

def validar_cpf(cpf: str) -> bool:
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i + 1) - num) for num in range(i))
        digito = ((soma * 10) % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True

def validar_data_nascimento(data_txt: str) -> bool:
    data_limpa = re.sub(r'[^\d/]', '', data_txt)
    if not re.match(r'^\d{2}/\d{2}/\d{4}$', data_limpa):
        return False
    try:
        dt = datetime.strptime(data_limpa, "%d/%m/%Y")
        ano_atual = datetime.now().year
        if dt.year < (ano_atual - 100) or dt.year > (ano_atual - 18):
            return False
        return True
    except Exception:
        return False
    return None

def converter_para_float(texto: str) -> float:
    limpo = re.sub(r'[^\d,.]', '', texto)
    if ',' in limpo and '.' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    elif ',' in limpo:
        limpo = limpo.replace(',', '.')
    try:
        return float(limpo)
    except ValueError:
        return 0.0

async def consultar_viacep(cep: str) -> dict:
    cep_limpo = re.sub(r'\D', '', cep)
    if len(cep_limpo) != 8:
        return None
    url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                dados = response.json()
                if "erro" not in dados:
                    return dados
    except Exception:
        pass
    return None


#  5. DISPAROS DE DISPOSITIVOS E SESSÕES VIA WHATSAPP (EVOLUTION API)

async def enviar_mensagem_whatsapp(numero_destino: str, texto: str):
    url = f'{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}'
    headers = {'apikey': EVOLUTION_TOKEN, 'Content-Type': 'application/json'}
    payload = {'number': numero_destino, 'text': texto}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Erro ao enviar mensagem para {numero_destino}: {e}")

async def notificar_grupo_corretores(dados: dict):
    url = f'{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}'
    headers = {'apikey': EVOLUTION_TOKEN, 'Content-Type': 'application/json'}
    texto_notificacao = (
        " *NOVO LEAD DE HOME EQUITY CAPTURADO!* \n\n"
        f" *Nome:* {dados.get('nome')}\n"
        f" *WhatsApp:* wa.me/{dados.get('celular')}\n"
        f" *CPF:* {dados.get('cpf')}\n"
        f" *Renda Mensal:* R$ {dados.get('renda')}\n"
        f" *Crédito Pretendido:* R$ {dados.get('valor')}\n"
        f" *Compõe Renda?* {dados.get('compor')}\n"
        f" *Cidade/UF do Imóvel:* {dados.get('cidade')}-{dados.get('uf')}\n\n"
        f" *Link do Comprovante:* {dados.get('doc')}\n\n"
        " _Lead salvo no banco de dados. Um corretor já pode assumir o atendimento!_"
    )
    payload = {'number': ID_GRUPO_CORRETORES, 'text': texto_notificacao}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Falha ao enviar notificação de grupo: {e}")


#  6. PERSISTÊNCIA - ROTINAS AUXILIARES DO MYSQL POOL
def obter_estado_usuario(remetente):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT estado FROM controle_sessao WHERE remetente = %s", (remetente,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None


def atualizar_estado_usuario(remetente, estado):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    if estado is None:
        cursor.execute("DELETE FROM controle_sessao WHERE remetente = %s", (remetente,))
    else:
        cursor.execute(
            "INSERT INTO controle_sessao (remetente, estado) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE estado = %s", 
            (remetente, estado, estado)
        )
    conn.commit()
    cursor.close()
    conn.close()


def salvar_dados_lead(remetente, campo, valor):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    celular_limpo = remetente.split('@')[0]
    cursor.execute(
        "INSERT IGNORE INTO leads_credito (remetente, celular) VALUES (%s, %s)", 
        (remetente, celular_limpo)
    )
    query = f"UPDATE leads_credito SET {campo} = %s WHERE remetente = %s"
    cursor.execute(query, (valor, remetente))
    conn.commit()
    cursor.close()
    conn.close()


def salvar_endereco_completo(remetente, cep, logradouro, bairro, cidade, estado):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    query = """
        UPDATE leads_credito
        SET cep_garantia = %s, logradouro_garantia = %s, bairro_garantia = %s, 
            cidade_garantia = %s, estado_garantia = %s
        WHERE remetente = %s
    """
    cursor.execute(query, (cep, logradouro, bairro, cidade, estado, remetente))
    conn.commit()
    cursor.close()
    conn.close()



# 7. PROCESSAMENTO E REGRAS DE DESVIO DO FLUXO

async def processar_mensagem_bot(remetente, texto_recebido, tipo_mensagem, message_obj):
    estado_atual = obter_estado_usuario(remetente)
    
    if estado_atual is None:
        if texto_recebido.lower() in ['oi', 'olá', 'ola', 'menu', 'inicio']:
            msg_inicial = (
                " Olá! Seja bem-vindo(a) à nossa consultoria de crédito.\n\n"
                "Para iniciarmos sua simulação de empréstimo com garantia, digite *1*."
            )
            await enviar_mensagem_whatsapp(remetente, msg_inicial)
        elif texto_recebido == '1':
            primeiro_passo = FLUXO_CADASTRO[0]
            atualizar_estado_usuario(remetente, primeiro_passo["estado"])
            await enviar_mensagem_whatsapp(remetente, primeiro_passo["pergunta"])
        return

    if estado_atual not in MAPA_ESTADOS:
        atualizar_estado_usuario(remetente, None)
        return

    passo = MAPA_ESTADOS[estado_atual]
    proximo_index = passo["id"] + 1

    if passo["estado"] == "AGUARDANDO_LGPD":
        if texto_recebido == "1":
            salvar_dados_lead(remetente, passo["campo"], "1")
        elif texto_recebido == "2":
            await enviar_mensagem_whatsapp(
                remetente, 
                " Compreendemos. Sem a autorização da LGPD não podemos seguir. "
                "Caso mude de ideia, digite *Oi*."
            )
            atualizar_estado_usuario(remetente, None)
            return
        else:
            await enviar_mensagem_whatsapp(
                remetente, 
                " Opção inválida. Digite *1* para autorizar ou *2* para recusar."
            )
            return

    elif passo["estado"] in ["AGUARDANDO_CPF", "AGUARDANDO_CPF_CONJUGE", "AGUARDANDO_CPF_2_PROPONENTE"]:
        cpf_limpo = re.sub(r'\D', '', texto_recebido)
        if not validar_cpf(cpf_limpo):
            await enviar_mensagem_whatsapp(
                remetente, 
                " *CPF inválido.* Por favor, digite um número válido (apenas números):"
            )
            return
        salvar_dados_lead(remetente, passo["campo"], cpf_limpo)

    elif passo["estado"] == "AGUARDANDO_NASCIMENTO":
        if not validar_data_nascimento(texto_recebido):
            await enviar_mensagem_whatsapp(
                remetente, 
                " *Data inválida ou não permitida.* Use o formato DD/MM/AAAA e "
                "certifique-se de que o proponente é maior de 18 anos:"
            )
            return
        salvar_dados_lead(remetente, passo["campo"], texto_recebido)

    elif passo["estado"] == "AGUARDANDO_ESTADO_CIVIL":
        mapeamento = {
            "1": "Solteiro(a)", 
            "2": "Casado(a)", 
            "3": "União Estável", 
            "4": "Divorciado(a)", 
            "5": "Viúvo(a)"
        }
        if texto_recebido not in mapeamento:
            await enviar_mensagem_whatsapp(remetente, " Opção inválida. Escolha um número de *1 a 5*.")
            return
        salvar_dados_lead(remetente, passo["campo"], mapeamento[texto_recebido])
        if texto_recebido in ["1", "4", "5"]:
            proximo_index = 8  # Salta os passos 6 e 7 do cônjuge

    elif passo["estado"] == "AGUARDANDO_VALOR":
        valor_num = converter_para_float(texto_recebido)
        if valor_num <= 0:
            await enviar_mensagem_whatsapp(
                remetente, 
                " Valor inválido. Digite um valor numérico correto (Ex: 150000):"
            )
            return
        salvar_dados_lead(remetente, passo["campo"], str(valor_num))
        if valor_num < LIMITE_ALTO_CREDITO:
            salvar_dados_lead(remetente, "compor_renda", "Não")
            proximo_index = 12  # Salta os passos 10 e 11 do 2º proponente
        else:
            salvar_dados_lead(remetente, "compor_renda", "Sim")

    elif passo["estado"] == "AGUARDANDO_CEP":
        dados_cep = await consultar_viacep(texto_recebido)
        if not dados_cep:
            await enviar_mensagem_whatsapp(
                remetente, 
                " *CEP não encontrado ou inválido.* Por favor, digite novamente "
                "apenas os 8 números do CEP:"
            )
            return
        salvar_endereco_completo(
            remetente,
            dados_cep.get("cep"),
            dados_cep.get("logradouro"),
            dados_cep.get("bairro"),
            dados_cep.get("localidade"),
            dados_cep.get("uf")
        )
        feedback_endereco = (
            f" *Endereço Localizado:*\n"
            f"• Rua: {dados_cep.get('logradouro')}\n"
            f"• Bairro: {dados_cep.get('bairro')}\n"
            f"• Cidade: {dados_cep.get('localidade')}-{dados_cep.get('uf')}"
        )
        await enviar_mensagem_whatsapp(remetente, feedback_endereco)

    elif passo["estado"] == "AGUARDANDO_DOCUMENTO":
        if tipo_mensagem not in ["documentMessage", "imageMessage"]:
            await enviar_mensagem_whatsapp(
                remetente, 
                " *Por favor, envie um arquivo válido.* Pode ser um PDF ou uma "
                "foto legível do seu comprovante:"
            )
            return
        media_url = (
            message_obj.get('documentMessage', {}).get('mediaUrl') or 
            message_obj.get('imageMessage', {}).get('mediaUrl') or 
            "Arquivo recebido (Armazenado localmente)"
        )
        salvar_dados_lead(remetente, passo["campo"], media_url)
        
    else:
        salvar_dados_lead(remetente, passo["campo"], texto_recebido)

    # Direcionamento ou encerramento
    if proximo_index < len(FLUXO_CADASTRO):
        proximo_passo = FLUXO_CADASTRO[proximo_index]
        atualizar_estado_usuario(remetente, proximo_passo["estado"])
        await enviar_mensagem_whatsapp(remetente, proximo_passo["pergunta"])
    else:
        atualizar_estado_usuario(remetente, None)
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT nome_completo, cpf, renda_mensal, valor_solicitado, compor_renda, "
            "cidade_garantia, estado_garantia, doc_comprovante_renda "
            "FROM leads_credito WHERE remetente = %s", 
            (remetente,)
        )
        lead_info = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if lead_info:
            dados_alerta = {
                "nome": lead_info.get("nome_completo"),
                "celular": remetente.split('@')[0],
                "cpf": lead_info.get("cpf"),
                "renda": lead_info.get("renda_mensal"),
                "valor": lead_info.get("valor_solicitado"),
                "compor": lead_info.get("compor_renda"),
                "cidade": lead_info.get("cidade_garantia"),
                "uf": lead_info.get("estado_garantia"),
                "doc": lead_info.get("doc_comprovante_renda")
            }
            await notificar_grupo_corretores(dados_alerta)
            
        sucesso_msg = (
            " *Cadastro e Documentação Concluídos!*\n\n"
            "Nossos especialistas em Home Equity receberam sua solicitação, endereço da "
            "garantia e comprovante de renda. Entraremos em contato com as propostas!"
        )
        await enviar_mensagem_whatsapp(remetente, sucesso_msg)

# 8. ENDPOINT DO WEBHOOK PRINCIPAL (ENTRYPOINT)

print("[3/5] Estruturando rotas do Webhook...")
app = FastAPI()

@app.get('/')
async def root():
    return {'status': 'ok', 'service': 'api'}

@app.get('/health')
async def health_check():
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        return {'status': 'ok', 'database': 'ok'}
    except mysql.connector.Error as err:
        print(f'Healthcheck do banco falhou: {err}')
        raise HTTPException(status_code=503, detail='Banco de dados indisponível')
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.post('/webhook')
async def receber_mensagem(request: Request):
    try:
        data = await request.json()
        message_data = data.get('data', {})
        
        key = message_data.get('key', {})
        remetente = key.get('remoteJid')
        
        # Ignora mensagens enviadas pelo próprio bot ou sem remetente
        if key.get('fromMe') or not remetente:
            return {'status': 'ignorado'}

        message_obj = message_data.get('message', {})
        tipo_mensagem = message_data.get('messageType')

        # Extração flexível do texto (cobre mensagens simples, respostas e mídias)
        texto_recebido = (
            message_obj.get('conversation')
            or message_obj.get('extendedTextMessage', {}).get('text')
            or message_obj.get('imageMessage', {}).get('caption')
            or message_obj.get('videoMessage', {}).get('caption')
            or message_obj.get('documentMessage', {}).get('caption')
            or message_obj.get('documentWithCaptionMessage', {})
                          .get('message', {})
                          .get('documentMessage', {})
                          .get('caption')
            or ''
        ).strip()

        await processar_mensagem_bot(remetente, texto_recebido, tipo_mensagem, message_obj)
        return {'status': 'sucesso'}

    except Exception as e:
        print(f'Erro no processamento do webhook: {e}')
        traceback.print_exc()
        return {'status': 'erro'}

## @app.post('/webhook')
##async def receber_mensagem(request: Request):
    ##try:
        ##data = await request.json()
        ##message_data = data.get('data', {})
        ##remetente = message_data.get('key', {}).get('remoteJid')
        ##if message_data.get('key', {}).get('fromMe') or not remetente:
        ##return {'status': 'ignorado'}

        ##message_obj = message_data.get('message', {})
        ##tipo_mensagem = message_data.get('messageType')
        ##texto_recebido = (
            ##message_obj.get('conversation')
            ##or message_obj.get('extendedTextMessage', {}).get('text')
            ##or message_obj.get('documentMessage', {}).get('caption')
            ##or message_obj.get('imageMessage', {}).get('caption')
            ##or ''
        ##).trip()
        ##await processar_mensagem_bot(remetente, texto_recebido, tipo_mensagem, message_obj)
        ##return {'status': 'sucesso'}
    ##except Exception as e:
        ##print(f'Erro no processamento do webhook: {e}')
        ##traceback.print_exc()
        ##return {'status': 'erro'}
##if __name__ == "__main__":'"
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)