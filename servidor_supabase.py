# ===== REMENDO AUTOMATICO - cola uma vez, nao mexe em mais nada =====
_orig_get_body = APIHandler.get_body
def _fixed_get_body(self):
    if hasattr(self, '_cached_body'):
        return self._cached_body
    try:
        self._cached_body = _orig_get_body(self)
    except:
        self._cached_body = {}
    return self._cached_body
APIHandler.get_body = _fixed_get_body

def garantir_schema_CORRIGIDO():
    with DBConnection() as (conn, cur):
        cur.execute("CREATE TABLE IF NOT EXISTS contas_bancarias (id SERIAL PRIMARY KEY, banco TEXT, ag_conta TEXT, provedor TEXT DEFAULT 'MANUAL', item_id TEXT, saldo NUMERIC DEFAULT 0, ultimo_sync TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS integracoes_config (id SERIAL PRIMARY KEY, tipo TEXT UNIQUE, provedor TEXT, api_key TEXT, client_id TEXT, client_secret TEXT, config_extra TEXT, ativo BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS maquininhas (id SERIAL PRIMARY KEY, operadora TEXT, taxa NUMERIC DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS repasses_ifood (id SERIAL PRIMARY KEY, periodo TEXT, bruto NUMERIC DEFAULT 0, taxa NUMERIC DEFAULT 0, liquido NUMERIC DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS boletos (id SERIAL PRIMARY KEY, conta_id INT, nosso_numero TEXT, link TEXT, linha_digitavel TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, status TEXT DEFAULT 'EMITIDO', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS notas_fiscais (id SERIAL PRIMARY KEY, tipo TEXT, numero TEXT, pessoa TEXT, total NUMERIC DEFAULT 0, total_impostos NUMERIC DEFAULT 0, aliq_icms NUMERIC DEFAULT 0, aliq_pis NUMERIC DEFAULT 0, aliq_cofins NUMERIC DEFAULT 0, aliq_iss NUMERIC DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS lancamentos_contabeis (id SERIAL PRIMARY KEY, origem TEXT, referencia_id INT, descricao TEXT, valor NUMERIC DEFAULT 0, tipo TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS arquivos (id SERIAL PRIMARY KEY, categoria TEXT, referencia TEXT, nome TEXT, url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS eventos_agenda (id SERIAL PRIMARY KEY, titulo TEXT, inicio TIMESTAMP, fim TIMESTAMP, tipo TEXT, responsavel TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS ponto_registros (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, entrada TIME, saida TIME, pausa_min NUMERIC DEFAULT 60, horas_trabalhadas NUMERIC DEFAULT 8, horas_extras NUMERIC DEFAULT 0, status TEXT DEFAULT 'ATIVO', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS ponto_ajustes (id SERIAL PRIMARY KEY, ponto_id INT, funcionario_matricula TEXT, data_ref DATE, campo TEXT, valor_antigo TEXT, valor_novo TEXT, motivo TEXT, status TEXT DEFAULT 'PENDENTE', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS atestados (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, dias NUMERIC DEFAULT 1, motivo TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS contas (id SERIAL PRIMARY KEY, tipo TEXT, descricao TEXT, pessoa TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, categoria TEXT, status TEXT DEFAULT 'ABERTO', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
        if cur.fetchone():
            cur.execute("UPDATE funcionarios SET senha_hash=%s, role='admin', status='ATIVO' WHERE matricula='AP-2026-0001'", (hash_senha("123"),))
        else:
            cur.execute("INSERT INTO funcionarios (matricula,nome,cargo,role,senha_hash,status) VALUES ('AP-2026-0001','Administrador','Gerente','admin',%s,'ATIVO')", (hash_senha("123"),))
        conn.commit()
    print("Schema corrigido.", flush=True)

garantir_schema = garantir_schema_CORRIGIDO

_orig_do_GET = APIHandler.do_GET
def _patched_do_GET(self):
    from urllib.parse import urlparse
    path = urlparse(self.path).path
    if path in ("/novas.js", "/public/novas.js"):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            caminho = None
            for pasta in (os.path.join(base, "public"), base):
                cand = os.path.join(pasta, "novas.js")
                if os.path.exists(cand):
                    caminho = cand
                    break
            if caminho is None:
                return self.responder({"erro": "novas.js nao encontrado"}, 404)
            with open(caminho, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.end_headers()
            self.wfile.write(data)
            return
        except Exception as e:
            return self.responder({"erro": str(e)}, 500)
    return _orig_do_GET(self)
APIHandler.do_GET = _patched_do_GET