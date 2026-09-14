import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = "https://kkzylqdyyrmfiayfuqfb.supabase.co"
SUPABASE_KEY = "sb_publishable_f4-wjMnAMr114DOeqV00Eg_RHSP-591"
EVOLUTION_API_URL = "https://evolution-api-gkgk.onrender.com"
EVOLUTION_TOKEN = "lc-banker-token"
INSTANCE_NAME = "lc-banker"

# TROCA AQUI PELO SEU NUMERO COM DDD
SEU_NUMERO_DONO = "5541999999999@s.whatsapp.net"

PROCESSADOS = set()
ESTADOS_MEM = {}
CONTADOR = {}

def get_h_upsert():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}
def get_h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

# ========= VISUAL PREMIUM - LECO =========
SAUDACAO = """*L.C. BANKERS ADVISORY*
━━━━━━━━━━━━━━━━━━
Olá.

Aqui é o *Leco*, consultor especialista em crédito com garantia de imóvel.

Taxas a partir de 1,09% a.m. | Atendimento consultivo.

Vamos iniciar sua análise?"""

LGPD_TEXTO = """*TERMO DE CONSENTIMENTO | LGPD*
━━━━━━━━━━━━━━━━━━
Conforme Lei 13.709/18, necessito da sua autorização para tratar seus dados *exclusivamente* para simulação de crédito.

*1* - Sim, autorizo
*2* - Não autorizo"""

MENU_PRINCIPAL = """*MENU PRINCIPAL*
━━━━━━━━━━━━━━━━━━
Selecione a opção desejada:

*1* • Crédito com Garantia de Imóvel
*2* • Refinanciamento / Aumento de Valor
*3* • Portabilidade de Contrato
*4* • Acompanhar Proposta em Andamento
*5* • Falar Diretamente com o Responsável

_Digite apenas o número._"""

