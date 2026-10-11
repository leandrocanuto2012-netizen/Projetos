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

# Conexao Supabase (PostgreSQL)
DATABASE_URI = os.environ.get("DATABASE_URI", "")

def get_conn():
    if DATABASE_URI:
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

def confirmar_senha_usuario(cur, u, dados):
    senha = dados.get("senha_usuario")
    if not u or not senha: return False
    return u.get("senha_hash") == hash_senha(senha)

SENHA_USUARIO_ERRO = {"erro": "Confirme com a sua senha de usuário para continuar", "senha_usuario_necessaria": True}

def validar_senha_adm(cur, senha):
    if not senha: return None
    cur.execute("SELECT * FROM funcionarios WHERE status='ATIVO' AND role IN ('admin','gerente') AND senha_hash=%s LIMIT 1",
                (hash_senha(senha),))
    return cur.fetchone()

def registrar_log_operacao(cur, evento, matricula=None, autorizado_por=None, detalhes=None):
    try:
        cur.execute("INSERT INTO log_operacoes (evento, matricula, autorizado_por, detalhes) VALUES (%s,%s,%s,%s)",
                    (evento, matricula, autorizado_por, json.dumps(detalhes or {}, default=str, ensure_ascii=False)))
    except Exception as e:
        print("Aviso: nao gravou log_operacoes:", e, flush=True)

