import os
import json
import hashlib
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

try:
    from wms_core import numero_float, registrar_wms_movimento
except ImportError:
    def numero_float(valor, padrao=0.0):
        try:
            return float(valor) if valor not in (None, "") else padrao
        except (ValueError, TypeError):
            return padrao

    def registrar_wms_movimento(cur, dados, tipo, origem, documento, funcionario_matricula=None):
        vu = numero_float(dados.get("valor_unitario"), 0)
        qty = numero_float(dados.get("qty"), 0)
        cur.execute("""INSERT INTO wms_movimentos
            (product_id, sku, produto_nome, tipo, qty, valor_unitario, valor_total,
             origem, documento, funcionario_matricula, location_code)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (dados.get("product_id"), dados.get("sku"), dados.get("produto_nome"),
             tipo, qty, vu, vu*qty, origem, documento, funcionario_matricula,
             dados.get("location_code", "A-01-01-01")))
        return cur.fetchone()['id']

load_dotenv()

# Conexao Supabase (PostgreSQL) - usa DATABASE_URI se existir, senao usa campos separados
DATABASE_URI = os.environ.get("DATABASE_URI", "")

def get_conn():
    if DATABASE_URI:
        # Usa a URI completa do Supabase (pooler ou direta)
        conn = psycopg2.connect(DATABASE_URI, connect_timeout=30)
    else:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ.get("DB_NAME", "postgres"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASS", ""),
            connect_timeout=30
        )
    conn.autocommit = False
    return conn

class DBConnection:
    def __enter__(self):
        self.conn = get_conn()
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self.conn, self.cur
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type: self.conn.rollback()
            else: self.conn.commit()
        except Exception: pass
        finally:
            try: self.cur.close()
            except Exception: pass
            try: self.conn.close()
            except Exception: pass

def ultimo_id(cur):
    cur.execute("SELECT LASTVAL() AS id")
    return cur.fetchone()['id']

MODULOS_PADRAO = ["dashboard","fornecedores","produtos","clientes","funcionarios","wms","caixa","comandas","rh","tesouraria","contabilidade","bancos","logistica","sites"]
PERFIS_AUTORIZADORES = {"admin","gerente","financeiro"}

def hash_senha(s): return hashlib.sha256(str(s or "").encode()).hexdigest()

def normalizar_permissoes(v):
    if isinstance(v, list): return v
    if isinstance(v, str) and v.strip():
        try:
            d = json.loads(v); return d if isinstance(d, list) else []
        except: return []
    return []

def normalizar_bool(v):
    if isinstance(v, bool): return v
    if v is None or v == "": return None
    t = str(v).strip().lower()
    if t in ("1","true","sim","s","yes","on"): return True
    if t in ("0","false","nao","não","n","no","off"): return False
    return bool(v)

def preparar_usuario(row):
    if not row: return None
    row = dict(row)
    row.pop("senha_hash", None)
    row["permissoes"] = normalizar_permissoes(row.get("permissoes"))
    return row

def buscar_funcionario(cur, mat):
    if not mat: return None
    cur.execute("SELECT * FROM funcionarios WHERE matricula=%s AND status='ATIVO' LIMIT 1", (mat,))
    return cur.fetchone()

def usuario_do_corpo(cur, dados):
    u = dados.get("usuario") or {}
    mat = u.get("matricula") or dados.get("operator_matricula") or dados.get("matricula")
    return buscar_funcionario(cur, mat)

def pode_autorizar(u):
    if not u: return False
    return u.get("role") in PERFIS_AUTORIZADORES or "tesouraria" in normalizar_permissoes(u.get("permissoes"))

def usuario_tem_modulo(u, mod):
    if not u: return False
    if u.get("role") in PERFIS_AUTORIZADORES: return True
    return mod in normalizar_permissoes(u.get("permissoes"))

def pode_gerir_rh(u):
    if not u: return False
    return u.get("role") in {"admin","gerente"} or "rh_admin" in normalizar_permissoes(u.get("permissoes"))

def gerar_numero_comanda():
    return "CMD" + datetime.now().strftime("%y%m%d%H%M%S%f")[-12:]

def atualizar_total_comanda(cur, cid):
    cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM comanda_itens WHERE comanda_id=%s", (cid,))
    t = cur.fetchone().get("t", 0)
    cur.execute("UPDATE comandas SET total=%s WHERE id=%s", (t, cid))
    return t

def log_caixa_terminal(evento, usuario=None, detalhes=None):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [CAIXA] {evento}", flush=True)
    if detalhes:
        for k, v in detalhes.items():
            print(f"  {str(k).upper()}: {v}", flush=True)

def garantir_schema():
    """No Supabase as tabelas sao criadas pelo SQL. Aqui so garantimos dados padrao."""
    with DBConnection() as (conn, cur):
        cur.execute("SELECT COUNT(*) AS t FROM formas_pagamento_taxas")
        if (cur.fetchone() or {}).get("t", 0) == 0:
            cur.executemany("INSERT INTO formas_pagamento_taxas (nome,tipo,taxa_percentual,taxa_fixa,operacao,ativo) VALUES (%s,%s,%s,%s,%s,TRUE)",
                [("PIX padrao","PIX",0,0,"RECEBIMENTO"),("Boleto padrao","BOLETO",1.5,0,"RECEBIMENTO"),
                 ("Cartao credito","CREDITO",3.5,0,"RECEBIMENTO"),("Dinheiro","DINHEIRO",0,0,"RECEBIMENTO")])
        cur.execute("SELECT COUNT(*) AS t FROM site_config_grid")
        if (cur.fetchone() or {}).get("t", 0) == 0:
            cur.executemany("INSERT INTO site_config_grid (secao,nome,valor,tipo,ativo,ordem) VALUES (%s,%s,%s,%s,TRUE,%s)",
                [("bot_geral","nome_bot","Dona Padaria","texto",1),
                 ("bot_geral","saudacao","Olá! Bem-vindo à Padaria! Como posso ajudar?","texto",2),
                 ("bot_geral","horario_atendimento","Seg-Sáb 6h às 20h, Dom 7h às 13h","texto",3),
                 ("bot_geral","endereco","Rua das Flores, 123 - Centro","texto",4),
                 ("bot_regras","oi|ola|olá|bom dia|boa tarde|boa noite","Saudação","regra_bot",10),
                 ("bot_regras","preco|valor|quanto custa|preço","Consulta preço","regra_bot",11),
                 ("bot_regras","horario|horário|abre|fecha|funcionamento","Horário","regra_bot",12),
                 ("bot_regras","endereco|endereço|onde fica|localizacao","Endereço","regra_bot",13),
                 ("bot_regras","pedido|comprar|quero|encomendar","Fazer pedido","regra_bot",14)])
        cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
        if cur.fetchone():
            cur.execute("UPDATE funcionarios SET senha_hash=%s, role='admin', permissoes=%s, status='ATIVO' WHERE matricula='AP-2026-0001'",
                (hash_senha("123"), json.dumps(MODULOS_PADRAO)))
        else:
            cur.execute("INSERT INTO funcionarios (matricula,nome,cargo,role,senha_hash,permissoes,status) VALUES (%s,%s,%s,%s,%s,%s,'ATIVO')",
                ("AP-2026-0001","Administrador","Gerente Geral","admin",hash_senha("123"),json.dumps(MODULOS_PADRAO)))
        conn.commit()
    print("Schema verificado no Supabase.", flush=True)


class APIHandler(BaseHTTPRequestHandler):
    def set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def get_body(self):
        tam = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tam)
        try: return json.loads(corpo) if tam else {}
        except: return {}

    def responder(self, dados, status=200):
        self.set_headers(status)
        self.wfile.write(json.dumps(dados, default=str, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}", flush=True)

    def do_GET(self):
        parsed = urlparse(self.path); path = parsed.path; query = parse_qs(parsed.query)
        # Serve o frontend (dashboard.html) na raiz
        if path in ("/", "/index.html", "/dashboard.html"):
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                with open(os.path.join(base, "dashboard.html"), "rb") as f:
                    conteudo = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(conteudo)
            except FileNotFoundError:
                self.responder({"erro": "dashboard.html nao encontrado na mesma pasta"}, 404)
            return
        try:
            with DBConnection() as (conn, cur):
                if path == "/api/health":
                    cur.execute("SELECT 1 as ok"); cur.fetchone()
                    return self.responder({"status":"ok","banco":"supabase conectado"})

                GET = {
                    "/api/fornecedores": "SELECT * FROM fornecedores ORDER BY id DESC LIMIT 100",
                    "/api/produtos": "SELECT * FROM produtos ORDER BY id DESC LIMIT 200",
                    "/api/clientes": "SELECT * FROM clientes ORDER BY id DESC LIMIT 100",
                    "/api/vendas": "SELECT * FROM vendas ORDER BY data DESC, id DESC LIMIT 200",
                    "/api/comandas": "SELECT * FROM comandas ORDER BY entrada_at DESC LIMIT 200",
                    "/api/autorizacoes": "SELECT * FROM autorizacoes ORDER BY created_at DESC LIMIT 200",
                    "/api/wms/estoque": "SELECT * FROM wms_estoque ORDER BY location_code LIMIT 200",
                    "/api/wms/movimentos": "SELECT * FROM wms_movimentos ORDER BY created_at DESC LIMIT 300",
                    "/api/livro-caixa": "SELECT * FROM livro_caixa ORDER BY data DESC LIMIT 100",
                    "/api/caixa/movimentos": "SELECT * FROM caixa_movimentos ORDER BY created_at DESC LIMIT 200",
                    "/api/rh/ferias": "SELECT * FROM rh_ferias ORDER BY solicitado_em DESC LIMIT 300",
                    "/api/rh/ponto": "SELECT * FROM rh_ponto ORDER BY data DESC, id DESC LIMIT 300",
                    "/api/rh/holerites": "SELECT * FROM rh_holerites ORDER BY competencia DESC LIMIT 300",
                    "/api/rh/eventos": "SELECT * FROM rh_eventos ORDER BY created_at DESC LIMIT 300",
                    "/api/logistica/movimentos": "SELECT * FROM logistica_movimentos ORDER BY created_at DESC LIMIT 300",
                    "/api/site/marketing": "SELECT * FROM site_marketing ORDER BY ativo DESC, id DESC",
                    "/api/site/clientes": "SELECT id,nome,email,telefone,status,created_at FROM site_clientes ORDER BY created_at DESC LIMIT 200",
                    "/api/bancos": "SELECT * FROM bancos_comerciais ORDER BY id",
                    "/api/formas-pagamento": "SELECT * FROM formas_pagamento_taxas WHERE ativo=TRUE ORDER BY id",
                }
                if path in GET:
                    cur.execute(GET[path])
                    chave = path.split("/")[-1].replace("-","_")
                    return self.responder({chave: [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/funcionarios":
                    cur.execute("SELECT * FROM funcionarios ORDER BY id DESC LIMIT 100")
                    return self.responder({"funcionarios":[preparar_usuario(r) for r in (cur.fetchall() or [])]})

                if path == "/api/comandas/itens":
                    cid = query.get("comanda_id",[None])[0]
                    if cid:
                        cur.execute("SELECT * FROM comanda_itens WHERE comanda_id=%s ORDER BY id", (cid,))
                    else:
                        cur.execute("SELECT * FROM comanda_itens ORDER BY created_at DESC LIMIT 300")
                    return self.responder({"itens": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/site/pedidos":
                    sf = query.get("status",[None])[0]
                    if sf:
                        cur.execute("SELECT * FROM site_pedidos WHERE status=%s ORDER BY created_at DESC LIMIT 200", (sf,))
                    else:
                        cur.execute("SELECT * FROM site_pedidos ORDER BY created_at DESC LIMIT 200")
                    return self.responder({"pedidos": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/site/config":
                    cur.execute("SELECT * FROM site_config_grid ORDER BY secao, ordem, id")
                    return self.responder({"configuracoes": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/caixa/status-online":
                    cur.execute("SELECT * FROM livro_caixa WHERE status='ABERTO' ORDER BY data DESC")
                    abertos = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT COUNT(*) AS t FROM autorizacoes WHERE status='PENDENTE'")
                    pend = (cur.fetchone() or {}).get("t",0)
                    cur.execute("""SELECT COALESCE(SUM(CASE WHEN tipo IN ('ENTRADA','RECEBIMENTO','VENDA','SUPRIMENTO') THEN valor ELSE 0 END),0)
                        - COALESCE(SUM(CASE WHEN tipo IN ('SAIDA','SANGRIA','ENVIO_TESOURARIA') THEN valor ELSE 0 END),0) AS saldo
                        FROM caixa_movimentos WHERE status='APROVADO'""")
                    saldo = (cur.fetchone() or {}).get("saldo",0)
                    return self.responder({"online":True,"caixas_abertos":abertos,"autorizacoes_pendentes":pend,"saldo_atual":float(saldo or 0)})

                if path == "/api/tesouraria/status":
                    cur.execute("SELECT * FROM livro_caixa WHERE status='ABERTO' ORDER BY data DESC")
                    abertos = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT * FROM caixa_movimentos ORDER BY created_at DESC LIMIT 100")
                    movs = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT * FROM autorizacoes WHERE status='PENDENTE' ORDER BY created_at")
                    pend = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("""SELECT COALESCE(SUM(CASE WHEN tipo IN ('ENTRADA','RECEBIMENTO','VENDA','SUPRIMENTO') THEN valor ELSE 0 END),0)
                        - COALESCE(SUM(CASE WHEN tipo IN ('SAIDA','SANGRIA','ENVIO_TESOURARIA') THEN valor ELSE 0 END),0) AS saldo
                        FROM caixa_movimentos WHERE status='APROVADO'""")
                    saldo = (cur.fetchone() or {}).get("saldo",0)
                    return self.responder({"caixas_abertos":abertos,"movimentos":movs,"autorizacoes_pendentes":pend,"saldo_atual":float(saldo or 0)})

                if path == "/api/contas":
                    cur.execute("SELECT * FROM contas_financeiras ORDER BY vencimento ASC LIMIT 300")
                    return self.responder({"contas": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/contabilidade/resumo":
                    cur.execute("SELECT status, COUNT(*) AS qtd, COALESCE(SUM(valor),0) AS total FROM contas_financeiras GROUP BY status")
                    por_status = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT categoria, COALESCE(SUM(valor),0) AS total FROM contas_financeiras WHERE status='ABERTO' GROUP BY categoria ORDER BY total DESC LIMIT 20")
                    por_cat = [dict(r) for r in (cur.fetchall() or [])]
                    return self.responder({"contas_por_status":por_status,"contas_por_categoria":por_cat})

                if path == "/api/bancos/movimentos":
                    bid = query.get("banco_id",[None])[0]
                    if bid:
                        cur.execute("SELECT * FROM banco_movimentos WHERE banco_id=%s ORDER BY data_movimento DESC LIMIT 200", (bid,))
                    else:
                        cur.execute("SELECT * FROM banco_movimentos ORDER BY data_movimento DESC LIMIT 200")
                    return self.responder({"movimentos": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/rh/resumo":
                    cur.execute("""SELECT f.matricula,f.nome,f.cargo,
                        COALESCE(SUM(p.horas_trabalhadas),0) AS horas_trabalhadas,
                        COALESCE(SUM(p.horas_extras),0) AS horas_extras,
                        COALESCE(SUM(CASE WHEN p.falta THEN 1 ELSE 0 END),0) AS faltas
                        FROM funcionarios f LEFT JOIN rh_ponto p ON p.funcionario_matricula=f.matricula
                        AND p.data >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY f.matricula,f.nome,f.cargo ORDER BY f.nome""")
                    assid = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("""SELECT operador_matricula AS matricula, COUNT(*) AS vendas,
                        COALESCE(SUM(total),0) AS valor, COALESCE(AVG(total),0) AS ticket_medio
                        FROM vendas WHERE operador_matricula IS NOT NULL
                        AND data >= NOW() - INTERVAL '30 days'
                        GROUP BY operador_matricula ORDER BY valor DESC""")
                    vendas_func = [dict(r) for r in (cur.fetchall() or [])]
                    return self.responder({"assiduidade":assid,"vendas_funcionarios":vendas_func})

                if path == "/api/dashboard/resumo":
                    hoje = datetime.now().strftime("%Y-%m-%d")
                    cur.execute("SELECT COALESCE(SUM(valor),0) AS total FROM contas_financeiras WHERE tipo='RECEBER' AND status='ABERTO' AND vencimento<=%s", (hoje,))
                    receber_hoje = float((cur.fetchone() or {}).get("total",0) or 0)
                    cur.execute("SELECT COALESCE(SUM(valor),0) AS total FROM contas_financeiras WHERE tipo='PAGAR' AND status='ABERTO' AND vencimento<=%s", (hoje,))
                    pagar_hoje = float((cur.fetchone() or {}).get("total",0) or 0)
                    cur.execute("SELECT COALESCE(SUM(total),0) AS total FROM vendas WHERE DATE(data)=%s", (hoje,))
                    vendas_hoje = float((cur.fetchone() or {}).get("total",0) or 0)
                    cur.execute("SELECT COALESCE(SUM(total),0) AS total FROM vendas WHERE EXTRACT(MONTH FROM data)=EXTRACT(MONTH FROM NOW()) AND EXTRACT(YEAR FROM data)=EXTRACT(YEAR FROM NOW())")
                    vendas_mes = float((cur.fetchone() or {}).get("total",0) or 0)
                    cur.execute("SELECT COUNT(*) AS t FROM produtos p LEFT JOIN wms_estoque e ON e.product_id=p.id WHERE COALESCE(e.qty,0) <= p.estoque_minimo AND p.status='ATIVO'")
                    estoque_baixo = (cur.fetchone() or {}).get("t",0)
                    cur.execute("SELECT COUNT(*) AS t FROM site_pedidos WHERE status='SOLICITADO'")
                    pedidos_pendentes = (cur.fetchone() or {}).get("t",0)
                    cur.execute("""SELECT DATE(data) AS dia, COALESCE(SUM(total),0) AS valor FROM vendas
                        WHERE data >= NOW() - INTERVAL '7 days' GROUP BY DATE(data) ORDER BY dia""")
                    vendas_7d = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT COALESCE(SUM(saldo),0) AS total FROM bancos_comerciais WHERE status='ATIVO'")
                    saldo_bancos = float((cur.fetchone() or {}).get("total",0) or 0)
                    return self.responder({
                        "receber_hoje":receber_hoje,"pagar_hoje":pagar_hoje,
                        "vendas_hoje":vendas_hoje,"vendas_mes":vendas_mes,
                        "estoque_baixo":estoque_baixo,"pedidos_pendentes":pedidos_pendentes,
                        "vendas_7d":vendas_7d,"saldo_bancos":saldo_bancos
                    })

                # ===== GRID 1: Bot Config =====
                if path == "/api/bot/config":
                    cur.execute("SELECT * FROM site_config_grid WHERE secao='bot_geral' ORDER BY ordem, id")
                    geral = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT * FROM site_config_grid WHERE secao='bot_regras' ORDER BY ordem, id")
                    regras = [dict(r) for r in (cur.fetchall() or [])]
                    return self.responder({"config_geral":geral,"regras":regras})

                # ===== GRID 2: Gerente =====
                if path == "/api/gerente/status-modulos":
                    modulos = []
                    checks = [
                        ("Caixa","SELECT COUNT(*) AS t FROM livro_caixa WHERE status='ABERTO'","caixa_aberto"),
                        ("Estoque Baixo","SELECT COUNT(*) AS t FROM produtos p LEFT JOIN wms_estoque e ON e.product_id=p.id WHERE COALESCE(e.qty,0)<=p.estoque_minimo AND p.status='ATIVO'","alertas"),
                        ("Contas Vencidas","SELECT COUNT(*) AS t FROM contas_financeiras WHERE status='ABERTO' AND vencimento<CURRENT_DATE","alertas"),
                        ("Pedidos Site","SELECT COUNT(*) AS t FROM site_pedidos WHERE status='SOLICITADO'","alertas"),
                        ("Autorizações","SELECT COUNT(*) AS t FROM autorizacoes WHERE status='PENDENTE'","alertas"),
                    ]
                    for nome, sql, tipo in checks:
                        cur.execute(sql); v = (cur.fetchone() or {}).get("t",0)
                        status = "ok" if v == 0 else "atencao"
                        if nome == "Caixa": status = "ok" if v>0 else "atencao"
                        elif v > 0: status = "alerta"
                        modulos.append({"modulo":nome,"valor":v,"status":status})
                    return self.responder({"modulos":modulos})

                if path == "/api/gerente/alertas":
                    alertas = []
                    cur.execute("SELECT COUNT(*) AS t FROM produtos p LEFT JOIN wms_estoque e ON e.product_id=p.id WHERE COALESCE(e.qty,0)<=p.estoque_minimo AND p.status='ATIVO'")
                    eb = (cur.fetchone() or {}).get("t",0)
                    if eb: alertas.append({"tipo":"estoque","mensagem":f"{eb} produto(s) com estoque baixo","nivel":"alerta"})
                    cur.execute("SELECT COUNT(*) AS t FROM contas_financeiras WHERE status='ABERTO' AND vencimento<CURRENT_DATE")
                    cv = (cur.fetchone() or {}).get("t",0)
                    if cv: alertas.append({"tipo":"financeiro","mensagem":f"{cv} conta(s) vencida(s)","nivel":"critico"})
                    cur.execute("SELECT COUNT(*) AS t FROM autorizacoes WHERE status='PENDENTE'")
                    ap = (cur.fetchone() or {}).get("t",0)
                    if ap: alertas.append({"tipo":"autorizacao","mensagem":f"{ap} autorização(ões) pendente(s)","nivel":"atencao"})
                    cur.execute("SELECT COUNT(*) AS t FROM site_pedidos WHERE status='SOLICITADO'")
                    pp = (cur.fetchone() or {}).get("t",0)
                    if pp: alertas.append({"tipo":"pedido","mensagem":f"{pp} pedido(s) do site pendente(s)","nivel":"atencao"})
                    return self.responder({"alertas":alertas})

                if path == "/api/gerente/relatorio-vendas":
                    cur.execute("""SELECT DATE(data) AS dia, origem, COALESCE(SUM(total),0) AS valor, COUNT(*) AS qtd
                        FROM vendas WHERE data >= NOW() - INTERVAL '7 days'
                        GROUP BY DATE(data), origem ORDER BY dia""")
                    return self.responder({"vendas": [dict(r) for r in (cur.fetchall() or [])]})

                # ===== GRID 3: IA Vendas =====
                if path == "/api/ia-vendas/produtos":
                    cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY id DESC LIMIT 100")
                    return self.responder({"produtos": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/ia-vendas/produtos-recomendados":
                    cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 6")
                    return self.responder({"recomendados": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/ia-vendas/metricas":
                    cur.execute("SELECT COUNT(*) AS t FROM site_pedidos")
                    total_pedidos = (cur.fetchone() or {}).get("t",0)
                    cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM site_pedidos WHERE status IN ('CONFIRMADO','PAGO','ENTREGUE')")
                    receita = float((cur.fetchone() or {}).get("t",0) or 0)
                    cur.execute("SELECT COUNT(*) AS t FROM site_clientes")
                    clientes = (cur.fetchone() or {}).get("t",0)
                    return self.responder({"total_pedidos":total_pedidos,"receita_ia":receita,"clientes_site":clientes})

                if path == "/api/integracao/ifood/status":
                    cur.execute("SELECT * FROM integracoes_ifood ORDER BY id DESC LIMIT 1")
                    return self.responder({"ifood": dict(cur.fetchone() or {})})

                return self.responder({"erro":"Rota não encontrada: "+path}, 404)
        except Exception as e:
            return self.responder({"erro": str(e)}, 500)

    def do_POST(self):
        dados = self.get_body()
        try:
            with DBConnection() as (conn, cur):
                path = urlparse(self.path).path

                if path == "/api/login":
                    mat = dados.get("matricula"); senha = dados.get("senha")
                    cur.execute("SELECT * FROM funcionarios WHERE matricula=%s LIMIT 1", (mat,))
                    u = cur.fetchone()
                    if not u or u.get("senha_hash") != hash_senha(senha):
                        return self.responder({"erro":"Credenciais inválidas"}, 401)
                    if u.get("status") != "ATIVO":
                        return self.responder({"erro":"Usuário inativo"}, 403)
                    return self.responder({"sucesso":True,"usuario":preparar_usuario(u)})

                if path == "/api/caixa/abrir":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("INSERT INTO livro_caixa (status,operator_matricula,fundo_inicial,data) VALUES ('ABERTO',%s,%s,NOW()) RETURNING id",
                        (u["matricula"], numero_float(dados.get("fundo_inicial"),0)))
                    cid = cur.fetchone()['id']
                    log_caixa_terminal("CAIXA ABERTA", u, {"caixa_id":cid})
                    return self.responder({"sucesso":True,"caixa_id":cid})

                if path == "/api/caixa/fechar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cid = dados.get("caixa_id")
                    cur.execute("SELECT * FROM livro_caixa WHERE id=%s LIMIT 1", (cid,))
                    cx = cur.fetchone()
                    if not cx or cx["status"] != "ABERTO": return self.responder({"erro":"Caixa não está aberto"}, 400)
                    cur.execute("UPDATE livro_caixa SET status='FECHADO',valor_fechamento=%s,observacao_fechamento=%s,closed_at=NOW() WHERE id=%s",
                        (numero_float(dados.get("valor_fechamento"),0), dados.get("observacao",""), cid))
                    return self.responder({"sucesso":True})

                if path == "/api/caixa/movimento":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    tipo = dados.get("tipo"); valor = numero_float(dados.get("valor"),0)
                    precisa = valor > 1000 and tipo in ("SAIDA","SANGRIA","ENVIO_TESOURARIA")
                    aut_por = None
                    if precisa:
                        aut = buscar_funcionario(cur, dados.get("autorizado_por"))
                        if not aut or not pode_autorizar(aut):
                            cur.execute("INSERT INTO autorizacoes (tipo,referencia_tabela,valor,solicitado_por,motivo) VALUES ('movimento_caixa','caixa_movimentos',%s,%s,%s)",
                                (valor, u["matricula"], dados.get("descricao","")))
                            return self.responder({"sucesso":False,"mensagem":"Aguardando autorização","autorizacao_pendente":True}, 202)
                        aut_por = aut["matricula"]
                    cur.execute("INSERT INTO caixa_movimentos (caixa_id,tipo,valor,descricao,operator_matricula,autorizado_por) VALUES (%s,%s,%s,%s,%s,%s)",
                        (dados.get("caixa_id"), tipo, valor, dados.get("descricao",""), u["matricula"], aut_por))
                    return self.responder({"sucesso":True,"movimento_id":ultimo_id(cur)})

                if path == "/api/venda/criar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    itens = dados.get("itens", [])
                    total = sum(numero_float(i.get("total"), numero_float(i.get("qty"),1)*numero_float(i.get("unit_price"),0)) for i in itens)
                    cur.execute("INSERT INTO vendas (cliente_nome,total,forma_pagamento,origem,operador_matricula,caixa_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                        (dados.get("cliente_nome","Balcão"), total, dados.get("forma_pagamento","DINHEIRO"),
                         dados.get("origem","loja"), u["matricula"], dados.get("caixa_id")))
                    vid = cur.fetchone()['id']
                    for i in itens:
                        qty = numero_float(i.get("qty"),1)
                        registrar_wms_movimento(cur, i, "SAIDA", "VENDA", f"VENDA-{vid}", u["matricula"])
                        cur.execute("UPDATE wms_estoque SET qty=qty-%s WHERE product_id=%s LIMIT 1", (qty, i.get("product_id")))
                    cur.execute("INSERT INTO caixa_movimentos (caixa_id,tipo,valor,descricao,operator_matricula) VALUES (%s,'VENDA',%s,%s,%s)",
                        (dados.get("caixa_id"), total, f"Venda #{vid}", u["matricula"]))
                    return self.responder({"sucesso":True,"venda_id":vid,"total":total})

                if path == "/api/wms/entrada":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    mid = registrar_wms_movimento(cur, dados, "ENTRADA", dados.get("origem","NOTA_FISCAL"), dados.get("documento"), u["matricula"])
                    qty = numero_float(dados.get("qty"),0); vu = numero_float(dados.get("valor_unitario"),0)
                    cur.execute("""INSERT INTO wms_estoque (product_id,sku,produto_nome,location_code,qty,valor_unitario,valor_total)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (product_id, location_code) DO UPDATE
                        SET qty=wms_estoque.qty+EXCLUDED.qty, valor_unitario=EXCLUDED.valor_unitario, valor_total=(wms_estoque.qty+EXCLUDED.qty)*EXCLUDED.valor_unitario""",
                        (dados.get("product_id"), dados.get("sku"), dados.get("produto_nome"),
                         dados.get("location_code","A-01-01-01"), qty, vu, qty*vu))
                    return self.responder({"sucesso":True,"movimento_id":mid})

                if path == "/api/wms/saida":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    mid = registrar_wms_movimento(cur, dados, "SAIDA", dados.get("origem","VENDA"), dados.get("documento"), u["matricula"])
                    cur.execute("UPDATE wms_estoque SET qty=qty-%s WHERE product_id=%s", (numero_float(dados.get("qty"),0), dados.get("product_id")))
                    return self.responder({"sucesso":True,"movimento_id":mid})

                if path == "/api/comandas/criar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    num = gerar_numero_comanda()
                    cur.execute("INSERT INTO comandas (numero,cliente_nome,funcionario_entrada) VALUES (%s,%s,%s) RETURNING id",
                        (num, dados.get("cliente_nome",""), u["matricula"]))
                    return self.responder({"sucesso":True,"comanda_id":cur.fetchone()['id'],"numero":num})

                if path == "/api/comandas/adicionar-item":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    qty = numero_float(dados.get("qty"),1); up = numero_float(dados.get("unit_price"),0)
                    cur.execute("""INSERT INTO comanda_itens (comanda_id,product_id,produto_nome,sku,qty,unit_price,total,funcionario_matricula)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("comanda_id"), dados.get("product_id"), dados.get("produto_nome"),
                         dados.get("sku"), qty, up, qty*up, u["matricula"]))
                    atualizar_total_comanda(cur, dados.get("comanda_id"))
                    return self.responder({"sucesso":True,"item_id":ultimo_id(cur)})

                if path == "/api/autorizacoes/decidir":
                    u = usuario_do_corpo(cur, dados)
                    if not u or not pode_autorizar(u): return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("UPDATE autorizacoes SET status=%s,aprovado_por=%s,decidido_em=NOW() WHERE id=%s",
                        (dados.get("decisao","APROVADO"), u["matricula"], dados.get("autorizacao_id")))
                    return self.responder({"sucesso":True})

                if path == "/api/rh/ponto/registrar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("""INSERT INTO rh_ponto (funcionario_matricula,data,entrada,saida,pausa_min,horas_trabalhadas,horas_extras,observacao,registrado_por)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("funcionario_matricula"), dados.get("data"), dados.get("entrada"), dados.get("saida"),
                         numero_float(dados.get("pausa_min"),0), numero_float(dados.get("horas_trabalhadas"),0),
                         numero_float(dados.get("horas_extras"),0), dados.get("observacao",""), u["matricula"]))
                    return self.responder({"sucesso":True,"ponto_id":ultimo_id(cur)})

                if path == "/api/rh/ferias/registrar":
                    u = usuario_do_corpo(cur, dados)
                    if not u or not pode_gerir_rh(u): return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("INSERT INTO rh_ferias (funcionario_matricula,inicio,fim,dias,observacao) VALUES (%s,%s,%s,%s,%s)",
                        (dados.get("funcionario_matricula"), dados.get("inicio"), dados.get("fim"),
                         numero_float(dados.get("dias"),0), dados.get("observacao","")))
                    return self.responder({"sucesso":True,"ferias_id":ultimo_id(cur)})

                if path == "/api/rh/holerites/criar":
                    u = usuario_do_corpo(cur, dados)
                    if not u or not pode_gerir_rh(u): return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("""INSERT INTO rh_holerites (funcionario_matricula,competencia,salario_base,horas_extras_valor,premios,plr,descontos,inss,fgts,liquido,criado_por)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("funcionario_matricula"), dados.get("competencia"),
                         numero_float(dados.get("salario_base"),0), numero_float(dados.get("horas_extras_valor"),0),
                         numero_float(dados.get("premios"),0), numero_float(dados.get("plr"),0),
                         numero_float(dados.get("descontos"),0), numero_float(dados.get("inss"),0),
                         numero_float(dados.get("fgts"),0), numero_float(dados.get("liquido"),0), u["matricula"]))
                    return self.responder({"sucesso":True,"holerite_id":ultimo_id(cur)})

                if path == "/api/contabilidade/conta/criar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("""INSERT INTO contas_financeiras (tipo,descricao,pessoa,valor,vencimento,status,categoria,observacao)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("tipo","PAGAR"), dados.get("descricao",""), dados.get("pessoa",""),
                         numero_float(dados.get("valor"),0), dados.get("vencimento"),
                         dados.get("status","ABERTO"), dados.get("categoria",""), dados.get("observacao","")))
                    return self.responder({"sucesso":True,"conta_id":ultimo_id(cur)})

                if path == "/api/contabilidade/conta/pagar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("UPDATE contas_financeiras SET status='PAGO',pagamento_data=CURRENT_DATE WHERE id=%s", (dados.get("conta_id"),))
                    return self.responder({"sucesso":True})

                if path == "/api/bancos/movimento/criar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("INSERT INTO banco_movimentos (banco_id,tipo,descricao,valor,data_movimento,origem) VALUES (%s,%s,%s,%s,%s,%s)",
                        (dados.get("banco_id"), dados.get("tipo"), dados.get("descricao",""),
                         numero_float(dados.get("valor"),0), dados.get("data_movimento") or datetime.now().strftime("%Y-%m-%d"),
                         dados.get("origem","MANUAL")))
                    return self.responder({"sucesso":True,"movimento_id":ultimo_id(cur)})

                if path == "/api/logistica/criar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("""INSERT INTO logistica_movimentos (tipo,produto_nome,qty,valor_unitario,valor_total,origem,destino,motorista,placa,observacao,criado_por)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("tipo","ENTREGA"), dados.get("produto_nome",""), numero_float(dados.get("qty"),0),
                         numero_float(dados.get("valor_unitario"),0), numero_float(dados.get("valor_total"),0),
                         dados.get("origem","Padaria"), dados.get("destino",""), dados.get("motorista",""),
                         dados.get("placa",""), dados.get("observacao",""), u["matricula"]))
                    return self.responder({"sucesso":True,"logistica_id":ultimo_id(cur)})

                if path == "/api/logistica/concluir":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("UPDATE logistica_movimentos SET status='CONCLUIDO',concluido_at=NOW() WHERE id=%s", (dados.get("logistica_id"),))
                    return self.responder({"sucesso":True})

                if path == "/api/site/pedido/criar":
                    cur.execute("""INSERT INTO site_pedidos (cliente_nome,telefone,entrega_endereco,forma_pagamento,subtotal,taxa_entrega,taxa_pagamento,total,status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'SOLICITADO') RETURNING id""",
                        (dados.get("cliente_nome"), dados.get("telefone"), dados.get("entrega_endereco"),
                         dados.get("forma_pagamento"), numero_float(dados.get("subtotal"),0),
                         numero_float(dados.get("taxa_entrega"),0), numero_float(dados.get("taxa_pagamento"),0),
                         numero_float(dados.get("total"),0)))
                    pid = cur.fetchone()['id']
                    for item in dados.get("itens", []):
                        qty = numero_float(item.get("qty"),1); up = numero_float(item.get("unit_price"),0)
                        cur.execute("INSERT INTO site_pedido_itens (pedido_id,product_id,produto_nome,sku,qty,unit_price,total) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (pid, item.get("product_id"), item.get("produto_nome"), item.get("sku"), qty, up, qty*up))
                    return self.responder({"sucesso":True,"pedido_id":pid})

                if path == "/api/site/pedido/status":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("UPDATE site_pedidos SET status=%s WHERE id=%s", (dados.get("status"), dados.get("pedido_id")))
                    return self.responder({"sucesso":True})

                if path == "/api/produtos/salvar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    pid = dados.get("id")
                    if pid:
                        cur.execute("UPDATE produtos SET nome=%s,sku=%s,categoria=%s,preco_venda=%s,custo=%s,estoque_minimo=%s,status=%s WHERE id=%s",
                            (dados.get("nome"), dados.get("sku"), dados.get("categoria"),
                             numero_float(dados.get("preco_venda"),0), numero_float(dados.get("custo"),0),
                             numero_float(dados.get("estoque_minimo"),0), dados.get("status","ATIVO"), pid))
                    else:
                        cur.execute("INSERT INTO produtos (nome,sku,categoria,preco_venda,custo,estoque_minimo,status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (dados.get("nome"), dados.get("sku"), dados.get("categoria"),
                             numero_float(dados.get("preco_venda"),0), numero_float(dados.get("custo"),0),
                             numero_float(dados.get("estoque_minimo"),0), dados.get("status","ATIVO")))
                    return self.responder({"sucesso":True})

                if path == "/api/clientes/salvar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cid = dados.get("id")
                    if cid:
                        cur.execute("UPDATE clientes SET nome=%s,cpf_cnpj=%s,telefone=%s,email=%s,endereco=%s WHERE id=%s",
                            (dados.get("nome"), dados.get("cpf_cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco"), cid))
                    else:
                        cur.execute("INSERT INTO clientes (nome,cpf_cnpj,telefone,email,endereco) VALUES (%s,%s,%s,%s,%s)",
                            (dados.get("nome"), dados.get("cpf_cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco")))
                    return self.responder({"sucesso":True})

                if path == "/api/fornecedores/salvar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    fid = dados.get("id")
                    if fid:
                        cur.execute("UPDATE fornecedores SET nome=%s,cnpj=%s,telefone=%s,email=%s,endereco=%s WHERE id=%s",
                            (dados.get("nome"), dados.get("cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco"), fid))
                    else:
                        cur.execute("INSERT INTO fornecedores (nome,cnpj,telefone,email,endereco) VALUES (%s,%s,%s,%s,%s)",
                            (dados.get("nome"), dados.get("cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco")))
                    return self.responder({"sucesso":True})

                if path == "/api/funcionarios/salvar":
                    u = usuario_do_corpo(cur, dados)
                    if not u or u.get("role") not in ("admin","gerente"): return self.responder({"erro":"Sem permissão"}, 403)
                    fid = dados.get("id"); mat = dados.get("matricula")
                    perm = dados.get("permissoes", MODULOS_PADRAO)
                    if isinstance(perm, list): perm = json.dumps(perm, ensure_ascii=False)
                    senha = dados.get("senha")
                    if fid:
                        if senha:
                            cur.execute("UPDATE funcionarios SET nome=%s,cargo=%s,role=%s,permissoes=%s,status=%s,senha_hash=%s WHERE id=%s",
                                (dados.get("nome"), dados.get("cargo"), dados.get("role","operador"), perm,
                                 dados.get("status","ATIVO"), hash_senha(senha), fid))
                        else:
                            cur.execute("UPDATE funcionarios SET nome=%s,cargo=%s,role=%s,permissoes=%s,status=%s WHERE id=%s",
                                (dados.get("nome"), dados.get("cargo"), dados.get("role","operador"), perm, dados.get("status","ATIVO"), fid))
                    else:
                        cur.execute("SELECT id FROM funcionarios WHERE matricula=%s LIMIT 1", (mat,))
                        if cur.fetchone(): return self.responder({"erro":"Matrícula já cadastrada"}, 400)
                        cur.execute("INSERT INTO funcionarios (matricula,nome,cargo,role,senha_hash,permissoes,status) VALUES (%s,%s,%s,%s,%s,%s,'ATIVO')",
                            (mat, dados.get("nome"), dados.get("cargo"), dados.get("role","operador"), hash_senha(senha or "123"), perm))
                    return self.responder({"sucesso":True})

                if path == "/api/site/config/salvar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("UPDATE site_config_grid SET valor=%s,ativo=%s WHERE id=%s",
                        (dados.get("valor"), normalizar_bool(dados.get("ativo")), dados.get("id")))
                    return self.responder({"sucesso":True})

                if path == "/api/site/config-grid/atualizar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    secao = dados.get("secao","bot_geral"); nome = dados.get("nome"); valor = dados.get("valor","")
                    cur.execute("SELECT id FROM site_config_grid WHERE secao=%s AND nome=%s LIMIT 1", (secao, nome))
                    ex = cur.fetchone()
                    if ex:
                        cur.execute("UPDATE site_config_grid SET valor=%s WHERE id=%s", (valor, ex["id"]))
                    else:
                        cur.execute("INSERT INTO site_config_grid (secao,nome,valor,tipo) VALUES (%s,%s,%s,'texto')", (secao, nome, valor))
                    return self.responder({"sucesso":True})

                # ===== GRID 1: Bot =====
                if path == "/api/bot/config":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    for chave, valor in dados.items():
                        if chave in ("usuario","matricula","operator_matricula"): continue
                        cur.execute("SELECT id FROM site_config_grid WHERE secao='bot_geral' AND nome=%s LIMIT 1", (chave,))
                        ex = cur.fetchone()
                        if ex:
                            cur.execute("UPDATE site_config_grid SET valor=%s WHERE id=%s", (str(valor), ex["id"]))
                        else:
                            cur.execute("INSERT INTO site_config_grid (secao,nome,valor,tipo,ordem) VALUES ('bot_geral',%s,%s,'texto',0)", (chave, str(valor)))
                    return self.responder({"sucesso":True})

                if path == "/api/bot/regras":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    rid = dados.get("id")
                    if rid:
                        cur.execute("UPDATE site_config_grid SET nome=%s,valor=%s,dados_ref=%s WHERE id=%s",
                            (dados.get("palavras_chave"), dados.get("resposta"), dados.get("acao"), rid))
                    else:
                        cur.execute("INSERT INTO site_config_grid (secao,nome,valor,tipo,dados_ref,ordem) VALUES ('bot_regras',%s,%s,'regra_bot',%s,0)",
                            (dados.get("palavras_chave",""), dados.get("resposta",""), dados.get("acao","")))
                    return self.responder({"sucesso":True})

                if path == "/api/bot/regras/excluir":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("DELETE FROM site_config_grid WHERE id=%s AND secao='bot_regras'", (dados.get("id"),))
                    return self.responder({"sucesso":True})

                if path == "/api/bot/responder":
                    msg = (dados.get("mensagem") or "").lower()
                    cur.execute("SELECT * FROM site_config_grid WHERE secao='bot_regras' AND ativo=TRUE")
                    regras = [dict(r) for r in (cur.fetchall() or [])]
                    for r in regras:
                        kws = (r.get("nome") or "").lower().split("|")
                        if any(k.strip() in msg for k in kws if k.strip()):
                            return self.responder({"resposta": r.get("valor") or "Entendi!", "acao": r.get("dados_ref") or ""})
                    cur.execute("SELECT valor FROM site_config_grid WHERE secao='bot_geral' AND nome='saudacao' LIMIT 1")
                    saud = (cur.fetchone() or {}).get("valor","Olá! Como posso ajudar?")
                    if any(p in msg for p in ["oi","ola","olá","bom dia","boa tarde","boa noite","hello"]):
                        return self.responder({"resposta": saud, "acao": "saudacao"})
                    if any(p in msg for p in ["preco","preço","valor","quanto","custa"]):
                        cur.execute("SELECT nome, preco_venda FROM produtos WHERE status='ATIVO' ORDER BY preco_venda LIMIT 5")
                        prods = [dict(r) for r in (cur.fetchall() or [])]
                        txt = "Nossos preços:\n" + "\n".join(f"- {p['nome']}: R$ {float(p['preco_venda']):.2f}" for p in prods)
                        return self.responder({"resposta": txt, "acao": "lista_precos", "produtos": prods})
                    if any(p in msg for p in ["horario","horário","abre","fecha","funcionamento"]):
                        cur.execute("SELECT valor FROM site_config_grid WHERE secao='bot_geral' AND nome='horario_atendimento' LIMIT 1")
                        h = (cur.fetchone() or {}).get("valor","Seg-Sáb 6h às 20h")
                        return self.responder({"resposta": f"Funcionamos: {h}", "acao": "horario"})
                    if any(p in msg for p in ["endereco","endereço","onde","localiza","fica"]):
                        cur.execute("SELECT valor FROM site_config_grid WHERE secao='bot_geral' AND nome='endereco' LIMIT 1")
                        e = (cur.fetchone() or {}).get("valor","Rua das Flores, 123")
                        return self.responder({"resposta": f"Estamos em: {e}", "acao": "endereco"})
                    if any(p in msg for p in ["pedido","comprar","quero","encomendar","fazer pedido"]):
                        cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 4")
                        rec = [dict(r) for r in (cur.fetchall() or [])]
                        return self.responder({"resposta":"Claro! Posso te ajudar a fazer um pedido. Veja algumas opções:", "acao":"iniciar_pedido","produtos":rec})
                    if any(p in msg for p in ["obrigado","obrigada","valeu","agradeço","agradeco"]):
                        return self.responder({"resposta":"De nada! Volte sempre!", "acao": "despedida"})
                    return self.responder({"resposta":"Desculpe, não entendi. Posso te ajudar com preços, horários, endereço ou fazer um pedido!", "acao":"default"})

                # ===== GRID 3: IA Vendas =====
                if path == "/api/ia-vendas/chat":
                    msg = (dados.get("mensagem") or "").lower()
                    if dados.get("acao") == "finalizar":
                        return self.responder({"resposta":"Pedido finalizado! Em breve entraremos em contato.","acao":"pedido_finalizado"})
                    if any(p in msg for p in ["recomenda","sugest","promo","oferta","combo","pacote"]):
                        cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 4")
                        rec = [dict(r) for r in (cur.fetchall() or [])]
                        return self.responder({"resposta":"Temos estas delícias em destaque hoje:", "acao":"recomendar","produtos":rec})
                    if any(p in msg for p in ["combo","kit","promocao","promoção"]):
                        return self.responder({"resposta":"Combo Família: 10 pães + 2 cafés + 1 bolo por R$ 49,90! Aproveite!", "acao":"combo"})
                    if any(p in msg for p in ["oi","ola","olá","bom dia","boa tarde","boa noite"]):
                        return self.responder({"resposta":"Olá! Sou a IA de Vendas da Padaria. Quer ver nossas delícias ou montar um pedido?","acao":"saudacao"})
                    cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 6")
                    return self.responder({"resposta":"Veja nossos produtos disponíveis:", "acao":"lista_produtos", "produtos": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/ia-vendas/salvar-pedido":
                    cur.execute("""INSERT INTO site_pedidos (cliente_nome,telefone,entrega_endereco,forma_pagamento,subtotal,total,status)
                        VALUES (%s,%s,%s,%s,%s,%s,'CONFIRMADO') RETURNING id""",
                        (dados.get("cliente_nome","Cliente IA"), dados.get("telefone",""),
                         dados.get("entrega_endereco",""), dados.get("forma_pagamento","PIX"),
                         numero_float(dados.get("subtotal"),0), numero_float(dados.get("total"),0)))
                    pid = cur.fetchone()['id']
                    for item in dados.get("itens", []):
                        qty = numero_float(item.get("qty"),1); up = numero_float(item.get("unit_price"),0)
                        cur.execute("INSERT INTO site_pedido_itens (pedido_id,product_id,produto_nome,sku,qty,unit_price,total) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (pid, item.get("product_id"), item.get("produto_nome"), item.get("sku"), qty, up, qty*up))
                        registrar_wms_movimento(cur, item, "SAIDA", "IA_VENDAS", f"PEDIDO-{pid}", "IA-VENDAS")
                        cur.execute("UPDATE wms_estoque SET qty=qty-%s WHERE product_id=%s", (qty, item.get("product_id")))
                    return self.responder({"sucesso":True,"pedido_id":pid})

                if path == "/api/integracao/ifood/configurar":
                    u = usuario_do_corpo(cur, dados)
                    if not u: return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("SELECT id FROM integracoes_ifood LIMIT 1")
                    ex = cur.fetchone()
                    if ex:
                        cur.execute("UPDATE integracoes_ifood SET merchant_id=%s,client_id=%s,client_secret=%s,ambiente=%s,status=%s,updated_at=NOW() WHERE id=%s",
                            (dados.get("merchant_id"), dados.get("client_id"), dados.get("client_secret"),
                             dados.get("ambiente","sandbox"), dados.get("status","INATIVO"), ex["id"]))
                    else:
                        cur.execute("INSERT INTO integracoes_ifood (merchant_id,client_id,client_secret,ambiente,status) VALUES (%s,%s,%s,%s,%s)",
                            (dados.get("merchant_id"), dados.get("client_id"), dados.get("client_secret"),
                             dados.get("ambiente","sandbox"), dados.get("status","INATIVO")))
                    return self.responder({"sucesso":True})

                return self.responder({"erro":"Ação não implementada: "+path}, 404)
        except Exception as e:
            return self.responder({"erro": str(e)}, 500)


def main():
    garantir_schema()
    porta = int(os.environ.get("PORT", 8080))
    servidor = HTTPServer(("0.0.0.0", porta), APIHandler)
    print(f"="*50, flush=True)
    print(f" Servidor Panificadora (SUPABASE) rodando na porta {porta}", flush=True)
    print(f" Banco: {os.environ.get('DB_NAME','postgres')} @ {os.environ.get('DB_HOST','localhost')}", flush=True)
    print(f" Login padrão: AP-2026-0001 / 123", flush=True)
    print(f"="*50, flush=True)
    servidor.serve_forever()

if __name__ == "__main__":
    main()
