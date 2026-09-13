import os
import re
import traceback
from datetime import datetime
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://kkzylqdyyrmfiayfuqfb.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'sb_publishable_f4-wjMnAMr114DOeqVO0Eg_RHSP-59l')
EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL', 'https://evolution-api-gkgk.onrender.com')
EVOLUTION_TOKEN = os.getenv('EVOLUTION_TOKEN', 'lc-banker-token'),
INSTANCE_NAME = os.getenv('EVOLUTION_INSTANCE', 'lc-banker')
ID_GRUPO_CORRETORES = os.getenv('CORRETORES_GROUP_ID', '9EE45C1B5E22-4654-A30B-E9C1D4D5E583.us')
LIMITE_ALTO_CREDITO = 200000.00
@app.post("/webhook")
@app.post("/webhook/{path:path}")  # <-- ADICIONA ESSA LINHA
async def webhook(request: Request, path: str = ""):

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

app = FastAPI(title="L.C. Banker & Advisory Bot - V25 Afiado")

# FIX CRITICO HEADERS E CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

class MensagemMassa(BaseModel):
    telefone: str
    mensagem: str
    conta: str = ""
    nome: str = ""
    empresa: str = ""
    produto: str = ""

class MassaRequest(BaseModel):
    clientes: list = []
    template: str = ""
    delay: int = 2000

FLUXO_CADASTRO = [
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": "\U0001f512 *Termo de Privacidade (LGPD):* Para prosseguirmos com a sua simulacao de credito, precisamos coletar alguns dados pessoais e financeiros. Voce autoriza o tratamento dos seus dados estritamente para esta finalidade?\n\nDigite:\n*1* - Sim, eu autorizo\n*2* - Nao autorizo"},
    {"id": 1, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "\U0001f464 Digite seu *Nome Completo*:"},
    {"id": 2, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "\U0001f4e7 Digite seu *E-mail* principal:"},
    {"id": 3, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "\U0001faaa Digite seu *CPF* (apenas numeros):"},
    {"id": 4, "estado": "AGUARDANDO_NASCIMENTO", "campo": "data_nascimento", "pergunta": "\U0001f4c5 Digite sua *Data de Nascimento* (Formato: DD/MM/AAAA):"},
    {"id": 5, "estado": "AGUARDANDO_ESTADO_CIVIL", "campo": "estado_civil", "pergunta": "\U0001f48d Qual o seu *Estado Civil*?\n\nDigite o numero da opcao:\n*1* - Solteiro(a)\n*2* - Casado(a)\n*3* - Uniao Estavel\n*4* - Divorciado(a)\n*5* - Viuvo(a)"},
    {"id": 6, "estado": "AGUARDANDO_NOME_CONJUGE", "campo": "nome_completo_companheiro", "pergunta": "\U0001f464 Digite o *Nome Completo do seu Conjugue/Companheiro*:"},
    {"id": 7, "estado": "AGUARDANDO_CPF_CONJUGE", "campo": "cpf_companheiro", "pergunta": "\U0001faaa Digite o *CPF do seu Conjuge* (apenas numeros):"},
    {"id": 8, "estado": "AGUARDANDO_RENDA", "campo": "renda_mensal", "pergunta": "\U0001f4b0 Qual e a sua *Renda Mensal* bruta atual? (Ex: 3500)"},
    {"id": 9, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": "\U0001f4b5 Qual o *Valor do Credito* que voce deseja solicitar? (Ex: 250000)"},
    {"id": 10, "estado": "AGUARDANDO_NOME_2_PROPONENTE", "campo": "nome_2_proponente", "pergunta": "\U0001f465 Como o valor solicitado e alto, e necessario compor renda. Digite o *Nome Completo do 2o Proponente*:"},
    {"id": 11, "estado": "AGUARDANDO_CPF_2_PROPONENTE", "campo": "cpf_2_proponente", "pergunta": "\U0001faaa Digite o *CPF do 2o Proponente* (apenas numeros):"},
    {"id": 12, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": "\U0001f3e0 Agora, digite o *CEP do imovel* que sera utilizado como garantia (apenas numeros):"},
    {"id": 13, "estado": "AGUARDANDO_DOCUMENTO", "campo": "doc_comprovante_renda", "pergunta": "\U0001f4c4 Para finalizar, envie um *documento ou foto* contendo a sua comprovacao de renda (Holerite, Extrato ou IR) diretamente aqui pelo chat:"}
]

MAPA_ESTADOS = {p["estado"]: p for p in FLUXO_CADASTRO}

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
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                dados = response.json()
                if "erro" not in dados:
                    return dados
    except Exception:
        pass
    return None

async def enviar_mensagem_whatsapp(numero_destino: str, texto: str):
    url = f'{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}'
    headers = {'apikey': EVOLUTION_TOKEN, 'Content-Type': 'application/json'}
    payload = {'number': numero_destino, 'text': texto}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers, timeout=10.0)
            print(f"Resposta envio {numero_destino} ({res.status_code}): {res.text}")
            return res.json() if res.status_code in [200,201] else {"status": "erro", "code": res.status_code, "text": res.text}
    except Exception as e:
        print(f"Erro ao enviar mensagem para {numero_destino}: {e}")
        return {"status": "erro", "detalhe": str(e)}

async def notificar_grupo_corretores(dados: dict):
    url = f'{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}'
    headers = {'apikey': EVOLUTION_TOKEN, 'Content-Type': 'application/json'}
    texto_notificacao = (
        "NOVO LEAD DE HOME EQUITY CAPTURADO!\n\n"
        f"Nome: {dados.get('nome')}\n"
        f"WhatsApp: wa.me/{dados.get('celular')}\n"
        f"CPF: {dados.get('cpf')}\n"
        f"Renda Mensal: R$ {dados.get('renda')}\n"
        f"Credito Pretendido: R$ {dados.get('valor')}\n"
        f"Compoe Renda? {dados.get('compor')}\n"
        f"Cidade/UF do Imovel: {dados.get('cidade')}-{dados.get('uf')}\n\n"
        f"Link do Comprovante: {dados.get('doc')}\n\n"
        "Lead salvo no banco Supabase. Atendimento liberado!"
    )
    payload = {'number': ID_GRUPO_CORRETORES, 'text': texto_notificacao}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=10.0)
    except Exception as e:
        print(f"Falha ao enviar notificacao de grupo: {e}")

