importar os
importar json
import hashlib
importar psycopg2
importar psycopg2.extras
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

tentar:
    from wms_core import numero_float, registrar_wms_movimento
exceto ImportError:
    def numero_float(valor, padrão=0,0):
        tentar:
            retorna float(valor) se valor não estiver em (None, "") senão padrao
        exceto (ValueError, TypeError):
            retornar padrao

    def registrador_wms_movimento(cur, dados, tipo, origem, documento, funcionario_matricula=Nenhum):
        vu = numero_float(dados.get("valor_unitario"), 0)
        quantidade = numero_float(dados.get("quantidade"), 0)
        cur.execute("""INSERIR EM wms_movimentos
            (id_produto, sku, nome_produto, tipo, quantidade, valor_unitário, valor_total,
             origem, documento, funcionario_matricula, location_code)
            VALORES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETORNANDO id""",
            (dados.get("product_id"), dados.get("sku"), dados.get("produto_nome"),
             tipo, quantidade, vu, vu*qty, origem, documento, funcionario_matricula,
             dados.get("código_local", "A-01-01-01")))
        retornar cur.fetchone()['id']

carregar_dotenv()

# Conexão Supabase (PostgreSQL) - usa DATABASE_URI se existir, se usa campos separados
DATABASE_URI = os.environ.get("DATABASE_URI", "")

def get_conn():
    se DATABASE_URI:
        # Usa um URI completo do Supabase (pooler ou direto)
        conexão = psycopg2.connect(DATABASE_URI, connect_timeout=30)
    outro:
        conexão = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            porta=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ.get("DB_NAME", "postgres"),
            usuário=os.environ.get("DB_USER", "postgres"),
            senha=os.environ.get("DB_PASS", ""),
            connect_timeout=30
        )
    conn.autocommit = False
    retornar conexão

classe DBConnection:
    def __enter__(self):
        self.conn = get_conn()
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        retornar self.conn, self.cur
    def __exit__(self, exc_type, exc_val, exc_tb):
        tentar:
            se exc_type: self.conn.rollback()
            senão: self.conn.commit()
        exceto Exceção: passar
        finalmente:
            tente: self.cur.close()
            exceto Exceção: passar
            tente: self.conn.close()
            exceto Exceção: passar

def ultimo_id(cur):
    cur.execute("SELECT LASTVAL() AS id")
    retornar cur.fetchone()['id']

MODULOS_PADRAO = ["dashboard","fornecedores","produtos","clientes","funcionarios","wms","caixa","comandas","rh","tesouraria","contabilidade","bancos","logistica","sites"]
PERFIS_AUTORIZADORES = {"admin","gerente","financeiro"}

def hash_senha(s): return hashlib.sha256(str(s or "").encode()).hexdigest()

def normalizar_permissões(v):
    Se `v` for uma instância da lista: retorne `v`.
    se isinstance(v, str) e v.strip():
        tentar:
            d = json.loads(v); retorna d se isinstance(d, lista) senão []
        exceto: retornar []
    retornar []

def normalizar_bool(v):
    Se `v` for uma instância de um booleano: retorne `v`.
    Se v for None ou v == "": retorne None
    t = str(v).strip().lower()
    se t estiver em ("1","verdadeiro","sim","s","sim","ligado"): retorne Verdadeiro
    if t in ("0","false","nao","não","n","no","off"): return False
    retornar bool(v)

def preparar_usuario(linha):
    Se não houver linha: retorne None
    linha = dict(linha)
    linha.pop("senha_hash", None)
    linha["permissões"] = normalizar_permissões(linha.get("permissões"))
    retornar linha

def buscar_funcionario(cur, mat):
    Se não for um tapete: retorne None
    cur.execute("SELECT * FROM funcionarios WHERE matrícula=%s AND status='ATIVO' LIMIT 1", (mat,))
    retornar cur.fetchone()

def usuário_do_corpo(cur, dados):
    u = dados.get("usuário") ou {}
    mat = u.get("matricula") ou dados.get("operator_matricula") ou dados.get("matricula")
    return buscar_funcionario(cur, mat)

def pode_autorizar(u):
    Se não for u: retorne Falso
    return u.get("role") em PERFIS_AUTORIZADORES ou "tesouraria" em normalizar_permissoes(u.get("permissoes"))

def usuario_tem_modulo(u, mod):
    Se não for u: retorne Falso
    if u.get("role") em PERFIS_AUTORIZADORES: retorne True
    retornar mod em normalizar_permissoes(u.get("permissoes"))

def pode_gerir_rh(u):
    Se não for u: retorne Falso
    retornar u.get("role") em {"admin","gerente"} ou "rh_admin" em normalizar_permissoes(u.get("permissoes"))

def gerar_numero_comanda():
    retornar "CMD" + datetime.now().strftime("%y%m%d%H%M%S%f")[-12:]

def atualizar_total_comanda(cur, cid):
    cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM comanda_itens WHERE comanda_id=%s", (cid,))
    t = cur.fetchone().get("t", 0)
    cur.execute("UPDATE comandas SET total=%s WHERE id=%s", (t, cid))
    retornar t

def log_caixa_terminal(evento, usuário=Nenhum, detalhes=Nenhum):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [CAIXA] {evento}", flush=True)
    se também:
        para k, v em detalhes.items():
            print(f" {str(k).upper()}: {v}", flush=True)

