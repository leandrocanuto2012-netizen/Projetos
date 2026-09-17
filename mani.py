import os, httpx, time
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="L.C. Bankers - V35")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ===== CONFIG =====
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-gkgk.onrender.com")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN") or os.getenv("EVOLUTION_API_KEY", "lc-banker-token")
INSTANCE_NAME = os.getenv("EVOLUTION_INSTANCE", os.getenv("INSTANCE_NAME", "lc-banker"))
SEU_NUMERO_DONO = os.getenv("SEU_NUMERO_DONO")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

AI_ATIVA = bool(GROQ_API_KEY and "gsk_" in GROQ_API_KEY)

PROCESSADOS = set()
ESTADOS_MEM = {}
ULTIMA_MSG = {}

def get_h_upsert():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}
def get_h():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

# ===== MENSAGENS =====
SAUDACAO = """*L.C. BANKERS ADVISORY*
━━━━━━━━━━━━━━━━━━
Olá.

Aqui é o *Leco*, consultor especialista em crédito com garantia de imóvel.
Taxas a partir de *1,09% a.m.* | Até *240 meses* | Até *60%* do valor do imóvel.

Atendimento consultivo, estilo banco private.

Vamos iniciar sua análise?"""

LGPD_TEXTO = """*TERMO DE CONSENTIMENTO | LGPD - Lei 13.709/18*
━━━━━━━━━━━━━━━━━━
Para seguir com a simulação, preciso da sua autorização para tratar seus dados *exclusivamente* para análise de crédito.

Seus dados não são compartilhados.

*1* - Sim, autorizo o tratamento
*2* - Não autorizo"""

MENU_PRINCIPAL = """*MENU PRINCIPAL - L.C. BANKERS*
━━━━━━━━━━━━━━━━━━
Selecione a opção desejada:

*1* • Crédito com Garantia de Imóvel
*2* • Refinanciamento / Aumento de Valor
*3* • Portabilidade de Contrato
*4* • Acompanhar Proposta em Andamento
*5* • Falar Diretamente com o Responsável

_Digite apenas o número da opção._"""

FLUXO_DADOS = [
    {"id": 0, "estado": "AGUARDANDO_NOME", "campo": "nome_completo", "pergunta": "*ETAPA 1/5 | IDENTIFICAÇÃO*\n━━━━━━━━━━━━━━━━━━\n👤 *Nome Completo*"},
    {"id": 1, "estado": "AGUARDANDO_EMAIL", "campo": "email", "pergunta": "*ETAPA 2/5 | CONTATO*\n━━━━━━━━━━━━━━━━━━\n📧 *Seu melhor E-mail*"},
    {"id": 2, "estado": "AGUARDANDO_CPF", "campo": "cpf", "pergunta": "*ETAPA 3/5 | VALIDAÇÃO*\n━━━━━━━━━━━━━━━━━━\n🔐 *CPF* (apenas números)"},
    {"id": 3, "estado": "AGUARDANDO_VALOR", "campo": "valor_solicitado", "pergunta": "*ETAPA 4/5 | VALOR*\n━━━━━━━━━━━━━━━━━━\n💰 *Valor Pretendido*\nEx: 350000"},
    {"id": 4, "estado": "AGUARDANDO_CEP", "campo": "cep_garantia", "pergunta": "*ETAPA 5/5 | GARANTIA*\n━━━━━━━━━━━━━━━━━━\n🏠 *CEP do Imóvel em Garantia*"},
]

async def send(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    h = {"apikey": EVOLUTION_TOKEN, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(url, json={"number": numero, "text": texto}, headers=h, timeout=20)
            print(f"SEND {numero}: {r.status_code}")
        except Exception as e:
            print(f"ERRO SEND: {e}")

async def resposta_meta_ai(pergunta: str):
    if not AI_ATIVA: return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": "Você é o Leco, consultor premium da L.C. BANKERS ADVISORY. Elegante, humano, banco private. Taxas a partir de 1,09% a.m., até 240 meses, até 60% do imóvel. Nunca prometa aprovação, seja consultivo. Resposta curta, premium. No final sempre pergunte qual opção do MENU 1 a 5 ele quer."},
                        {"role": "user", "content": pergunta}
                    ],
                    "max_tokens": 450, "temperature": 0.6
                }, timeout=20)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"ERRO GROQ: {e}")
    return None

async def get_estado(remetente):
    return ESTADOS_MEM.get(remetente)

async def set_estado(remetente, estado):
    if estado is None: ESTADOS_MEM.pop(remetente, None)
    else: ESTADOS_MEM[remetente] = estado
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try:
        async with httpx.AsyncClient() as client:
            if estado is None:
                await client.delete(f"{SUPABASE_URL}/rest/v1/controle_sessao?remetente=eq.{remetente}", headers=get_h(), timeout=5)
            else:
                await client.post(f"{SUPABASE_URL}/rest/v1/controle_sessao?on_conflict=remetente", json={"remetente": remetente, "estado": estado}, headers=get_h_upsert(), timeout=5)
    except: pass

