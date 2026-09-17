"""
ADAPTOR INTEGRADO - evolution-api + lc-bankersadvisory + supabase + redis
Cole este arquivo como main.py na raiz do repo Projetos (substitui o atual)
ou como adaptor/main.py se seu Render aponta pra subpasta.

Render vai fazer deploy sozinho após o push.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Optional
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- CONFIG ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("REDIS_REST_URL")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-gkgk.onrender.com")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
BANKERS_API_URL = os.getenv("BANKERS_API_URL", "https://lc-bankersadvisory.onrender.com")
COMPANY_ID = os.getenv("COMPANY_ID", "00000000-0000-0000-0000-000000000001")
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "erp:afonsopena:")

app = FastAPI(title="adaptor - Afonso Pena Integrado")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPERS ---
def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def normalize_phone(phone: str) -> str:
    # 5541... apenas numeros
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('55') and len(digits) >= 12:
        return digits
    if len(digits) >= 10:
        return '55' + digits[-11:]  # assume BR
    return digits

async def supabase_select(table: str, params: str):
    async with httpx.AsyncClient() as client:
        url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
        r = await client.get(url, headers=get_supabase_headers(), timeout=15)
        r.raise_for_status()
        return r.json()

async def supabase_insert(table: str, payload: dict):
    async with httpx.AsyncClient() as client:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        r = await client.post(url, headers=get_supabase_headers(), json=payload, timeout=15)
        if r.status_code >= 400:
            print(f"[SUPABASE ERROR] {table} {r.status_code} {r.text}")
        r.raise_for_status()
        return r.json()

async def check_banker_can_reactivate(customer_id: str, phone: str) -> bool:
    """
    Chama lc-bankersadvisory pra ver se pode reativar.
    Se o seu bankers não tem endpoint ainda, ele retorna True por padrão.
    Tenta 3 rotas comuns, se falhar libera.
    """
    if not BANKERS_API_URL:
        return True
    async with httpx.AsyncClient() as client:
        for path in ["/check-credit", "/can-reactivate", "/validate-customer", "/api/check"]:
            try:
                url = f"{BANKERS_API_URL.rstrip('/')}{path}"
                resp = await client.post(url, json={"customer_id": customer_id, "phone": phone, "company_id": COMPANY_ID}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    # espera {"can_reactivate": bool} ou {"blocked": bool}
                    if "can_reactivate" in data:
                        return bool(data["can_reactivate"])
                    if "blocked" in data:
                        return not bool(data["blocked"])
                    # se retornou sem bloquear, libera
                    return True
            except Exception as e:
                print(f"[BANKERS] tentativa {path} falhou: {e}")
                continue
    # Fallback: checa financial_titles direto no supabase (trava de inadimplencia)
    try:
        titles = await supabase_select("financial_titles", f"customer_id=eq.{customer_id}&status=eq.Atrasado")
        if titles and len(titles) > 0:
            print(f"[BANKERS FALLBACK] cliente {customer_id} com titulo atrasado, bloqueando")
            return False
    except Exception as e:
        print(f"[BANKERS FALLBACK] erro ao checar financial_titles: {e}")
    return True

async def get_or_create_customer(phone: str, name: Optional[str] = None):
    phone_norm = normalize_phone(phone)
    # busca
    try:
        customers = await supabase_select("customers", f"phone=eq.{phone_norm}&company_id=eq.{COMPANY_ID}&limit=1")
        if customers:
            return customers[0]
    except Exception as e:
        print(f"[CUSTOMER SELECT] erro: {e}")
    
    # cria
    payload = {
        "company_id": COMPANY_ID,
        "phone": phone_norm,
        "name": name or f"Cliente {phone_norm[-4:]}",
        "last_purchase": (datetime.utcnow() - timedelta(days=45)).isoformat()
    }
    try:
        created = await supabase_insert("customers", payload)
        return created[0] if isinstance(created, list) else created
    except Exception as e:
        print(f"[CUSTOMER INSERT] erro: {e}")
        # tenta buscar de novo se deu conflito
        try:
            customers = await supabase_select("customers", f"phone=eq.{phone_norm}&limit=1")
            if customers:
                return customers[0]
        except:
            pass
        return None

def redis_set_cooldown(customer_id: str):
    if not REDIS_URL:
        return
    try:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
        key = f"{REDIS_PREFIX}cooldown:customer:{customer_id}"
        # 15 dias
        r.set(key, datetime.utcnow().isoformat(), ex=15*24*3600)
        print(f"[REDIS] cooldown set {key}")
    except Exception as e:
        print(f"[REDIS] erro cooldown: {e}")

def redis_check_cooldown(customer_id: str) -> bool:
    if not REDIS_URL:
        return False
    try:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
        key = f"{REDIS_PREFIX}cooldown:customer:{customer_id}"
        return r.exists(key) == 1
    except:
        return False

async def trigger_reactivation_flow(customer: dict, channel: str = "WHATSAPP", external_chat_id: str = ""):
    customer_id = customer["id"]
    if redis_check_cooldown(customer_id):
        print(f"[FLOW] cliente {customer_id} em cooldown, ignorando")
        return
    
    # checa banker
    can = await check_banker_can_reactivate(customer_id, customer.get("phone",""))
    if not can:
        print(f"[FLOW] cliente {customer_id} bloqueado pelo bankers")
        return

    # verifica dias sem comprar
    last_purchase_str = customer.get("last_purchase")
    days_inactive = 45
    if last_purchase_str:
        try:
            last = datetime.fromisoformat(last_purchase_str.replace("Z",""))
            days_inactive = (datetime.utcnow() - last).days
        except:
            pass

    # seleciona campanha (30,60,90,120)
    trigger_type = "REACTIVATION_30D"
    if days_inactive >= 120:
        trigger_type = "REACTIVATION_120D"
    elif days_inactive >= 90:
        trigger_type = "REACTIVATION_90D"
    elif days_inactive >= 60:
        trigger_type = "REACTIVATION_60D"

    # busca campanha ativa
    try:
        camps = await supabase_select("bot_campaigns", f"trigger_event_type=eq.{trigger_type}&active=eq.true&limit=1")
        if not camps:
            # fallback qualquer reativacao
            camps = await supabase_select("bot_campaigns", f"active=eq.true&limit=1")
    except Exception as e:
        print(f"[CAMP SELECT] erro: {e}")
        camps = []

    campaign_id = camps[0]["id"] if camps else None

    # cria conversa
    conv_payload = {
        "company_id": COMPANY_ID,
        "customer_id": customer_id,
        "channel": channel,
        "external_chat_id": external_chat_id or customer.get("phone",""),
        "status": "BOT_ACTIVE"
    }
    try:
        conv = await supabase_insert("bot_conversations", conv_payload)
        conv_id = conv[0]["id"] if isinstance(conv, list) else conv.get("id")
        print(f"[FLOW] conversa criada {conv_id} para {customer_id} campanha {trigger_type}")

        # se tiver campanha, cria execucao
        if campaign_id and conv_id:
            exec_payload = {
                "campaign_id": campaign_id,
                "conversation_id": conv_id,
                "customer_id": customer_id,
                "status": "PENDING"
            }
            await supabase_insert("bot_campaign_executions", exec_payload)

        redis_set_cooldown(customer_id)

        # envia msg via evolution-api (opcional)
        if EVOLUTION_API_URL and EVOLUTION_API_KEY:
            try:
                msg_text = f"Olá {customer.get('name','')}! Sentimos sua falta há {days_inactive} dias. Que tal voltar? 🥖"
                if camps and camps[0].get("name"):
                    msg_text = f"Olá {customer.get('name','')}! {camps[0].get('name')} - {days_inactive} dias sem você por aqui!"
                async with httpx.AsyncClient() as client:
                    send_url = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/instance"
                    # tenta formato evolution v2
                    await client.post(send_url, json={"number": customer.get("phone"), "text": msg_text}, headers={"apikey": EVOLUTION_API_KEY}, timeout=10)
            except Exception as e:
                print(f"[EVOLUTION SEND] erro: {e}")

    except Exception as e:
        print(f"[FLOW] erro ao criar conversa: {e}")

# --- ENDPOINTS ---
@app.get("/")
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "adaptor",
        "company_id": COMPANY_ID,
        "supabase": bool(SUPABASE_URL),
        "redis": bool(REDIS_URL),
        "evolution": EVOLUTION_API_URL,
        "bankers": BANKERS_API_URL,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/webhook/whatsapp")
async def webhook_whatsapp(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook que a evolution-api vai chamar.
    Payload evolution: {event, instance, data: {key, pushName, message, ...}}
    """
    try:
        body = await request.json()
    except:
        body = {}
    
    print(f"[WEBHOOK] recebido: {str(body)[:500]}")

    # tenta extrair telefone e nome em varios formatos evolution
    phone = None
    name = None
    external_chat_id = ""

    # formato 1: evolution v2 messages.upsert
    data = body.get("data") or body
    if isinstance(data, dict):
        # key.remoteJid
        key = data.get("key") or {}
        if key.get("remoteJid"):
            phone = key.get("remoteJid")
            external_chat_id = phone
        # pushName
        name = data.get("pushName") or data.get("push_name") or body.get("pushName")
        # numero direto
        if not phone:
            phone = data.get("number") or data.get("from") or body.get("from") or body.get("phone")

    # formato 2: payload simples que voce mandar manual
    if not phone:
        phone = body.get("phone") or body.get("remoteJid")

    if not phone:
        return {"status": "ignored", "reason": "no phone found", "body_keys": list(body.keys())}

    phone_norm = normalize_phone(phone)
    background_tasks.add_task(process_incoming_message, phone_norm, name or "Cliente WhatsApp", external_chat_id or phone_norm)

    return {"status": "queued", "phone": phone_norm}

async def process_incoming_message(phone: str, name: str, external_chat_id: str):
    customer = await get_or_create_customer(phone, name)
    if not customer:
        print(f"[PROCESS] falhou ao criar/buscar cliente {phone}")
        return
    await trigger_reactivation_flow(customer, "WHATSAPP", external_chat_id)

@app.post("/customers")
async def create_customer_manual(req: Request):
    body = await req.json()
    phone = body.get("phone")
    name = body.get("name")
    if not phone:
        return {"error": "phone required"}
    customer = await get_or_create_customer(phone, name)
    return {"customer": customer}

@app.get("/customers/{phone}")
async def get_customer(phone: str):
    phone_norm = normalize_phone(phone)
    customers = await supabase_select("customers", f"phone=eq.{phone_norm}&limit=1")
    return {"customer": customers[0] if customers else None}

@app.post("/test-reactivation/{phone}")
async def test_reactivation(phone: str):
    phone_norm = normalize_phone(phone)
    customer = await get_or_create_customer(phone_norm, "Teste Manual")
    if not customer:
        return {"error": "não criou cliente"}
    await trigger_reactivation_flow(customer, "WHATSAPP", phone_norm)
    return {"status": "triggered", "customer": customer}

# Para rodar local: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
