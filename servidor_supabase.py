import os
import json
import hashlib
import random
import psycopg2
import psycopg2.extras
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
load_dotenv()

def numero_float(v, pad=0.0):
    try:
        if v in (None,""): return pad
        return float(v)
    except: return pad

def hash_senha(s):
    return hashlib.sha256(str(s or "").encode()).hexdigest()

DATABASE_URI = os.environ.get("DATABASE_URI","")
def get_conn():
    if DATABASE_URI:
        c = psycopg2.connect(DATABASE_URI, connect_timeout=30)
    else:
        c = psycopg2.connect(host=os.environ.get("DB_HOST","localhost"),port=int(os.environ.get("DB_PORT",5432)),dbname=os.environ.get("DB_NAME","postgres"),user=os.environ.get("DB_USER","postgres"),password=os.environ.get("DB_PASS",""),connect_timeout=30)
    c.autocommit=False
    return c

class DBConnection:
    def __enter__(self):
        self.conn=get_conn()
        self.cur=self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self.conn,self.cur
    def __exit__(self, a,b,c):
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
        cur.execute("CREATE TABLE IF NOT EXISTS funcionarios (id SERIAL PRIMARY KEY, matricula VARCHAR(20) UNIQUE, nome VARCHAR(100), cargo VARCHAR(100), role VARCHAR(20) DEFAULT 'operador', senha_hash VARCHAR(255), permissoes TEXT DEFAULT '[]', status VARCHAR(20) DEFAULT 'ATIVO', salario NUMERIC DEFAULT 1500, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS contas_bancarias (id SERIAL PRIMARY KEY, banco TEXT, ag_conta TEXT, provedor TEXT DEFAULT 'MANUAL', item_id TEXT, saldo NUMERIC DEFAULT 0, ultimo_sync TIMESTAMP, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS integracoes_config (id SERIAL PRIMARY KEY, tipo TEXT UNIQUE, provedor TEXT, api_key TEXT, client_id TEXT, client_secret TEXT, config_extra TEXT, ativo BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS maquininhas (id SERIAL PRIMARY KEY, operadora TEXT, taxa NUMERIC DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS repasses_ifood (id SERIAL PRIMARY KEY, periodo TEXT, bruto NUMERIC DEFAULT 0, taxa NUMERIC DEFAULT 0, liquido NUMERIC DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS boletos (id SERIAL PRIMARY KEY, conta_id INT, nosso_numero TEXT, link TEXT, linha_digitavel TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, status TEXT DEFAULT 'EMITIDO', created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS notas_fiscais (id SERIAL PRIMARY KEY, tipo TEXT, numero TEXT, pessoa TEXT, total NUMERIC DEFAULT 0, total_impostos NUMERIC DEFAULT 0, aliq_icms NUMERIC DEFAULT 0, aliq_pis NUMERIC DEFAULT 0, aliq_cofins NUMERIC DEFAULT 0, aliq_iss NUMERIC DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS lancamentos_contabeis (id SERIAL PRIMARY KEY, origem TEXT, referencia_id INT, descricao TEXT, valor NUMERIC DEFAULT 0, tipo TEXT, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS arquivos (id SERIAL PRIMARY KEY, categoria TEXT, referencia TEXT, nome TEXT, url TEXT, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS eventos_agenda (id SERIAL PRIMARY KEY, titulo TEXT, inicio TIMESTAMP, fim TIMESTAMP, tipo TEXT, responsavel TEXT, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS ponto_registros (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, entrada TIME, saida TIME, pausa_min NUMERIC DEFAULT 60, horas_trabalhadas NUMERIC DEFAULT 8, horas_extras NUMERIC DEFAULT 0, status TEXT DEFAULT 'ATIVO', created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS ponto_ajustes (id SERIAL PRIMARY KEY, ponto_id INT, funcionario_matricula TEXT, data_ref DATE, campo TEXT, valor_antigo TEXT, valor_novo TEXT, motivo TEXT, status TEXT DEFAULT 'PENDENTE', created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS atestados (id SERIAL PRIMARY KEY, funcionario_matricula TEXT, data DATE, dias NUMERIC DEFAULT 1, motivo TEXT, created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS contas_financeiras (id SERIAL PRIMARY KEY, tipo TEXT, descricao TEXT, pessoa TEXT, valor NUMERIC DEFAULT 0, vencimento DATE, categoria TEXT, status TEXT DEFAULT 'ABERTO', created_at TIMESTAMP DEFAULT NOW())")
        cur.execute("SELECT id FROM funcionarios WHERE matricula='AP-2026-0001' LIMIT 1")
        if cur.fetchone():
            cur.execute("UPDATE funcionarios SET senha_hash=%s, role='admin', status='ATIVO' WHERE matricula='AP-2026-0001'",(hash_senha("123"),))
        else:
            cur.execute("INSERT INTO funcionarios (matricula,nome,cargo,role,senha_hash,status) VALUES ('AP-2026-0001','Administrador','Gerente','admin',%s,'ATIVO')",(hash_senha("123"),))
        conn.commit()
    print("Schema pronto",flush=True)

