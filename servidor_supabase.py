import os, json, hashlib, random, uuid
import psycopg2, psycopg2.extras
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
load_dotenv()

def numero_float(v,pad=0.0):
 try:
  if v in (None,""): return pad
  return float(v)
 except: return pad
def hash_senha(s): return hashlib.sha256(str(s or "").encode()).hexdigest()
def normalizar_bool(v):
 if isinstance(v,bool): return v
 if v in (None,""): return None
 t=str(v).lower()
 return True if t in ("1","true","sim") else False if t in ("0","false","nao") else bool(v)

DATABASE_URI=os.environ.get("DATABASE_URI","")
def get_conn():
 if DATABASE_URI: c=psycopg2.connect(DATABASE_URI,connect_timeout=30)
 else: c=psycopg2.connect(host=os.environ.get("DB_HOST","localhost"),port=int(os.environ.get("DB_PORT",5432)),dbname=os.environ.get("DB_NAME","postgres"),user=os.environ.get("DB_USER","postgres"),password=os.environ.get("DB_PASS",""),connect_timeout=30)
 c.autocommit=False;return c

class DBConnection:
 def __enter__(self):
  self.conn=get_conn();self.cur=self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor);return self.conn,self.cur
 def __exit__(self,a,b,c):
  try:
   if a: self.conn.rollback()
   else: self.conn.commit()
  except: pass
  try: self.cur.close()
  except: pass
  try: self.conn.close()
  except: pass

MODULOS_PADRAO=["dashboard","fornecedores","produtos","clientes","funcionarios","wms","caixa","comandas","rh","tesouraria","contabilidade","bancos","logistica","sites"]
def buscar_funcionario(cur,mat):
 if not mat: return None
 cur.execute("SELECT * FROM funcionarios WHERE matricula=%s AND status='ATIVO' LIMIT 1",(mat,));return cur.fetchone()
def usuario_do_corpo(cur,dados):
 u=dados.get("usuario") or {}
 mat=u.get("matricula") or dados.get("operator_matricula") or dados.get("matricula")
 return buscar_funcionario(cur,mat)
def confirmar_senha_usuario(cur,u,dados):
 s=dados.get("senha_usuario")
 if not u or not s: return False
 return u.get("senha_hash")==hash_senha(s)
def validar_senha_adm(cur,senha):
 if not senha: return None
 cur.execute("SELECT * FROM funcionarios WHERE status='ATIVO' AND role IN ('admin','gerente') AND senha_hash=%s LIMIT 1",(hash_senha(senha),));return cur.fetchone()
def ultimo_id(cur):
 cur.execute("SELECT LASTVAL() AS id");return cur.fetchone()['id']

