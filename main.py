import os, re, traceback
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="L.C. Banker V25.3")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://kkzylqdyyrmfiayfuqfb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_f4-wjMnAMr114DOeqV00Eg_RHSP-591")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-gkgk.onrender.com")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN", "lc-banker-token")
INSTANCE_NAME = os.getenv("EVOLUTION_INSTANCE", "lc-banker")
LIMITE_ALTO = 200000.0

# ANTI-LOOP - trava mensagem duplicada da Evolution
PROCESSADOS = set()

def get_h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

FLUXO = [
    {"id": 0, "estado": "AGUARDANDO_LGPD", "campo": "lgpd_autorizado", "pergunta": "Conforme a LGPD, você autoriza liberar seus dados para pesquisa e demais assuntos para se tornar nosso cliente?\n\nDigite:\n1 - Sim, autorizo\n2 - Não autorizo"},
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
    url = f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}&order=created_at.desc&limit=1&select=estado"
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
        async with httpx.AsyncClient() as client:
            if estado is None:
                url = f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}"
                await client.delete(url, headers=get_h(), timeout=5.0)
            else:
                # TENTA ATUALIZAR, SE NAO EXISTIR CRIA
                url_patch = f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}"
                r = await client.patch(url_patch, json={"estado": estado}, headers=get_h(), timeout=5.0)
                if r.status_code == 200 and len(r.json()) == 0: # nao achou pra atualizar
                    url_post = f"{SUPABASE_URL}/rest/v1/controle_sessao"
                    hh = get_h()
                    hh["Prefer"] = "resolution=merge-duplicates"
                    await client.post(url_post, json={"remetente": remetente, "estado": estado}, headers=hh, timeout=5.0)
                elif r.status_code not in [200,204]:
                    url_post = f"{SUPABASE_URL}/rest/v1/controle_sessao"
                    hh = get_h()
                    hh["Prefer"] = "resolution=merge-duplicates"
                    await client.post(url_post, json={"remetente": remetente, "estado": estado}, headers=hh, timeout=5.0)
    except Exception as e:
        print(f"Erro set_estado: {e}")

async def save_lead(remetente, campo, valor):
    try:
        cel = remetente.split("@")[0]
        async with httpx.AsyncClient() as client:
            hh = get_h()
            hh["Prefer"] = "resolution=merge-duplicates"
            await client.post(f"{SUPABASE_URL}/rest/v1/leads_credito", json={"remetente": remetente, "celular": cel}, headers=hh, timeout=5.0)
            await client.patch(f"{SUPABASE_URL}/rest/v1/leads_credito?remetente=eq.{remetente}", json={campo: valor}, headers=get_h(), timeout=5.0)
    except Exception as e:
        print(e)

@app.get("/")
async def root(): return {"status": "online", "service": "LECO V25.3 FIX LOOP"}

@app.post("/webhook")
@app.post("/webhook/{path:path}")
async def wh(request: Request, path: str = ""):
    try:
        data = await request.json()
        payload = data.get("data", data)
        m = payload.get("messages", [payload])[0] if isinstance(payload.get("messages"), list) else payload
        key = m.get("key", {})
        msg_id = key.get("id", "")

        # TRAVA LOOP DE WEBHOOK DUPLICADO
        if msg_id in PROCESSADOS:
            return {"status": "ok - duplicado"}
        if msg_id:
            PROCESSADOS.add(msg_id)
            if len(PROCESSADOS) > 200: PROCESSADOS.clear()

        if key.get("fromMe"): return {"status": "ok"}
        jid = key.get("remoteJid", "")
        if not jid or "@g.us" in jid: return {"status": "ok"}

        message = m.get("message", {})
        txt = message.get("conversation") or message.get("extendedTextMessage", {}).get("text") or ""
        txt = txt.strip()
        if not txt: return {"status": "ok"}

        estado = await get_estado(jid)
        print(f"JID: {jid} ESTADO: {estado} TXT: {txt}")

        if estado is None:
            if txt.lower() in ["oi","ola","olá","menu","inicio","início","1","iniciar"]:
                await send(jid, "Olá, tudo bem? 😊\n\nMeu nome é *Leco*, eu falo aqui da *L.C. Banker & Advisory*.\n\nEu sou a robô criada pelo nosso querido Leandro, que é o banker responsável pela plataforma, e estou aqui para te ajudar.")
                await set_estado(jid, "AGUARDANDO_LGPD")
                await send(jid, FLUXO[0]["pergunta"])
            return {"status": "ok"}

        # SE JA ESTA NO FLUXO, O 1 VALE COMO SIM
        if estado == "AGUARDANDO_LGPD":
            if txt in ["2","nao","não","n","Nao"]:
                await save_lead(jid, "lgpd_autorizado", "NAO")
                await send(jid, "Poxa, muito obrigado pelo seu contato, fica até a próxima! 🙏")
                await set_estado(jid, None)
                return {"status": "ok"}
            if txt in ["1","sim","s","Sim","SIM","autorizo"]:
                await save_lead(jid, "lgpd_autorizado", "SIM")
                await set_estado(jid, FLUXO[1]["estado"])
                await send(jid, FLUXO[1]["pergunta"])
                return {"status": "ok"}
            await send(jid, "Responda 1 para SIM ou 2 para NÃO")
            return {"status": "ok"}

        passo = next((p for p in FLUXO if p["estado"] == estado), None)
        if passo:
            await save_lead(jid, passo["campo"], txt)
            prox_id = passo["id"] + 1
            if passo["estado"] == "AGUARDANDO_ESTADO_CIVIL" and txt in ["1","4","5"]:
                prox_id = 8
            if passo["estado"] == "AGUARDANDO_VALOR":
                try:
                    v = float(re.sub(r'[^\d]','',txt))
                    if v <= LIMITE_ALTO: prox_id = 12
                except: pass

            if prox_id < len(FLUXO):
                await set_estado(jid, FLUXO[prox_id]["estado"])
                await send(jid, FLUXO[prox_id]["pergunta"])
            else:
                await set_estado(jid, None)
                await send(jid, "Cadastro Concluído! ✅ Equipe L.C. Banker vai analisar.")
    except Exception as e:
        print(f"ERRO: {e}")
        traceback.print_exc()
    return {"status": "ok"}
