import os, re, traceback, time
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
SUPABASE_URL = "https://kkzylqdyyrmfiayfuqfb.supabase.co"
SUPABASE_KEY = "sb_publishable_f4-wjMnAMr114DOeqV00Eg_RHSP-591"
EVOLUTION_API_URL = "https://evolution-api-gkgk.onrender.com"
EVOLUTION_TOKEN = "lc-banker-token"
INSTANCE_NAME = "lc-banker"
ULTIMO_ENVIO = {}
PROCESSADOS = set()
def get_h(): return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}
FLUXO = [
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": "Conforme a LGPD, você autoriza liberar seus dados?\n\n1 - Sim, autorizo\n2 - Não autorizo"},
    {"id": 1, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "Digite seu Nome Completo:"},
]
async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as c:
            await c.post(url, json={"number": numero, "text": texto}, headers=h, timeout=10)
    except: pass
async def get_estado(remetente):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&select=estado", headers=get_h(), timeout=5)
            if r.status_code == 200 and r.json(): return r.json()[0]["estado"]
    except: pass
    return None
async def set_estado(remetente, estado):
    try:
        async with httpx.AsyncClient() as client:
            await client.delete(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}", headers=get_h(), timeout=5)
            if estado: await client.post(f"{SUPABASE_URL}/rest/v1/controle_sessao", json={"remetente": remetente, "estado": estado}, headers=get_h(), timeout=5)
    except: pass
async def save_lead(remetente, campo, valor):
    try:
        cel = remetente.split("@")[0]
        async with httpx.AsyncClient() as client:
            await client.post(f"{SUPABASE_URL}/rest/v1/leads_credito", json={"remetente": remetente, "celular": cel}, headers={**get_h(), "Prefer": "resolution=merge-duplicates"}, timeout=5)
            await client.patch(f"{SUPABASE_URL}/rest/v1/leads_credito?remetente=eq.{remetente}", json={campo: valor}, headers=get_h(), timeout=5)
    except: pass
@app.get("/")
async def root(): return {"status": "online"}
@app.post("/webhook")
@app.post("/webhook/{path:path}")
async def wh(request: Request, path: str = ""):
    data = await request.json()
    payload = data.get("data", data)
    m = payload.get("messages", [payload])[0] if isinstance(payload.get("messages"), list) else payload
    key = m.get("key", {})
    if key.get("fromMe"): return {"status": "ok"}
    jid = key.get("remoteJid", "")
    if not jid or "@g.us" in jid: return {"status": "ok"}
    message = m.get("message", {})
    txt = (message.get("conversation") or message.get("extendedTextMessage", {}).get("text") or "").strip()
    if not txt: return {"status": "ok"}
    estado = await get_estado(jid)
    print(f"RECEBIDO: {txt} ESTADO: {estado}")
    if estado is None:
        if txt.lower() in ["oi","ola","olá","1","menu","inicio"]:
            await set_estado(jid, "AGUARDANDO_LGPD")
            await send(jid, "Olá, tudo bem? 😊\n\nMeu nome é *Leco*, da *L.C. Banker & Advisory*.")
            await send(jid, FLUXO[0]["pergunta"])
        return {"status": "ok"}
    if estado == "AGUARDANDO_LGPD" and txt == "1":
        await save_lead(jid, "lgpd_autorizado", "SIM")
        await set_estado(jid, FLUXO[1]["estado"])
        await send(jid, FLUXO[1]["pergunta"])
        return {"status": "ok"}
    return {"status": "ok"}