def garantir_schema():
 with DBConnection() as (conn,cur):
  cur.execute("CREATE TABLE IF NOT EXISTS funcionarios (id SERIAL PRIMARY KEY, matricula VARCHAR(20) UNIQUE, nome VARCHAR(100), cargo VARCHAR(100), role VARCHAR(20) DEFAULT 'operador', senha_hash VARCHAR(255), permissoes TEXT DEFAULT '[]', status VARCHAR(20) DEFAULT 'ATIVO', salario NUMERIC DEFAULT 1500)")
  cur.execute("CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, nome TEXT, sku TEXT, categoria TEXT, preco_venda NUMERIC DEFAULT 0, custo NUMERIC DEFAULT 0, estoque_minimo NUMERIC DEFAULT 0, status TEXT DEFAULT 'ATIVO')")
  cur.execute("CREATE TABLE IF NOT EXISTS vendas (id SERIAL PRIMARY KEY, cliente_nome TEXT, total NUMERIC DEFAULT 0, forma_pagamento TEXT, origem TEXT, operador_matricula TEXT, caixa_id INT, comanda_id INT, status TEXT DEFAULT 'CONFIRMADA', data TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS venda_itens (id SERIAL PRIMARY KEY, venda_id INT, product_id INT, produto_nome TEXT, qty NUMERIC DEFAULT 1, unit_price NUMERIC DEFAULT 0, total NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS comandas (id SERIAL PRIMARY KEY, numero TEXT, cliente_nome TEXT, total NUMERIC DEFAULT 0, status TEXT DEFAULT 'ABERTA', entrada_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS comanda_itens (id SERIAL PRIMARY KEY, comanda_id INT, produto_nome TEXT, qty NUMERIC DEFAULT 1, unit_price NUMERIC DEFAULT 0, total NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS wms_estoque (id SERIAL PRIMARY KEY, product_id INT, produto_nome TEXT, location_code TEXT DEFAULT 'A-01-01-01', qty NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS wms_movimentos (id SERIAL PRIMARY KEY, produto_nome TEXT, tipo TEXT, qty NUMERIC DEFAULT 0, origem TEXT, documento TEXT, created_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS livro_caixa (id SERIAL PRIMARY KEY, status TEXT DEFAULT 'ABERTO', operator_matricula TEXT, fundo_inicial NUMERIC DEFAULT 0, data TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS caixa_movimentos (id SERIAL PRIMARY KEY, caixa_id INT, tipo TEXT, valor NUMERIC DEFAULT 0, descricao TEXT, operator_matricula TEXT, status TEXT DEFAULT 'APROVADO', created_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS autorizacoes (id SERIAL PRIMARY KEY, tipo TEXT, valor NUMERIC DEFAULT 0, motivo TEXT, status TEXT DEFAULT 'PENDENTE', solicitado_por TEXT, created_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS log_operacoes (id SERIAL PRIMARY KEY, evento TEXT, matricula TEXT, detalhes TEXT, created_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS produto_receitas (id SERIAL PRIMARY KEY, produto_id INT, insumo_id INT, insumo_nome TEXT, quantidade_por_unidade NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS site_config_grid (id SERIAL PRIMARY KEY, secao TEXT, nome TEXT, valor TEXT, ativo BOOLEAN DEFAULT TRUE)")
  cur.execute("CREATE TABLE IF NOT EXISTS site_pedidos (id SERIAL PRIMARY KEY, cliente_nome TEXT, telefone TEXT, forma_pagamento TEXT, total NUMERIC DEFAULT 0, status TEXT DEFAULT 'SOLICITADO', created_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS contas_financeiras (id SERIAL PRIMARY KEY, tipo TEXT, descricao TEXT, pessoa TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, status TEXT DEFAULT 'ABERTO', categoria TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS rh_ponto (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, entrada TIME, saida TIME, horas_trabalhadas NUMERIC DEFAULT 8)")
  cur.execute("CREATE TABLE IF NOT EXISTS contas_bancarias (id SERIAL PRIMARY KEY, banco TEXT, ag_conta TEXT, provedor TEXT DEFAULT 'MANUAL', saldo NUMERIC DEFAULT 0, ultimo_sync TIMESTAMP)")
  cur.execute("CREATE TABLE IF NOT EXISTS integracoes_config (id SERIAL PRIMARY KEY, tipo TEXT UNIQUE, provedor TEXT, api_key TEXT, client_id TEXT, client_secret TEXT, config_extra TEXT, ativo BOOLEAN DEFAULT FALSE)")
  cur.execute("CREATE TABLE IF NOT EXISTS maquininhas (id SERIAL PRIMARY KEY, operadora TEXT, taxa NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS repasses_ifood (id SERIAL PRIMARY KEY, periodo TEXT, bruto NUMERIC DEFAULT 0, taxa NUMERIC DEFAULT 0, liquido NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS boletos (id SERIAL PRIMARY KEY, conta_id INT, nosso_numero TEXT, link TEXT, linha_digitavel TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, status TEXT DEFAULT 'EMITIDO')")
  cur.execute("CREATE TABLE IF NOT EXISTS notas_fiscais (id SERIAL PRIMARY KEY, tipo TEXT, numero TEXT, pessoa TEXT, total NUMERIC DEFAULT 0, total_impostos NUMERIC DEFAULT 0, aliq_icms NUMERIC DEFAULT 0, aliq_pis NUMERIC DEFAULT 0, aliq_cofins NUMERIC DEFAULT 0, aliq_iss NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS lancamentos_contabeis (id SERIAL PRIMARY KEY, origem TEXT, descricao TEXT, valor NUMERIC DEFAULT 0, tipo TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS arquivos (id SERIAL PRIMARY KEY, categoria TEXT, referencia TEXT, nome TEXT, url TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS eventos_agenda (id SERIAL PRIMARY KEY, titulo TEXT, inicio TIMESTAMP, fim TIMESTAMP, tipo TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS ponto_registros (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, entrada TIME, saida TIME, horas_trabalhadas NUMERIC DEFAULT 8, horas_extras NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS ponto_ajustes (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, campo TEXT, valor_novo TEXT, motivo TEXT, status TEXT DEFAULT 'PENDENTE')")
  cur.execute("CREATE TABLE IF NOT EXISTS atestados (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, dias NUMERIC DEFAULT 1)")
  cur.execute("CREATE TABLE IF NOT EXISTS contratos (id SERIAL PRIMARY KEY, cliente TEXT, cpf_cnpj TEXT, objeto TEXT, valor NUMERIC DEFAULT 0, prazo DATE, status TEXT DEFAULT 'RASCUNHO', tipo TEXT, texto TEXT, foro TEXT, hash_assinatura TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS producao_ordens (id SERIAL PRIMARY KEY, produto_nome TEXT, qtd_meta NUMERIC DEFAULT 0, qtd_pronta NUMERIC DEFAULT 0, responsavel_matricula TEXT, responsavel_nome TEXT, inicio TIMESTAMPTZ DEFAULT NOW(), previsao_fim TIMESTAMPTZ, custo_insumos NUMERIC DEFAULT 0, preco_un NUMERIC DEFAULT 0, status TEXT DEFAULT 'EM_PRODUCAO')")
  cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
  if cur.fetchone(): cur.execute("UPDATE funcionarios SET senha_hash=%s, role='admin', status='ATIVO' WHERE matricula='AP-2026-0001'",(hash_senha("123"),))
  else: cur.execute("INSERT INTO funcionarios (matricula,nome,role,senha_hash,status) VALUES ('AP-2026-0001','Admin','admin',%s,'ATIVO')",(hash_senha("123"),))
  conn.commit()
 print("Schema pronto",flush=True)