FLUXO_DADOS = [
    {"id": 0, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "*ETAPA 1/5 | IDENTIFICAÇÃO*\n━━━━━━━━━━━━━━━━━━\n👤 *Nome Completo*\n\nInforme como consta no documento."},
    {"id": 1, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "*ETAPA 2/5 | CONTATO*\n━━━━━━━━━━━━━━━━━━\n📧 *E-mail Principal*\n\nOnde enviaremos sua proposta."},
    {"id": 2, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "*ETAPA 3/5 | VALIDAÇÃO*\n━━━━━━━━━━━━━━━━━━\n🔐 *CPF*\n\nApenas números. Ambiente 100% seguro."},
    {"id": 3, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": "*ETAPA 4/5 | VALOR*\n━━━━━━━━━━━━━━━━━━\n💰 *Valor Pretendido*\n\nEx: 350000"},
    {"id": 4, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": "*ETAPA 5/5 | GARANTIA*\n━━━━━━━━━━━━━━━━━━\n🏠 *CEP do Imóvel em Garantia*\n\nÚltima etapa."},
]

MSG_FINAL = """*PROTOCOLO GERADO* ✅
━━━━━━━━━━━━━━━━━━
Dados recebidos com sucesso.

Protocolo: *LCB-{final}*

Nossa mesa técnica da *L.C. BANKERS* analisará seu perfil e retornará em até *02h úteis* com as melhores condições.

Atenciosamente,
*Leco* | Consultoria
L.C. Bankers Advisory"""

MSG_FALAR_COM_DONO_CLIENTE = """*ATENDIMENTO DIRECIONADO* 👨‍💼
━━━━━━━━━━━━━━━━━━
Perfeito.

Já notifiquei o responsável. Ele te atenderá aqui mesmo em até *10 minutos*.

Se desejar, pode adiantar sua dúvida."""

# ========= FUNCOES =========
async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as c:
        await c.post(url, json={"number": numero, "text": texto}, headers=h, timeout=10)

async def get_estado(remetente):
    if remetente in ESTADOS_MEM: return ESTADOS_MEM[remetente]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&select=estado", headers=get_h(), timeout=5)
            if r.status_code == 200 and r.json():
                ESTADOS_MEM[remetente] = r.json()[0]["estado"]
                return ESTADOS_MEM[remetente]
    except: pass
    return None

async def set_estado(remetente, estado):
    if estado is None:
        ESTADOS_MEM.pop(remetente, None)
        CONTADOR.pop(remetente, None)
    else:
        ESTADOS_MEM[remetente] = estado
        CONTADOR[remetente] = CONTADOR.get(remetente, 0) + 1
        if CONTADOR[remetente] > 8:
            ESTADOS_MEM.pop(remetente, None)
            CONTADOR.pop(remetente, None)
            estado = None
    try:
        async with httpx.AsyncClient() as client:
            url = f"{SUPABASE_URL}/rest/v1/controle_sessao?on_conflict=remetente"
            if estado is None:
                await client.delete(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}", headers=get_h(), timeout=5)
            else:
                await client.post(url, json={"remetente": remetente, "estado": estado, "contador": CONTADOR.get(remetente,0)}, headers=get_h_upsert(), timeout=5)
    except: pass

async def save_lead(remetente, campo, valor):
    try:
        cel = remetente.split("@")[0]
        async with httpx.AsyncClient() as client:
            url = f"{SUPABASE_URL}/rest/v1/leads_credito?on_conflict=remetente"
            await client.post(url, json={"remetente": remetente, "celular": cel, campo: valor}, headers=get_h_upsert(), timeout=5)
    except: pass

async def processa(jid, txt):
    estado = await get_estado(jid)

    if estado is None:
        await set_estado(jid, "AGUARDANDO_LGPD")
        await send(jid, SAUDACAO)
        await send(jid, LGPD_TEXTO)
        return

    if estado == "AGUARDANDO_LGPD":
        if txt == "1":
            await save_lead(jid, "lgpd_autorizado", "SIM")
            await set_estado(jid, "AGUARDANDO_MENU")
            await send(jid, MENU_PRINCIPAL)
            return
        if txt == "2":
            await set_estado(jid, None)
            await send(jid, "Entendido. Encerramos por aqui.\n\n*L.C. Bankers Advisory*")
            return
        await send(jid, "Por favor, digite *1* para SIM ou *2* para NÃO")
        return

    if estado == "AGUARDANDO_MENU":
        if txt in ["1","2","3"]:
            tipos = {"1":"CREDITO_GARANTIA","2":"REFIN","3":"PORTABILIDADE"}
            await save_lead(jid, "tipo_solicitacao", tipos[txt])
            await set_estado(jid, FLUXO_DADOS[0]["estado"])
            await send(jid, FLUXO_DADOS[0]["pergunta"])
            return
        if txt == "4":
            await set_estado(jid, "AGUARDANDO_CPF_ACOMPANHAR")
            await send(jid, "*ACOMPANHAMENTO DE PROPOSTA*\n━━━━━━━━━━━━━━━━━━\n🔍 Informe seu *CPF* para consulta:")
            return
        if txt == "5":
            await save_lead(jid, "tipo_solicitacao", "FALAR_COM_DONO")
            await set_estado(jid, None)
            await send(jid, MSG_FALAR_COM_DONO_CLIENTE)
            if "999999999" not in SEU_NUMERO_DONO:
                await send(SEU_NUMERO_DONO, f"🚨 *LEAD QUER FALAR COM VOCÊ*\n━━━━━━━━━━━━━━\nDe: {jid}\nCel: {jid.split('@')[0]}\nTipo: FALAR_COM_DONO")
            return
        await send(jid, "Opção inválida. Digite de *1* a *5*.")
        await send(jid, MENU_PRINCIPAL)
        return

    if estado == "AGUARDANDO_CPF_ACOMPANHAR":
        await save_lead(jid, "cpf", txt)
        await set_estado(jid, None)
        await send(jid, f"*CONSULTA SOLICITADA* 🔍\n━━━━━━━━━━━━━━━━━━\nCPF *{txt}* recebido.\n\nNossa equipe retornará com o status.\n\n— *Leco*")
        return

    passo = next((p for p in FLUXO_DADOS if p["estado"] == estado), None)
    if passo:
        await save_lead(jid, passo["campo"], txt)
        prox = passo["id"] + 1
        if prox < len(FLUXO_DADOS):
            await set_estado(jid, FLUXO_DADOS[prox]["estado"])
            await send(jid, FLUXO_DADOS[prox]["pergunta"])
        else:
            await set_estado(jid, None)
            await send(jid, MSG_FINAL.format(final=jid.split('@')[0][-4:]))

@app.get("/")
async def root(): return {"ok": True}

@app.post("/webhook")
@app.post("/webhook/{path:path}")
async def webhook(request: Request, background_tasks: BackgroundTasks, path: str = ""):
    data = await request.json()
    payload = data.get("data", data)
    m = payload.get("messages", [payload])[0] if isinstance(payload.get("messages"), list) else payload
    key = m.get("key", {})
    if key.get("fromMe"): return {"ok": True}
    jid = key.get("remoteJid", "")
    if not jid or "@g.us" in jid: return {"ok": True}
    msg_id = key.get("id","")
    if msg_id in PROCESSADOS: return {"ok": True}
    PROCESSADOS.add(msg_id)
    msg = m.get("message", {})
    txt = (msg.get("conversation") or msg.get("extendedTextMessage", {}).get("text") or "").strip()
    if not txt: return {"ok": True}
    background_tasks.add_task(processa, jid, txt)
    return {"ok": True}