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

def get_h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

FLUXO = [
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": "Conforme a LGPD, você autoriza liberar seus dados para pesquisa?\n\n1 - Sim, autorizo\n2 - Não autorizo"},
    {"id": 1, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "Digite seu Nome Completo:"},
    {"id": 2, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "Digite seu E-mail:"},
    {"id": 3, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "Digite seu CPF (apenas numeros):"},
    {"id": 4, "estado": "AGUARDANDO_NASCIMENTO", "campo": "data_nascimento", "pergunta": "Data Nascimento DD/MM/AAAA:"},
    {"id": 5, "estado": "AGUARDANDO_ESTADO_CIVIL", "campo": "estado_civil", "pergunta": "Estado Civil? 1-Solteiro 2-Casado 3-Uniao 4-Divorciado 5-Viuvo"},
    {"id": 6, "estado": "AGUARDANDO_NOME_CONJUGE", "campo": "nome_completo_companheiro", "pergunta": "Nome Completo do Conjuge:"},
    {"id": 7, "estado": "AGUARDANDO_CPF_CONJUGE", "campo": "cpf_companheiro", "pergunta": "CPF do Conjuge:"},
    {"id": 8, "estado": "AGUARDANDO_RENDA", "campo": "renda_mensal", "pergunta": "Renda Mensal bruta? Ex: 3500"},
    {"id": 9, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": "Valor do Credito? Ex: 250000"},
    {"id": 10, "estado": "AGUARDANDO_NOME_2_PROPONENTE", "campo": "nome_2_proponente", "pergunta": "Nome 2o Proponente:"},
    {"id": 11, "estado": "AGUARDANDO_CPF_2_PROPONENTE", "campo": "cpf_2_proponente", "pergunta": "CPF 2o Proponente:"},
    {"id": 12, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": "CEP do imovel garantia:"},
    {"id": 13, "estado": "AGUARDANDO_DOCUMENTO", "campo": "doc_comprovante_renda", "pergunta": "Envie documento comprovacao renda:"}
]

async def send(numero, texto):
    # TRAVA ANTI-SPAM DE 2 SEGUNDOS
    agora = time.time()
    if numero in ULTIMO_ENVIO and agora - ULTIMO_ENVIO[numero] < 2:
        return
    ULTIMO_ENVIO[numero] = agora
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
            if r.status_code == 200 and r.json():
                return r.json()[0]["estado"]
    except: pass
    return None

async def set_estado(remetente, estado):
    # METODO DELETE + INSERT - 100% CERTEZA QUE GRAVA
    try:
        async with httpx.AsyncClient() as client:
            await client.delete(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}", headers=get_h(), timeout=5)
            if estado is not None:
                await client.post(f"{SUPABASE_URL}/rest/v1/controle_sessao", json={"remetente": remetente, "estado": estado}, headers=get_h(), timeout=5)
    except Exception as e:
        print(f"ERRO SET_ESTADO: {e}")

async def save_lead(remetente, campo, valor):
    try:
        cel = remetente.split("@")[0]
        async with httpx.AsyncClient() as client:
            await client.post(f"{SUPABASE_URL}/rest/v1/leads_credito", json={"remetente": remetente, "celular": cel}, headers={**get_h(), "Prefer": "resolution=merge-duplicates"}, timeout=5)
            await client.patch(f"{SUPABASE_URL}/rest/v1/leads_credito?remetente=eq.{remetente}", json={campo: valor}, headers=get_h(), timeout=5)
    except: pass

@app.post("/webhook")
async def wh(request: Request):
    try:
        data = await request.json()
        # FILTRA SÓ MENSAGEM NOVA
        if data.get("event") and data.get("event")!= "messages.upsert":
            return {"status": "ignorado"}
        payload = data.get("data", data)
        m = payload.get("messages", [payload])[0] if isinstance(payload.get("messages"), list) else payload
        key = m.get("key", {})
        if key.get("fromMe"): return {"status": "ok"}
        jid = key.get("remoteJid", "")
        if not jid or "@g.us" in jid: return {"status": "ok"}

        msg_id = key.get("id","")
        if msg_id in PROCESSADOS: return {"status": "duplicado"}
        PROCESSADOS.add(msg_id)

        message = m.get("message", {})
        txt = (message.get("conversation") or message.get("extendedTextMessage", {}).get("text") or "").strip()
        if not txt: return {"status": "ok"}

        estado = await get_estado(jid)
        print(f"ESTADO ATUAL: {estado} TXT: {txt}")

        if estado is None:
            if txt.lower() in ["oi","ola","olá","1","menu","inicio"]:
                await set_estado(jid, "AGUARDANDO_LGPD")
                await send(jid, "Olá, tudo bem? 😊\n\nMeu nome é *Leco*, da *L.C. Banker & Advisory*.\n\nSou a robô criada pelo Leandro, banker responsável pela plataforma.")
                await send(jid, FLUXO[0]["pergunta"])
            return {"status": "ok"}

        if estado == "AGUARDANDO_LGPD":
            if txt == "2":
                await save_lead(jid, "lgpd_autorizado", "NAO")
                await send(jid, "Obrigado! Até a próxima 🙏")
                await set_estado(jid, None)
                return {"status": "ok"}
            if txt == "1":
                await save_lead(jid, "lgpd_autorizado", "SIM")
                await set_estado(jid, FLUXO[1]["estado"])
                await send(jid, FLUXO[1]["pergunta"])
                return {"status": "ok"}
            await send(jid, "Digite 1 para SIM ou 2 para NÃO")
            return {"status": "ok"}

        passo = next((p for p in FLUXO if p["estado"] == estado), None)
        if passo:
            await save_lead(jid, passo["campo"], txt)
            prox = passo["id"] + 1
            if prox < len(FLUXO):
                await set_estado(jid, FLUXO[prox]["estado"])
                await send(jid, FLUXO[prox]["pergunta"])
            else:
                await set_estado(jid, None)
                await send(jid, "Cadastro Concluído! ✅ Equipe vai analisar.")
    except Exception as e:
        print(e)
        traceback.print_exc()
    return {"status": "ok"}