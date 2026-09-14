import os, re, traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://kkzylqdyyrmfiayfuqfb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_f4-wjMnAMr114DOeqV00Eg_RHSP-591")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-gkgk.onrender.com")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN", "lc-banker-token")
INSTANCE_NAME = os.getenv("EVOLUTION_INSTANCE", "lc-banker")
ID_GRUPO = os.getenv("CORRETORES_GROUP_ID", "9EE45C1B5E22-4654-A30B-E9C1D4D5E583.us")
async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    p = {"number": numero, "text": texto}
    async with httpx.AsyncClient() as c:
        await c.post(url, json=p, headers=h)
@app.get("/")
async def root():
    return {"status": "ok"}
@app.get("/health")
async def health():
    return {"status": "ok", "instance": INSTANCE_NAME}
@app.post("/webhook")
@app.post("/webhook/{path:path}")
async def wh(request: Request, path: str = ""):
    try:
        data = await request.json()
        payload = data.get("data", data)
        m = payload.get("messages", [payload])[0] if isinstance(payload.get("messages"), list) else payload
        key = m.get("key", {})
        if key.get("fromMe"):
            return {"status": "ok"}
        jid = key.get("remoteJid", "")
        if not jid or "@g.us" in jid:
            return {"status": "ok"}
        msg = m.get("message", {})
        txt = msg.get("conversation") or msg.get("extendedTextMessage", {}).get("text") or ""
        if txt:
            phone = jid.split("@")[0]
            await send(jid, f"Ola! L.C. Banker V25 OK - Recebido: {txt}")
    except Exception as e:
        print(e)
    return {"status": "ok"}