def garantir_schema():
    """Garantir tabelas extras e dados padrão no Supabase."""
    com DBConnection() como (conn, cur):
        cur.execute("""CREATE TABLE IF NOT EXISTS produto_receitas (
            ID da chave primária serial,
            produto_id INT NÃO NULO,
            insumo_id INT NÃO NULO,
            insumo_nome VARCHAR(200),
            quantidade_por_unidade NUMERIC(10,3) NÃO NULO PADRÃO 0,
            unidade VARCHAR(10) DEFAULT 'UN',
            criado_em TIMESTAMP DEFAULT TIMESTAMP_ATUAL
        )"""
        cur.execute("SELECT COUNT(*) AS t FROM formas_pagamento_taxas")
        if (cur.fetchone() or {}).get("t", 0) == 0:
            cur.executemany("INSERT INTO formas_pagamento_taxas (nome,tipo,taxa_percentual,taxa_fixa,operacao,ativo) VALORES (%s,%s,%s,%s,%s,TRUE)",
                [("PIX padrão","PIX",0,0,"RECEBIMENTO"),("Boleto padrão","BOLETO",1.5,0,"RECEBIMENTO"),
                 ("Cartão de crédito","CREDITO",3.5,0,"RECEBIMENTO"),("Dinheiro","DINHEIRO",0,0,"RECEBIMENTO")])
        cur.execute("SELECT COUNT(*) AS t FROM site_config_grid")
        if (cur.fetchone() or {}).get("t", 0) == 0:
            cur.executemany("INSERT INTO site_config_grid (secao,nome,valor,tipo,ativo,ordem) VALORES (%s,%s,%s,%s,TRUE,%s)",
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
        se cur.fetchone():
            cur.execute("UPDATE funcionarios SET senha_hash=%s, role='admin', permissoes=%s, status='ATIVO' WHERE matricula='AP-2026-0001'",
                (hash_senha("123"), json.dumps(MODULOS_PADRAO)))
        outro:
            cur.execute("INSERT INTO funcionários (matricula,nome,cargo,role,senha_hash,permissoes,status) VALORES (%s,%s,%s,%s,%s,%s,'ATIVO')",
                ("AP-2026-0001","Administrador","Gerente Geral","admin",hash_senha("123"),json.dumps(MODULOS_PADRAO)))
        conn.commit()
    print("Esquema selecionado no Supabase.", flush=True)


classe APIHandler(BaseHTTPRequestHandler):
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
        tente: retorne json.loads(corpo) se tam senão {}
        exceto: retorne {}

    def responder(self, dados, status=200):
        self.set_headers(status)
        self.wfile.write(json.dumps(dados, default=str, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}", flush=True)

    def do_GET(self):
        analisado = urlparse(self.path); caminho = analisado.path; consulta = analisar_qs(analisado.query)
        # Servir arquivos estatísticos: site público na raiz, dashboard em /admin
        arquivos_estáticos = {
            "/": ("site.html", "text/html; charset=utf-8"),
            "/site": ("site.html", "text/html; charset=utf-8"),
            "/site.html": ("site.html", "text/html; charset=utf-8"),
            "/admin": ("dashboard.html", "text/html; charset=utf-8"),
            "/dashboard": ("dashboard.html", "text/html; charset=utf-8"),
            "/dashboard.html": ("dashboard.html", "text/html; charset=utf-8"),
            "/index.html": ("site.html", "text/html; charset=utf-8"),
        }
        se o caminho estiver em arquivos_staticos:
            nome_arq, ctype = arquivos_staticos[caminho]
            tentar:
                base = os.path.dirname(os.path.abspath(__file__))
                # procura em público/ primeiro, depois na mesma pasta do servidor
                caminho = Nenhum
                para pasta em (os.path.join(base, "public"), base):
                    cand = os.path.join(pasta, nome_arq)
                    se os.path.exists(cand):
                        caminho = cand
                        quebrar
                se caminho for None:
                    aumentar FileNotFoundError(nome_arq)
                com open(caminho, "rb") como f:
                    conteúdo = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(conteúdo)
            exceto FileNotFoundError:
                self.responder({"erro": f"{nome_arq} não encontrado na mesma pasta"}, 404)
            retornar
        tentar:
            com DBConnection() como (conn, cur):
                Se o caminho for igual a "/api/health":
                    cur.execute("SELECT 1 as ok"); cur.fetchone()
                    return self.responder({"status":"ok","banco":"supabase conectada"})

                OBTER = {
                    "/api/fornecedores": "SELECT * FROM fornecedores ORDER BY id DESC LIMIT 100",
                    "/api/produtos": "SELECT * FROM produtos ORDER BY id DESC LIMIT 200",
                    "/api/clientes": "SELECT * FROM clientes ORDER BY id DESC LIMIT 100",
                    "/api/vendas": "SELECT * FROM vendas ORDER BY data DESC, id DESC LIMIT 200",
                    "/api/comandas": "SELECT * FROM comandos ORDER BY entrada_at DESC LIMIT 200",
                    "/api/autorizacoes": "SELECT * FROM autorizacoes ORDER BY created_at DESC LIMIT 200",
                    "/api/wms/estoque": "SELECT * FROM wms_estoque ORDER BY location_code LIMIT 200",
                    "/api/wms/movimentos": "SELECT * FROM wms_movimentos ORDER BY created_at DESC LIMIT 300",
                    "/api/livro-caixa": "SELECT * FROM livro_caixa ORDER BY data DESC LIMIT 100",
                    "/api/caixa/movimentos": "SELECT * FROM caixa_movimentos ORDER BY criado_no DESC LIMIT 200",
                    "/api/rh/ferias": "SELECT * FROM rh_ferias ORDER BY solicitado_em DESC LIMIT 300",
                    "/api/rh/ponto": "SELECT * FROM rh_ponto ORDER BY data DESC, id DESC LIMIT 300",
                    "/api/rh/holerites": "SELECT * FROM rh_holerites ORDER BY competência DESC LIMIT 300",
                    "/api/rh/eventos": "SELECT * FROM rh_eventos ORDER BY created_at DESC LIMIT 300",
                    "/api/logistica/movimentos": "SELECT * FROM logistica_movimentos ORDER BY created_at DESC LIMIT 300",
                    "/api/site/marketing": "SELECT * FROM site_marketing ORDER BY ativo DESC, id DESC",
                    "/api/site/clientes": "SELECT id,nome,email,telefone,status,created_at FROM site_clientes ORDER BY created_at DESC LIMIT 200",
                    "/api/bancos": "SELECT * FROM bancos_comerciais ORDER BY id",
                    "/api/formas-pagamento": "SELECT * FROM formas_pagamento_taxas WHERE ativo=TRUE ORDER BY id",
                }
                se o caminho estiver em GET:
                    cur.execute(GET[caminho])
                    chave = path.split("/")[-1].replace("-","_")
                    retornar self.responder({chave: [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/funcionarios":
                    cur.execute("SELECT * FROM funcionarios ORDER BY id DESC LIMIT 100")
                    return self.responder({"funcionarios":[preparar_usuario(r) for r in (cur.fetchall() ou [])]})

                if path == "/api/comandas/itens":
                    cid = query.get("comanda_id",[None])[0]
                    se cid:
                        cur.execute("SELECT * FROM comanda_itens WHERE comanda_id=%s ORDER BY id", (cid,))
                    outro:
                        cur.execute("SELECT * FROM comanda_itens ORDER BY created_at DESC LIMIT 300")
                    retornar self.responder({"itens": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/site/pedidos":
                    sf = query.get("status",[None])[0]
                    se sf:
                        cur.execute("SELECT * FROM site_pedidos WHERE status=%s ORDER BY created_at DESC LIMIT 200", (sf,))
                    outro:
                        cur.execute("SELECT * FROM site_pedidos ORDER BY created_at DESC LIMIT 200")
                    retornar self.responder({"pedidos": [dict(r) for r in (cur.fetchall() or [])]})

                Se o caminho for igual a "/api/site/config":
                    cur.execute("SELECT * FROM site_config_grid ORDER BY secao, ordem, id")
                    retornar self.responder({"configurações": [dict(r) for r in (cur.fetchall() or [])]})

                se o caminho for igual a "/api/caixa/status-online":
                    cur.execute("SELECT * FROM livro_caixa WHERE status='ABERTO' ORDER BY data DESC")
                    abertas = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT COUNT(*) AS t FROM autorizacoes WHERE status='PENDENTE'")
                    pend = (cur.fetchone() or {}).get("t",0)
                    cur.execute("""SELECT COALESCE(SUM(CASE WHEN tipo IN ('ENTRADA','RECEBIMENTO','VENDA','SUPRIMENTO') THEN valor ELSE 0 END),0)
                        - COALESCE(SUM(CASE WHEN tipo IN ('SAIDA','SANGRIA','ENVIO_TESOURARIA') THEN valor ELSE 0 END),0) AS saldo
                        FROM caixa_movimentos WHERE status='APROVADO'""")
                    saldo = (cur.fetchone() or {}).get("saldo",0)
                    return self.responder({"online":True,"caixas_abertos":abertos,"autorizacoes_pendentes":pend,"saldo_atual":float(saldo or 0)})

                se o caminho for igual a "/api/tesouraria/status":
                    cur.execute("SELECT * FROM livro_caixa WHERE status='ABERTO' ORDER BY data DESC")
                    abertas = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT * FROM caixa_movimentos ORDER BY created_at DESC LIMIT 100")
                    movs = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT * FROM autorizacoes WHERE status='PENDENTE' ORDER BY created_at")
                    pend = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("""SELECT COALESCE(SUM(CASE WHEN tipo IN ('ENTRADA','RECEBIMENTO','VENDA','SUPRIMENTO') THEN valor ELSE 0 END),0)
                        - COALESCE(SUM(CASE WHEN tipo IN ('SAIDA','SANGRIA','ENVIO_TESOURARIA') THEN valor ELSE 0 END),0) AS saldo
                        FROM caixa_movimentos WHERE status='APROVADO'""")
                    saldo = (cur.fetchone() or {}).get("saldo",0)
                    return self.responder({"caixas_abertos":abertos,"movimentos":movs,"autorizacoes_pendentes":pend,"saldo_atual":float(saldo or 0)})

                Se o caminho for igual a "/api/contas":
                    cur.execute("SELECT * FROM contas_financeiras ORDER BY vencimento ASC LIMIT 300")
                    retornar self.responder({"contas": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/contabilidade/resumo":
                    cur.execute("SELECT status, COUNT(*) AS qtd, COALESCE(SUM(valor),0) AS total FROM contas_financeiras GROUP BY status")
                    por_status = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT categoria, COALESCE(SUM(valor),0) AS total FROM contas_financeiras WHERE status='ABERTO' GROUP BY categoria ORDER BY total DESC LIMIT 20")
                    por_cat = [dict(r) for r in (cur.fetchall() or [])]
                    return self.responder({"contas_por_status":por_status,"contas_por_categoria":por_cat})

                if path == "/api/bancos/movimentos":
                    lance = consulta.get("banco_id",[None])[0]
                    se houver lance:
                        cur.execute("SELECT * FROM banco_movimentos WHERE banco_id=%s ORDER BY data_movimento DESC LIMIT 200", (bid,))
                    outro:
                        cur.execute("SELECT * FROM banco_movimentos ORDER BY data_movimento DESC LIMIT 200")
                    retornar self.responder({"movimentos": [dict(r) for r in (cur.fetchall() or [])]})

                se o caminho for igual a "/api/rh/resumo":
                    cur.execute("""SELECIONE f.matricula,f.nome,f.carga,
                        COALESCE(SUM(p.horas_trabalhadas),0) AS horas_trabalhadas,
                        COALESCE(SUM(p.horas_extras),0) AS horas_extras,
                        COALESCE(SUM(CASE WHEN p.falta THEN 1 ELSE 0 END),0) AS faltas
                        FROM funcionarios f LEFT JOIN rh_ponto p ON p.funcionario_matricula=f.matricula
                        E p.data >= DATA_ATUAL - INTERVALO '30 dias'
                        AGRUPAR POR f.matricula,f.nome,f.cargo ORDENAR POR f.nome""")
                    assid = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("""SELECT operador_matricula AS matrícula, COUNT(*) AS vendas,
                        COALESCE(SUM(total),0) AS valor, COALESCE(AVG(total),0) AS ticket_medio
                        DE vendas ONDE operador_matrícula NÃO É NULO
                        E dados >= AGORA() - INTERVALO '30 dias'
                        GROUP BY operador_matricula ORDER BY valor DESC""")
                    vendas_func = [dict(r) for r in (cur.fetchall() or [])]
                    return self.responder({"assiduidade":assid,"vendas_funcionarios":vendas_func})

                se caminho == "/api/dashboard/resumo":
                    hoje = datetime.now().strftime("%Y-%m-%d")
                    cur.execute("SELECT COALESCE(SUM(valor),0) AS total FROM contas_financeiras WHERE tipo='RECEBER' AND status='ABERTO' AND vencimento<=%s", (hoje,))
                    receber_hoje = float((cur.fetchone() ou {}).get("total",0) ou 0)
                    cur.execute("SELECT COALESCE(SUM(valor),0) AS total FROM contas_financeiras WHERE tipo='PAGAR' AND status='ABERTO' AND vencimento<=%s", (hoje,))
                    pagar_hoje = float((cur.fetchone() ou {}).get("total",0) ou 0)
                    cur.execute("SELECT COALESCE(SUM(total),0) AS total FROM vendas WHERE DATE(data)=%s", (hoje,))
                    vendas_hoje = float((cur.fetchone() ou {}).get("total",0) ou 0)
                    cur.execute("SELECT COALESCE(SUM(total),0) AS total FROM vendas WHERE EXTRACT(MONTH FROM data)=EXTRACT(MONTH FROM NOW()) AND EXTRACT(YEAR FROM data)=EXTRACT(YEAR FROM NOW())")
                    vendas_mes = float((cur.fetchone() or {}).get("total",0) or 0)
                    cur.execute("SELECT COUNT(*) AS t FROM produtos p LEFT JOIN wms_estoque e ON e.product_id=p.id WHERE COALESCE(e.qty,0) <= p.estoque_minimo AND p.status='ATIVO'")
                    estoque_baixo = (cur.fetchone() ou {}).get("t",0)
                    cur.execute("SELECT COUNT(*) AS t FROM site_pedidos WHERE status='SOLICITADO'")
                    pedidos_pendentes = (cur.fetchone() ou {}).get("t",0)
                    cur.execute("""SELECT DATE(dados) AS dia, COALESCE(SUM(total),0) AS valor FROM vendas
                        ONDE data >= AGORA() - INTERVALO '7 dias' AGRUPAR POR DATA(data) ORDENAR POR dia""")
                    vendas_7d = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT COALESCE(SUM(saldo),0) AS total FROM bancos_comerciais WHERE status='ATIVO'")
                    saldo_bancos = float((cur.fetchone() or {}).get("total",0) or 0)
                    retornar self.responder({
                        "receber_hoje":receber_hoje,"pagar_hoje":pagar_hoje,
                        "vendas_hoje":vendas_hoje,"vendas_mes":vendas_mes,
                        "estoque_baixo":estoque_baixo,"pedidos_pendentes":pedidos_pendentes,
                        "vendas_7d":vendas_7d,"saldo_bancos":saldo_bancos
                    })

                # ===== PRODUÇÃO / RECEITAS =====
                if path == "/api/produção/receitas":
                    pid = query.get("produto_id",[None])[0]
                    se pid:
                        cur.execute("SELECT * FROM produto_receitas WHERE produto_id=%s ORDER BY id", (pid,))
                    outro:
                        cur.execute("SELECT * FROM produto_receitas ORDER BY produto_id, id LIMITE 500")
                    retornar self.responder({"receitas": [dict(r) for r in (cur.fetchall() or [])]})

                # ===== GRADE 1: Configuração do Bot =====
                Se o caminho for igual a "/api/bot/config":
                    cur.execute("SELECT * FROM site_config_grid WHERE secao='bot_geral' ORDER BY ordem, id")
                    geral = [dict(r) for r in (cur.fetchall() or [])]
                    cur.execute("SELECT * FROM site_config_grid WHERE secao='bot_regras' ORDER BY ordem, id")
                    regras = [dict(r) for r in (cur.fetchall() or [])]
                    return self.responder({"config_geral":geral,"regras":regras})

                # ===== GRADE 2: Gerente =====
                if path == "/api/gerente/status-modulos":
                    módulos = []
                    verificações = [
                        ("Caixa","SELECT COUNT(*) AS t FROM livro_caixa WHERE status='ABERTO'","caixa_aberto"),
                        ("Estoque Baixo","SELECT COUNT(*) AS t FROM produtos p LEFT JOIN wms_estoque e ON e.product_id=p.id WHERE COALESCE(e.qty,0)<=p.estoque_minimo AND p.status='ATIVO'","alertas"),
                        ("Contas Vencidas","SELECT COUNT(*) AS t FROM contas_financeiras WHERE status='ABERTO' AND vencimento<CURRENT_DATE","alertas"),
                        ("Site de Pedidos","SELECT COUNT(*) AS t FROM site_pedidos WHERE status='SOLICITADO'","alertas"),
                        ("Autorizações","SELECT COUNT(*) AS t FROM autorizações WHERE status='PENDENTE'","alertas"),
                    ]
                    para nome, sql, tipo em cheques:
                        cur.execute(sql); v = (cur.fetchone() or {}).get("t",0)
                        status = "ok" if v == 0 else "atencao"
                        if nome == "Caixa": status = "ok" if v>0 else "atencao"
                        elif v > 0: status = "alerta"
                        módulos.append({"módulo":nome,"valor":v,"status":status})
                    return self.responder({"módulos":módulos})

                if path == "/api/gerente/alertas":
                    alertas = []
                    cur.execute("SELECT COUNT(*) AS t FROM produtos p LEFT JOIN wms_estoque e ON e.product_id=p.id WHERE COALESCE(e.qty,0)<=p.estoque_minimo AND p.status='ATIVO'")
                    eb = (cur.fetchone() ou {}).get("t",0)
                    if eb: alertas.append({"tipo":"estoque","mensagem":f"{eb} produto(s) com estoque baixo","nivel":"alerta"})
                    cur.execute("SELECT COUNT(*) AS t FROM contas_financeiras WHERE status='ABERTO' AND vencimento<CURRENT_DATE")
                    cv = (cur.fetchone() ou {}).get("t",0)
                    if cv: alertas.append({"tipo":"financeiro","mensagem":f"{cv} conta(s) vencida(s)","nivel":"critico"})
                    cur.execute("SELECT COUNT(*) AS t FROM autorizacoes WHERE status='PENDENTE'")
                    ap = (cur.fetchone() ou {}).get("t",0)
                    if ap: alertas.append({"tipo":"autorização","mensagem":f"{ap} autorização(ões) pendente(s)","nivel":"atencao"})
                    cur.execute("SELECT COUNT(*) AS t FROM site_pedidos WHERE status='SOLICITADO'")
                    pp = (cur.fetchone() ou {}).get("t",0)
                    if pp: alertas.append({"tipo":"pedido","mensagem":f"{pp} pedido(s) do site pendente(s)","nivel":"atencao"})
                    return self.responder({"alertas":alertas})

                if path == "/api/gerente/relatorio-vendas":
                    cur.execute("""SELECT DATE(dados) AS dia, origem, COALESCE(SUM(total),0) AS valor, COUNT(*) AS qtd
                        FROM vendas WHERE data >= NOW() - INTERVALO '7 dias'
                        AGRUPAR POR DATA(data), origem ORDENAR POR dia""")
                    retornar self.responder({"vendas": [dict(r) for r in (cur.fetchall() or [])]})

                # ===== GRADE 3: IA Vendas =====
                if path == "/api/ia-vendas/produtos":
                    cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY id DESC LIMIT 100")
                    retornar self.responder({"produtos": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/ia-vendas/produtos-recomendados":
                    cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 6")
                    retornar self.responder({"recomendados": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/ia-vendas/métricas":
                    cur.execute("SELECT COUNT(*) AS t FROM site_pedidos")
                    total_pedidos = (cur.fetchone() or {}).get("t",0)
                    cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM site_pedidos WHERE status IN ('CONFIRMADO','PAGO','ENTREGUE')")
                    receita = float((cur.fetchone() or {}).get("t",0) or 0)
                    cur.execute("SELECT COUNT(*) AS t FROM site_clientes")
                    clientes = (cur.fetchone() ou {}).get("t",0)
                    return self.responder({"total_pedidos":total_pedidos,"receita_ia":receita,"clientes_site":clientes})

                se o caminho for igual a "/api/integracao/ifood/status":
                    cur.execute("SELECT * FROM integracoes_ifood ORDER BY id DESC LIMIT 1")
                    retornar self.responder({"ifood": dict(cur.fetchone() or {})})

                return self.responder({"erro":"Rota não encontrada: "+path}, 404)
        exceto Exception como e:
            retornar self.responder({"erro": str(e)}, 500)

    def do_POST(self):
        dados = self.get_body()
        tentar:
            com DBConnection() como (conn, cur):
                caminho = urlparse(self.path).path

                Se o caminho for igual a "/api/login":
                    mat = dados.get("matrícula"); senha = dados.get("senha")
                    cur.execute("SELECT * FROM funcionarios WHERE matrícula=%s LIMIT 1", (mat,))
                    u = cur.fetchone()
                    se não você ou u.get("senha_hash") != hash_senha(senha):
                        return self.responder({"erro":"Credenciais inválidos"}, 401)
                    if u.get("status") != "ATIVO":
                        return self.responder({"erro":"Usuário inativo"}, 403)
                    return self.responder({"sucesso":True,"usuario":preparar_usuario(u)})

                if path == "/api/caixa/abrir":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("INSERT INTO livro_caixa (status,operador_matricula,fundo_inicial,dados) VALORES ('ABERTO',%s,%s,AGORA()) RETORNANDO id",
                        (u["matrícula"], numero_float(dados.get("fundo_inicial"),0)))
                    cid = cur.fetchone()['id']
                    log_caixa_terminal("CAIXA ABERTA", você, {"caixa_id":cid})
                    return self.responder({"sucesso":True,"caixa_id":cid})

                if path == "/api/caixa/fechar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cid = dados.get("caixa_id")
                    cur.execute("SELECT * FROM livro_caixa WHERE id=%s LIMIT 1", (cid,))
                    cx = cur.fetchone()
                    se não cx ou cx["status"] != "ABERTO": return self.responder({"erro":"Caixa não está aberta"}, 400)
                    cur.execute("ATUALIZAÇÃO livro_caixa SET status='FECHADO',valor_fechamento=%s,observacao_fechamento=%s,closed_at=AGORA() WHERE id=%s",
                        (numero_float(dados.get("valor_fechamento"),0), dados.get("observacao",""), cid))
                    return self.responder({"sucesso":True})

                if path == "/api/caixa/movimento":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    tipo = dados.get("tipo"); valor = numero_float(dados.get("valor"),0)
                    precisa = valor > 1000 e tipo in ("SAIDA","SANGRIA","ENVIO_TESOURARIA")
                    aut_por = Nenhum
                    se não:
                        aut = buscar_funcionario(cur, dados.get("autorizado_por"))
                        se não aut ou não pode_autorizar(aut):
                            cur.execute("INSERT INTO autorizações (tipo,referencia_tabela,valor,solicitado_por,motivo) VALUES ('movimento_caixa','caixa_movimentos',%s,%s,%s)",
                                (valor, u["matricula"], dados.get("descricao","")))
                            return self.responder({"sucesso":False,"mensagem":"Aguardando autorização","autorizacao_pendente":True}, 202)
                        aut_por = aut["matricula"]
                    cur.execute("INSERT INTO caixa_movimentos (caixa_id,tipo,valor,descricao,operator_matricula,autorizado_por) VALORES (%s,%s,%s,%s,%s,%s)",
                        (dados.get("caixa_id"), tipo, valor, dados.get("descricao",""), u["matricula"], aut_por))
                    return self.responder({"sucesso":True,"movimento_id":ultimo_id(cur)})

                if path == "/api/venda/criar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    itens = dados.get("itens", [])
                    total = soma(numero_float(i.get("total"), numero_float(i.get("qty"),1)*numero_float(i.get("unit_price"),0)) para i em itens)
                    cur.execute("INSERIR EM vendas (nome_cliente,total,forma_pagamento,origem,operador_matricula,caixa_id) VALORES (%s,%s,%s,%s,%s,%s) RETORNANDO id",
                        (dados.get("nome_cliente","Balcão"), total, dados.get("forma_pagamento","DINHEIRO"),
                         dados.get("origem","loja"), u["matricula"], dados.get("caixa_id")))
                    vid = cur.fetchone()['id']
                    para i em itens:
                        qty = numero_float(i.get("qty"),1)
                        registrador_wms_movimento(cur, i, "SAIDA", "VENDA", f"VENDA-{vid}", u["matricula"])
                        cur.execute("UPDATE wms_estoque SET qty=qty-%s WHERE product_id=%s LIMIT 1", (qty, i.get("product_id")))
                    cur.execute("INSERT INTO caixa_movimentos (caixa_id,tipo,valor,descricao,operator_matricula) VALORES (%s,'VENDA',%s,%s,%s)",
                        (dados.get("caixa_id"), total, f"Venda #{vid}", u["matricula"]))
                    return self.responder({"sucesso":True,"venda_id":vid,"total":total})

                se o caminho for igual a "/api/wms/entrada":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    mid = registrador_wms_movimento(cur, dados, "ENTRADA", dados.get("origem","NOTA_FISCAL"), dados.get("documento"), u["matricula"])
                    quantidade = numero_float(dados.get("quantidade"),0); vu = numero_float(dados.get("valor_unitario"),0)
                    cur.execute("""INSERT INTO wms_estoque (product_id,sku,produto_nome,location_code,qty,valor_unitario,valor_total)
                        VALORES (%s,%s,%s,%s,%s,%s,%s)
                        EM CASO DE CONFLITO (product_id, location_code) FAÇA ATUALIZAÇÃO
                        SET qtd=wms_estoque.qty+EXCLUDED.qty, valor_unitario=EXCLUDED.valor_unitario, valor_total=(wms_estoque.qty+EXCLUDED.qty)*EXCLUDED.valor_unitario""",
                        (dados.get("product_id"), dados.get("sku"), dados.get("produto_nome"),
                         dados.get("location_code","A-01-01-01"), qty, vu, qty*vu))
                    return self.responder({"sucesso":True,"movimento_id":mid})

                se o caminho for igual a "/api/wms/saida":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    mid = registrador_wms_movimento(cur, dados, "SAIDA", dados.get("origem","VENDA"), dados.get("documento"), u["matricula"])
                    cur.execute("UPDATE wms_estoque SET qty=qty-%s WHERE product_id=%s", (numero_float(dados.get("qty"),0), dados.get("product_id")))
                    return self.responder({"sucesso":True,"movimento_id":mid})

                if path == "/api/comandas/criar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    num = gerar_numero_comanda()
                    cur.execute("INSERT INTO comandos (numero,nome_cliente,funcionario_entrada) VALUES (%s,%s,%s) RETURNING id",
                        (num, dados.get("nome_cliente",""), u["matricula"]))
                    return self.responder({"sucesso":True,"comanda_id":cur.fetchone()['id'],"numero":num})

                if path == "/api/comandas/adicionar-item":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    qtd = numero_float(dados.get("qtd"),1); up = numero_float(dados.get("unit_price"),0)
                    cur.execute("""INSERT INTO comanda_itens (comanda_id,product_id,produto_nome,sku,qty,unit_price,total,funcionario_matricula)
                        VALORES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("comanda_id"), dados.get("product_id"), dados.get("produto_nome"),
                         dados.get("sku"), qty, up, qty*up, u["matricula"]))
                    atualizar_total_comanda(cur, dados.get("comanda_id"))
                    return self.responder({"sucesso":True,"item_id":ultimo_id(cur)})

                if path == "/api/autorizacoes/decidir":
                    u = usuário_do_corpo(cur, dados)
                    if not u ou not pode_autorizar(u): return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("UPDATE autorizações SET status=%s,aprovado_por=%s,decidido_em=NOW() WHERE id=%s",
                        (dados.get("decisão","APROVADO"), u["matricula"], dados.get("autorizacao_id")))
                    return self.responder({"sucesso":True})

                if path == "/api/rh/ponto/registrar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("""INSERT INTO rh_ponto (funcionario_matricula,data,entrada,saida,pausa_min,horas_trabalhadas,horas_extras,observacao,registrado_por)
                        VALORES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("funcionario_matricula"), dados.get("dados"), dados.get("entrada"), dados.get("saida"),
                         numero_float(dados.get("pausa_min"),0), numero_float(dados.get("horas_trabalhadas"),0),
                         numero_float(dados.get("horas_extras"),0), dados.get("observacao",""), u["matricula"]))
                    return self.responder({"sucesso":True,"ponto_id":ultimo_id(cur)})

                if path == "/api/rh/ferias/registrar":
                    u = usuário_do_corpo(cur, dados)
                    se não você ou não pode_gerir_rh(u): return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("INSERIR EM rh_ferias (funcionario_matricula,inicio,fim,dias,observacao) VALORES (%s,%s,%s,%s,%s)",
                        (dados.get("funcionario_matricula"), dados.get("inicio"), dados.get("fim"),
                         numero_float(dados.get("dias"),0), dados.get("observacao","")))
                    return self.responder({"sucesso":True,"ferias_id":ultimo_id(cur)})

                if path == "/api/rh/holerites/criar":
                    u = usuário_do_corpo(cur, dados)
                    se não você ou não pode_gerir_rh(u): return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("""INSERT INTO rh_holerites (funcionario_matricula,competencia,salario_base,horas_extras_valor,premios,plr,descontos,inss,fgts,liquido,criado_por)
                        VALORES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("funcionario_matricula"), dados.get("competência"),
                         numero_float(dados.get("salario_base"),0), numero_float(dados.get("horas_extras_valor"),0),
                         numero_float(dados.get("prêmios"),0), numero_float(dados.get("plr"),0),
                         numero_float(dados.get("descontos"),0), numero_float(dados.get("inss"),0),
                         numero_float(dados.get("fgts"),0), numero_float(dados.get("liquido"),0), u["matricula"]))
                    return self.responder({"sucesso":True,"holerite_id":ultimo_id(cur)})

                if path == "/api/contabilidade/conta/criar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("""INSERT INTO contas_financeiras (tipo,descricao,pessoa,valor,vencimento,status,categoria,observacao)
                        VALORES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("tipo","PAGAR"), dados.get("descricao",""), dados.get("pessoa",""),
                         numero_float(dados.get("valor"),0), dados.get("vencimento"),
                         dados.get("status","ABERTO"), dados.get("categoria",""), dados.get("observacao","")))
                    return self.responder({"sucesso":True,"conta_id":ultimo_id(cur)})

                if path == "/api/contabilidade/conta/pagar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("UPDATE contas_financeiras SET status='PAGO',pagamento_data=CURRENT_DATE WHERE id=%s", (dados.get("conta_id"),))
                    return self.responder({"sucesso":True})

                if path == "/api/bancos/movimento/criar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("INSERT INTO banco_movimentos (banco_id,tipo,descricao,valor,data_movimento,origem) VALORES (%s,%s,%s,%s,%s,%s)",
                        (dados.get("banco_id"), dados.get("tipo"), dados.get("descricao",""),
                         numero_float(dados.get("valor"),0), dados.get("data_movimento") ou datetime.now().strftime("%Y-%m-%d"),
                         dados.get("origem","MANUAL")))
                    return self.responder({"sucesso":True,"movimento_id":ultimo_id(cur)})

                if path == "/api/logistica/criar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("""INSERT INTO logistica_movimentos (tipo,produto_nome,qty,valor_unitario,valor_total,origem,destino,motorista,placa,observacao,criado_por)
                        VALORES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (dados.get("tipo","ENTREGA"), dados.get("produto_nome",""), numero_float(dados.get("qty"),0),
                         numero_float(dados.get("valor_unitário"),0), numero_float(dados.get("valor_total"),0),
                         dados.get("origem","Padaria"), dados.get("destino",""), dados.get("motorista",""),
                         dados.get("placa",""), dados.get("observacao",""), u["matricula"]))
                    return self.responder({"sucesso":True,"logistica_id":ultimo_id(cur)})

                if path == "/api/logistica/concluir":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("ATUALIZAÇÃO logistica_movimentos SET status='CONCLUIDO',concluido_at=AGORA() WHERE id=%s", (dados.get("logistica_id"),))
                    return self.responder({"sucesso":True})

                if path == "/api/site/pedido/criar":
                    cur.execute("""INSERT INTO site_pedidos (cliente_nome,telefone,entrega_endereco,forma_pagamento,subtotal,taxa_entrega,taxa_pagamento,total,status)
                        VALORES (%s,%s,%s,%s,%s,%s,%s,%s,'SOLICITADO') RETORNANDO id""",
                        (dados.get("nome_cliente"), dados.get("telefone"), dados.get("entrega_endereco"),
                         dados.get("forma_pagamento"), numero_float(dados.get("subtotal"),0),
                         numero_float(dados.get("taxa_entrega"),0), numero_float(dados.get("taxa_pagamento"),0),
                         numero_float(dados.get("total"),0)))
                    pid = cur.fetchone()['id']
                    para item em dados.get("itens", []):
                        qtd = numero_float(item.get("qtd"),1); up = numero_float(item.get("preço_unit"),0)
                        cur.execute("INSERIR EM site_pedido_itens (pedido_id,product_id,produto_nome,sku,qty,unit_price,total) VALORES (%s,%s,%s,%s,%s,%s,%s)",
                            (pid, item.get("product_id"), item.get("produto_nome"), item.get("sku"), qty, up, qty*up))
                    return self.responder({"sucesso":True,"pedido_id":pid})

                se o caminho for igual a "/api/site/pedido/status":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("UPDATE site_pedidos SET status=%s WHERE id=%s", (dados.get("status"), dados.get("pedido_id")))
                    return self.responder({"sucesso":True})

                if caminho == "/api/produtos/salvar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    pid = dados.get("id")
                    se pid:
                        cur.execute("ATUALIZAÇÃO produtos SET nome=%s,sku=%s,categoria=%s,preco_venda=%s,custo=%s,estoque_minimo=%s,status=%s WHERE id=%s",
                            (dados.get("nome"), dados.get("sku"), dados.get("categoria"),
                             numero_float(dados.get("pré-venda"),0), numero_float(dados.get("custo"),0),
                             numero_float(dados.get("estoque_minimo"),0), dados.get("status","ATIVO"), pid))
                    outro:
                        cur.execute("INSERIR EM produtos (nome,sku,categoria,preco_venda,custo,estoque_minimo,status) VALORES (%s,%s,%s,%s,%s,%s,%s)",
                            (dados.get("nome"), dados.get("sku"), dados.get("categoria"),
                             numero_float(dados.get("pré-venda"),0), numero_float(dados.get("custo"),0),
                             numero_float(dados.get("estoque_minimo"),0), dados.get("status","ATIVO")))
                    return self.responder({"sucesso":True})

                if caminho == "/api/clientes/salvar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cid = dados.get("id")
                    se cid:
                        cur.execute("ATUALIZAR clientes SET nome=%s,cpf_cnpj=%s,telefone=%s,email=%s,endereco=%s WHERE id=%s",
                            (dados.get("nome"), dados.get("cpf_cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco"), cid))
                    outro:
                        cur.execute("INSERT INTO clientes (nome,cpf_cnpj,telefone,email,endereco) VALORES (%s,%s,%s,%s,%s)",
                            (dados.get("nome"), dados.get("cpf_cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco")))
                    return self.responder({"sucesso":True})

                if path == "/api/fornecedores/salvar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    fid = dados.get("id")
                    se fid:
                        cur.execute("ATUALIZAÇÃO fornecedores SET nome=%s,cnpj=%s,telefone=%s,email=%s,endereco=%s WHERE id=%s",
                            (dados.get("nome"), dados.get("cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco"), fid))
                    outro:
                        cur.execute("INSERT INTO fornecedores (nome,cnpj,telefone,email,endereco) VALORES (%s,%s,%s,%s,%s)",
                            (dados.get("nome"), dados.get("cnpj"), dados.get("telefone"), dados.get("email"), dados.get("endereco")))
                    return self.responder({"sucesso":True})

                if path == "/api/funcionarios/salvar":
                    u = usuário_do_corpo(cur, dados)
                    if not u ou u.get("role") not in ("admin","gerente"): return self.responder({"erro":"Sem permissão"}, 403)
                    fid = dados.get("id"); mat = dados.get("matrícula")
                    perm = dados.get("permissões", MODULOS_PADRAO)
                    se isinstance(perm, list): perm = json.dumps(perm, ensure_ascii=False)
                    senha = dados.get("senha")
                    se fid:
                        se a senha:
                            cur.execute("ATUALIZAÇÃO funcionarios SET nome=%s,cargo=%s,role=%s,permissoes=%s,status=%s,senha_hash=%s WHERE id=%s",
                                (dados.get("nome"), dados.get("carga"), dados.get("role","operador"), perm,
                                 dados.get("status","ATIVO"), hash_senha(senha), fid))
                        outro:
                            cur.execute("UPDATE funcionarios SET nome=%s,cargo=%s,role=%s,permissoes=%s,status=%s WHERE id=%s",
                                (dados.get("nome"), dados.get("carga"), dados.get("role","operador"), perm, dados.get("status","ATIVO"), fid))
                    outro:
                        cur.execute("SELECT id FROM funcionarios WHERE matrícula=%s LIMIT 1", (mat,))
                        if cur.fetchone(): return self.responder({"erro":"Matrícula já cadastrada"}, 400)
                        cur.execute("INSERT INTO funcionários (matricula,nome,cargo,role,senha_hash,permissoes,status) VALORES (%s,%s,%s,%s,%s,%s,'ATIVO')",
                            (mat, dados.get("nome"), dados.get("cargo"), dados.get("role","operador"), hash_senha(senha ou "123"), perm))
                    return self.responder({"sucesso":True})

                Se o caminho for igual a "/api/site/config/salvar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("UPDATE site_config_grid SET valor=%s,ativo=%s WHERE id=%s",
                        (dados.get("valor"), normalizar_bool(dados.get("ativo")), dados.get("id")))
                    return self.responder({"sucesso":True})

                Se o caminho for igual a "/api/site/config-grid/atualizar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    secao = dados.get("secao","bot_geral"); nome = dados.get("nome"); valor = dados.get("valor","")
                    cur.execute("SELECT id FROM site_config_grid WHERE secao=%s AND nome=%s LIMIT 1", (secao, nome))
                    ex = cur.fetchone()
                    se por exemplo:
                        cur.execute("UPDATE site_config_grid SET valor=%s WHERE id=%s", (valor, ex["id"]))
                    outro:
                        cur.execute("INSERT INTO site_config_grid (seção,nome,valor,tipo) VALORES (%s,%s,%s,'texto')", (seção, nome, valor))
                    return self.responder({"sucesso":True})

                # ===== PRODUÇÃO / RECEITAS =====
                if path == "/api/produção/receita/salvar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    rid = dados.get("id")
                    se livrar:
                        cur.execute("ATUALIZAÇÃO produto_receitas SET insumo_id=%s, insumo_nome=%s, quantidade_por_unidade=%s, unidade=%s WHERE id=%s",
                            (dados.get("insumo_id"), dados.get("insumo_nome"), numero_float(dados.get("quantidade_por_unidade"),0), dados.get("unidade","UN"), rid))
                    outro:
                        cur.execute("INSERIR EM produto_receitas (produto_id,insumo_id,insumo_nome,quantidade_por_unidade,unidade) VALORES (%s,%s,%s,%s,%s)",
                            (dados.get("produto_id"), dados.get("insumo_id"), dados.get("insumo_nome"),
                             numero_float(dados.get("quantidade_por_unidade"),0), dados.get("unidade","UN")))
                    return self.responder({"sucesso":True})

                if path == "/api/produção/receita/excluir":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("DELETE FROM produto_receitas WHERE id=%s", (dados.get("id"),))
                    return self.responder({"sucesso":True})

                if path == "/api/produção/simular":
                    pid = dados.get("id_produto"); qtd = numero_float(dados.get("qtd"),1)
                    cur.execute("SELECT * FROM produto_receitas WHERE produto_id=%s", (pid,))
                    receita = [dict(r) para r em (cur.fetchall() ou [])]
                    se não Receita:
                        return self.responder({"sucesso":False,"mensagem":"Este produto não tem receita cadastrada. Adicione os insumos primeiro."})
                    cur.execute("SELECT * FROM produtos WHERE id=%s LIMIT 1", (pid,))
                    prod = cur.fetchone()
                    resultado = []
                    falta = Falso
                    para r em receita:
                        necessário = float(r["quantidade_por_unidade"]) * qtd
                        cur.execute("SELECT COALESCE(SUM(qty),0) AS q FROM wms_estoque WHERE product_id=%s", (r["insumo_id"],))
                        disp = float((cur.fetchone() or {}).get("q",0) or 0)
                        suficiente = disp >= necess
                        se não for suficiente: falta = True
                        resultado.append({"insumo":r["insumo_nome"],"insumo_id":r["insumo_id"],
                            "necessario":necess,"disponivel":disp,"suficiente":suficiente,
                            "unidade":r.get("unidade","UN")})
                    return self.responder({"sucesso":True,"produto":dict(prod) if prod else {},
                        "qtd_produzir":qtd,"ingredientes":resultado,"falta_insumo":falta})

                if path == "/api/produção/confirmar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    pid = dados.get("id_produto"); qtd = numero_float(dados.get("qtd"),1)
                    # Primeiro simule pra garantir que tem consumo
                    cur.execute("SELECT * FROM produto_receitas WHERE produto_id=%s", (pid,))
                    receita = [dict(r) para r em (cur.fetchall() ou [])]
                    se não Receita:
                        return self.responder({"sucesso":False,"mensagem":"Sem receita cadastrada"})
                    para r em receita:
                        necessário = float(r["quantidade_por_unidade"]) * qtd
                        cur.execute("SELECT COALESCE(SUM(qty),0) AS q FROM wms_estoque WHERE product_id=%s", (r["insumo_id"],))
                        disp = float((cur.fetchone() or {}).get("q",0) or 0)
                        se disp < necessário:
                            return self.responder({"sucesso":False,"mensagem":f"Falta {r['insumo_nome']}: precisa de {necess}, tem {disp}"}, 400)
                    # Dá baixa nos insumos
                    cur.execute("SELECT nome, sku, preco_venda, custo FROM produtos WHERE id=%s LIMIT 1", (pid,))
                    prod = cur.fetchone() ou {}
                    para r em receita:
                        necessário = float(r["quantidade_por_unidade"]) * qtd
                        registrador_wms_movimento(cur, {"product_id":r["insumo_id"],"sku":"","produto_nome":r["insumo_nome"],"qty":necess,"valor_unitario":0},
                            "SAIDA", "PRODUÇÃO", f"PROD-{pid}", u["matricula"])
                        cur.execute("UPDATE wms_estoque SET qty=qty-%s WHERE product_id=%s", (necess, r["insumo_id"]))
                    # Adicionado produto o acabado no estoque
                    vu = float(prod.get("custo",0) or 0)
                    cur.execute("""INSERT INTO wms_estoque (product_id,sku,produto_nome,location_code,qty,valor_unitario,valor_total)
                        VALORES (%s,%s,%s,'PRODUÇÃO',%s,%s,%s)
                        EM CASO DE CONFLITO (product_id, location_code) FAÇA ATUALIZAÇÃO
                        DEFINIR qty=wms_estoque.qty+EXCLUDED.qty, valor_total=(wms_estoque.qty+EXCLUDED.qty)*EXCLUDED.valor_unitário""",
                        (pid, prod.get("sku",""), prod.get("nome","Produto"), qtd, vu, qtd*vu))
                    registrador_wms_movimento(cur, {"product_id":pid,"sku":prod.get("sku",""),"produto_nome":prod.get("nome",""),"qty":qtd,"valor_unitário":vu},
                        "ENTRADA", "PRODUÇÃO", f"PROD-{pid}", u["matricula"])
                    return self.responder({"sucesso":True,"mensagem":f"Produção de {qtd}x {prod.get('nome','')} confirmada! Estoque atualizado."})

                # ===== GRADE 1: Robô =====
                Se o caminho for igual a "/api/bot/config":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    para chave, valor em dados.items():
                        if chave in ("usuário","matricula","operador_matricula"): continuar
                        cur.execute("SELECT id FROM site_config_grid WHERE secao='bot_geral' AND nome=%s LIMIT 1", (chave,))
                        ex = cur.fetchone()
                        se por exemplo:
                            cur.execute("UPDATE site_config_grid SET valor=%s WHERE id=%s", (str(valor), ex["id"]))
                        outro:
                            cur.execute("INSERT INTO site_config_grid (secao,nome,valor,tipo,ordem) VALUES ('bot_geral',%s,%s,'texto',0)", (chave, str(valor)))
                    return self.responder({"sucesso":True})

                Se o caminho for igual a "/api/bot/regras":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    rid = dados.get("id")
                    se livrar:
                        cur.execute("UPDATE site_config_grid SET nome=%s,valor=%s,dados_ref=%s WHERE id=%s",
                            (dados.get("palavras_chave"), dados.get("resposta"), dados.get("acao"), rid))
                    outro:
                        cur.execute("INSERT INTO site_config_grid (secao,nome,valor,tipo,dados_ref,ordem) VALORES ('bot_regras',%s,%s,'regra_bot',%s,0)",
                            (dados.get("palavras_chave",""), dados.get("resposta",""), dados.get("acao","")))
                    return self.responder({"sucesso":True})

                if path == "/api/bot/regras/excluir":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Operador não identificado"}, 403)
                    cur.execute("DELETE FROM site_config_grid WHERE id=%s AND secao='bot_regras'", (dados.get("id"),))
                    return self.responder({"sucesso":True})

                Se o caminho for igual a "/api/bot/responder":
                    msg = (dados.get("mensagem") ou "").lower()
                    cur.execute("SELECT * FROM site_config_grid WHERE secao='bot_regras' AND ativo=TRUE")
                    regras = [dict(r) for r in (cur.fetchall() or [])]
                    para r em regras:
                        kws = (r.get("nome") ou "").lower().split("|")
                        se algum(k.strip() em msg para k em kws se k.strip()):
                            return self.responder({"resposta": r.get("valor") ou "Entendi!", "acao": r.get("dados_ref") ou ""})
                    cur.execute("SELECT valor FROM site_config_grid WHERE secao='bot_geral' AND nome='saudacao' LIMIT 1")
                    saud = (cur.fetchone() or {}).get("valor","Olá! Como posso ajudar?")
                    if any(p in msg for p in ["oi","ola","olá","bom dia","boa tarde","boa noite","olá"]):
                        return self.responder({"resposta": saud, "acao": "saudacao"})
                    if any(p in msg for p in ["preco","preço","valor","quanto","custa"]):
                        cur.execute("SELECT nome, preco_venda FROM produtos WHERE status='ATIVO' ORDER BY preco_venda LIMIT 5")
                        prods = [dict(r) for r in (cur.fetchall() or [])]
                        txt = "Nossos preços:\n" + "\n".join(f"- {p['nome']}: R$ {float(p['preco_venda']):.2f}" for p in prods)
                        return self.responder({"resposta": txt, "acao": "lista_precos", "produtos": prods})
                    if any(p in msg for p in ["horario","horário","abre","fecha","funcionamento"]):
                        cur.execute("SELECT valor FROM site_config_grid WHERE secao='bot_geral' AND nome='horario_atendimento' LIMITE 1")
                        h = (cur.fetchone() ou {}).get("valor","Seg-Sáb 6h às 20h")
                        return self.responder({"resposta": f"Funcionamos: {h}", "acao": "horario"})
                    if any(p in msg for p in ["endereco","endereço","onde","localiza","fica"]):
                        cur.execute("SELECT valor FROM site_config_grid WHERE secao='bot_geral' AND nome='endereco' LIMIT 1")
                        e = (cur.fetchone() ou {}).get("valor","Rua das Flores, 123")
                        return self.responder({"resposta": f"Estamos em: {e}", "acao": "endereco"})
                    if any(p in msg for p in ["pedido","comprar","quero","encomendar","fazer pedido"]):
                        cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 4")
                        rec = [dict(r) para r em (cur.fetchall() ou [])]
                        return self.responder({"resposta":"Claro! Posso te ajudar a fazer um pedido. Veja algumas opções:", "acao":"iniciar_pedido","produtos":rec})
                    if any(p in msg for p in ["obrigado","obrigada","valeu","agradeço","agradeco"]):
                        return self.responder({"resposta":"De nada! Volte sempre!", "acao": "despedida"})
                    return self.responder({"resposta":"Desculpe, não entendi. Posso te ajudar com preços, horários, endereço ou fazer um pedido!", "acao":"default"})

                # ===== GRADE 3: IA Vendas =====
                if caminho == "/api/ia-vendas/chat":
                    msg = (dados.get("mensagem") ou "").lower()
                    if dados.get("acao") == "finalizar":
                        return self.responder({"resposta":"Pedido finalizado! Em breve entraremos em contato.","acao":"pedido_finalizado"})
                    se algum(p em msg para p em ["recomenda","sugest","promo","oferta","combo","pacote"]):
                        cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 4")
                        rec = [dict(r) para r em (cur.fetchall() ou [])]
                        return self.responder({"resposta":"Temos estas delícias em destaque hoje:", "acao":"recomendar","produtos":rec})
                    if any(p in msg for p in ["combo","kit","promocao","promoção"]):
                        return self.responder({"resposta":"Combo Família: 10 pães + 2 cafés + 1 bolo por R$ 49,90! Aproveite!", "acao":"combo"})
                    if any(p in msg for p in ["oi","ola","olá","bom dia","boa tarde","boa noite"]):
                        return self.responder({"resposta":"Olá! Sou a IA de Vendas da Padaria. Quer ver nossas delícias ou montar um pedido?","acao":"saudacao"})
                    cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY RANDOM() LIMIT 6")
                    return self.responder({"resposta":"Veja nossos produtos disponíveis:", "acao":"lista_produtos", "produtos": [dict(r) for r in (cur.fetchall() or [])]})

                if path == "/api/ia-vendas/salvar-pedido":
                    cur.execute("""INSERT INTO site_pedidos (nome_cliente,telefone,entrega_endereco,forma_pagamento,subtotal,total,status)
                        VALORES (%s,%s,%s,%s,%s,%s,'CONFIRMADO') RETORNANDO id""",
                        (dados.get("nome_cliente","Cliente IA"), dados.get("telefone",""),
                         dados.get("entrega_endereco",""), dados.get("forma_pagamento","PIX"),
                         numero_float(dados.get("subtotal"),0), numero_float(dados.get("total"),0)))
                    pid = cur.fetchone()['id']
                    para item em dados.get("itens", []):
                        qtd = numero_float(item.get("qtd"),1); up = numero_float(item.get("preço_unit"),0)
                        cur.execute("INSERIR EM site_pedido_itens (pedido_id,product_id,produto_nome,sku,qty,unit_price,total) VALORES (%s,%s,%s,%s,%s,%s,%s)",
                            (pid, item.get("product_id"), item.get("produto_nome"), item.get("sku"), qty, up, qty*up))
                        registrador_wms_movimento(cur, item, "SAIDA", "IA_VENDAS", f"PEDIDO-{pid}", "IA-VENDAS")
                        cur.execute("UPDATE wms_estoque SET qty=qty-%s WHERE product_id=%s", (qty, item.get("product_id")))
                    return self.responder({"sucesso":True,"pedido_id":pid})

                if path == "/api/integracao/ifood/configurar":
                    u = usuário_do_corpo(cur, dados)
                    se não você: return self.responder({"erro":"Sem permissão"}, 403)
                    cur.execute("SELECT id FROM integracoes_ifood LIMIT 1")
                    ex = cur.fetchone()
                    se por exemplo:
                        cur.execute("UPDATE integracoes_ifood SET merchant_id=%s,client_id=%s,client_secret=%s,ambiente=%s,status=%s,updated_at=NOW() WHERE id=%s",
                            (dados.get("merchant_id"), dados.get("client_id"), dados.get("client_secret"),
                             dados.get("ambiente","sandbox"), dados.get("status","INATIVO"), ex["id"]))
                    outro:
                        cur.execute("INSERT INTO integracoes_ifood (merchant_id,client_id,client_secret,ambiente,status) VALUES (%s,%s,%s,%s,%s)",
                            (dados.get("merchant_id"), dados.get("client_id"), dados.get("client_secret"),
                             dados.get("ambiente","sandbox"), dados.get("status","INATIVO")))
                    return self.responder({"sucesso":True})

                return self.responder({"erro":"Ação não inovadora: "+path}, 404)
        exceto Exception como e:
            retornar self.responder({"erro": str(e)}, 500)


def main():
    garantir_esquema()
    porta = int(os.environ.get("PORTA", 8080))
    servidor = HTTPServer(("0.0.0.0", porta), APIHandler)
    print(f"="*50, flush=True)
    print(f" Servidor Panificadora (SUPABASE) rodando na porta {porta}", flush=True)
    print(f" Banco: {os.environ.get('DB_NAME','postgres')} @ {os.environ.get('DB_HOST','localhost')}", flush=True)
    print(f" Login padrão: AP-2026-0001 / 123", flush=True)
    print(f"="*50, flush=True)
    servidor.serve_forever()

se __name__ == "__main__":
    principal()