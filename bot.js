// bot.js - liga no server.js sem mudar layout
const fs = require('fs');
const qrcode = require('qrcode');
const pino = require('pino');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');

const DONO = process.env.DONO_NUMERO || '5511999999999';
const NOME_LOJA = process.env.NOME_LOJA || 'Marmitaria';
const PIX = process.env.PIX || 'pix-aqui';

let sock=null, lastQR=null;
let clientes={}; let pedidos=[]; let caixa=[]; let fila=[];
try{ if(fs.existsSync('./clientes-bot.json')) clientes=JSON.parse(fs.readFileSync('./clientes-bot.json')); }catch(e){}
try{ if(fs.existsSync('./pedidos-bot.json')) pedidos=JSON.parse(fs.readFileSync('./pedidos-bot.json')); }catch(e){}
try{ if(fs.existsSync('./caixa-bot.json')) caixa=JSON.parse(fs.readFileSync('./caixa-bot.json')); }catch(e){}
try{ if(fs.existsSync('./fila-enviar.json')) fila=JSON.parse(fs.readFileSync('./fila-enviar.json')); }catch(e){}
function salvar(){ try{ fs.writeFileSync('./clientes-bot.json',JSON.stringify(clientes)); fs.writeFileSync('./pedidos-bot.json',JSON.stringify(pedidos)); fs.writeFileSync('./caixa-bot.json',JSON.stringify(caixa)); fs.writeFileSync('./fila-enviar.json',JSON.stringify(fila)); }catch(e){} }
function avisarCliente(jid,texto){ fila.push({jid,texto}); salvar(); }

function iniciarComServer(app){
  app.get('/qr', async(req,res)=>{
    if(!lastQR) return res.send('Bot ja conectado!');
    const img=await qrcode.toDataURL(lastQR);
    res.send('<h1>Escaneie no WhatsApp:</h1><img src="'+img+'" width="300"/>');
  });
  app.get('/api/bot-pedidos',(req,res)=>{
    let total=caixa.reduce((s,v)=>s+v.total,0);
    res.json({pedidos:[...pedidos].reverse(), totalCaixa:total, qtd:pedidos.length});
  });
  app.post('/api/bot-confirmar/:id',(req,res)=>{
    let o=pedidos.find(x=>x.id==req.params.id); if(!o) return res.json({ok:0});
    o.status='PREPARO'; o.tempo=(req.body&&req.body.tempo)||'30'; salvar();
    if(o.jid!=='SITE') avisarCliente(o.jid,'Ola *'+o.nome+'*! ✅ Pedido #'+o.id+' CONFIRMADO!\n⏱ Tempo: *'+o.tempo+' min*\nEstamos preparando! 🍱');
    res.json({ok:1});
  });
  app.post('/api/bot-pronto/:id',(req,res)=>{
    let o=pedidos.find(x=>x.id==req.params.id); if(!o) return res.json({ok:0});
    o.status='PRONTO'; salvar();
    if(o.jid!=='SITE') avisarCliente(o.jid,'🎉 *'+o.nome+'* pedido #'+o.id+' tá PRONTO! 🛵');
    res.json({ok:1});
  });
  app.post('/api/bot-entregue/:id',(req,res)=>{
    let o=pedidos.find(x=>x.id==req.params.id); if(!o) return res.json({ok:0});
    o.status='ENTREGUE'; caixa.push({id:o.id,cliente:o.nome,total:o.total,data:new Date().toLocaleString('pt-BR')}); salvar();
    res.json({ok:1});
  });
  // PAINEL USA SEU MESMO CSS, MESMA COR
  app.get('/painel-bot',(req,res)=>{
    res.send(`<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/estilo-padrao.css"><style>*{box-sizing:border-box}body{margin:0;font-family:Arial;background:#FFF3E8}.topo{background:#FF6A00;color:#fff;padding:20px;text-align:center}.box{max-width:500px;margin:auto;padding:12px}.card{background:#fff;border-radius:14px;padding:12px;margin-bottom:10px}button{width:100%;padding:11px;margin-top:6px;border-radius:10px;border:none;font-weight:bold}input{width:100%;padding:10px;border-radius:10px;border:1px solid #ddd;margin-top:6px}</style></head><body><div class="topo"><h2>🍱 PEDIDOS WHATSAPP</h2><div>💰 Caixa Bot: R$ <span id="t">0</span></div></div><div class="box"><div id="l">Carregando...</div></div><script>async function load(){let r=await fetch('/api/bot-pedidos');let j=await r.json();document.getElementById('t').innerText=j.totalCaixa;let h='';for(let p of j.pedidos){h+='<div class=card><b>#'+p.id+' '+p.nome+'</b> ['+p.status+']<br>'+p.itens+'<br><b>R$'+p.total+'</b> '+p.tam+' '+p.rest+'<br>'+p.end;if(p.status=='NOVO')h+='<input id=t'+p.id+' placeholder="Tempo ex 30"><button style="background:#FF6A00;color:#fff" onclick="c(\\''+p.id+'\\')">✅ OK + AVISAR TEMPO</button>';if(p.status=='PREPARO')h+='<button style="background:#25D366;color:#fff" onclick="p2(\\''+p.id+'\\')">🛵 PRONTO + AVISAR</button>';if(p.status=='PRONTO')h+='<button style="background:#111;color:#fff" onclick="e(\\''+p.id+'\\')">💰 ENTREGUE + CAIXA</button>';h+='</div>';}document.getElementById('l').innerHTML=h||'Sem pedidos';}async function c(id){let t=document.getElementById('t'+id).value||'30';await fetch('/api/bot-confirmar/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tempo:t})});load();}async function p2(id){await fetch('/api/bot-pronto/'+id,{method:'POST'});load();}async function e(id){await fetch('/api/bot-entregue/'+id,{method:'POST'});load();}load();setInterval(load,5000);</script></body></html>`);
  });
  startBot();
}