async def save_lead(remetente, campo, valor):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try:
        cel = remetente.split("@")[0]
        async with httpx.AsyncClient() as client:
            await client.post(f"{SUPABASE_URL}/rest/v1/leads_credito?on_conflict=remetente", json={"remetente": remetente, "celular": cel, campo: valor}, headers=get_h_upsert(), timeout=5)
            # Também garante na tabela customers (compatível com seu endpoint novo)
            await client.post(f"{SUPABASE_URL}/rest/v1/customers?on_conflict=phone", json={"phone": cel, "name": valor if campo=="nome_completo" else "Cliente WhatsApp", "source": "whatsapp", "status": "lead"}, headers=get_h_upsert(), timeout=5)
    except Exception as e:
        print(f"Erro save_lead: {e}")

async def processa(jid, txt):
    agora = time.time()
    if jid in ULTIMA_MSG and ULTIMA_MSG[jid]["txt"] == txt and agora - ULTIMA_MSG[jid]["ts"] < 8:
        print(f"LOOP IGNORADO {jid}")
        return
    ULTIMA_MSG[jid] = {"txt": txt, "ts": agora}

    estado = await get_estado(jid)
    print(f">>> JID: {jid} | ESTADO: {estado} | MSG: {txt}")

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
            await send(jid, "Entendido. Encerramos por aqui. Quando quiser voltar, basta mandar um *Oi*.")
            return
        await send(jid, "Por favor, digite *1* para SIM ou *2* para NÃO.")
        return

    if estado == "AGUARDANDO_MENU":
        if txt in ["1","2","3"]:
            tipos = {"1": "CREDITO_GARANTIA", "2": "REFIN", "3": "PORTABILIDADE"}
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
            await send(jid, "Perfeito. Já notifiquei o responsável. Você será atendido aqui mesmo em até *10 minutos*.")
            if SEU_NUMERO_DONO:
                await send(SEU_NUMERO_DONO, f"🚨 *LEAD QUER FALAR COM VOCÊ*\nDe: {jid}\nMsg: {txt}")
            return
        ia = await resposta_meta_ai(txt)
        if ia:
            await send(jid, ia)
        else:
            await send(jid, f"Excelente pergunta sobre '{txt}'.")
        await send(jid, MENU_PRINCIPAL)
        await set_estado(jid, "AGUARDANDO_MENU")
        return

    if estado == "AGUARDANDO_CPF_ACOMPANHAR":
        await save_lead(jid, "cpf", txt)
        await set_estado(jid, None)
        await send(jid, f"CPF *{txt}* recebido. Já consulto o status da sua proposta e te retorno aqui mesmo.")
        if SEU_NUMERO_DONO:
            await send(SEU_NUMERO_DONO, f"🔍 *ACOMPANHAMENTO* - {jid} CPF {txt}")
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
            await send(jid, f"*PROTOCOLO GERADO COM SUCESSO* ✅\n━━━━━━━━━━━━━━━━━━\nProtocolo: *LCB-{jid[-4:]}*\n\nRecebemos seus dados. Nossa equipe retornará em até *02h úteis* com a simulação.\n\nAgradecemos a confiança na *L.C. BANKERS.*")
            if SEU_NUMERO_DONO:
                await send(SEU_NUMERO_DONO, f"🎯 *NOVO LEAD COMPLETO* - {jid}")
        return

@app.get("/")
@app.get("/health")
async def root():
    return {"ok": True, "versao": "V35 UNIFICADO", "ia": AI_ATIVA, "instance": INSTANCE_NAME, "supabase": bool(SUPABASE_URL)}

@app.get("/test-ia")
async def test_ia(q: str = "qual a taxa?"):
    resp = await resposta_meta_ai(q)
    return {"pergunta": q, "resposta": resp, "ativa": AI_ATIVA}

# ENDPOINT UNICO - Evolution deve apontar pra /webhook
@app.post("/webhook")
@app.post("/webhook/whatsapp")
@app.post("/webhook/{path:path}")
async def webhook(request: Request, background_tasks: BackgroundTasks, path: str = ""):
    try:
        data = await request.json()
    except:
        return {"ok": True}
    
    d = data.get("data", data)
    msg_data = d
    if isinstance(d.get("messages"), list):
        msg_data = d["messages"][0]
    elif isinstance(d.get("data"), dict):
        inner = d["data"]
        msg_data = inner["messages"][0] if isinstance(inner.get("messages"), list) else inner

    key = msg_data.get("key", {})
    if key.get("fromMe"): 
        return {"ok": True}
    jid = key.get("remoteJid") or ""
    if not jid or "@g.us" in jid or "status@broadcast" in jid: 
        return {"ok": True}

    msg_id = key.get("id","")
    if msg_id in PROCESSADOS: 
        return {"ok": True}
    PROCESSADOS.add(msg_id)
    if len(PROCESSADOS) > 500: 
        PROCESSADOS.clear()

    msg = msg_data.get("message", {})
    txt = (msg.get("conversation") or msg.get("extendedTextMessage", {}).get("text") or msg.get("imageMessage", {}).get("caption") or "").strip()
    if not txt: 
        return {"ok": True}

    background_tasks.add_task(processa, jid, txt)
    return {"ok": True}