async def obter_estado_usuario(remetente: str):
    url = f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&select=estado"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=get_supabase_headers(), timeout=5.0)
            if resp.status_code == 200:
                dados = resp.json()
                return dados[0]['estado'] if dados else None
    except Exception as e:
        print(f"Erro ao obter estado no Supabase: {e}")
    return None

async def atualizar_estado_usuario(remetente: str, estado: str):
    if estado is None:
        url = f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}"
        try:
            async with httpx.AsyncClient() as client:
                await client.delete(url, headers=get_supabase_headers(), timeout=5.0)
        except Exception as e:
            print(f"Erro ao deletar estado no Supabase: {e}")
    else:
        url = f"{SUPABASE_URL}/rest/v1/controle_sessao"
        payload = {"remetente": remetente, "estado": estado}
        headers = get_supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, headers=headers, timeout=5.0)
        except Exception as e:
            print(f"Erro ao atualizar estado no Supabase: {e}")

async def salvar_dados_lead(remetente: str, campo: str, valor: str):
    celular_limpo = remetente.split('@')[0]
    url_upsert = f"{SUPABASE_URL}/rest/v1/leads_credito"
    headers = get_supabase_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    payload_init = {"remetente": remetente, "celular": celular_limpo}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url_upsert, json=payload_init, headers=headers, timeout=5.0)
            url_update = f"{SUPABASE_URL}/rest/v1/leads_credito?remetente=eq.{remetente}"
            await client.patch(url_update, json={campo: valor}, headers=get_supabase_headers(), timeout=5.0)
    except Exception as e:
        print(f"Erro ao salvar lead no Supabase: {e}")

async def salvar_endereco_completo(remetente: str, cep, logradouro, bairro, cidade, estado):
    url = f"{SUPABASE_URL}/rest/v1/leads_credito?remetente=eq.{remetente}"
    payload = {
        "cep_garantia": cep,
        "logradouro_garantia": logradouro,
        "bairro_garantia": bairro,
        "cidade_garantia": cidade,
        "estado_garantia": estado
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.patch(url, json=payload, headers=get_supabase_headers(), timeout=5.0)
    except Exception as e:
        print(f"Erro ao salvar endereco no Supabase: {e}")

async def obter_informacoes_lead(remetente: str):
    url = f"{SUPABASE_URL}/rest/v1/leads_credito?remetente=eq.{remetente}&select=*"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=get_supabase_headers(), timeout=5.0)
            if resp.status_code == 200:
                dados = resp.json()
                return dados[0] if dados else None
    except Exception as e:
        print(f"Erro ao obter lead do Supabase: {e}")
    return None

