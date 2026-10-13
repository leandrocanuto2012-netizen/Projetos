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
def garantir_schema():
 with DBConnection() as (conn,cur):
  cur.execute("CREATE TABLE IF NOT EXISTS funcionarios (id SERIAL PRIMARY KEY, matricula VARCHAR(20) UNIQUE, nome VARCHAR(100), role VARCHAR(20) DEFAULT 'operador', senha_hash VARCHAR(255), status VARCHAR(20) DEFAULT 'ATIVO', salario NUMERIC DEFAULT 1500)")
  cur.execute("CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, nome TEXT, preco_venda NUMERIC DEFAULT 0, status TEXT DEFAULT 'ATIVO')")
  cur.execute("CREATE TABLE IF NOT EXISTS vendas (id SERIAL PRIMARY KEY, cliente_nome TEXT, total NUMERIC DEFAULT 0, forma_pagamento TEXT, status TEXT DEFAULT 'CONFIRMADA', data TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS comandas (id SERIAL PRIMARY KEY, numero TEXT, cliente_nome TEXT, status TEXT DEFAULT 'ABERTA')")
  cur.execute("CREATE TABLE IF NOT EXISTS wms_estoque (id SERIAL PRIMARY KEY, produto_nome TEXT, qty NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS wms_movimentos (id SERIAL PRIMARY KEY, produto_nome TEXT, tipo TEXT, qty NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS livro_caixa (id SERIAL PRIMARY KEY, status TEXT DEFAULT 'ABERTO')")
  cur.execute("CREATE TABLE IF NOT EXISTS caixa_movimentos (id SERIAL PRIMARY KEY, tipo TEXT, valor NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS site_pedidos (id SERIAL PRIMARY KEY, cliente_nome TEXT, total NUMERIC DEFAULT 0, status TEXT DEFAULT 'SOLICITADO', forma_pagamento TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS site_config_grid (id SERIAL PRIMARY KEY, secao TEXT, nome TEXT, valor TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS contas_financeiras (id SERIAL PRIMARY KEY, tipo TEXT, pessoa TEXT, valor NUMERIC DEFAULT 0, status TEXT DEFAULT 'ABERTO')")
  cur.execute("CREATE TABLE IF NOT EXISTS contas_bancarias (id SERIAL PRIMARY KEY, banco TEXT, ag_conta TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS integracoes_config (id SERIAL PRIMARY KEY, tipo TEXT UNIQUE, provedor TEXT, api_key TEXT, ativo BOOLEAN DEFAULT FALSE)")
  cur.execute("CREATE TABLE IF NOT EXISTS notas_fiscais (id SERIAL PRIMARY KEY, tipo TEXT, numero TEXT, total NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS arquivos (id SERIAL PRIMARY KEY, categoria TEXT, nome TEXT, url TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS eventos_agenda (id SERIAL PRIMARY KEY, titulo TEXT, inicio TIMESTAMP)")
  cur.execute("CREATE TABLE IF NOT EXISTS ponto_registros (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE)")
  cur.execute("CREATE TABLE IF NOT EXISTS ponto_ajustes (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, campo TEXT, valor_novo TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS atestados (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE)")
  cur.execute("CREATE TABLE IF NOT EXISTS contratos (id SERIAL PRIMARY KEY, cliente TEXT, valor NUMERIC DEFAULT 0, texto TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS producao_ordens (id SERIAL PRIMARY KEY, produto_nome TEXT, qtd_meta NUMERIC DEFAULT 0, qtd_pronta NUMERIC DEFAULT 0, responsavel_matricula TEXT, responsavel_nome TEXT, inicio TIMESTAMPTZ DEFAULT NOW(), previsao_fim TIMESTAMPTZ, custo_insumos NUMERIC DEFAULT 0, preco_un NUMERIC DEFAULT 0, status TEXT DEFAULT 'EM_PRODUCAO')")
  cur.execute("CREATE TABLE IF NOT EXISTS frota_veiculos (id SERIAL PRIMARY KEY, placa TEXT)")
  cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
  if cur.fetchone(): cur.execute("UPDATE funcionarios SET senha_hash=%s WHERE matricula='AP-2026-0001'",(hash_senha("123"),))
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
  p=urlparse(self.path);path=p.path
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
     except: return []
    if path=="/api/health": return self.responder({"status":"ok"})
    if path=="/api/dashboard/resumo": return self.responder({"vendas_hoje":0,"vendas_mes":0,"estoque_baixo":0,"vendas_7d":[]})
    if path=="/api/gerente/alertas": return self.responder({"alertas":[]})
    if path=="/api/produtos": return self.responder({"produtos":sel("SELECT * FROM produtos LIMIT 200")})
    if path=="/api/ia-vendas/produtos":
     lst=sel("SELECT * FROM produtos WHERE status='ATIVO' LIMIT 100");return self.responder({"produtos":lst,"recomendados":lst[:6]})
    if path=="/api/vendas": return self.responder({"vendas":sel("SELECT * FROM vendas LIMIT 200")})
    if path=="/api/comandas/abertas": return self.responder({"comandas":sel("SELECT * FROM comandas WHERE status='ABERTA' LIMIT 200")})
    if path=="/api/caixa/status-online": return self.responder({"online":True,"caixas_abertos":sel("SELECT * FROM livro_caixa WHERE status='ABERTO'"),"saldo_atual":0})
    if path=="/api/wms/estoque": return self.responder({"estoque":sel("SELECT * FROM wms_estoque LIMIT 200")})
    if path=="/api/wms/movimentos": return self.responder({"movimentos":sel("SELECT * FROM wms_movimentos LIMIT 200")})
    if path=="/api/contas": return self.responder({"contas":sel("SELECT * FROM contas_financeiras LIMIT 300")})
    if path=="/api/funcionarios": return self.responder({"funcionarios":sel("SELECT matricula,nome FROM funcionarios")})
    if path=="/api/site/pedidos": return self.responder({"pedidos":sel("SELECT * FROM site_pedidos LIMIT 200")})
    if path=="/api/site/config": return self.responder({"configuracoes":[]})
    if path=="/api/bot/config": return self.responder({"config_geral":[],"regras":[]})
    if path=="/api/bancos/config": return self.responder({"configs":sel("SELECT * FROM integracoes_config"),"contas":[]})
    if path=="/api/bancos/vinculos": return self.responder({"contas":sel("SELECT * FROM contas_bancarias")})
    if path=="/api/nf_lista": return self.responder({"notas":sel("SELECT * FROM notas_fiscais LIMIT 100")})
    if path=="/api/dre_resumo": return self.responder({"receita":0,"lucro":0,"impostos":0})
    if path=="/api/arquivos_lista": return self.responder({"arquivos":sel("SELECT * FROM arquivos LIMIT 100")})
    if path=="/api/agenda_lista": return self.responder({"eventos":sel("SELECT * FROM eventos_agenda LIMIT 200")})
    if path=="/api/rh/ponto_calc": return self.responder({"ponto":sel("SELECT * FROM ponto_registros LIMIT 200"),"ajustes":[],"atestados":[]})
    if path=="/api/contratos_lista": return self.responder({"contratos":sel("SELECT * FROM contratos LIMIT 100")})
    if path=="/api/faturamento_resumo": return self.responder({"total":0,"vendas":0})
    if path=="/api/auditoria_resumo": return self.responder({"vendas":sel("SELECT id,total FROM vendas LIMIT 100"),"pedidos":[],"produtos":[]})
    if path=="/api/producao/acompanhamento": return self.responder({"ordens":sel("SELECT * FROM producao_ordens ORDER BY id DESC LIMIT 100")})
    if path=="/api/frota_lista": return self.responder({"veiculos":sel("SELECT * FROM frota_veiculos LIMIT 100")})
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
  d=self.get_body()
  try:
   with DBConnection() as (conn,cur):
    if path=="/api/login":
     cur.execute("SELECT * FROM funcionarios WHERE matricula=%s LIMIT 1",(d.get("matricula"),));u=cur.fetchone()
     if not u or u.get("senha_hash")!=hash_senha(d.get("senha")): return self.responder({"erro":"login"},401)
     u=dict(u);u.pop("senha_hash",None);return self.responder({"sucesso":True,"usuario":u})
    if path=="/api/caixa/abrir": cur.execute("INSERT INTO livro_caixa (status) VALUES ('ABERTO') RETURNING id");return self.responder({"sucesso":True,"caixa_id":cur.fetchone()['id']})
    if path=="/api/venda/criar":
     tot=sum(numero_float(i.get("total"),0) for i in (d.get("itens") or []))
     cur.execute("INSERT INTO vendas (cliente_nome,total,forma_pagamento) VALUES (%s,%s,%s) RETURNING id",(d.get("cliente_nome") or "Balcao",tot,"DINHEIRO"));return self.responder({"sucesso":True,"venda_id":cur.fetchone()['id']})
    if path=="/api/comandas/criar": cur.execute("INSERT INTO comandas (numero,status) VALUES (%s,'ABERTA') RETURNING id",("CMD"+str(random.randint(1000,9999)),));return self.responder({"sucesso":True,"numero":"CMD"})
    if path=="/api/produtos/salvar": cur.execute("INSERT INTO produtos (nome,preco_venda,status) VALUES (%s,%s,'ATIVO')",(d.get("nome"),numero_float(d.get("preco_venda"))));return self.responder({"sucesso":True})
    if path=="/api/bancos/conta": cur.execute("INSERT INTO contas_bancarias (banco,ag_conta) VALUES (%s,%s)",(d.get("banco"),d.get("ag_conta")));return self.responder({"sucesso":True})
    if path=="/api/bancos/config": cur.execute("INSERT INTO integracoes_config (tipo,provedor,api_key,ativo) VALUES (%s,%s,%s,TRUE) ON CONFLICT (tipo) DO UPDATE SET provedor=EXCLUDED.provedor",(d.get("tipo"),d.get("provedor"),d.get("api_key")));return self.responder({"sucesso":True})
    if path=="/api/boletos/gerar": return self.responder({"sucesso":True,"link":"https://boleto.teste/BL1"})
    if path=="/api/nf/criar": cur.execute("INSERT INTO notas_fiscais (tipo,numero,total) VALUES (%s,%s,%s)",(d.get("tipo"),d.get("numero"),numero_float(d.get("total"))));return self.responder({"sucesso":True})
    if path=="/api/agenda/criar": cur.execute("INSERT INTO eventos_agenda (titulo,inicio) VALUES (%s,%s)",(d.get("titulo"),d.get("inicio")));return self.responder({"sucesso":True})
    if path=="/api/rh/ponto/registrar2": cur.execute("INSERT INTO ponto_registros (funcionario_matricula,data) VALUES (%s,%s)",(d.get("funcionario_matricula"),d.get("data")));return self.responder({"sucesso":True})
    if path=="/api/contratos/criar": cur.execute("INSERT INTO contratos (cliente,valor,texto) VALUES (%s,%s,%s) RETURNING id",(d.get("cliente"),numero_float(d.get("valor")),"CONTRATO"));nid=cur.fetchone()["id"];return self.responder({"sucesso":True,"id":nid,"texto":"CONTRATO "+str(d.get("cliente"))})
    if path in ("/api/bot/responder","/api/ia-vendas/chat"):
     msg=str(d.get("mensagem") or "").lower()
     if "preco" in msg or "preço" in msg or "valor" in msg: resp="Nossos preços estão no cardápio do site. Quer que eu monte seu pedido?"
     elif "hora" in msg or "aberto" in msg or "endereco" in msg: resp="Atendemos seg a sáb 7h às 19h. Entrega pelo site."
     elif "oi" in msg or "ola" in msg or "bom" in msg: resp="Olá! Sou o bot da padaria. Quer ver pães, bolos ou fazer pedido?"
     else: resp="Entendi: "+d.get("mensagem")+". Sou o bot da padaria, posso ajudar com pedido, preço e horário."
     return self.responder({"resposta":resp})
    if path=="/api/producao/iniciar": cur.execute("INSERT INTO producao_ordens (produto_nome,qtd_meta,responsavel_matricula,responsavel_nome,previsao_fim,custo_insumos,preco_un) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",(d.get("produto_nome"),numero_float(d.get("qtd_meta")),d.get("responsavel_matricula"),d.get("responsavel_nome"),d.get("previsao_fim") or None,numero_float(d.get("custo_insumos")),numero_float(d.get("preco_un"))));return self.responder({"sucesso":True,"id":cur.fetchone()["id"]})
    if path=="/api/producao/atualizar": cur.execute("UPDATE producao_ordens SET qtd_pronta=%s WHERE id=%s",(numero_float(d.get("qtd_pronta")),d.get("id")));return self.responder({"sucesso":True})
    if path=="/api/producao/concluir": cur.execute("UPDATE producao_ordens SET status='CONCLUIDA' WHERE id=%s",(d.get("id"),));return self.responder({"sucesso":True})
    if path=="/api/frota/veiculo/criar": cur.execute("INSERT INTO frota_veiculos (placa) VALUES (%s)",(d.get("placa"),));return self.responder({"sucesso":True})
    return self.responder({"erro":"Rota "+path},404)
  except Exception as e: return self.responder({"erro":str(e)},500)
def run():
 garantir_schema();port=int(os.environ.get("PORT",8080));server=HTTPServer(("0.0.0.0",port),APIHandler);print(f"Rodando {port}",flush=True);server.serve_forever()
if __name__=="__main__": run()