class APIHandler(BaseHTTPRequestHandler):
 def handle(self):
  try: super().handle()
  except: pass
 def set_headers(self,s=200):
  self.send_response(s);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Access-Control-Allow-Origin","*");self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS");self.send_header("Access-Control-Allow-Headers","Content-Type");self.end_headers()
 def do_OPTIONS(self):
  self.send_response(204);self.send_header("Access-Control-Allow-Origin","*");self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS");self.send_header("Access-Control-Allow-Headers","Content-Type");self.end_headers()
 def get_body(self):
  try: t=int(self.headers.get("Content-Length",0));b=self.rfile.read(t) if t else b"{}";return json.loads(b) if b else {}
  except: return {}
 def responder(self,d,s=200):
  try: self.set_headers(s);self.wfile.write(json.dumps(d,default=str,ensure_ascii=False).encode("utf-8"))
  except: pass
 def log_message(self,f,*a): print(f"[{datetime.now().strftime('%H:%M:%S')}] {a[0]}",flush=True)
 def serve_static(self,nome,ctype):
  try:
   base=os.path.dirname(os.path.abspath(__file__))
   for pasta in (os.path.join(base,"public"),base):
    c=os.path.join(pasta,nome)
    if os.path.exists(c):
     with open(c,"rb") as f: data=f.read()
     try: self.send_response(200);self.send_header("Content-Type",ctype);self.end_headers();self.wfile.write(data)
     except: pass
     return True
   return False
  except: return False
 def do_GET(self):
  p=urlparse(self.path);path=p.path;q=parse_qs(p.query)
  if path in ("/","/site","/site.html"): 
   if self.serve_static("site.html","text/html; charset=utf-8"): return
  if path in ("/admin","/dashboard","/dashboard.html"):
   if self.serve_static("dashboard.html","text/html; charset=utf-8"): return
  if path in ("/extra","/extra.html"):
   if self.serve_static("extra.html","text/html; charset=utf-8"): return
  if path.startswith("/uploads/"):
   if self.serve_static(path.lstrip("/"),"application/octet-stream"): return
  try:
   with DBConnection() as (conn,cur):
    def sel(sql):
     try: cur.execute(sql);return [dict(r) for r in (cur.fetchall() or [])]
     except Exception as e: return []
    if path=="/api/health": return self.responder({"status":"ok"})
    if path=="/api/dashboard/resumo":
     try: cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM vendas WHERE DATE(data)=CURRENT_DATE");vh=float((cur.fetchone() or {}).get("t",0) or 0)
     except: vh=0
     return self.responder({"vendas_hoje":vh,"vendas_mes":vh,"estoque_baixo":0,"vendas_7d":[],"saldo_bancos":0,"receber_hoje":0,"pagar_hoje":0})
    if path=="/api/produtos": return self.responder({"produtos":sel("SELECT * FROM produtos ORDER BY id DESC LIMIT 200")})
    if path in ("/api/ia-vendas/produtos","/api/ia-vendas/produtos-recomendados"): lst=sel("SELECT * FROM produtos WHERE status='ATIVO' LIMIT 100");return self.responder({"produtos":lst,"recomendados":lst[:6]})
    if path=="/api/vendas": return self.responder({"vendas":sel("SELECT * FROM vendas ORDER BY id DESC LIMIT 200")})
    if path=="/api/comandas": return self.responder({"comandas":sel("SELECT * FROM comandas ORDER BY id DESC LIMIT 200")})
    if path=="/api/comandas/abertas": return self.responder({"comandas":sel("SELECT * FROM comandas WHERE status='ABERTA' ORDER BY id DESC LIMIT 200")})
    if path=="/api/caixa/movimentos": return self.responder({"movimentos":sel("SELECT * FROM caixa_movimentos ORDER BY id DESC LIMIT 200")})
    if path=="/api/caixa/status-online":
     ab=sel("SELECT * FROM livro_caixa WHERE status='ABERTO'");return self.responder({"online":True,"caixas_abertos":ab,"autorizacoes_pendentes":0,"saldo_atual":0})
    if path=="/api/tesouraria/status": return self.responder({"caixas_abertos":[],"movimentos":sel("SELECT * FROM caixa_movimentos ORDER BY id DESC LIMIT 100"),"autorizacoes_pendentes":[],"saldo_atual":0})
    if path=="/api/wms/estoque": return self.responder({"estoque":sel("SELECT * FROM wms_estoque LIMIT 200")})
    if path=="/api/wms/movimentos": return self.responder({"movimentos":sel("SELECT * FROM wms_movimentos ORDER BY id DESC LIMIT 200")})
    if path=="/api/contas": return self.responder({"contas":sel("SELECT * FROM contas_financeiras LIMIT 300")})
    if path=="/api/funcionarios": return self.responder({"funcionarios":sel("SELECT id,matricula,nome,cargo,role,status,salario FROM funcionarios")})
    if path=="/api/clientes": return self.responder({"clientes":sel("SELECT * FROM clientes LIMIT 200")})
    if path=="/api/fornecedores": return self.responder({"fornecedores":sel("SELECT * FROM fornecedores LIMIT 200")})
    if path=="/api/site/pedidos": return self.responder({"pedidos":sel("SELECT * FROM site_pedidos ORDER BY id DESC LIMIT 200")})
    if path=="/api/site/config": return self.responder({"configuracoes":sel("SELECT * FROM site_config_grid")})
    if path=="/api/bot/config": return self.responder({"config_geral":[],"regras":[]})
    if path=="/api/gerente/alertas": return self.responder({"alertas":[]})
    if path=="/api/producao/receitas": return self.responder({"receitas":sel("SELECT * FROM produto_receitas LIMIT 200")})
    # EXTRA
    if path=="/api/bancos/config": return self.responder({"configs":sel("SELECT * FROM integracoes_config"),"contas":sel("SELECT * FROM contas_bancarias")})
    if path=="/api/bancos/vinculos": return self.responder({"contas":sel("SELECT * FROM contas_bancarias"),"maquininhas":sel("SELECT * FROM maquininhas"),"ifood":sel("SELECT * FROM repasses_ifood")})
    if path=="/api/nf_lista": return self.responder({"notas":sel("SELECT * FROM notas_fiscais LIMIT 100")})
    if path=="/api/dre_resumo":
     nfs=sel("SELECT * FROM notas_fiscais LIMIT 500");rec=sum(float(n.get("total") or 0) for n in nfs if n.get("tipo")=="SAIDA");imp=sum(float(n.get("total_impostos") or 0) for n in nfs if n.get("tipo")=="SAIDA");return self.responder({"receita":rec,"impostos":imp,"liq":rec-imp,"lucro":rec-imp})
    if path=="/api/arquivos_lista": return self.responder({"arquivos":sel("SELECT * FROM arquivos LIMIT 100")})
    if path=="/api/agenda_lista": return self.responder({"eventos":sel("SELECT * FROM eventos_agenda LIMIT 200")})
    if path=="/api/rh/ponto_calc": return self.responder({"ponto":sel("SELECT * FROM ponto_registros LIMIT 200"),"ajustes":sel("SELECT * FROM ponto_ajustes LIMIT 200"),"atestados":sel("SELECT * FROM atestados LIMIT 200"),"funcionarios":sel("SELECT matricula,nome,salario FROM funcionarios")})
    if path=="/api/contratos_lista": return self.responder({"contratos":sel("SELECT * FROM contratos LIMIT 100")})
    if path=="/api/faturamento_resumo":
     try: cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM vendas");tv=float((cur.fetchone() or {}).get("t",0) or 0)
     except: tv=0
     return self.responder({"vendas":tv,"site":0,"total":tv})
    if path=="/api/auditoria_resumo": return self.responder({"vendas":sel("SELECT id,total,status FROM vendas LIMIT 200"),"pedidos":sel("SELECT id,total FROM site_pedidos LIMIT 200"),"produtos":sel("SELECT id,nome FROM produtos LIMIT 200")})
    if path=="/api/producao/acompanhamento": return self.responder({"ordens":sel("SELECT * FROM producao_ordens ORDER BY id DESC LIMIT 100")})
    return self.responder({"erro":"Rota "+path},404)
  except Exception as e: return self.responder({"erro":str(e)},500)
 def do_POST(self):
  path=urlparse(self.path).path
  if path=="/api/arquivos/upload":
   try:
    ctype=self.headers.get("Content-Type","");boundary=ctype.split("boundary=")[1].strip().strip('"').encode();raw=self.rfile.read(int(self.headers.get("Content-Length",0)));filedata=None
    for part in raw.split(b"--"+boundary):
     if b'filename=' in part:
      _,_,body=part.partition(b"\r\n\r\n");filedata=body.rsplit(b"\r\n",1)[0];break
    fname=f"{uuid.uuid4().hex}.bin";base=os.path.dirname(os.path.abspath(__file__));up=os.path.join(base,"public","uploads");os.makedirs(up,exist_ok=True);open(os.path.join(up,fname),"wb").write(filedata or b"")
    with DBConnection() as (c2,q2): q2.execute("INSERT INTO arquivos (categoria,nome,url) VALUES ('GERAL',%s,%s)",(fname,f"/uploads/{fname}"))
    return self.responder({"sucesso":True,"url":f"/uploads/{fname}"})
   except Exception as e: return self.responder({"erro":str(e)},500)
  dados=self.get_body();d=dados
  try:
   with DBConnection() as (conn,cur):
    if path=="/api/login":
     cur.execute("SELECT * FROM funcionarios WHERE matricula=%s LIMIT 1",(d.get("matricula"),));u=cur.fetchone()
     if not u or u.get("senha_hash")!=hash_senha(d.get("senha")): return self.responder({"erro":"login"},401)
     u=dict(u);u.pop("senha_hash",None);return self.responder({"sucesso":True,"usuario":u})
    if path=="/api/caixa/abrir":
     u=usuario_do_corpo(cur,d);cur.execute("INSERT INTO livro_caixa (status,operator_matricula,fundo_inicial) VALUES ('ABERTO',%s,%s) RETURNING id",(u["matricula"] if u else "AP-2026-0001",numero_float(d.get("fundo_inicial"))));return self.responder({"sucesso":True,"caixa_id":cur.fetchone()['id']})
    if path=="/api/caixa/fechar":
     cur.execute("UPDATE livro_caixa SET status='FECHADO' WHERE id=%s",(d.get("caixa_id"),));return self.responder({"sucesso":True})
    if path=="/api/caixa/movimento":
     u=usuario_do_corpo(cur,d);cur.execute("INSERT INTO caixa_movimentos (caixa_id,tipo,valor,descricao,operator_matricula) VALUES (%s,%s,%s,%s,%s)",(d.get("caixa_id"),d.get("tipo"),numero_float(d.get("valor")),d.get("descricao"),u["matricula"] if u else ""));return self.responder({"sucesso":True})
    if path=="/api/venda/criar":
     u=usuario_do_corpo(cur,d);itens=d.get("itens",[]);total=sum(numero_float(i.get("total"),0) for i in itens)
     cur.execute("INSERT INTO vendas (cliente_nome,total,forma_pagamento,operador_matricula,caixa_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",(d.get("cliente_nome") or "Balcao",total,d.get("forma_pagamento") or "DINHEIRO",u["matricula"] if u else "",d.get("caixa_id")));vid=cur.fetchone()['id']
     for i in itens: cur.execute("INSERT INTO venda_itens (venda_id,produto_nome,qty,total) VALUES (%s,%s,%s,%s)",(vid,i.get("produto_nome"),numero_float(i.get("qty"),1),numero_float(i.get("total"),0)))
     return self.responder({"sucesso":True,"venda_id":vid})
    if path=="/api/venda/estornar":
     cur.execute("UPDATE vendas SET status='ESTORNADA' WHERE id=%s",(d.get("venda_id"),));return self.responder({"sucesso":True})
    if path=="/api/comandas/criar":
     cur.execute("INSERT INTO comandas (numero,cliente_nome,status) VALUES (%s,%s,'ABERTA') RETURNING id",("CMD"+str(random.randint(1000,9999)),d.get("cliente_nome")));return self.responder({"sucesso":True,"comanda_id":cur.fetchone()['id']})
    if path=="/api/comandas/adicionar-item":
     cur.execute("INSERT INTO comanda_itens (comanda_id,produto_nome,qty,total) VALUES (%s,%s,%s,%s)",(d.get("comanda_id"),d.get("produto_nome"),numero_float(d.get("qty"),1),numero_float(d.get("total"),0)));return self.responder({"sucesso":True})
    if path=="/api/wms/entrada":
     cur.execute("INSERT INTO wms_movimentos (produto_nome,tipo,qty,origem) VALUES (%s,'ENTRADA',%s,%s)",(d.get("produto_nome"),numero_float(d.get("qty"),0),d.get("origem")));return self.responder({"sucesso":True})
    if path=="/api/wms/saida":
     cur.execute("INSERT INTO wms_movimentos (produto_nome,tipo,qty,origem) VALUES (%s,'SAIDA',%s,%s)",(d.get("produto_nome"),numero_float(d.get("qty"),0),d.get("origem")));return self.responder({"sucesso":True})
    if path=="/api/produtos/salvar":
     cur.execute("INSERT INTO produtos (nome,preco_venda,status) VALUES (%s,%s,'ATIVO')",(d.get("nome"),numero_float(d.get("preco_venda"))));return self.responder({"sucesso":True})
    if path=="/api/contabilidade/conta/criar":
     cur.execute("INSERT INTO contas_financeiras (tipo,descricao,pessoa,valor,status) VALUES (%s,%s,%s,%s,'ABERTO')",(d.get("tipo"),d.get("descricao"),d.get("pessoa"),numero_float(d.get("valor"))));return self.responder({"sucesso":True})
    if path=="/api/rh/ponto/registrar":
     cur.execute("INSERT INTO rh_ponto (funcionario_matricula,data,entrada,saida) VALUES (%s,%s,%s,%s)",(d.get("funcionario_matricula"),d.get("data"),d.get("entrada"),d.get("saida")));return self.responder({"sucesso":True})
    # EXTRA
    if path=="/api/bancos/config": cur.execute("INSERT INTO integracoes_config (tipo,provedor,api_key,ativo) VALUES (%s,%s,%s,TRUE) ON CONFLICT (tipo) DO UPDATE SET provedor=EXCLUDED.provedor",(d.get("tipo"),d.get("provedor"),d.get("api_key")));return self.responder({"sucesso":True})
    if path=="/api/bancos/conta": cur.execute("INSERT INTO contas_bancarias (banco,ag_conta) VALUES (%s,%s)",(d.get("banco"),d.get("ag_conta")));return self.responder({"sucesso":True})
    if path=="/api/bancos/maquininha": cur.execute("INSERT INTO maquininhas (operadora,taxa) VALUES (%s,%s)",(d.get("operadora"),numero_float(d.get("taxa"))));return self.responder({"sucesso":True})
    if path=="/api/ifood/sync": cur.execute("INSERT INTO site_pedidos (cliente_nome,total,status,forma_pagamento) VALUES ('iFood',%s,'CONFIRMADO','IFOOD') RETURNING id",(numero_float(d.get("total")),));return self.responder({"sucesso":True,"pedido_id":cur.fetchone()["id"]})
    if path=="/api/boletos/gerar": cur.execute("INSERT INTO boletos (nosso_numero,link,valor,vencimento) VALUES (%s,%s,%s,%s)",("BL1","https://boleto.teste/BL1",numero_float(d.get("valor")),d.get("vencimento")));return self.responder({"sucesso":True,"link":"https://boleto.teste/BL1"})
    if path=="/api/nf/criar": cur.execute("INSERT INTO notas_fiscais (tipo,numero,total) VALUES (%s,%s,%s)",(d.get("tipo"),d.get("numero"),numero_float(d.get("total"))));return self.responder({"sucesso":True})
    if path=="/api/dre/simular": return self.responder({"pis":0,"cofins":0,"icms":0,"iss":0,"lucro":0})
    if path=="/api/agenda/criar": cur.execute("INSERT INTO eventos_agenda (titulo,inicio) VALUES (%s,%s)",(d.get("titulo"),d.get("inicio")));return self.responder({"sucesso":True})
    if path=="/api/rh/ponto/registrar2": cur.execute("INSERT INTO ponto_registros (funcionario_matricula,data,entrada,saida) VALUES (%s,%s,%s,%s)",(d.get("funcionario_matricula"),d.get("data"),d.get("entrada"),d.get("saida")));return self.responder({"sucesso":True})
    if path=="/api/rh/ponto/ajustar": cur.execute("INSERT INTO ponto_ajustes (funcionario_matricula,campo,valor_novo) VALUES (%s,%s,%s)",(d.get("funcionario_matricula"),d.get("campo"),d.get("valor_novo")));return self.responder({"sucesso":True})
    if path=="/api/rh/atestados/criar": cur.execute("INSERT INTO atestados (funcionario_matricula,data,dias) VALUES (%s,%s,%s)",(d.get("funcionario_matricula"),d.get("data"),1));return self.responder({"sucesso":True})
    if path=="/api/contratos/criar": cur.execute("INSERT INTO contratos (cliente,valor,texto,tipo) VALUES (%s,%s,%s,%s) RETURNING id",(d.get("cliente"),numero_float(d.get("valor")),"CONTRATO "+str(d.get("tipos")),str(d.get("tipos"))));nid=cur.fetchone()["id"];return self.responder({"sucesso":True,"id":nid,"texto":"CONTRATO "+str(d.get("tipos"))})
    if path=="/api/contratos/assinar": cur.execute("UPDATE contratos SET hash_assinatura=%s WHERE id=%s",("HASH"+str(d.get("id")),d.get("id")));return self.responder({"sucesso":True})
    if path=="/api/bot/responder": return self.responder({"resposta":"Ola bot"})
    if path=="/api/producao/iniciar": cur.execute("INSERT INTO producao_ordens (produto_nome,qtd_meta,responsavel_matricula,responsavel_nome,previsao_fim,custo_insumos,preco_un) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",(d.get("produto_nome"),numero_float(d.get("qtd_meta")),d.get("responsavel_matricula"),d.get("responsavel_nome"),d.get("previsao_fim") or None,numero_float(d.get("custo_insumos")),numero_float(d.get("preco_un"))));return self.responder({"sucesso":True,"id":cur.fetchone()["id"]})
    if path=="/api/producao/atualizar": cur.execute("UPDATE producao_ordens SET qtd_pronta=%s WHERE id=%s",(numero_float(d.get("qtd_pronta")),d.get("id")));return self.responder({"sucesso":True})
    if path=="/api/producao/concluir": cur.execute("UPDATE producao_ordens SET status='CONCLUIDA' WHERE id=%s",(d.get("id"),));return self.responder({"sucesso":True})
    return self.responder({"erro":"Rota "+path},404)
  except Exception as e: return self.responder({"erro":str(e)},500)

def run():
 garantir_schema();port=int(os.environ.get("PORT",8080));server=HTTPServer(("0.0.0.0",port),APIHandler);print(f"Rodando {port}",flush=True);server.serve_forever()
if __name__=="__main__": run()