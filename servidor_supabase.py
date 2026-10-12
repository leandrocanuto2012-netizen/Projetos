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
  cur.execute("CREATE TABLE IF NOT EXISTS funcionarios (id SERIAL PRIMARY KEY, matricula VARCHAR(20) UNIQUE, nome VARCHAR(100), cargo VARCHAR(100), role VARCHAR(20) DEFAULT 'operador', senha_hash VARCHAR(255), status VARCHAR(20) DEFAULT 'ATIVO', salario NUMERIC DEFAULT 1500, created_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, nome TEXT, preco_venda NUMERIC DEFAULT 0, status TEXT DEFAULT 'ATIVO')")
  cur.execute("CREATE TABLE IF NOT EXISTS clientes (id SERIAL PRIMARY KEY, nome TEXT, telefone TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS site_config_grid (id SERIAL PRIMARY KEY, secao TEXT, nome TEXT, valor TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS site_pedidos (id SERIAL PRIMARY KEY, cliente_nome TEXT, telefone TEXT, forma_pagamento TEXT, total NUMERIC DEFAULT 0, status TEXT DEFAULT 'SOLICITADO', created_at TIMESTAMP DEFAULT NOW())")
  cur.execute("CREATE TABLE IF NOT EXISTS contas_bancarias (id SERIAL PRIMARY KEY, banco TEXT, ag_conta TEXT, provedor TEXT DEFAULT 'MANUAL', saldo NUMERIC DEFAULT 0, ultimo_sync TIMESTAMP)")
  cur.execute("CREATE TABLE IF NOT EXISTS integracoes_config (id SERIAL PRIMARY KEY, tipo TEXT UNIQUE, provedor TEXT, api_key TEXT, client_id TEXT, client_secret TEXT, config_extra TEXT, ativo BOOLEAN DEFAULT FALSE)")
  cur.execute("CREATE TABLE IF NOT EXISTS maquininhas (id SERIAL PRIMARY KEY, operadora TEXT, taxa NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS repasses_ifood (id SERIAL PRIMARY KEY, periodo TEXT, bruto NUMERIC DEFAULT 0, taxa NUMERIC DEFAULT 0, liquido NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS boletos (id SERIAL PRIMARY KEY, conta_id INT, nosso_numero TEXT, link TEXT, linha_digitavel TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, status TEXT DEFAULT 'EMITIDO')")
  cur.execute("CREATE TABLE IF NOT EXISTS notas_fiscais (id SERIAL PRIMARY KEY, tipo TEXT, numero TEXT, pessoa TEXT, total NUMERIC DEFAULT 0, total_impostos NUMERIC DEFAULT 0, aliq_icms NUMERIC DEFAULT 0, aliq_pis NUMERIC DEFAULT 0, aliq_cofins NUMERIC DEFAULT 0, aliq_iss NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS lancamentos_contabeis (id SERIAL PRIMARY KEY, origem TEXT, referencia_id INT, descricao TEXT, valor NUMERIC DEFAULT 0, tipo TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS arquivos (id SERIAL PRIMARY KEY, categoria TEXT, referencia TEXT, nome TEXT, url TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS eventos_agenda (id SERIAL PRIMARY KEY, titulo TEXT, inicio TIMESTAMP, fim TIMESTAMP, tipo TEXT, responsavel TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS ponto_registros (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, entrada TIME, saida TIME, horas_trabalhadas NUMERIC DEFAULT 8, horas_extras NUMERIC DEFAULT 0)")
  cur.execute("CREATE TABLE IF NOT EXISTS ponto_ajustes (id SERIAL PRIMARY KEY, ponto_id INT, funcionario_matricula TEXT, data_ref DATE, campo TEXT, valor_novo TEXT, motivo TEXT, status TEXT DEFAULT 'PENDENTE')")
  cur.execute("CREATE TABLE IF NOT EXISTS atestados (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, dias NUMERIC DEFAULT 1, motivo TEXT)")
  cur.execute("CREATE TABLE IF NOT EXISTS contas_financeiras (id SERIAL PRIMARY KEY, tipo TEXT, descricao TEXT, pessoa TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, categoria TEXT, status TEXT DEFAULT 'ABERTO')")
  cur.execute("CREATE TABLE IF NOT EXISTS contratos (id SERIAL PRIMARY KEY, cliente TEXT, cpf_cnpj TEXT, objeto TEXT, valor NUMERIC DEFAULT 0, prazo DATE, status TEXT DEFAULT 'RASCUNHO', tipo TEXT DEFAULT '', itens TEXT DEFAULT '', texto TEXT DEFAULT '', foro TEXT DEFAULT '', hash_assinatura TEXT, gov_cpf TEXT)")
  cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
  if cur.fetchone(): cur.execute("UPDATE funcionarios SET senha_hash=%s, role='admin', status='ATIVO' WHERE matricula='AP-2026-0001'",(hash_senha("123"),))
  else: cur.execute("INSERT INTO funcionarios (matricula,nome,cargo,role,senha_hash,status) VALUES ('AP-2026-0001','Administrador','Gerente','admin',%s,'ATIVO')",(hash_senha("123"),))
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
  try:
   t=int(self.headers.get("Content-Length",0));b=self.rfile.read(t) if t else b"{}";return json.loads(b) if b else {}
  except: return {}
 def responder(self,d,s=200):
  try:
   self.set_headers(s);self.wfile.write(json.dumps(d,default=str,ensure_ascii=False).encode("utf-8"))
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
  if path in ("/novas.js","/public/novas.js"):
   if self.serve_static("novas.js","application/javascript; charset=utf-8"): return
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
    if path=="/api/produtos": return self.responder({"produtos":sel("SELECT * FROM produtos ORDER BY id DESC LIMIT 200")})
    if path in ("/api/ia-vendas/produtos","/api/ia-vendas/produtos-recomendados"):
     lst=sel("SELECT * FROM produtos WHERE status='ATIVO' LIMIT 100");return self.responder({"produtos":lst,"recomendados":lst[:6]})
    if path=="/api/site/config": return self.responder({"configuracoes":sel("SELECT * FROM site_config_grid")})
    if path=="/api/site/pedidos": return self.responder({"pedidos":sel("SELECT * FROM site_pedidos ORDER BY id DESC LIMIT 200")})
    if path=="/api/bot/config": return self.responder({"config_geral":[],"regras":[]})
    if path=="/api/gerente/alertas": return self.responder({"alertas":[]})
    if path=="/api/clientes": return self.responder({"clientes":sel("SELECT * FROM clientes LIMIT 200")})
    if path=="/api/funcionarios": return self.responder({"funcionarios":sel("SELECT id,matricula,nome,cargo,role,status,salario FROM funcionarios")})
    if path=="/api/vendas": return self.responder({"vendas":sel("SELECT * FROM vendas ORDER BY id DESC LIMIT 200")})
    if path=="/api/contas": return self.responder({"contas":sel("SELECT * FROM contas_financeiras ORDER BY id DESC LIMIT 300")})
    if path=="/api/bancos/config": return self.responder({"configs":sel("SELECT * FROM integracoes_config"),"contas":sel("SELECT * FROM contas_bancarias")})
    if path=="/api/bancos/vinculos": return self.responder({"contas":sel("SELECT * FROM contas_bancarias"),"maquininhas":sel("SELECT * FROM maquininhas"),"ifood":sel("SELECT * FROM repasses_ifood")})
    if path=="/api/nf_lista": return self.responder({"notas":sel("SELECT * FROM notas_fiscais ORDER BY id DESC LIMIT 100")})
    if path=="/api/dre_resumo":
     nfs=sel("SELECT * FROM notas_fiscais LIMIT 500");rec=sum(float(n.get("total") or 0) for n in nfs if n.get("tipo")=="SAIDA");imp=sum(float(n.get("total_impostos") or 0) for n in nfs if n.get("tipo")=="SAIDA");cus=sum(float(n.get("total") or 0) for n in nfs if n.get("tipo")=="ENTRADA");return self.responder({"receita":rec,"impostos":imp,"liq":rec-imp,"custos":cus,"lucro":rec-imp-cus})
    if path=="/api/arquivos_lista": return self.responder({"arquivos":sel("SELECT * FROM arquivos ORDER BY id DESC LIMIT 100")})
    if path=="/api/agenda_lista": return self.responder({"eventos":sel("SELECT * FROM eventos_agenda ORDER BY inicio LIMIT 200")})
    if path=="/api/rh/ponto_calc": return self.responder({"ponto":sel("SELECT * FROM ponto_registros LIMIT 500"),"ajustes":sel("SELECT * FROM ponto_ajustes LIMIT 200"),"atestados":sel("SELECT * FROM atestados LIMIT 200"),"funcionarios":sel("SELECT matricula,nome,salario FROM funcionarios")})
    if path=="/api/dashboard/resumo": return self.responder({"vendas_hoje":0,"vendas_mes":0,"estoque_baixo":0,"vendas_7d":[],"saldo_bancos":0,"receber_hoje":0,"pagar_hoje":0})
    if path=="/api/faturamento_resumo":
     try: cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM vendas");tv=float((cur.fetchone() or {}).get("t",0) or 0)
     except: tv=0
     try: cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM site_pedidos WHERE status!='CANCELADO'");ts=float((cur.fetchone() or {}).get("t",0) or 0)
     except: ts=0
     return self.responder({"vendas":tv,"notas":0,"site":ts,"total":tv+ts})
    if path=="/api/contratos_lista": return self.responder({"contratos":sel("SELECT * FROM contratos ORDER BY id DESC LIMIT 100")})
    if path=="/api/contratos/modelos": return self.responder({"modelos":[{"id":"PRESTACAO_SERVICOS","nome":"Prestacao"},{"id":"PRODUCAO_FORNECIMENTO","nome":"Producao"},{"id":"COMPRA_VENDA","nome":"Compra/Venda"},{"id":"ARMAZENAGEM","nome":"Armazenagem"},{"id":"LOCACAO_ESPACO","nome":"Locacao"}]})
    if path=="/api/auditoria_resumo": return self.responder({"vendas":sel("SELECT id,total,status FROM vendas LIMIT 200"),"pedidos":sel("SELECT id,cliente_nome,total,status FROM site_pedidos LIMIT 200"),"produtos":sel("SELECT id,nome,status FROM produtos LIMIT 200")})
    return self.responder({"erro":"Rota nao encontrada "+path},404)
  except Exception as e: return self.responder({"erro":str(e)},500)
 def do_POST(self):
  path=urlparse(self.path).path
  if path=="/api/arquivos/upload":
   try:
    ctype=self.headers.get("Content-Type","");boundary=ctype.split("boundary=")[1].strip().strip('"').encode();length=int(self.headers.get("Content-Length",0));raw=self.rfile.read(length);parts=raw.split(b"--"+boundary)
    filedata=None;filename="arq";categoria="GERAL";referencia=""
    for part in parts:
     if b"Content-Disposition" not in part: continue
     head,_,body=part.partition(b"\r\n\r\n");body=body.rsplit(b"\r\n",1)[0];h=head.decode(errors="ignore")
     if 'name="file"' in h:
      for line in h.split(";"):
       if "filename=" in line: filename=line.split("filename=")[1].strip().strip('"').strip("'")
      filedata=body
     elif 'name="categoria"' in h: categoria=body.decode(errors="ignore").strip()
     elif 'name="referencia"' in h: referencia=body.decode(errors="ignore").strip()
    if not filedata: return self.responder({"erro":"sem arquivo"},400)
    fname=f"{uuid.uuid4().hex}{os.path.splitext(filename)[1][:10]}";base=os.path.dirname(os.path.abspath(__file__));updir=os.path.join(base,"public","uploads");os.makedirs(updir,exist_ok=True)
    open(os.path.join(updir,fname),"wb").write(filedata);url=f"/uploads/{fname}"
    with DBConnection() as (c2,cur2): cur2.execute("INSERT INTO arquivos (categoria,referencia,nome,url) VALUES (%s,%s,%s,%s)",(categoria,referencia,filename,url))
    return self.responder({"sucesso":True,"url":url})
   except Exception as e: return self.responder({"erro":str(e)},500)
  d=self.get_body()
  try:
   with DBConnection() as (conn,cur):
    if path=="/api/login":
     mat=str(d.get("matricula","")).strip();sen=str(d.get("senha","")).strip();cur.execute("SELECT * FROM funcionarios WHERE matricula=%s LIMIT 1",(mat,));u=cur.fetchone()
     if not u: return self.responder({"erro":"Matricula nao encontrada"},401)
     if u.get("senha_hash")!=hash_senha(sen): return self.responder({"erro":"Senha invalida"},401)
     u=dict(u);u.pop("senha_hash",None);return self.responder({"sucesso":True,"usuario":u})
    if path=="/api/bancos/config":
     cur.execute("INSERT INTO integracoes_config (tipo,provedor,api_key,client_id,client_secret,config_extra,ativo) VALUES (%s,%s,%s,%s,%s,%s,TRUE) ON CONFLICT (tipo) DO UPDATE SET provedor=EXCLUDED.provedor, api_key=EXCLUDED.api_key, ativo=TRUE",(d.get("tipo"),d.get("provedor"),d.get("api_key"),d.get("client_id"),d.get("client_secret"),d.get("config_extra")));return self.responder({"sucesso":True})
    if path=="/api/bancos/conta":
     cur.execute("INSERT INTO contas_bancarias (banco,ag_conta) VALUES (%s,%s)",(d.get("banco"),d.get("ag_conta")));return self.responder({"sucesso":True})
    if path=="/api/bancos/maquininha":
     cur.execute("INSERT INTO maquininhas (operadora,taxa) VALUES (%s,%s)",(d.get("operadora"),numero_float(d.get("taxa"))));return self.responder({"sucesso":True})
    if path=="/api/bancos/sync": return self.responder({"sucesso":True,"modo":"LOCAL","saldo":0})
    if path=="/api/ifood/sync":
     tot=numero_float(d.get("total"));cur.execute("INSERT INTO site_pedidos (cliente_nome,total,status,forma_pagamento) VALUES (%s,%s,'CONFIRMADO','IFOOD') RETURNING id",(d.get("cliente_nome") or "iFood",tot));pid=cur.fetchone()["id"];cur.execute("INSERT INTO repasses_ifood (periodo,bruto,taxa,liquido) VALUES (TO_CHAR(NOW(),'YYYY-MM'),%s,%s,%s)",(tot,tot*0.27,tot*0.73));return self.responder({"sucesso":True,"pedido_id":pid})
    if path=="/api/boletos/gerar":
     valor=numero_float(d.get("valor"));nosso=f"BL{random.randint(10000,99999)}";link=f"https://boleto.teste/{nosso}"
     try: cur.execute("INSERT INTO contas_financeiras (tipo,descricao,pessoa,valor,vencimento,status) VALUES ('RECEBER',%s,%s,%s,%s,'ABERTO') RETURNING id",(d.get("descricao") or nosso,d.get("pessoa"),valor,d.get("vencimento")));nid=cur.fetchone()["id"]
     except: nid=None
     cur.execute("INSERT INTO boletos (conta_id,nosso_numero,link,valor,vencimento) VALUES (%s,%s,%s,%s,%s)",(nid,nosso,link,valor,d.get("vencimento")));return self.responder({"sucesso":True,"link":link,"linha_digitavel":nosso,"nosso_numero":nosso})
    if path=="/api/nf/criar":
     tot=numero_float(d.get("total"));timp=tot*numero_float(d.get("aliq_icms"))/100+tot*numero_float(d.get("aliq_pis"))/100+tot*numero_float(d.get("aliq_cofins"))/100+tot*numero_float(d.get("aliq_iss"))/100
     cur.execute("INSERT INTO notas_fiscais (tipo,numero,pessoa,total,total_impostos) VALUES (%s,%s,%s,%s,%s) RETURNING id",(d.get("tipo"),d.get("numero"),d.get("pessoa"),tot,timp));nid=cur.fetchone()["id"];return self.responder({"sucesso":True,"impostos":timp})
    if path=="/api/dre/simular":
     fat=numero_float(d.get("faturamento"));cus=numero_float(d.get("custo"));reg=str(d.get("regime") or "SIMPLES").upper()
     if reg=="SIMPLES": pis=fat*0.0065;cof=fat*0.03;icms=fat*0.034;iss=fat*0.02
     elif reg=="PRESUMIDO": pis=fat*0.0065;cof=fat*0.03;icms=fat*0.18*0.3;iss=fat*0.05*0.32
     else: pis=fat*0.0165;cof=fat*0.076;icms=fat*0.18;iss=fat*0.005
     return self.responder({"pis":pis,"cofins":cof,"icms":icms,"iss":iss,"lucro":fat-(pis+cof+icms+iss)-cus})
    if path=="/api/arquivos/upload_json":
     cur.execute("INSERT INTO arquivos (categoria,referencia,nome,url) VALUES (%s,%s,%s,%s)",(d.get("categoria"),d.get("referencia"),d.get("nome"),d.get("url")));return self.responder({"sucesso":True})
    if path=="/api/agenda/criar":
     cur.execute("INSERT INTO eventos_agenda (titulo,inicio,fim,tipo) VALUES (%s,%s,%s,%s)",(d.get("titulo"),d.get("inicio"),d.get("fim"),d.get("tipo")));return self.responder({"sucesso":True})
    if path=="/api/rh/ponto/registrar2":
     cur.execute("INSERT INTO ponto_registros (funcionario_matricula,data,entrada,saida) VALUES (%s,%s,%s,%s)",(d.get("funcionario_matricula"),d.get("data"),d.get("entrada"),d.get("saida")));return self.responder({"sucesso":True})
    if path=="/api/rh/atestados/criar":
     cur.execute("INSERT INTO atestados (funcionario_matricula,data,dias) VALUES (%s,%s,%s)",(d.get("funcionario_matricula"),d.get("data"),numero_float(d.get("dias"),1)));return self.responder({"sucesso":True})
    if path=="/api/bot/responder": return self.responder({"resposta":"Ola! Sou o bot. Em breve WhatsApp."})
    if path=="/api/contratos/criar":
     tipos=d.get("tipos") or ["PRESTACAO_SERVICOS"];cli=d.get("cliente","");val=numero_float(d.get("valor"));txt="CONTRATO "+",".join(tipos)+" Cliente:"+cli+" Valor:"+str(val)+" "+str(d.get("objeto",""))
     if "PRESTACAO_SERVICOS" in tipos: txt+=" | Clausula Servicos Art593 CC."
     if "PRODUCAO_FORNECIMENTO" in tipos: txt+=" | Clausula Producao ANVISA."
     if "COMPRA_VENDA" in tipos: txt+=" | Clausula CompraVenda Art481."
     if "ARMAZENAGEM" in tipos: txt+=" | Clausula Armazenagem Art627."
     if "LOCACAO_ESPACO" in tipos: txt+=" | Clausula Locacao Lei8245."
     cur.execute("INSERT INTO contratos (cliente,cpf_cnpj,objeto,valor,prazo,tipo,itens,texto,foro) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",(cli,d.get("cpf_cnpj"),d.get("objeto"),val,d.get("prazo"),",".join(tipos),d.get("objeto"),txt,d.get("foro")));nid=cur.fetchone()["id"];return self.responder({"sucesso":True,"id":nid,"texto":txt})
    if path=="/api/contratos/assinar":
     import hashlib as _h;hx=_h.sha256(f"{d.get('id')}-{d.get('gov_cpf')}".encode()).hexdigest();cur.execute("UPDATE contratos SET status='ASSINADO', hash_assinatura=%s, gov_cpf=%s WHERE id=%s",(hx,d.get("gov_cpf"),d.get("id")));return self.responder({"sucesso":True,"hash":hx,"validar":"https://validar.iti.gov.br"})
    return self.responder({"erro":"Rota nao encontrada "+path},404)
  except Exception as e: return self.responder({"erro":str(e)},500)
def run():
 garantir_schema();port=int(os.environ.get("PORT",8080));server=HTTPServer(("0.0.0.0",port),APIHandler);print(f"Servidor rodando {port}",flush=True);server.serve_forever()
if __name__=="__main__": run()