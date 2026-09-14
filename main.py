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

PROCESSADOS = set()

def get_h_upsert():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation"
    }

def get_h():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

FLUXO = [
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": "Conforme a LGPD, autoriza seus dados?\n\n1 - Sim\n2 - Não"},
    {"id": 1, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "Nome completo:"},
    {"id": 2, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "E-mail:"},
    {"id": 3, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "CPF (só números):"},
    {"id": 4, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": "Valor do crédito? Ex: 250000"},
    {"id": 5, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": "CEP do imóvel:"},
]

async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as c:
            await c.post(url, json={"number": numero, "text": texto}, headers=h, timeout=10)
    except Exception as e:
        print(f"ERRO SEND: {e}")

async def get_estado(remetente):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&select=estado", headers=get_h(), timeout=5)
            if r.status_code == 200 and r.json():
                return r.json()[0]["estado"]
    except: pass
    return None

async def set_estado(remetente, estado):
    try:
        async with httpx.AsyncClient() as client:
            # UPSERT ATÔMICO - não apaga mais
            url = f"{SUPABASE_URL}/rest/v1/controle_sessao?on_conflict=remetente"
            if estado is None:
                await client.delete(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}", headers=get_h(), timeout=5)
            else:
                await client.post(url, json={"remetente": remetente, "estado": estado}, headers=get_h_upsert(), timeout=5)
    except Exception as e:
        print(f"ERRO SET_ESTADO: {e}")

async def save_lead(remetente, campo, valor):
    try:
        cel = remetente.split("@")[0]
        async with httpx.AsyncClient() as client:
            url = f"{SUPABASE_URL}/rest/v1/leads_credito?on_conflict=remetente"
            await client.post(url, json={"remetente": remetente, "celular": cel, campo: valor}, headers=get_h_upsert(), timeout=5)
    except: pass

async def processa(jid, txt):
    estado = await get_estado(jid)
    print(f"PROCESSANDO JID:{jid} ESTADO:{estado} TXT:{txt}")

    if estado is None:
        if txt.lower() in ["oi","ola","olá","1","menu","inicio","olá"]:
            await set_estado(jid, "AGUARDANDO_LGPD")
            await send(jid, "Olá! 😊 Aqui é a *Leco* da *L.C. Banker*")
            await send(jid, FLUXO[0]["pergunta"])
        return

    if estado == "AGUARDANDO_LGPD":
        if txt == "2":
            await save_lead(jid, "lgpd_autorizado", "NAO")
            await set_estado(jid, None)
            await send(jid, "Entendido! Até mais 🙏")
            return
        if txt == "1":
            await save_lead(jid, "lgpd_autorizado", "SIM")
            await set_estado(jid, FLUXO[1]["estado"])
            await send(jid, FLUXO[1]["pergunta"])
            return
        await send(jid, "Digite 1 para SIM ou 2 para NÃO")
        return

    passo = next((p for p in FLUXO if p["estado"] == estado), None)
    if passo:
        await save_lead(jid, passo["campo"], txt)
        prox = passo["id"] + 1
        if prox < len(FLUXO):
            await set_estado(jid, FLUXO[prox]["estado"])
            await send(jid, FLUXO[prox]["pergunta"])
        else:
            await set_estado(jid, None)
            await send(jid, "Cadastro concluído ✅")

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
    if len(PROCESSADOS) > 500: PROCESSADOS.clear()

    msg = m.get("message", {})
    txt = (msg.get("conversation") or msg.get("extendedTextMessage", {}).get("text") or "").strip()
    if not txt: return {"ok": True}

    # RESPONDE NA HORA PRA EVOLUTION NÃO REENVIAR
    background_tasks.add_task(processa, jid, txt)
    return {"status": "ok"}