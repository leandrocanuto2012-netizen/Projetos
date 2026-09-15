import os
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ================= CONFIG =================
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://kkzylqdyyrmfiayfuqfb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_f4-wjMnAMr114DOeqV00Eg_RHSP-591")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-gkgk.onrender.com")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN", "lc-banker-token")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "lc-banker")
SEU_NUMERO_DONO = os.getenv("SEU_NUMERO_DONO", "5541996944260@s.whatsapp.net")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "gsk_SUA_CHAVE_AQUI")
AI_ATIVA = True if GROQ_API_KEY and "gsk_" in GROQ_API_KEY else False

PROCESSADOS = set()
ESTADOS_MEM = {}

def get_h_upsert():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}
def get_h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

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
Selecione:

*1* • Crédito com Garantia de Imóvel
*2* • Refinanciamento / Aumento de Valor
*3* • Portabilidade de Contrato
*4* • Acompanhar Proposta
*5* • Falar com Responsável

_Digite apenas o número._"""

FLUXO_DADOS = [
    {"id": 0, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "*ETAPA 1/5 | IDENTIFICAÇÃO*\n━━━━━━━━━━━━━━━━━━\n👤 *Nome Completo*"},
    {"id": 1, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "*ETAPA 2/5 | CONTATO*\n━━━━━━━━━━━━━━━━━━\n📧 *E-mail Principal*"},
    {"id": 2, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "*ETAPA 3/5 | VALIDAÇÃO*\n━━━━━━━━━━━━━━━━━━\n🔐 *CPF* (só números)"},
    {"id": 3, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": "*ETAPA 4/5 | VALOR*\n━━━━━━━━━━━━━━━━━━\n💰 *Valor Pretendido* Ex: 350000"},
    {"id": 4, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": "*ETAPA 5/5 | GARANTIA*\n━━━━━━━━━━━━━━━━━━\n🏠 *CEP do Imóvel em Garantia*"},
]

async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    # Evolution v2.3.7 aceita @lid e @s.whatsapp.net direto
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(url, json={"number": numero, "text": texto}, headers=h, timeout=20)
            print(f"SEND {numero}: {r.status_code}")
        except Exception as e:
            print(f"ERRO SEND: {e}")

async def resposta_meta_ai(pergunta: str):
    if not AI_ATIVA:
        print("IA DESATIVADA - sem GROQ key")
        return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": "Você é o Leco, consultor premium da L.C. BANKERS ADVISORY. Humano, elegante, banco private. Taxas a partir de 1,09% a.m., até 240 meses, até 60% do imóvel. Nunca prometa aprovação. Seja curto, direto, premium. No final sempre puxe para o MENU 1 a 5."},
                        {"role": "user", "content": pergunta}
                    ],
                    "max_tokens": 450,
                    "temperature": 0.6
                },
                timeout=20
            )
            print(f"GROQ {r.status_code}: {r.text[:300]}")
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"ERRO IA: {e}")
    return None

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
    else:
        ESTADOS_MEM[remetente] = estado
    try:
        async with httpx.AsyncClient() as client:
            url = f"{SUPABASE_URL}/rest/v1/controle_sessao?on_conflict=remetente"
            if estado is None:
                await client.delete(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}", headers=get_h(), timeout=5)
            else:
                await client.post(url, json={"remetente": remetente, "estado": estado, "contador": 0}, headers=get_h_upsert(), timeout=5)
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
    print(f">>> JID: {jid} | ESTADO: {estado} | MSG: {txt} | IA: {AI_ATIVA}")

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
            await send(jid, "Entendido. Encerramos por aqui.")
            return
        await send(jid, "Digite *1* para SIM ou *2* para NÃO")
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
            await send(jid, "*ACOMPANHAMENTO*\n🔍 Informe seu *CPF*:")
            return
        if txt == "5":
            await save_lead(jid, "tipo_solicitacao", "FALAR_COM_DONO")
            await set_estado(jid, None)
            await send(jid, "Já notifiquei o responsável. Te atende aqui em até *10 min*.")
            if "999999999" not in SEU_NUMERO_DONO:
                await send(SEU_NUMERO_DONO, f"🚨 *LEAD QUER FALAR COM VOCÊ*\nDe: {jid}")
            return

        # META AI - SEM LOOP, SEM CONTADOR
        ia = await resposta_meta_ai(txt)
        if ia:
            await send(jid, ia)
        await send(jid, MENU_PRINCIPAL)
        await set_estado(jid, "AGUARDANDO_MENU")
        return

    if estado == "AGUARDANDO_CPF_ACOMPANHAR":
        await save_lead(jid, "cpf", txt)
        await set_estado(jid, None)
        await send(jid, f"CPF *{txt}* recebido. Já consulto o status e te retorno.")
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
            await send(jid, f"*PROTOCOLO GERADO* ✅\nProtocolo: *LCB-{jid[-4:]}*\nRetornaremos em até *02h úteis*.")
        return

@app.get("/")
async def root():
    return {"ok": True, "leco": "V30 LID FIX", "meta_ai": AI_ATIVA, "groq_ok": AI_ATIVA}

@app.get("/test-ia")
async def test_ia(q: str = "qual a taxa?"):
    resp = await resposta_meta_ai(q)
    return {"pergunta": q, "resposta": resp, "ativa": AI_ATIVA}

@app.post("/webhook")
@app.post("/webhook/{path:path}")
async def webhook(request: Request, background_tasks: BackgroundTasks, path: str = ""):
    data = await request.json()
    print(f"PAYLOAD: {str(data)[:800]}")

    d = data.get("data", data)
    # Evolution v2.3.7 - pega a mensagem do jeito certo
    msg_data = d
    if isinstance(d.get("messages"), list):
        msg_data = d["messages"][0]
    elif isinstance(d.get("data"), dict):
        msg_data = d["data"]
        if isinstance(msg_data.get("messages"), list):
            msg_data = msg_data["messages"][0]

    key = msg_data.get("key", {})
    if key.get("fromMe"): return {"ok": True}

    jid = key.get("remoteJid") or msg_data.get("remoteJid") or ""
    if not jid or "@g.us" in jid: return {"ok": True}

    msg_id = key.get("id","")
    if msg_id in PROCESSADOS: return {"ok": True}
    PROCESSADOS.add(msg_id)

    msg = msg_data.get("message", {})
    txt = (
        msg.get("conversation") or
        msg.get("extendedTextMessage", {}).get("text") or
        msg.get("imageMessage", {}).get("caption") or
        msg.get("videoMessage", {}).get("caption") or
        ""
    ).strip()

    if not txt: return {"ok": True}

    background_tasks.add_task(processa, jid, txt)
    return {"ok": True}