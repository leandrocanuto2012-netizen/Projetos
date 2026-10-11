import os
import json
import hashlib
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ====== CONEXÃO BANCO ======
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

# ====== FUNÇÕES UTILITÁRIAS ======
def numero_float(valor, padrao=0.0):
    try:
        return float(valor) if valor not in (None, "") else padrao
    except (ValueError, TypeError):
        return padrao

def hash_senha(s):
    return hashlib.sha256(str(s or "").encode()).hexdigest()

def extrair_id(path):
    """Extrai o ID do final da URL com segurança"""
    partes = path.rstrip('/').split('/')
    return partes[-1] if partes and partes[-1].isdigit() else None

# ====== CRIAÇÃO DAS TABELAS ======
def garantir_schema():
    with DBConnection() as (conn, cur):
        # Funcionários
        cur.execute("""CREATE TABLE IF NOT EXISTS funcionarios (
            id SERIAL PRIMARY KEY,
            matricula VARCHAR(20) UNIQUE NOT NULL,
            nome VARCHAR(100) NOT NULL,
            cargo VARCHAR(100),
            role VARCHAR(20) DEFAULT 'operador',
            senha_hash VARCHAR(255) NOT NULL,
            permissoes TEXT DEFAULT '[]',
            status VARCHAR(20) DEFAULT 'ATIVO',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Produtos
        cur.execute("""CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(200) NOT NULL,
            categoria VARCHAR(100),
            unidade VARCHAR(10) DEFAULT 'UN',
            preco_custo DECIMAL(12,2) DEFAULT 0,
            preco_venda DECIMAL(12,2) DEFAULT 0,
            estoque_minimo DECIMAL(12,2) DEFAULT 0,
            estoque_atual DECIMAL(12,2) DEFAULT 0,
            ativo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Clientes
        cur.execute("""CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(150) NOT NULL,
            documento VARCHAR(20),
            telefone VARCHAR(20),
            email VARCHAR(150),
            endereco TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Fornecedores
        cur.execute("""CREATE TABLE IF NOT EXISTS fornecedores (
            id SERIAL PRIMARY KEY,
            razao_social VARCHAR(200) NOT NULL,
            cnpj VARCHAR(20),
            telefone VARCHAR(20),
            email VARCHAR(150),
            endereco TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Ponto
        cur.execute("""CREATE TABLE IF NOT EXISTS registros_ponto (
            id SERIAL PRIMARY KEY,
            funcionario_id INTEGER NOT NULL,
            tipo VARCHAR(10) NOT NULL,
            data_hora TIMESTAMP NOT NULL,
            observacao TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Caixa
        cur.execute("""CREATE TABLE IF NOT EXISTS caixas (
            id SERIAL PRIMARY KEY,
            funcionario_id INTEGER NOT NULL,
            valor_inicial DECIMAL(12,2) DEFAULT 0,
            valor_final DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(20) DEFAULT 'ABERTO',
            data_abertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_fechamento TIMESTAMP
        )""")

        # Movimentos de Caixa
        cur.execute("""CREATE TABLE IF NOT EXISTS movimentos_caixa (
            id SERIAL PRIMARY KEY,
            caixa_id INTEGER NOT NULL,
            tipo VARCHAR(20) NOT NULL,
            valor DECIMAL(12,2) NOT NULL,
            descricao TEXT,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Vendas
        cur.execute("""CREATE TABLE IF NOT EXISTS vendas (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER,
            funcionario_id INTEGER NOT NULL,
            caixa_id INTEGER NOT NULL,
            valor_total DECIMAL(12,2) NOT NULL,
            forma_pagamento VARCHAR(50),
            status VARCHAR(20) DEFAULT 'CONCLUIDA',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Itens da Venda
        cur.execute("""CREATE TABLE IF NOT EXISTS venda_itens (
            id SERIAL PRIMARY KEY,
            venda_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade DECIMAL(12,2) NOT NULL,
            valor_unitario DECIMAL(12,2) NOT NULL,
            valor_total DECIMAL(12,2) NOT NULL
        )""")

        # Contas Financeiras
        cur.execute("""CREATE TABLE IF NOT EXISTS contas_financeiras (
            id SERIAL PRIMARY KEY,
            descricao VARCHAR(255) NOT NULL,
            tipo VARCHAR(20) NOT NULL,
            categoria VARCHAR(100),
            valor DECIMAL(12,2) NOT NULL,
            data_vencimento DATE NOT NULL,
            status VARCHAR(20) DEFAULT 'ABERTO',
            valor_pago DECIMAL(12,2) DEFAULT 0,
            data_pagamento DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Inserir usuário admin padrão
        cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
        if not cur.fetchone():
            cur.execute("""INSERT INTO funcionarios 
                (matricula, nome, cargo, role, senha_hash, permissoes, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                ("AP-2026-0001", "Administrador", "Gerente", "admin",
                 hash_senha("123"), '["dashboard","produtos","clientes","caixa","ponto","financeiro"]', "ATIVO"))

        conn.commit()
    print("✅ Banco pronto!", flush=True)

# ====== HANDLER DA API ======
class APIHandler(BaseHTTPRequestHandler):
    def set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def get_body(self):
        tam = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tam)
        try:
            return json.loads(corpo) if tam else {}
        except:
            return {}

    def responder(self, dados, status=200):
        self.set_headers(status)
        self.wfile.write(json.dumps(dados, default=str, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}", flush=True)

    # ====== SERVIR ARQUIVOS ESTÁTICOS ======
    def serve_static(self, path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        public_dir = os.path.join(base_dir, "public")
        
        if path == "/":
            path = "/index.html"
        
        ext = os.path.splitext(path)[1].lower()
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon"
        }
        ctype = content_types.get(ext, "application/octet-stream")
        
        caminho = os.path.join(public_dir, path.lstrip("/"))
        
        try:
            with open(caminho, "rb") as f:
                conteudo = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(conteudo)
            return True
        except FileNotFoundError:
            return False

    # ====== ROTAS GET ======
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Tentar servir arquivo estático
        if self.serve_static(path):
            return

        try:
            with DBConnection() as (conn, cur):
                # Health Check
                if path == "/api/health":
                    cur.execute("SELECT 1")
                    return self.responder({"status": "ok", "horario": datetime.now().isoformat()})

                # Produtos
                if path == "/api/produtos":
                    cur.execute("SELECT * FROM produtos ORDER BY id DESC LIMIT 100")
                    return self.responder({"produtos": [dict(r) for r in cur.fetchall() or []]})

                # Clientes
                if path == "/api/clientes":
                    cur.execute("SELECT * FROM clientes ORDER BY id DESC LIMIT 100")
                    return self.responder({"clientes": [dict(r) for r in cur.fetchall() or []]})

                # Fornecedores
                if path == "/api/fornecedores":
                    cur.execute("SELECT * FROM fornecedores ORDER BY id DESC LIMIT 100")
                    return self.responder({"fornecedores": [dict(r) for r in cur.fetchall() or []]})

                # Funcionários
                if path == "/api/funcionarios":
                    cur.execute("SELECT id, matricula, nome, cargo, role, status, created_at FROM funcionarios ORDER BY nome")
                    return self.responder({"funcionarios": [dict(r) for r in cur.fetchall() or []]})

                # Ponto - registros
                if path == "/api/ponto/registros":
                    cur.execute("""
                        SELECT rp.*, f.nome as funcionario_nome 
                        FROM registros_ponto rp
                        JOIN funcionarios f ON rp.funcionario_id = f.id
                        ORDER BY rp.data_hora DESC LIMIT 100
                    """)
                    return self.responder({"registros": [dict(r) for r in cur.fetchall() or []]})

                # Caixa - status
                if path == "/api/caixa/status":
                    cur.execute("SELECT * FROM caixas WHERE status='ABERTO' ORDER BY id DESC LIMIT 1")
                    caixa = cur.fetchone()
                    return self.responder({"caixa": dict(caixa) if caixa else None})

                # Movimentos do caixa
                if path == "/api/caixa/movimentos":
                    caixa_id = parse_qs(parsed.query).get("caixa_id", [None])[0]
                    if caixa_id:
                        cur.execute("SELECT * FROM movimentos_caixa WHERE caixa_id = %s ORDER BY id", (caixa_id,))
                        movs = cur.fetchall() or []
                    else:
                        movs = []
                    return self.responder({"movimentos": [dict(r) for r in movs]})

                # Vendas
                if path == "/api/vendas":
                    cur.execute("""
                        SELECT v.*, f.nome as funcionario_nome, c.nome as cliente_nome
                        FROM vendas v
                        LEFT JOIN funcionarios f ON v.funcionario_id = f.id
                        LEFT JOIN clientes c ON v.cliente_id = c.id
                        ORDER BY v.id DESC LIMIT 50
                    """)
                    return self.responder({"vendas": [dict(r) for r in cur.fetchall() or []]})

                # Contas Financeiras
                if path == "/api/contas":
                    cur.execute("SELECT * FROM contas_financeiras ORDER BY data_vencimento")
                    return self.responder({"contas": [dict(r) for r in cur.fetchall() or []]})

                # Resumo Contábil
                if path == "/api/contabilidade/resumo":
                    cur.execute("SELECT status, COUNT(*) AS qtd, SUM(valor) AS total FROM contas_financeiras GROUP BY status")
                    por_status = cur.fetchall() or []
                    
                    cur.execute("SELECT tipo, SUM(valor) AS total FROM contas_financeiras WHERE status='PAGO' GROUP BY tipo")
                    totais = {r["tipo"]: r["total"] for r in cur.fetchall() or []}
                    receitas = numero_float(totais.get("RECEITA", 0))
                    despesas = numero_float(totais.get("DESPESA", 0))
                    
                    return self.responder({
                        "por_status": [dict(r) for r in por_status],
                        "receitas_total": receitas,
                        "despesas_total": despesas,
                        "saldo": receitas - despesas
                    })

                self.responder({"erro": "Rota não encontrada"}, 404)
            return
        except Exception as e:
            print(f"❌ Erro GET: {e}", flush=True)
            self.responder({"erro": str(e)}, 500)

    # ====== ROTAS POST ======
    def do_POST(self):
        path = urlparse(self.path).path
        dados = self.get_body()

        try:
            with DBConnection() as (conn, cur):
                # Login
                if path == "/api/login":
                    mat = dados.get("matricula", "").strip()
                    senha = dados.get("senha", "").strip()
                    cur.execute("SELECT * FROM funcionarios WHERE matricula=%s AND status='ATIVO' LIMIT 1", (mat,))
                    u = cur.fetchone()
                    if u and u.get("senha_hash") == hash_senha(senha):
                        return self.responder({"sucesso": True, "usuario": dict(u)})
                    return self.responder({"sucesso": False, "erro": "Matrícula ou senha inválida"})

                # Bater Ponto
                if path == "/api/ponto/bater":
                    funcionario_id = dados.get("funcionario_id")
                    tipo = dados.get("tipo")
                    data_hora = dados.get("data_hora") or datetime.now().isoformat()
                    observacao = dados.get("observacao", "")
                    
                    if not funcionario_id or tipo not in ("ENTRADA", "SAÍDA", "SAIDA"):
                        return self.responder({"erro": "Dados inválidos"}, 400)
                    
                    cur.execute("""INSERT INTO registros_ponto 
                        (funcionario_id, tipo, data_hora, observacao)
                        VALUES (%s, %s, %s, %s) RETURNING id""",
                        (funcionario_id, tipo.upper(), data_hora, observacao))
                    reg_id = cur.fetchone()["id"]
                    conn.commit()
                    return self.responder({"sucesso": True, "id": reg_id, "mensagem": f"{tipo} registrado com sucesso"})

                # Abrir Caixa
                if path == "/api/caixa/abrir":
                    funcionario_id = dados.get("funcionario_id")
                    valor_inicial = numero_float(dados.get("valor_inicial", 0))
                    
                    if not funcionario_id:
                        return self.responder({"erro": "Funcionário obrigatório"}, 400)
                    
                    # Verificar se já há caixa aberto
                    cur.execute("SELECT id FROM caixas WHERE status='ABERTO' LIMIT 1")
                    if cur.fetchone():
                        return self.responder({"erro": "Já existe um caixa aberto"}, 400)
                    
                    cur.execute("""INSERT INTO caixas (funcionario_id, valor_inicial, status)
                        VALUES (%s, %s, 'ABERTO') RETURNING id""",
                        (funcionario_id, valor_inicial))
                    caixa_id = cur.fetchone()["id"]
                    
                    cur.execute("""INSERT INTO movimentos_caixa (caixa_id, tipo, valor, descricao)
                        VALUES (%s, 'ABERTURA', %s, 'Valor inicial')""",
                        (caixa_id, valor_inicial))
                    
                    conn.commit()
                    return self.responder({"sucesso": True, "caixa_id": caixa_id})

                # Fechar Caixa
                if path == "/api/caixa/fechar":
                    caixa_id = dados.get("caixa_id")
                    valor_final = numero_float(dados.get("valor_final", 0))
                    
                    cur.execute("SELECT * FROM caixas WHERE id = %s AND status='ABERTO'", (caixa_id,))
                    if not cur.fetchone():
                        return self.responder({"erro": "Caixa aberto não encontrado"}, 404)
                    
                    cur.execute("""UPDATE caixas 
                        SET status='FECHADO', valor_final=%s, data_fechamento=%s
                        WHERE id=%s""",
                        (valor_final, datetime.now().isoformat(), caixa_id))
                    
                    cur.execute("""INSERT INTO movimentos_caixa (caixa_id, tipo, valor, descricao)
                        VALUES (%s, 'FECHAMENTO', %s, 'Fechamento do caixa')""",
                        (caixa_id, valor_final))
                    
                    conn.commit()
                    return self.responder({"sucesso": True, "mensagem": "Caixa fechado com sucesso"})

                # Cadastrar Produto
                if path == "/api/produtos/criar":
                    nome = dados.get("nome")
                    if not nome:
                        return self.responder({"erro": "Nome é obrigatório"}, 400)
                    
                    cur.execute("""INSERT INTO produtos 
                        (nome, categoria, unidade, preco_custo, preco_venda, estoque_minimo, estoque_atual)
                        VALUES (%s, %s, %s, %s, %s, %s, 0) RETURNING id""",
                        (nome, dados.get("categoria"), dados.get("unidade", "UN"),
                         numero_float(dados.get("preco_custo")),
                         numero_float(dados.get("preco_venda")),
                         numero_float(dados.get("estoque_minimo", 0))))
                    pid = cur.fetchone()["id"]
                    conn.commit()
                    return self.responder({"sucesso": True, "id": pid})

                # Editar Produto
                if path.startswith("/api/produtos/editar/"):
                    pid = extrair_id(path)
                    if not pid:
                        return self.responder({"erro": "ID inválido"}, 400)
                    
                    cur.execute("""UPDATE produtos SET
                        nome=%s, categoria=%s, unidade=%s, preco_custo=%s, 
                        preco_venda=%s, estoque_minimo=%s, estoque_atual=%s
                        WHERE id=%s""",
                        (dados.get("nome"), dados.get("categoria"), dados.get("unidade", "UN"),
                         numero_float(dados.get("preco_custo")), numero_float(dados.get("preco_venda")),
                         numero_float(dados.get("estoque_minimo", 0)), numero_float(dados.get("estoque_atual", 0)), pid))
                    conn.commit()
                    return self.responder({"sucesso": True})

                # Excluir Produto
                if path.startswith("/api/produtos/excluir/"):
                    pid = extrair_id(path)
                    if not pid:
                        return self.responder({"erro": "ID inválido"}, 400)
                    cur.execute("DELETE FROM produtos WHERE id = %s", (pid,))
                    conn.commit()
                    return self.responder({"sucesso": True})

                # Cadastrar Cliente
                if path == "/api/clientes/criar":
                    nome = dados.get("nome")
                    if not nome:
                        return self.responder({"erro": "Nome é obrigatório"}, 400)
                    
                    cur.execute("""INSERT INTO clientes (nome, documento, telefone, email, endereco)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (nome, dados.get("documento"), dados.get("telefone"),
                         dados.get("email"), dados.get("endereco")))
                    cid = cur.fetchone()["id"]
                    conn.commit()
                    return self.responder({"sucesso": True, "id": cid})

                # Cadastrar Fornecedor
                if path == "/api/fornecedores/criar":
                    razao_social = dados.get("razao_social")
                    if not razao_social:
                        return self.responder({"erro": "Razão social é obrigatória"}, 400)
                    
                    cur.execute("""INSERT INTO fornecedores (razao_social, cnpj, telefone, email, endereco)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (razao_social, dados.get("cnpj"), dados.get("telefone"),
                         dados.get("email"), dados.get("endereco")))
                    fid = cur.fetchone()["id"]
                    conn.commit()
                    return self.responder({"sucesso": True, "id": fid})

                # Criar Conta
                if path == "/api/contas/criar":
                    descricao = dados.get("descricao")
                    tipo = dados.get("tipo")
                    valor = numero_float(dados.get("valor"))
                    data_vencimento = dados.get("data_vencimento")
                    
                    if not all([descricao, tipo, valor, data_vencimento]):
                        return self.responder({"erro": "Campos obrigatórios faltando"}, 400)
                    
                    cur.execute("""INSERT INTO contas_financeiras 
                        (descricao, tipo, categoria, valor, data_vencimento, status)
                        VALUES (%s, %s, %s, %s, %s, 'ABERTO') RETURNING id""",
                        (descricao, tipo, dados.get("categoria"), valor, data_vencimento))
                    conta_id = cur.fetchone()["id"]
                    conn.commit()
                    return self.responder({"sucesso": True, "id": conta_id})

                # Pagar Conta
                if path == "/api/contas/pagar":
                    conta_id = dados.get("id")
                    valor_pago = numero_float(dados.get("valor_pago"))
                    data_pagamento = dados.get("data_pagamento") or datetime.now().strftime("%Y-%m-%d")
                    
                    cur.execute("SELECT * FROM contas_financeiras WHERE id = %s", (conta_id,))
                    if not cur.fetchone():
                        return self.responder({"erro": "Conta não encontrada"}, 404)
                    
                    cur.execute("""UPDATE contas_financeiras
                        SET status = 'PAGO', valor_pago = %s, data_pagamento = %s
                        WHERE id = %s""", (valor_pago, data_pagamento, conta_id))
                    conn.commit()
                    return self.responder({"sucesso": True, "mensagem": "Conta paga com sucesso"})

                # Registrar Venda
                if path == "/api/vendas/registrar":
                    venda = dados.get("venda")
                    itens = dados.get("itens", [])
                    
                    if not venda or not itens:
                        return self.responder({"erro": "Dados da venda e itens obrigatórios"}, 400)
                    
                    cur.execute("""INSERT INTO vendas 
                        (cliente_id, funcionario_id, caixa_id, valor_total, forma_pagamento, status)
                        VALUES (%s, %s, %s, %s, %s, 'CONCLUIDA') RETURNING id""",
                        (venda.get("cliente_id"), venda.get("funcionario_id"),
                         venda.get("caixa_id"), numero_float(venda.get("valor_total")),
                         venda.get("forma_pagamento")))
                    venda_id = cur.fetchone()["id"]
                    
                    for item in itens:
                        cur.execute("""INSERT INTO venda_itens 
                            (venda_id, produto_id, quantidade, valor_unitario, valor_total)
                            VALUES (%s, %s, %s, %s, %s)""",
                            (venda_id, item.get("produto_id"), numero_float(item.get("quantidade")),
                             numero_float(item.get("valor_unitario")), numero_float(item.get("valor_total"))))
                    
                    conn.commit()
                    return self.responder({"sucesso": True, "venda_id": venda_id})

                self.responder({"erro": "Rota não encontrada"}, 404)
            return
        except Exception as e:
            print(f"❌ Erro POST: {e}", flush=True)
            self.responder({"erro": str(e)}, 500)

# ====== INICIAR SERVIDOR ======
def run(port=None):
    garantir_schema()
    if not port:
        port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    print(f"🚀 Servidor rodando na porta {port}", flush=True)
    print(f"📍 Acesse: http://localhost:{port}", flush=True)
    print(f"🔑 Login: AP-2026-0001 / 123", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹ Servidor parado", flush=True)
        server.server_close()

if __name__ == "__main__":
    run()