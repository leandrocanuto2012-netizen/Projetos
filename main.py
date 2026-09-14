import httpx
#... seu código anterior...

# COLOCA SUA CHAVE AQUI (pode usar OpenAI, Groq de graça, ou Llama da Meta)
GROQ_API_KEY = "SUA_CHAVE_GROQ_GRATIS_AQUI"
AI_ATIVA = True # deixa True pra ligar a Meta AI no Leco

PROMPT_LECO_PREMIUM = """
Você é o Leco, consultor premium da L.C. BANKERS ADVISORY.
Tom: elegante, banco private, suíço, direto, sem gíria.
Nunca fala que é IA. Você é o Leco.
Objetivo: tirar dúvidas sobre crédito com garantia de imóvel, taxas a partir de 1,09%, prazo até 240 meses.
Se o cliente quer simulação, puxa pro fluxo: pede nome, email, cpf, valor, cep.
Sempre termina oferecendo as opções do menu.
Resposta curta, premium, com ━━━━━ quando precisar.
"""

async def resposta_meta_ai(historico, pergunta_cliente):
    if not AI_ATIVA: return None
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile", # Meta Llama da Meta
                    "messages": [
                        {"role": "system", "content": PROMPT_LECO_PREMIUM},
                        {"role": "user", "content": f"Cliente disse: {pergunta_cliente}"}
                    ],
                    "max_tokens": 400,
                    "temperature": 0.6
                },
                timeout=15
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
    except: pass
    return None

# Dentro do seu processa(), adiciona no final:
# if texto não é 1,2,3,4,5 e não é CPF/email, chama a IA:

# if estado not in ["AGUARDANDO_NOME", "AGUARDANDO_EMAIL"...]:
# resp_ia = await resposta_meta_ai([], txt)
# if resp_ia:
# await send(jid, resp_ia)
# await send(jid, MENU_PRINCIPAL)
# return