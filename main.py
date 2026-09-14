import os, re, traceback
from datetime import datetime
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="L.C. Banker V25.1")
# CORRIGIDO: não pode usar * com credentials=True
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# AGORA 100% VIA ENV - sem segredo no código
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # sua publishable key
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN")
INSTANCE_NAME = os.getenv("EVOLUTION_INSTANCE", "lc-banker")
ID_GRUPO_CORRETORES = os.getenv("CORRETORES_GROUP_ID")
LIMITE_ALTO = 200000.0

def get_h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

FLUXO = [
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": "LGPD: Autoriza uso dos dados? Digite 1-Sim 2-Nao"},
    {"id": 1, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "Digite seu Nome Completo:"},
    {"id": 2, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "Digite seu E-mail:"},
    {"id": 3, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "Digite seu CPF (apenas numeros):"},
    {"id": 4, "estado": "AGUARDANDO_NASCIMENTO", "campo": "data_nascimento", "pergunta": "Digite sua Data de Nascimento DD/MM/AAAA:"},
    {"id": 5, "estado": "AGUARDANDO_ESTADO_CIVIL", "campo": "estado_civil", "pergunta": "Estado Civil? 1-Solteiro 2-Casado 3-Uniao 4-Divorciado 5-Viuvo"},
    {"id": 6, "estado": "AGUARDANDO_NOME_CONJUGE", "campo": "nome_completo_companheiro", "pergunta": "Nome Completo do Conjuge:"},
    {"id": 7, "estado": "AGUARDANDO_CPF_CONJUGE", "campo": "cpf_companheiro", "pergunta": "CPF do Conjuge:"},
    {"id": 8, "estado": "AGUARDANDO_RENDA", "campo": "renda_mensal", "pergunta": "Renda Mensal bruta? Ex: 3500"},
    {"id": 9, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": "Valor do Credito? Ex: 250000"},
    {"id": 10, "estado": "AGUARDANDO_NOME_2_PROPONENTE", "campo": "nome_2_proponente", "pergunta": "Nome Completo do 2o Proponente:"},
    {"id": 11, "estado": "AGUARDANDO_CPF_2_PROPONENTE", "campo": "cpf_2_proponente", "pergunta": "CPF do 2o Proponente:"},
    {"id": 12, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": "CEP do imovel garantia:"},
    {"id": 13, "estado": "AGUARDANDO_DOCUMENTO", "campo": "doc_comprovante_renda", "pergunta": "Envie documento comprovacao renda (foto/PDF):"}
]

async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    p = {"number": numero, "text": texto}
    try:
        async with httpx.AsyncClient() as c:
            await c.post(url, json=p, headers=h, timeout=10.0)
    except Exception as e:
        print(f"Erro send: {e}")

async def get_estado(remetente):
    url = f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&select=estado"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=get_h(), timeout=5.0)
            if resp.status_code == 200:
                d = resp.json()
                return d[0]["estado"] if d else None
    except: pass
    return None

async def set_estado(remetente, estado):
    try:
        if estado is None:
            url = f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}"
            async with httpx.AsyncClient() as client:
                await client.delete(url, headers=get_h(), timeout=5.0)
        else:
            url = f"{SUPABASE_URL}/rest/v1/controle_sessao"
            payload = {"remetente": remetente, "estado": estado}
            hh = get_h()
            hh["Prefer"] = "resolution=merge-duplicates"
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, headers=hh, timeout=5.0)
    except Exception as e:
        print(e)

async def save_lead(remetente, campo, valor):
    try:
        cel = remetente.split("@")[0]
        url = f"{SUPABASE_URL}/rest/v1/leads_credito"
        hh = get_h()
        hh["Prefer"] = "resolution=merge-duplicates"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"remetente": remetente, "celular": cel}, headers=hh, timeout=5.0)
            url2 = f"{SUPABASE_URL}/rest/v1/leads_credito?remetente=eq.{remetente}"
            await client.patch(url2, json={campo: valor}, headers=get_h(), timeout=5.0)
    except Exception as e:
        print(e)

@app.get("/")
async def root():
    return {"status": "online", "service": "L.C. Banker V25.1 FIX", "headers": "alocado"}

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

        message = m.get("message", {})
        txt = message.get("conversation") or message.get("extendedTextMessage", {}).get("text") or message.get("imageMessage", {}).get("caption") or message.get("documentMessage", {}).get("caption") or ""
        txt = txt.strip()
        tipo = "imageMessage" if "imageMessage" in message else "documentMessage" if "documentMessage" in message else "conversation"

        if not txt and tipo not in ["imageMessage", "documentMessage"]:
            return {"status": "ok"}

        estado = await get_estado(jid)
        if estado is None:
            if txt.lower() in ["oi", "ola", "olá", "menu", "inicio", "início"]:
                await send(jid, "Olá! Seja bem-vindo a L.C. Banker & Advisory. Digite 1 para iniciar simulação Home Equity.")
            elif txt == "1":
                await set_estado(jid, FLUXO[0]["estado"])
                await send(jid, FLUXO[0]["pergunta"])
            return {"status": "ok"}

        passo = next((p for p in FLUXO if p["estado"] == estado), None)
        if passo:
            await save_lead(jid, passo["campo"], txt)

            # LÓGICA INTELIGENTE DE FLUXO
            prox_id = passo["id"] + 1
            # Se for solteiro/divorciado/viuvo, pula cônjuge
            if passo["estado"] == "AGUARDANDO_ESTADO_CIVIL" and txt in ["1", "4", "5"]:
                prox_id = 8
            # Se valor baixo, pula 2o proponente
            if passo["estado"] == "AGUARDANDO_VALOR":
                try:
                    v = float(re.sub(r'[^\d]', '', txt))
                    if v <= LIMITE_ALTO:
                        prox_id = 12
                except: pass

            if prox_id < len(FLUXO):
                await set_estado(jid, FLUXO[prox_id]["estado"])
                await send(jid, FLUXO[prox_id]["pergunta"])
            else:
                await set_estado(jid, None)
                await send(jid, "Cadastro Concluído! Equipe L.C. Banker vai analisar e entrar em contato.")
    except Exception as e: