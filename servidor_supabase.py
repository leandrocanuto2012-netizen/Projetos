import os
import json
import hashlib
import psycopg2
import psycopg2.extras
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

load_dotenv()

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

def hash_senha(s):
    return hashlib.sha256(str(s or "").encode()).hexdigest()

def garantir_schema():
    with DBConnection() as (conn, cur):
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
        cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
        if not cur.fetchone():
            cur.execute("""INSERT INTO funcionarios 
                (matricula, nome, cargo, role, senha_hash, permissoes, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                ("AP-2026-0001", "Administrador", "Gerente", "admin",
                 hash_senha("123"), '["dashboard","produtos","clientes"]', "ATIVO"))
        conn.commit()
    print("✅ Banco pronto!", flush=True)

class APIHandler(BaseHTTPRequestHandler):
    def set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        arquivos = {
            "/": ("dashboard.html", "text/html; charset=utf-8"),
            "/dashboard": ("dashboard.html", "text/html; charset=utf-8"),
            "/dashboard.html": ("dashboard.html", "text/html; charset=utf-8"),
        }
        if path in arquivos:
            nome_arq, ctype = arquivos[path]
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                caminho = os.path.join(base, nome_arq)
                with open(caminho, "rb") as f:
                    conteudo = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(conteudo)
            except FileNotFoundError:
                self.responder({"erro": f"Arquivo {nome_arq} não encontrado"}, 404)
            return

        try:
            with DBConnection() as (conn, cur):
                if path == "/api/health":
                    cur.execute("SELECT 1")
                    return self.responder({"status": "ok"})
                if path == "/api/produtos":
                    cur.execute("SELECT * FROM produtos ORDER BY id DESC LIMIT 100")
                    return self.responder({"produtos": [dict(r) for r in cur.fetchall() or []]})
                if path == "/api/clientes":
                    cur.execute("SELECT * FROM clientes ORDER BY id DESC LIMIT 100")
                    return self.responder({"clientes": [dict(r) for r in cur.fetchall() or []]})
            self.responder({"erro": "Rota não encontrada"}, 404)
        except Exception as e:
            print(f"Erro GET: {e}", flush=True)
            self.responder({"erro": str(e)}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        dados = self.get_body()

        try:
            with DBConnection() as (conn, cur):
                if path == "/api/login":
                    mat = dados.get("matricula", "").strip()
                    senha = dados.get("senha", "").strip()
                    cur.execute("SELECT * FROM funcionarios WHERE matricula=%s AND status='ATIVO' LIMIT 1", (mat,))
                    u = cur.fetchone()
                    if u and u.get("senha_hash") == hash_senha(senha):
                        return self.responder({"sucesso": True, "usuario": dict(u)})
                    return self.responder({"sucesso": False, "erro": "Matrícula ou senha inválida"})
            self.responder({"erro": "Rota não encontrada"}, 404)
        except Exception as e:
            print(f"Erro POST: {e}", flush=True)
            self.responder({"erro": str(e)}, 500)

def run(port=8080):
    garantir_schema()
    server = HTTPServer(('0.0.0.0'), port, APIHandler)
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