const temp={};
async function startBot(){
  const {state,saveCreds}=await useMultiFileAuthState('./auth');
  sock=makeWASocket({auth:state,logger:pino({level:'silent'}),browser:['Marmitaria','Chrome','1.0']});
  sock.ev.on('creds.update',saveCreds);
  sock.ev.on('connection.update',(u)=>{
    if(u.qr){lastQR=u.qr;console.log('QR pronto /qr');}
    if(u.connection==='open'){lastQR=null;console.log('Bot ON');}
    if(u.connection==='close'&&u.lastDisconnect?.error?.output?.statusCode!==DisconnectReason.loggedOut) startBot();
  });
  // envia fila (tempo, pronto) a cada 4s
  setInterval(async()=>{
    if(!sock||fila.length==0) return;
    let m=fila.shift(); salvar();
    try{ await sock.sendMessage(m.jid,{text:m.texto}); }catch(e){}
  },4000);

  sock.ev.on('messages.upsert',async({messages})=>{
    const m=messages[0]; if(!m.message||m.key.fromMe) return;
    const de=m.key.remoteJid; if(de.includes('@g.us')) return;
    const bruto=m.message.conversation||m.message.extendedTextMessage?.text||'';
    const texto=bruto.trim().toUpperCase();
    const resp=(t)=>sock.sendMessage(de,{text:t});
    if(!clientes[de]){
      if(!temp[de]){ temp[de]={etapa:'nome'}; await resp('Ola! Bem-vindo a *'+NOME_LOJA+'* 😊\nQual seu *NOME*?'); return; }
      let p=temp[de];
      if(p.etapa==='nome'){ p.nome=bruto.trim(); p.etapa='rest'; await resp('Prazer *'+p.nome+'*!\nRestrição?\n1-Nenhuma\n2-Sem gluten\n3-Sem lactose\n4-Vegetariano\n5-Vegano'); return; }
      if(p.etapa==='rest'){ let r=bruto.trim(); if(r==='1')r='Nenhuma'; if(r==='2')r='Sem gluten'; if(r==='3')r='Sem lactose'; if(r==='4')r='Vegetariano'; if(r==='5')r='Vegano'; p.rest=r; p.etapa='tam'; await resp('Tamanho padrão? *P / M / G*'); return; }
      if(p.etapa==='tam'){ let t=texto; if(!['P','M','G'].includes(t))t='M'; clientes[de]={nome:p.nome,rest:r2p(p.rest),tam:t,end:'',ult:null}; salvar(); temp[de]={itens:[],etapa:'esc'}; await resp('Pronto *'+p.nome+'*! ✅\n1-Frango 18\n2-Carne 20\n3-Feijoada 22\n4-Strogonoff 22\nDigite ou FINALIZAR'); return; }
    }
    function r2p(x){return x}
    let c=clientes[de];
    if(!temp[de]){ temp[de]={itens:[],etapa:'rep'}; await resp('Ola *'+c.nome+'*! Bom te ver 😍\nAinda é SEM '+c.rest+' tam '+c.tam+' IGUAL?\n1-SIM IGUAL\n2-NOVO'); return; }
    let ped=temp[de];
    if(ped.etapa==='rep'){ if(texto==='1'&&c.ult){ ped.itens=c.ult; ped.etapa='end'; await resp('Mantendo igual ✅ Entregar em '+(c.end||'?')+'? Digite OK ou novo'); return; } else{ ped.etapa='esc'; ped.itens=[]; await resp('1-Frango 18\n2-Carne 20\n3-Feijoada 22\n4-Strogonoff 22'); return; } }
    if(ped.etapa==='esc'){
      if(['1','2','3','4'].includes(texto)){ const n={'1':'Frango 18','2':'Carne 20','3':'Feijoada 22','4':'Strogonoff 22'}; const v={'1':18,'2':20,'3':22,'4':22}; ped.itens.push({nome:n[texto],valor:v[texto]}); await resp('✅ '+n[texto]+' Outro ou FINALIZAR'); return; }
      if(texto==='FINALIZAR'){ if(ped.itens.length==0){await resp('Vazio');return;} ped.etapa='end'; await resp(c.end?'Tam '+c.tam+' igual? Entregar em '+c.end+'? OK ou novo':'Manda ENDEREÇO:'); return; }
      if(['OI','OLA','MENU','CARDAPIO'].includes(texto)){ ped.etapa='rep'; await resp('Ola *'+c.nome+'*! Ainda SEM '+c.rest+' igual? 1-SIM 2-NOVO'); return; }
      await resp('Digite 1 a 4 ou FINALIZAR'); return;
    }
    if(ped.etapa==='end'){
      if((texto==='OK'||texto==='SIM')&&c.end) ped.end=c.end; else{ ped.end=bruto; c.end=bruto; salvar(); }
      ped.etapa='pag'; await resp('Pagamento? 1-PIX ('+PIX+') 2-Dinheiro 3-Cartao'); return;
    }
    if(ped.etapa==='pag'){
      let total=ped.itens.reduce((s,i)=>s+i.valor,0);
      let lista=ped.itens.map(i=>'▪️ '+i.nome).join('\n');
      let pag=texto.includes('1')?'PIX':texto.includes('2')?'Dinheiro':'Cartao';
      let id=String(Date.now()).slice(-5);
      pedidos.push({id,nome:c.nome,jid:de,itens:lista,total,tam:c.tam,rest:c.rest,end:ped.end,pag,status:'NOVO',tempo:''}); c.ult=ped.itens; salvar();
      await resp('*PEDIDO #'+id+' RECEBIDO!* 🎉\n'+lista+'\nTotal R$'+total+'\nAguarde confirmo o tempo aqui! 🙏');
      try{ await sock.sendMessage(DONO+'@s.whatsapp.net',{text:'*NOVO #'+id+'* '+c.nome+' R$'+total+'\nAbre /painel-bot'});}catch(e){}
      delete temp[de]; return;
    }
  });
}
module.exports={iniciarComServer};