def garantir_schema():
    with DBConnection() as (conn, cur):
        cur.execute("""CREATE TABLE IF NOT EXISTS log_operacoes (
            id SERIAL PRIMARY KEY,
            evento VARCHAR(80) NOT NULL,
            matricula VARCHAR(20),
            autorizado_por VARCHAR(20),
            detalhes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("ALTER TABLE vendas ADD COLUMN IF NOT EXISTS estornado_por VARCHAR(20)")
        cur.execute("ALTER TABLE vendas ADD COLUMN IF NOT EXISTS estornado_em TIMESTAMP")
        cur.execute("ALTER TABLE vendas ADD COLUMN IF NOT EXISTS motivo_estorno VARCHAR(255)")
        cur.execute("""CREATE TABLE IF NOT EXISTS venda_itens (
            id SERIAL PRIMARY KEY,
            venda_id INT NOT NULL,
            product_id INT,
            produto_nome VARCHAR(200),
            sku VARCHAR(50),
            qty NUMERIC(10,3) DEFAULT 1,
            unit_price NUMERIC(10,2) DEFAULT 0,
            total NUMERIC(12,2) DEFAULT 0
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS produto_receitas (
            id SERIAL PRIMARY KEY,
            produto_id INT NOT NULL,
            insumo_id INT NOT NULL,
            insumo_nome VARCHAR(200),
            quantidade_por_unidade NUMERIC(10,3) NOT NULL DEFAULT 0,
            unidade VARCHAR(10) DEFAULT 'UN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
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
        
        arquivos_staticos = {
            "/": ("site.html", "text/html; charset=utf-8"),
            "/site": ("site.html", "text/html; charset=utf-8"),
            "/site.html": ("site.html", "text/html; charset=utf-8"),
            "/admin": ("dashboard.html", "text/html; charset=utf-8"),
            "/dashboard": ("dashboard.html", "text/html; charset=utf-8"),
            "/dashboard.html": ("dashboard.html", "text/html; charset=utf-8"),
            "/index.html": ("site.html", "text/html; charset=utf-8"),
        }
        if path in arquivos_staticos:
            nome_arq, ctype = arquivos_staticos[path]
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                caminho = None
                for pasta in (os.path.join(base, "public"), base):
                    cand = os.path.join(pasta, nome_arq)
                    if os.path.exists(cand):
                        caminho = cand
                        break
                if caminho is None:
                    raise FileNotFoundError(nome_arq)
                with open(caminho, "rb") as f:
                    conteudo = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(conteudo)
            except FileNotFoundError:
                self.responder({"erro": f"{nome_arq} não encontrado"}, 404)
            return
        
        try:
            with DBConnection() as (conn, cur):
                if path == "/api/health":
                    cur.execute("SELECT 1 as ok"); cur.fetchone()
                    return self.responder({"status":"ok","banco":"supabase conectado"})

                if path == "/api/login":
                    return self.responder({"sucesso":False,"erro":"Use POST para login"}, 405)

                if path == "/api/dashboard/resumo":
                    cur.execute("SELECT COALESCE(SUM(total),0) FROM vendas WHERE data::date = CURRENT_DATE")
                    vendas_hoje = float((cur.fetchone() or {}).get("coalesce", 0))
                    cur.execute("SELECT COUNT(*) FROM wms_estoque WHERE qty <= minimo")
                    estoque_baixo = (cur.fetchone() or {}).get("count", 0)
                    cur.execute("SELECT COUNT(*) FROM site_pedidos WHERE status='PENDENTE'")
                    pedidos_pendentes = (cur.fetchone() or {}).get("count", 0)
                    return self.responder({
                        "vendas_hoje": vendas_hoje,
                        "estoque_baixo": estoque_baixo,
                        "pedidos_pendentes": pedidos_pendentes
                    })

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

                if path == "/api/comandas/abertas":
                    cur.execute("SELECT id,numero,cliente_nome,total FROM comandas WHERE status='ABERTA' ORDER BY entrada_at DESC LIMIT 200")
                    return self.responder({"comandas": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/wms/alertas-estoque":
                    cur.execute("""SELECT p.id, p.nome, p.sku, e.qty as estoque_atual, p.estoque_minimo,
                        CASE WHEN e.qty <= 0 THEN 'CRITICO' WHEN e.qty <= p.estoque_minimo THEN 'BAIXO' ELSE 'OK' END as status_estoque,
                        GREATEST(0, p.estoque_minimo - e.qty) as sugestao_compra
                        FROM produtos p LEFT JOIN wms_estoque e ON p.id = e.product_id
                        WHERE p.estoque_minimo > 0 AND (e.qty IS NULL OR e.qty <= p.estoque_minimo)
                        ORDER BY status_estoque DESC, p.nome""")
                    dados = [dict(r) for r in (cur.fetchall() or [])]
                    return self.responder({"alertas": dados, "total_criticos": len(dados)})

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
                    "/api/bancos": "SELECT * FROM bancos_comerciais ORDER BY id",
                    "/api/formas-pagamento": "SELECT * FROM formas_pagamento_taxas WHERE ativo=TRUE ORDER BY id",
                    "/api/site/pedidos": "SELECT * FROM site_pedidos ORDER BY created_at DESC LIMIT 200",
                }
                if path in GET:
                    cur.execute(GET[path])
                    chave = path.split("/")[-1].replace("-","_")
                    return self.responder({chave: [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/funcionarios":
                    cur.execute("SELECT * FROM funcionarios ORDER BY id DESC LIMIT 100")
                    return self.responder({"funcionarios":[preparar_usuario(r) for r in (cur.fetchall() or [])]})

                if path == "/api/site/config":
                    cur.execute("SELECT * FROM site_config_grid ORDER BY secao, ordem, id")
                    return self.responder({"configuracoes": [dict(r) for r in (cur.fetchall() or [])]})

                self.responder({"erro": "Rota não encontrada", "path": path}, 404)
            return
        except Exception as e:
            print(f"Erro GET {path}: {e}", flush=True)
            self.responder({"erro": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path); path = parsed.path
        dados = self.get_body()
        
        try:
            with DBConnection() as (conn, cur):
                if path == "/api/login":
                    mat = dados.get("matricula","").strip()
                    senha = dados.get("senha","").strip()
                    cur.execute("SELECT * FROM funcionarios WHERE matricula=%s AND status='ATIVO' LIMIT 1", (mat,))
                    u = cur.fetchone()
                    if u and u.get("senha_hash") == hash_senha(senha):
                        return self.responder({"sucesso":True,"usuario":preparar_usuario(u)})
                    return self.responder({"sucesso":False,"erro":"Matrícula ou senha inválida"})

                if path == "/api/site/pedido/status":
                    pid = dados.get("pedido_id")
                    novo_status = dados.get("status")
                    if not pid or not novo_status:
                        return self.responder({"erro":"Dados incompletos"}, 400)
                    cur.execute("UPDATE site_pedidos SET status=%s WHERE id=%s", (novo_status, pid))
                    registrar_log_operacao(cur, f"Pedido {pid} -> {novo_status}", dados.get("usuario",{}).get("matricula"))
                    return self.responder({"sucesso":True})

                self.responder({"erro": "Rota POST não implementada"}, 404)
        except Exception as e:
            print(f"Erro POST {path}: {e}", flush=True)
            self.responder({"erro": str(e)}, 500)


def run(server_class=HTTPServer, handler_class=APIHandler, port=8080):
    garantir_schema()
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"🚀 Servidor rodando na porta {port}", flush=True)
    print(f"📄 Painel: http://localhost:{port}/admin", flush=True)
    print(f"🌐 Site público: http://localhost:{port}/", flush=True)
    print(f"🔑 Login padrão: AP-2026-0001 / 123", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.", flush=True)
        httpd.server_close()

if __name__ == "__main__":
    run()