async def processar_mensagem_bot(remetente, texto_recebido, tipo_mensagem, message_obj):
    estado_atual = await obter_estado_usuario(remetente)
    if estado_atual is None:
        if texto_recebido.lower() in ['oi', 'ola', 'menu', 'inicio']:
            msg_inicial = (
                "Ola! Seja bem-vindo(a) a *L.C. Banker & Advisory*.\n\n"
                "Para iniciarmos sua simulacao de emprestimo com garantia (Home Equity), digite *1*."
            )
            await enviar_mensagem_whatsapp(remetente, msg_inicial)
        elif texto_recebido == '1':
            primeiro_passo = FLUXO_CADASTRO[0]
            await atualizar_estado_usuario(remetente, primeiro_passo["estado"])
            await enviar_mensagem_whatsapp(remetente, primeiro_passo["pergunta"])
        return

    if estado_atual not in MAPA_ESTADOS:
        await atualizar_estado_usuario(remetente, None)
        return

    passo = MAPA_ESTADOS[estado_atual]
    proximo_index = passo["id"] + 1

    if passo["estado"] == "AGUARDANDO_LGPD":
        if texto_recebido == "1":
            await salvar_dados_lead(remetente, passo["campo"], "1")
        elif texto_recebido == "2":
            await enviar_mensagem_whatsapp(remetente, "Compreendemos. Sem a autorizacao da LGPD nao podemos seguir. Caso mude de ideia, digite *Oi*.")
            await atualizar_estado_usuario(remetente, None)
            return
        else:
            await enviar_mensagem_whatsapp(remetente, "Opcao invalida. Digite *1* para autorizar ou *2* para recusar.")
            return
    elif passo["estado"] in ["AGUARDANDO_CPF", "AGUARDANDO_CPF_CONJUGE", "AGUARDANDO_CPF_2_PROPONENTE"]:
        cpf_limpo = re.sub(r'\D', '', texto_recebido)
        if not validar_cpf(cpf_limpo):
            await enviar_mensagem_whatsapp(remetente, "CPF invalido. Por favor, digite um numero valido (apenas numeros):")
            return
        await salvar_dados_lead(remetente, passo["campo"], cpf_limpo)
    elif passo["estado"] == "AGUARDANDO_NASCIMENTO":
        if not validar_data_nascimento(texto_recebido):
            await enviar_mensagem_whatsapp(remetente, "Data invalida. Use o formato DD/MM/AAAA e certifique-se de que e maior de 18 anos:")
            return
        await salvar_dados_lead(remetente, passo["campo"], texto_recebido)
    elif passo["estado"] == "AGUARDANDO_ESTADO_CIVIL":
        mapeamento = {"1": "Solteiro(a)", "2": "Casado(a)", "3": "Uniao Estavel", "4": "Divorciado(a)", "5": "Viuvo(a)"}
        if texto_recebido not in mapeamento:
            await enviar_mensagem_whatsapp(remetente, "Opcao invalida. Escolha um numero de *1 a 5*.")
            return
        await salvar_dados_lead(remetente, passo["campo"], mapeamento[texto_recebido])
        if texto_recebido in ["1", "4", "5"]:
            proximo_index = 8
    elif passo["estado"] == "AGUARDANDO_VALOR":
        valor_num = converter_para_float(texto_recebido)
        if valor_num <= 0:
            await enviar_mensagem_whatsapp(remetente, "Valor invalido. Digite um valor numerico correto (Ex: 150000):")
            return
        await salvar_dados_lead(remetente, passo["campo"], str(valor_num))
        if valor_num < LIMITE_ALTO_CREDITO:
            await salvar_dados_lead(remetente, "compor_renda", "Nao")
            proximo_index = 12
        else:
            await salvar_dados_lead(remetente, "compor_renda", "Sim")
    elif passo["estado"] == "AGUARDANDO_CEP":
        dados_cep = await consultar_viacep(texto_recebido)
        if not dados_cep:
            await enviar_mensagem_whatsapp(remetente, "CEP nao encontrado. Digite novamente apenas os 8 numeros do CEP:")
            return
        await salvar_endereco_completo(remetente, dados_cep.get("cep"), dados_cep.get("logradouro"), dados_cep.get("bairro"), dados_cep.get("localidade"), dados_cep.get("uf"))
        feedback_endereco = f"Endereco Localizado:\n Rua: {dados_cep.get('logradouro')}\n Bairro: {dados_cep.get('bairro')}\n Cidade: {dados_cep.get('localidade')}-{dados_cep.get('uf')}"
        await enviar_mensagem_whatsapp(remetente, feedback_endereco)
    elif passo["estado"] == "AGUARDANDO_DOCUMENTO":
        if tipo_mensagem not in ["documentMessage", "imageMessage"]:
            await enviar_mensagem_whatsapp(remetente, "Por favor, envie um arquivo valido. Pode ser um PDF ou foto legivel do comprovante:")
            return
        media_url = message_obj.get('documentMessage', {}).get('mediaUrl') or message_obj.get('imageMessage', {}).get('mediaUrl') or "Arquivo recebido no WhatsApp"
        await salvar_dados_lead(remetente, passo["campo"], media_url)
    else:
        await salvar_dados_lead(remetente, passo["campo"], texto_recebido)

    if proximo_index < len(FLUXO_CADASTRO):
        proximo_passo = FLUXO_CADASTRO[proximo_index]
        await atualizar_estado_usuario(remetente, proximo_passo["estado"])
        await enviar_mensagem_whatsapp(remetente, proximo_passo["pergunta"])
    else:
        await atualizar_estado_usuario(remetente, None)
        lead_info = await obter_informacoes_lead(remetente)
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
            "Cadastro e Documentacao Concluidos!\n\n"
            "Nossa equipe de especialistas da *L.C. Banker & Advisory* recebeu suas informacoes. "
            "Analisaremos o imovel de garantia e entraremos em contato em breve com a proposta!"
        )
        await enviar_mensagem_whatsapp(remetente, sucesso_msg)

