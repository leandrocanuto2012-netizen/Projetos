import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# ADICIONA ISSO NO TOPO
CONTADOR = {} # jid -> número de vezes que passou

def inc_contador(jid):
    CONTADOR[jid] = CONTADOR.get(jid, 0) + 1
    return CONTADOR[jid]

async def get_estado(remetente):
    if remetente in ESTADOS_MEM:
        return ESTADOS_MEM[remetente]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&select=estado,contador", headers=get_h(), timeout=5)
            if r.status_code == 200 and r.json():
                dados = r.json()[0]
                ESTADOS_MEM[remetente] = dados["estado"]
                CONTADOR[remetente] = dados.get("contador", 0)
                return dados["estado"]
    except: pass
    return None

async def set_estado(remetente, estado):
    c = inc_contador(remetente) if estado else 0
    if estado is None:
        ESTADOS_MEM.pop(remetente, None)
        CONTADOR.pop(remetente, None)
    else:
        ESTADOS_MEM[remetente] = estado

    # TRAVA ANTI-LOOP PELO CONTADOR
    if c > 6:
        print(f"LOOP DETECTADO JID:{remetente} CONTADOR:{c} - RESETANDO")
        ESTADOS_MEM.pop(remetente, None)
        CONTADOR.pop(remetente, None)
        estado = None
        c = 0

    try:
        async with httpx.AsyncClient() as client:
            url = f"{SUPABASE_URL}/rest/v1/controle_sessao?on_conflict=remetente"
            if estado is None:
                await client.delete(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}", headers=get_h(), timeout=5)
            else:
                # AGORA GRAVA ESTADO + CONTADOR
                r = await client.post(url, json={"remetente": remetente, "estado": estado, "contador": c}, headers=get_h_upsert(), timeout=5)
                print(f"SUPABASE SET CONTADOR:{c} STATUS:{r.status_code}")
    except Exception as e:
        print(f"ERRO SET: {e}")

async def processa(jid, txt):
    estado = await get_estado(jid)
    c = CONTADOR.get(jid, 0)
    print(f"PROCESSANDO JID:{jid} ESTADO:{estado} TXT:{txt} CONTADOR:{c}")
    # resto igual...
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = "https://kkzylqdyyrmfiayfuqfb.supabase.co"
SUPABASE_KEY = "sb_publishable_f4-wjMnAMr114DOeqV00Eg_RHSP-591"
EVOLUTION_API_URL = "https://evolution-api-gkgk.onrender.com"
EVOLUTION_TOKEN = "lc-banker-token"
INSTANCE_NAME = "lc-banker"

PROCESSADOS = set()
ESTADOS_MEM = {} # CACHE NA MEMÓRIA ANTI-LOOP

def get_h_upsert():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}
def get_h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

FLUXO = [
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": "Conforme LGPD autoriza?\n\n1 - Sim\n2 - Não"},
    {"id": 1, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "Nome completo:"},
    {"id": 2, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "E-mail:"},
]

async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as c:
        await c.post(url, json={"number": numero, "text": texto}, headers=h, timeout=10)

async def get_estado(remetente):
    # 1º tenta memória
    if remetente in ESTADOS_MEM:
        return ESTADOS_MEM[remetente]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&select=estado", headers=get_h(), timeout=5)
            print(f"SUPABASE GET {r.status_code} {r.text}")
            if r.status_code == 200 and r.json():
                estado = r.json()[0]["estado"]
                ESTADOS_MEM[remetente] = estado
                return estado
    except Exception as e:
        print(f"ERRO GET_ESTADO: {e}")
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
                r = await client.post(url, json={"remetente": remetente, "estado": estado}, headers=get_h_upsert(), timeout=5)
                print(f"SUPABASE SET {r.status_code} {r.text}")
    except Exception as e:
        print(f"ERRO SET_ESTADO: {e}")

async def processa(jid, txt):
    estado = await get_estado(jid)
    print(f"PROCESSANDO JID:{jid} ESTADO:{estado} TXT:{txt}")

    if estado is None:
        await set_estado(jid, "AGUARDANDO_LGPD")
        await send(jid, "Olá! Aqui é a Leco da L.C. Banker")
        await send(jid, FLUXO[0]["pergunta"])
        return

    if estado == "AGUARDANDO_LGPD":
        if txt == "1":
            await set_estado(jid, FLUXO[1]["estado"])
            await send(jid, FLUXO[1]["pergunta"])
            return
        await send(jid, "Digite 1 para SIM")
        return

    passo = next((p for p in FLUXO if p["estado"] == estado), None)
    if passo:
        prox = passo["id"] + 1
        if prox < len(FLUXO):
            await set_estado(jid, FLUXO[prox]["estado"])
            await send(jid, FLUXO[prox]["pergunta"])
        else:
            await set_estado(jid, None)
            await send(jid, "Concluído ✅")

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