class APIHandler(BaseHTTPRequestHandler):
    def set_headers(self,s=200):
        self.send_response(s)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()
    def get_body(self):
        try:
            t=int(self.headers.get("Content-Length",0))
            b=self.rfile.read(t) if t else b"{}"
            return json.loads(b) if b else {}
        except: return {}
    def responder(self,d,s=200):
        try:
            self.set_headers(s)
            try:
                self.wfile.write(json.dumps(d,default=str,ensure_ascii=False).encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError):
                pass
            return True
        except:
            pass
    def log_message(self,f,*a): print(f"[{datetime.now().strftime('%H:%M:%S')}] {a[0]}",flush=True)
    def serve_static(self,nome,ctype):
        base=os.path.dirname(os.path.abspath(__file__))
        for pasta in (os.path.join(base,"public"),base):
            c=os.path.join(pasta,nome)
            if os.path.exists(c):
                with open(c,"rb") as f: data=f.read()
                self.send_response(200); self.send_header("Content-Type",ctype); self.end_headers()
                try:
                    self.wfile.write(data);
                except (BrokenPipeError, ConnectionResetError):
                    pass 
                return True
        return False
    def do_GET(self):
        from urllib.parse import urlparse as up, parse_qs as pq
        p=up(self.path); path=p.path; q=pq(p.query)
        if path in ("/admin","/dashboard","/dashboard.html"):
            if self.serve_static("dashboard.html","text/html; charset=utf-8"): return
            if self.serve_static("site.html","text/html; charset=utf-8"): return
            return self.responder({"erro":"html nao achado"},404)
        if path in ("/novas.js","/public/novas.js"):
            if self.serve_static("novas.js","application/javascript; charset=utf-8"): return
            return self.responder({"erro":"novas.js nao achado"},404)
        if path in ("/","/site","/site.html"):
            if self.serve_static("site.html","text/html; charset=utf-8"): return
        try:
            with DBConnection() as (conn,cur):
                def sel(sql):
                    try:
                        cur.execute(sql)
                        return [dict(r) for r in (cur.fetchall() or [])]
                    except: return []
                if path=="/api/health": return self.responder({"status":"ok"})
                if path=="/api/bancos/config":
                    return self.responder({"configs":sel("SELECT * FROM integracoes_config ORDER BY tipo"),"contas":sel("SELECT * FROM contas_bancarias ORDER BY id DESC LIMIT 100")})
                if path=="/api/bancos/vinculos":
                    return self.responder({"contas":sel("SELECT * FROM contas_bancarias ORDER BY id DESC"),"maquininhas":sel("SELECT * FROM maquininhas ORDER BY id DESC"),"ifood":sel("SELECT * FROM repasses_ifood ORDER BY id DESC")})
                if path=="/api/nf_lista": return self.responder({"notas":sel("SELECT * FROM notas_fiscais ORDER BY id DESC LIMIT 100")})
                if path=="/api/dre_resumo":
                    nfs=sel("SELECT * FROM notas_fiscais LIMIT 500")
                    rec=sum(float(n.get("total") or 0) for n in nfs if n.get("tipo")=="SAIDA")
                    imp=sum(float(n.get("total_impostos") or 0) for n in nfs if n.get("tipo")=="SAIDA")
                    cus=sum(float(n.get("total") or 0) for n in nfs if n.get("tipo")=="ENTRADA")
                    return self.responder({"receita":rec,"impostos":imp,"liq":rec-imp,"custos":cus,"lucro":rec-imp-cus})
                if path=="/api/arquivos_lista": return self.responder({"arquivos":sel("SELECT * FROM arquivos ORDER BY id DESC LIMIT 100")})
                if path=="/api/agenda_lista":
                    evs=sel("SELECT * FROM eventos_agenda ORDER BY inicio LIMIT 200")
                    ano=q.get("ano",[None])[0]; mes=q.get("mes",[None])[0]
                    if ano and mes:
                        pref=f"{ano}-{str(mes).zfill(2)}"; evs=[e for e in evs if str(e.get("inicio") or "").startswith(pref)]
                    return self.responder({"eventos":evs})
                if path=="/api/rh/ponto_calc":
                    return self.responder({"ponto":sel("SELECT * FROM ponto_registros ORDER BY data DESC LIMIT 500"),"ajustes":sel("SELECT * FROM ponto_ajustes ORDER BY id DESC LIMIT 200"),"atestados":sel("SELECT * FROM atestados ORDER BY data DESC LIMIT 200"),"funcionarios":sel("SELECT matricula,nome,salario FROM funcionarios ORDER BY nome")})
                if path=="/api/produtos":
                    if path in ("/api/ia-vendas/produtos", "/api/ia-vendas/produtos-recomendados"):
                            try:
                                cur.execute("SELECT * FROM produtos WHERE status='ATIVO' ORDER BY id DESC LIMIT 100")
                                lst = [dict(r) for r in cur.fetchall() or []]
                                return self.responder({"produtos": lst, "recomendados": lst[:6]})
                            except:
                                return self.responder({"produtos": [], "recomendados": []})
                    if path == "/api/site/config":
                        return self.responder({"configuracoes": []})
                    if path == "/api/bot/config":
                        return self.responder({"config_geral": [], "regras": []})
                        return self.responder({"produtos":sel("SELECT * FROM produtos ORDER BY id DESC LIMIT 200")})
                if path=="/api/clientes": return self.responder({"clientes":sel("SELECT * FROM clientes ORDER BY id DESC LIMIT 200")})
                if path=="/api/funcionarios": return self.responder({"funcionarios":sel("SELECT id,matricula,nome,cargo,role,status FROM funcionarios ORDER BY id DESC LIMIT 200")})
                if path=="/api/vendas": return self.responder({"vendas":sel("SELECT * FROM vendas ORDER BY id DESC LIMIT 200")})
                if path=="/api/contas": return self.responder({"contas":sel("SELECT * FROM contas_financeiras ORDER BY id DESC LIMIT 300")})
                if path=="/api/dashboard/resumo":
                    try:
                        cur.execute("SELECT COALESCE(SUM(total),0) AS t FROM vendas WHERE DATE(data)=CURRENT_DATE"); vh=float((cur.fetchone() or {}).get("t",0) or 0)
                    except: vh=0
                    return self.responder({"vendas_hoje":vh,"vendas_mes":vh,"estoque_baixo":0,"vendas_7d":[],"saldo_bancos":0,"receber_hoje":0,"pagar_hoje":0})
                if path=="/api/gerente/alertas": return self.responder({"alertas":[]})
                return self.responder({"erro":"Rota nao encontrada "+path},404)
        except Exception as e: return self.responder({"erro":str(e)},500)
    def do_POST(self):
        path=urlparse(self.path).path; d=self.get_body()
        try:
            with DBConnection() as (conn,cur):
                if path=="/api/login":
                    mat=str(d.get("matricula","")).strip(); sen=str(d.get("senha","")).strip()
                    cur.execute("SELECT * FROM funcionarios WHERE matricula=%s LIMIT 1",(mat,)); u=cur.fetchone()
                    if not u: return self.responder({"erro":"Matricula nao encontrada"},401)
                    if u.get("senha_hash")!=hash_senha(sen): return self.responder({"erro":"Senha invalida"},401)
                    if u.get("status")!="ATIVO": return self.responder({"erro":"Inativo"},403)
                    u=dict(u); u.pop("senha_hash",None)
                    return self.responder({"sucesso":True,"usuario":u})
                if path=="/api/bancos/config":
                    cur.execute("INSERT INTO integracoes_config (tipo,provedor,api_key,client_id,client_secret,config_extra,ativo) VALUES (%s,%s,%s,%s,%s,%s,TRUE) ON CONFLICT (tipo) DO UPDATE SET provedor=EXCLUDED.provedor, api_key=EXCLUDED.api_key, client_id=EXCLUDED.client_id, client_secret=EXCLUDED.client_secret, config_extra=EXCLUDED.config_extra, ativo=TRUE",(d.get("tipo"),d.get("provedor"),d.get("api_key"),d.get("client_id"),d.get("client_secret"),d.get("config_extra")))
                    return self.responder({"sucesso":True})
                if path=="/api/bancos/conta":
                    cur.execute("INSERT INTO contas_bancarias (banco,ag_conta,provedor) VALUES (%s,%s,%s)",(d.get("banco"),d.get("ag_conta"),d.get("provedor") or "MANUAL"))
                    return self.responder({"sucesso":True})
                if path=="/api/bancos/maquininha":
                    cur.execute("INSERT INTO maquininhas (operadora,taxa) VALUES (%s,%s)",(d.get("operadora"),numero_float(d.get("taxa"))))
                    return self.responder({"sucesso":True})
                if path=="/api/bancos/sync":
                    cid=d.get("conta_id"); saldo=0
                    try:
                        cur.execute("SELECT COALESCE(SUM(valor),0) AS s FROM caixa_movimentos WHERE status='APROVADO'"); saldo=float((cur.fetchone() or {}).get("s",0) or 0)
                    except: saldo=0
                    if cid:
                        cur.execute("UPDATE contas_bancarias SET saldo=%s, ultimo_sync=NOW() WHERE id=%s",(saldo,cid))
                    return self.responder({"sucesso":True,"modo":"LOCAL","saldo":saldo})
                if path=="/api/ifood/sync":
                    tot=numero_float(d.get("total"))
                    cur.execute("INSERT INTO site_pedidos (cliente_nome,telefone,forma_pagamento,total,status) VALUES (%s,%s,'IFOOD',%s,'CONFIRMADO') RETURNING id",(d.get("cliente_nome") or "Cliente iFood",d.get("telefone") or "",tot)); pid=cur.fetchone()["id"]
                    cur.execute("INSERT INTO repasses_ifood (periodo,bruto,taxa,liquido) VALUES (TO_CHAR(NOW(),'YYYY-MM'),%s,%s,%s)",(tot,tot*0.27,tot*0.73))
                    return self.responder({"sucesso":True,"pedido_id":pid})
                if path=="/api/boletos/gerar":
                    valor=numero_float(d.get("valor")); venc=d.get("vencimento"); pessoa=d.get("pessoa") or "Cliente"
                    nosso=f"BL{random.randint(10000,99999)}"; link=f"https://boleto.teste/{nosso}"; linha=f"23793.38128 60007.827136 95000.063305 1 991700000{int(valor*100)}"
                    try:
                        cur.execute("INSERT INTO contas_financeiras (tipo,descricao,pessoa,valor,vencimento,categoria,status) VALUES ('RECEBER',%s,%s,%s,%s,'BOLETO','ABERTO') RETURNING id",(d.get("descricao") or nosso,pessoa,valor,venc)); nid=cur.fetchone()["id"]
                    except: nid=None
                    cur.execute("INSERT INTO boletos (conta_id,nosso_numero,link,linha_digitavel,valor,vencimento) VALUES (%s,%s,%s,%s,%s,%s)",(nid,nosso,link,linha,valor,venc))
                    return self.responder({"sucesso":True,"link":link,"linha_digitavel":linha,"nosso_numero":nosso})
                if path=="/api/nf/criar":
                    tot=numero_float(d.get("total")); timp=tot*numero_float(d.get("aliq_icms"))/100+tot*numero_float(d.get("aliq_pis"))/100+tot*numero_float(d.get("aliq_cofins"))/100+tot*numero_float(d.get("aliq_iss"))/100
                    cur.execute("INSERT INTO notas_fiscais (tipo,numero,pessoa,total,total_impostos,aliq_icms,aliq_pis,aliq_cofins,aliq_iss) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",(d.get("tipo"),d.get("numero"),d.get("pessoa"),tot,timp,numero_float(d.get("aliq_icms")),numero_float(d.get("aliq_pis")),numero_float(d.get("aliq_cofins")),numero_float(d.get("aliq_iss")))); nid=cur.fetchone()["id"]
                    cur.execute("INSERT INTO lancamentos_contabeis (origem,referencia_id,descricao,valor,tipo) VALUES ('NF',%s,%s,%s,%s)",(nid,f"NF {d.get('tipo')} {d.get('numero')}",tot,d.get("tipo")))
                    return self.responder({"sucesso":True,"numero":d.get("numero"),"impostos":timp})
                if path=="/api/dre/simular":
                    fat=numero_float(d.get("faturamento")); cus=numero_float(d.get("custo")); reg=str(d.get("regime") or "SIMPLES").upper()
                    if reg=="SIMPLES": pis=fat*0.0065; cof=fat*0.03; icms=fat*0.034; iss=fat*0.02
                    elif reg=="PRESUMIDO": pis=fat*0.0065; cof=fat*0.03; icms=fat*numero_float(d.get("aliq_icms"),18)/100*0.3; iss=fat*numero_float(d.get("aliq_iss"),5)/100*0.32
                    else: pis=fat*0.0165; cof=fat*0.076; icms=fat*numero_float(d.get("aliq_icms"),18)/100; iss=fat*numero_float(d.get("aliq_iss"),5)/100*0.1
                    return self.responder({"pis":pis,"cofins":cof,"icms":icms,"iss":iss,"lucro":fat-(pis+cof+icms+iss)-cus})
                if path=="/api/arquivos/upload_json":
                    cur.execute("INSERT INTO arquivos (categoria,referencia,nome,url) VALUES (%s,%s,%s,%s)",(d.get("categoria"),d.get("referencia"),d.get("nome"),d.get("url")))
                    return self.responder({"sucesso":True})
                if path=="/api/agenda/criar":
                    u=d.get("usuario") or {}
                    cur.execute("INSERT INTO eventos_agenda (titulo,inicio,fim,tipo,responsavel) VALUES (%s,%s,%s,%s,%s)",(d.get("titulo"),d.get("inicio"),d.get("fim"),d.get("tipo"),u.get("matricula")))
                    return self.responder({"sucesso":True})
                if path=="/api/rh/ponto/registrar2":
                    cur.execute("INSERT INTO ponto_registros (funcionario_matricula,data,entrada,saida,horas_trabalhadas,horas_extras) VALUES (%s,%s,%s,%s,%s,%s)",(d.get("funcionario_matricula"),d.get("data"),d.get("entrada"),d.get("saida"),numero_float(d.get("horas_trabalhadas"),8),numero_float(d.get("horas_extras"),0)))
                    return self.responder({"sucesso":True})
                if path=="/api/rh/ponto/ajustar":
                    cur.execute("INSERT INTO ponto_ajustes (ponto_id,funcionario_matricula,data_ref,campo,valor_novo,motivo) VALUES (%s,%s,%s,%s,%s,%s)",(d.get("ponto_id"),d.get("funcionario_matricula"),d.get("data_ref"),d.get("campo"),str(d.get("valor_novo") or ""),d.get("motivo")))
                    return self.responder({"sucesso":True})
                if path=="/api/rh/atestados/criar":
                    cur.execute("INSERT INTO atestados (funcionario_matricula,data,dias,motivo) VALUES (%s,%s,%s,%s)",(d.get("funcionario_matricula"),d.get("data"),numero_float(d.get("dias"),1),d.get("motivo")))
                    return self.responder({"sucesso":True})
                return self.responder({"erro":"Rota nao encontrada "+path},404)
        except Exception as e: return self.responder({"erro":str(e)},500)
    def run():
        garantir_schema()
            port=int(os.environ.get("PORT",8080))
            server=HTTPServer(("0.0.0.0",port),APIHandler)
            print(f"Servidor rodando porta {port}",flush=True)
            server.serve_forever()
        if __name__=="__main__":
        run()