@app.get('/')
async def root():
    return {'status': 'online', 'service': 'L.C. Banker & Advisory Bot V25', 'logo': 'LC', 'evolution': INSTANCE_NAME, 'render': 'https://lc-bankersadvisory.onrender.com', 'headers': 'alocado'}

@app.head('/')
async def head_root():
    return {'status': 'ok'}

@app.get('/health')
async def health_check():
    return {'status': 'ok', 'headers': 'alocado', 'cors': 'liberado', 'evolution_url': EVOLUTION_API_URL, 'instance': INSTANCE_NAME, 'contas': '0000 CEO, 0001 PF, 1100 PJ'}

@app.options('/{path:path}')
async def options_handler(path: str):
    return {'status': 'ok', 'path': path}

@app.post('/send')
@app.post('/api/send')
@app.post('/api/massa')
@app.post('/message/sendText/{instance}')
async def enviar_massa(request: Request, instance: str = None):
    try:
        data = await request.json()
        print(f"Massa recebida: {data}")
        telefone = data.get('telefone') or data.get('number') or data.get('celular')
        mensagem = data.get('mensagem') or data.get('text') or data.get('message')
        conta = data.get('conta', '')
        nome = data.get('nome', '')

        if 'clientes' in data:
            resultados = []
            for cliente in data['clientes']:
                tel = cliente.get('telefone') or cliente.get('number')
                msg = cliente.get('mensagem') or cliente.get('text') or data.get('template','')
                if cliente.get('nome'):
                    primeiro = cliente['nome'].split()[0]
                    msg = msg.replace('{primeiro_nome}', primeiro).replace('{nome}', cliente['nome'])
                msg = msg.replace('{conta}', cliente.get('conta','')).replace('{empresa}', cliente.get('empresa','')).replace('{produto}', cliente.get('produto',''))
                res = await enviar_mensagem_whatsapp(tel, msg)
                resultados.append({"telefone": tel, "status": "enviado", "conta": cliente.get('conta'), "evolution": res})
            return {"status": "massa_enviada", "total": len(resultados), "resultados": resultados, "headers": "ok", "contas": "0000,0001,1100"}

        if telefone and mensagem:
            if nome:
                primeiro = nome.split()[0]
                mensagem = mensagem.replace('{primeiro_nome}', primeiro).replace('{nome}', nome)
            mensagem = mensagem.replace('{conta}', conta)
            res = await enviar_mensagem_whatsapp(telefone, mensagem)
            return {"status": "enviado", "para": telefone, "conta": conta, "mensagem": mensagem, "evolution_response": res, "headers_alocado": True}

        return {"status": "erro", "detalhe": "telefone e mensagem obrigatorios", "recebido": data}
    except Exception as e:
        print(f'Erro rota massa: {e}')
        traceback.print_exc()
        return {'status': 'erro', 'detalhe': str(e), 'headers': 'alocado mas erro interno'}

@app.post('/webhook')
async def receber_mensagem(request: Request):
    try:
        data = await request.json()
        print(f"Payload bruto: {data}")
        event = data.get('event')
        message_data = data.get('data', {})
        if event in ["messages.upsert", "MESSAGES_UPSERT"] or message_data:
            key = message_data.get('key', {})
            remetente = key.get('remoteJid')
            if key.get('fromMe') or not remetente:
                return {'status': 'ignorado'}
            message_obj = message_data.get('message', {})
            tipo_mensagem = message_data.get('messageType')
            texto_recebido = (
                message_obj.get('conversation')
                or message_obj.get('extendedTextMessage', {}).get('text')
                or message_obj.get('imageMessage', {}).get('caption')
                or message_obj.get('videoMessage', {}).get('caption')
                or message_obj.get('documentMessage', {}).get('caption')
                or message_obj.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage', {}).get('caption')
                or ''
            ).strip()
            print(f"Processando mensagem de [{remetente}]: '{texto_recebido}'")
            await processar_mensagem_bot(remetente, texto_recebido, tipo_mensagem, message_obj)
        return {'status': 'sucesso'}
    except Exception as e:
        print(f'Erro no processamento do webhook: {e}')
        traceback.print_exc()
        return {'status': 'erro'}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)