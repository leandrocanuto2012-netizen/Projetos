// public/novas.js - COMPLETO - funciona com servidor HTTPServer + psycopg2
// usa: /api/bancos/vinculos /api/nf_lista /api/dre_resumo /api/arquivos_lista /api/agenda_lista /api/rh/ponto_calc

async function renderArquivos(){
  const c=document.getElementById('content');
  c.innerHTML='<h1 class="page-title">Arquivos</h1><p class="page-sub">Fotos de produtos, funcionarios e registros.</p>'
  +'<div class="card"><div class="form-grid"><div class="form-group"><label>Categoria</label><select id="arqCat"><option>PRODUTO</option><option>FUNCIONARIO</option><option>REGISTRO</option><option>NF</option></select></div>'
  +'<div class="form-group"><label>Referencia</label><input id="arqRef" placeholder="ex: pao frances"></div>'
  +'<div class="form-group"><label>Nome do arquivo</label><input id="arqNome" placeholder="foto.jpg"></div>'
  +'<div class="form-group" style="grid-column:1/-1"><label>Link URL (Storage Supabase)</label><input id="arqUrl" placeholder="https://..."></div></div>'
  +'<div class="form-actions"><button class="btn btn-primary" onclick="uploadArquivo()">Enviar</button></div></div>'
  +'<div class="card" id="arqList">Carregando...</div>';
  lucide.createIcons();
  const r=await apiGET('/api/arquivos_lista');
  document.getElementById('arqList').innerHTML=tabelaSimples(r.arquivos||[],[
    {chave:'categoria',titulo:'Categoria'},{chave:'referencia',titulo:'Ref'},
    {chave:'nome',titulo:'Arquivo'},{chave:'created_at',titulo:'Data',render:d=>new Date(d.created_at).toLocaleString('pt-BR')}
  ],d=>'<a class="btn btn-sm btn-secondary" href="'+(d.url||'#')+'" target="_blank">Abrir</a>');
  lucide.createIcons();
}
async function uploadArquivo(){
  const r=await apiPOST('/api/arquivos/upload_json',{...userPayload(),categoria:document.getElementById('arqCat').value,referencia:document.getElementById('arqRef').value,nome:document.getElementById('arqNome').value,url:document.getElementById('arqUrl').value});
  if(r.sucesso){toast('Enviado!');renderArquivos();}else toast(r.erro||'Erro','error');
}

async function renderAgenda(){
  const c=document.getElementById('content');
  c.innerHTML='<h1 class="page-title">Agenda</h1><p class="page-sub">Compromissos, producao e entregas.</p>'
  +'<div class="card"><div style="display:flex;gap:8px;align-items:center"><button class="btn btn-secondary" onclick="agendaNav(-1)">◀</button><strong id="agendaTitle" style="flex:1;text-align:center"></strong><button class="btn btn-secondary" onclick="agendaNav(1)">▶</button><button class="btn btn-primary" onclick="modalEvento()">Novo</button></div>'
  +'<div id="agendaGrid" style="display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-top:14px"></div></div><div class="card" id="agendaList"></div>';
  lucide.createIcons(); window._agendaBase=new Date(); carregarAgenda();
}
async function carregarAgenda(){
  const base=window._agendaBase; const y=base.getFullYear(), m=base.getMonth();
  document.getElementById('agendaTitle').textContent=base.toLocaleDateString('pt-BR',{month:'long',year:'numeric'});
  const r=await apiGET('/api/agenda_lista?ano='+y+'&mes='+(m+1)); const evs=r.eventos||[];
  const first=new Date(y,m,1).getDay(); const days=new Date(y,m+1,0).getDate();
  let h=''; ['Dom','Seg','Ter','Qua','Qui','Sex','Sab'].forEach(d=>h+='<div style="font-weight:700;font-size:12px;text-align:center">'+d+'</div>');
  for(let i=0;i<first;i++)h+='<div></div>';
  for(let d=1;d<=days;d++){
    const list=evs.filter(e=>new Date(e.inicio).getDate()===d);
    const iso=y+'-'+String(m+1).padStart(2,'0')+'-'+String(d).padStart(2,'0');
    h+='<div style="border:1px solid var(--border);border-radius:8px;min-height:80px;padding:6px;cursor:pointer" onclick="modalEvento(\''+iso+'\')"><div style="font-weight:700">'+d+'</div>'+list.map(e=>'<div style="font-size:11px;background:var(--accent-soft);border-radius:4px;padding:2px 4px;margin-top:2px">'+e.titulo+'</div>').join('')+'</div>';
  }
  document.getElementById('agendaGrid').innerHTML=h;
  document.getElementById('agendaList').innerHTML=tabelaSimples(evs,[{chave:'titulo',titulo:'Titulo'},{chave:'inicio',titulo:'Inicio',render:d=>new Date(d.inicio).toLocaleString('pt-BR')},{chave:'tipo',titulo:'Tipo'}]);
}
function agendaNav(d){window._agendaBase.setMonth(window._agendaBase.getMonth()+d);carregarAgenda();}
function modalEvento(data){ data=data||''; document.getElementById('modalContainer').innerHTML='<div class="modal-overlay" onclick="if(event.target===this)this.remove()"><div class="modal"><h3>Novo Evento</h3><div class="form-grid"><div class="form-group" style="grid-column:1/-1"><label>Titulo</label><input id="evTit"></div><div class="form-group"><label>Inicio</label><input id="evIni" type="datetime-local" value="'+data+'T08:00"></div><div class="form-group"><label>Fim</label><input id="evFim" type="datetime-local" value="'+data+'T09:00"></div><div class="form-group"><label>Tipo</label><select id="evTipo"><option>REUNIAO</option><option>PRODUCAO</option><option>ENTREGA</option><option>FINANCEIRO</option></select></div></div><div class="form-actions"><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Cancelar</button><button class="btn btn-primary" onclick="salvarEvento()">Salvar</button></div></div></div>'; }
async function salvarEvento(){ const r=await apiPOST('/api/agenda/criar',{...userPayload(),titulo:document.getElementById('evTit').value,inicio:document.getElementById('evIni').value,fim:document.getElementById('evFim').value,tipo:document.getElementById('evTipo').value}); if(r.sucesso){document.querySelector('.modal-overlay').remove();carregarAgenda();toast('Agendado!');}else toast(r.erro||'Erro','error'); }

async function renderBancos(){
  const c=document.getElementById('content');
  c.innerHTML='<h1 class="page-title">Vincular Bancos - Automatico</h1><p class="page-sub">Cola a chave uma vez, depois so Sincronizar.</p>'
  +'<div class="card"><div class="card-title">1. Chaves API - qualquer banco</div><div id="cfgBox">Carregando...</div>'
  +'<div class="form-grid" style="margin-top:10px"><div class="form-group"><label>Tipo</label><select id="cfgTipo"><option>BANCO</option><option>IFOOD</option><option>NF</option><option>BOLETO</option></select></div>'
  +'<div class="form-group"><label>Provedor</label><input id="cfgProv" list="listaProv" placeholder="PLUGGY, ASAAS, INTER, ITAU, FOCUS..."><datalist id="listaProv"><option>PLUGGY</option><option>ASAAS</option><option>INTER</option><option>ITAU</option><option>CIELO</option><option>IFOOD</option><option>FOCUS</option></datalist></div>'
  +'<div class="form-group"><label>API Key / Token</label><input id="cfgKey"></div><div class="form-group"><label>Client ID</label><input id="cfgCli"></div>'
  +'<div class="form-group"><label>Client Secret</label><input id="cfgSec" type="password"></div>'
  +'<div class="form-group" style="grid-column:1/-1"><label>Extra</label><input id="cfgExtra" placeholder=\'{"itemId":"..."}\'></div></div>'
  +'<div class="form-actions"><button class="btn btn-primary btn-sm" onclick="salvarCfg()">Salvar e Ativar</button></div></div>'
  +'<div class="grid-2"><div class="card"><div class="card-title">Contas + Saldo Geral</div><div id="bancoContas"></div>'
  +'<div class="form-grid" style="margin-top:10px"><div class="form-group"><label>Banco</label><input id="bcBanco"></div><div class="form-group"><label>Ag/Conta</label><input id="bcConta"></div></div>'
  +'<div class="form-actions"><button class="btn btn-secondary btn-sm" onclick="salvarBanco()">Salvar</button><button class="btn btn-primary btn-sm" onclick="syncBanco()">Sincronizar Agora</button></div></div>'
  +'<div class="card"><div class="card-title">Maquininhas + iFood</div><div id="bancoMaq"></div>'
  +'<div class="form-grid" style="margin-top:10px"><div class="form-group"><label>Operadora</label><select id="mqOp"><option>Cielo</option><option>Rede</option><option>Stone</option><option>PagSeguro</option><option>Mercado Pago</option></select></div><div class="form-group"><label>Taxa %</label><input id="mqTaxa" type="number" value="1.99"></div></div>'
  +'<div class="form-actions"><button class="btn btn-primary btn-sm" onclick="salvarMaq()">Salvar Maq</button></div><div id="ifoodBox" style="margin-top:10px"></div>'
  +'<div class="form-grid"><div class="form-group"><label>Cliente iFood</label><input id="ifCli" value="Cliente iFood"></div><div class="form-group"><label>Total</label><input id="ifBru" type="number"></div></div>'
  +'<div class="form-actions"><button class="btn btn-primary btn-sm" onclick="syncIfood()">Puxar iFood</button></div></div></div>'
  +'<div class="card"><div class="card-title">Boleto Automatico -> Contas a Receber</div><div class="form-grid"><div class="form-group"><label>Cliente</label><input id="blPessoa"></div><div class="form-group"><label>Valor</label><input id="blValor" type="number"></div><div class="form-group"><label>Vencimento</label><input id="blVenc" type="date"></div><div class="form-group"><label>Descricao</label><input id="blDesc" value="Boleto padaria"></div></div><div class="form-actions"><button class="btn btn-primary btn-sm" onclick="gerarBoleto()">Gerar Boleto</button></div><div id="blOut" style="margin-top:10px"></div></div>';
  lucide.createIcons();
  const r=await apiGET('/api/bancos/config');
  document.getElementById('cfgBox').innerHTML=tabelaSimples(r.configs||[],[{chave:'tipo',titulo:'Tipo'},{chave:'provedor',titulo:'Provedor'},{chave:'ativo',titulo:'Ativo',render:d=>d.ativo?'SIM':'NAO'}]);
  const rb=await apiGET('/api/bancos/vinculos');
  document.getElementById('bancoContas').innerHTML=tabelaSimples(rb.contas||[],[{chave:'banco',titulo:'Banco'},{chave:'saldo',titulo:'Saldo',render:d=>fmt(d.saldo)},{chave:'ultimo_sync',titulo:'Sync',render:d=>d.ultimo_sync?new Date(d.ultimo_sync).toLocaleString('pt-BR'):'-'}],d=>'<button class="btn btn-sm btn-primary" onclick="syncBanco('+d.id+')">Sync</button>');
  document.getElementById('bancoMaq').innerHTML=tabelaSimples(rb.maquininhas||[],[{chave:'operadora',titulo:'Op'},{chave:'taxa',titulo:'Taxa'}]);
  document.getElementById('ifoodBox').innerHTML=tabelaSimples(rb.ifood||[],[{chave:'periodo',titulo:'Per'},{chave:'bruto',titulo:'Bruto',render:d=>fmt(d.bruto)}]);
  window._contaSel=(rb.contas||[])[0]?.id;
}
async function salvarCfg(){ const r=await apiPOST('/api/bancos/config',{tipo:document.getElementById('cfgTipo').value,provedor:document.getElementById('cfgProv').value,api_key:document.getElementById('cfgKey').value,client_id:document.getElementById('cfgCli').value,client_secret:document.getElementById('cfgSec').value,config_extra:document.getElementById('cfgExtra').value}); if(r.sucesso){toast('Chave salva!');renderBancos();}else toast(r.erro||'Erro','error'); }
async function salvarBanco(){ const r=await apiPOST('/api/bancos/conta',{...userPayload(),banco:document.getElementById('bcBanco').value,ag_conta:document.getElementById('bcConta').value}); if(r.sucesso)renderBancos(); }
async function salvarMaq(){ const r=await apiPOST('/api/bancos/maquininha',{...userPayload(),operadora:document.getElementById('mqOp').value,taxa:document.getElementById('mqTaxa').value}); if(r.sucesso)renderBancos(); }
async function syncBanco(id){ const cid=id||window._contaSel; const r=await apiPOST('/api/bancos/sync',{conta_id:cid}); if(r.sucesso){toast('Saldo '+fmt(r.saldo)+' ('+r.modo+')');renderBancos();}else toast(r.erro||'Erro','error'); }
async function syncIfood(){ const r=await apiPOST('/api/ifood/sync',{cliente_nome:document.getElementById('ifCli').value,total:document.getElementById('ifBru').value,itens:[]}); if(r.sucesso){toast('iFood '+r.pedido_id+' lancado!');renderBancos();}else toast(r.erro||'Erro','error'); }
async function gerarBoleto(){ const r=await apiPOST('/api/boletos/gerar',{pessoa:document.getElementById('blPessoa').value,valor:document.getElementById('blValor').value,vencimento:document.getElementById('blVenc').value,descricao:document.getElementById('blDesc').value}); if(r.sucesso){document.getElementById('blOut').innerHTML='<b>'+r.nosso_numero+'</b> <a href="'+r.link+'" target="_blank">Abrir</a><br>'+r.linha_digitavel+'<br>Ja foi pra Contas a Receber!';}else toast(r.erro||'Erro','error'); }

async function renderNF(){
  const c=document.getElementById('content');
  c.innerHTML='<h1 class="page-title">NF Entrada / Saida</h1><p class="page-sub">Emite e ja contabiliza.</p>'
  +'<div class="card"><div class="form-grid"><div class="form-group"><label>Tipo</label><select id="nfTipo"><option>ENTRADA</option><option>SAIDA</option></select></div><div class="form-group"><label>Numero</label><input id="nfNum"></div><div class="form-group"><label>Pessoa</label><input id="nfPessoa"></div><div class="form-group"><label>Total</label><input id="nfTotal" type="number"></div><div class="form-group"><label>ICMS %</label><input id="nfIcms" type="number" value="18"></div><div class="form-group"><label>PIS %</label><input id="nfPis" type="number" value="1.65"></div><div class="form-group"><label>COFINS %</label><input id="nfCof" type="number" value="7.6"></div><div class="form-group"><label>ISS %</label><input id="nfIss" type="number" value="5"></div></div><div class="form-actions"><button class="btn btn-primary" onclick="salvarNF()">Emitir + Contabilizar</button></div></div><div class="card" id="nfList">Carregando...</div>';
  lucide.createIcons();
  const r=await apiGET('/api/nf_lista');
  document.getElementById('nfList').innerHTML=tabelaSimples(r.notas||[],[{chave:'tipo',titulo:'Tipo'},{chave:'numero',titulo:'No'},{chave:'pessoa',titulo:'Pessoa'},{chave:'total',titulo:'Total',render:d=>fmt(d.total)},{chave:'total_impostos',titulo:'Imp.',render:d=>fmt(d.total_impostos)}]);
  lucide.createIcons();
}
async function salvarNF(){ const r=await apiPOST('/api/nf/criar',{...userPayload(),tipo:document.getElementById('nfTipo').value,numero:document.getElementById('nfNum').value,pessoa:document.getElementById('nfPessoa').value,total:document.getElementById('nfTotal').value,aliq_icms:document.getElementById('nfIcms').value,aliq_pis:document.getElementById('nfPis').value,aliq_cofins:document.getElementById('nfCof').value,aliq_iss:document.getElementById('nfIss').value}); if(r.sucesso){toast('NF contabilizada! '+fmt(r.impostos));renderNF();}else toast(r.erro||'Erro','error'); }

async function renderDRE(){
  const c=document.getElementById('content'); const mes=new Date().toISOString().slice(0,7);
  c.innerHTML='<h1 class="page-title">DRE + Simulador</h1><p class="page-sub">PIS, COFINS, ICMS, ISS</p>'
  +'<div class="grid-2"><div class="card"><div class="card-title">DRE Real</div><div class="form-group"><label>Competencia</label><input id="dreComp" type="month" value="'+mes+'"></div><div class="form-actions" style="justify-content:flex-start"><button class="btn btn-primary btn-sm" onclick="carregarDRE()">Gerar</button></div><div id="dreOut"></div></div>'
  +'<div class="card"><div class="card-title">Simulador</div><div class="form-grid"><div class="form-group"><label>Regime</label><select id="simReg"><option>SIMPLES</option><option>PRESUMIDO</option><option>REAL</option></select></div><div class="form-group"><label>Faturamento</label><input id="simFat" type="number" value="100000"></div><div class="form-group"><label>Custo</label><input id="simCus" type="number" value="40000"></div><div class="form-group"><label>ICMS %</label><input id="simIcms" type="number" value="18"></div><div class="form-group"><label>ISS %</label><input id="simIss" type="number" value="5"></div></div><div class="form-actions" style="justify-content:flex-start"><button class="btn btn-primary btn-sm" onclick="simular()">Simular</button></div><div id="simOut"></div></div></div>';
  lucide.createIcons();
}
async function carregarDRE(){ const r=await apiGET('/api/dre_resumo?comp='+document.getElementById('dreComp').value); document.getElementById('dreOut').innerHTML='<table class="data-table"><tr><td>Receita</td><td style="text-align:right">'+fmt(r.receita)+'</td></tr><tr><td>Impostos</td><td style="text-align:right;color:red">-'+fmt(r.impostos)+'</td></tr><tr><td>Liquida</td><td style="text-align:right"><b>'+fmt(r.liq)+'</b></td></tr><tr><td>Custos</td><td style="text-align:right;color:red">-'+fmt(r.custos)+'</td></tr><tr><td><b>Lucro</b></td><td style="text-align:right"><b>'+fmt(r.lucro)+'</b></td></tr></table>'; }
async function simular(){ const r=await apiPOST('/api/dre/simular',{regime:document.getElementById('simReg').value,faturamento:document.getElementById('simFat').value,custo:document.getElementById('simCus').value,aliq_icms:document.getElementById('simIcms').value,aliq_iss:document.getElementById('simIss').value}); document.getElementById('simOut').innerHTML='PIS '+fmt(r.pis)+' | COFINS '+fmt(r.cofins)+' | ICMS '+fmt(r.icms)+' | ISS '+fmt(r.iss)+'<br><b>Lucro '+fmt(r.lucro)+'</b>'; }

async function renderPonto(){
  const c=document.getElementById('content'); const mes=new Date().toISOString().slice(0,7);
  c.innerHTML='<h1 class="page-title">Ponto Eletronico</h1><p class="page-sub">Ajuste, atestado e calculo com valor a repassar.</p>'
  +'<div class="card"><div class="form-grid"><div class="form-group"><label>Mes</label><input id="ptFiltroMes" type="month" value="'+mes+'"></div><div class="form-group"><label>Funcionario</label><select id="ptFiltroFunc"><option value="">Todos (geral)</option></select></div><div class="form-group"><label>Valor hora padrao</label><input id="ptValorHora" type="number" value="10"></div></div>'
  +'<div class="form-actions" style="justify-content:flex-start"><button class="btn btn-primary btn-sm" onclick="carregarDadosPonto()">Calcular</button> <button class="btn btn-secondary btn-sm" onclick="modalPonto()">Registrar Ponto</button> <button class="btn btn-secondary btn-sm" onclick="modalAtestado()">Atestado</button></div><div id="ptResumo" style="margin-top:14px"></div></div>'
  +'<div class="card"><div class="card-title">Detalhamento</div><div id="ptDetalhe" style="margin-top:10px"></div></div>'
  +'<div class="grid-2"><div class="card"><div class="card-title">Atestados</div><div id="ptAtest"></div></div><div class="card"><div class="card-title">Ajustes Pendentes</div><div id="ptAjust"></div></div></div>';
  carregarDadosPonto();
}
async function carregarDadosPonto(){
  const mes=(document.getElementById('ptFiltroMes')||{}).value||new Date().toISOString().slice(0,7);
  const matFiltro=(document.getElementById('ptFiltroFunc')||{}).value||'';
  const valorHoraPadrao=parseFloat(document.getElementById('ptValorHora').value||10);
  const r=await apiGET('/api/rh/ponto_calc');
  const pontos=(r.ponto||[]).filter(p=>(p.data||'').startsWith(mes) && (!matFiltro || p.funcionario_matricula===matFiltro));
  const funcs=r.funcionarios||[];
  const sel=document.getElementById('ptFiltroFunc');
  if(sel && sel.options.length<=1){ funcs.forEach(f=>{ const o=document.createElement('option'); o.value=f.matricula; o.textContent=(f.nome||f.matricula)+' - '+f.matricula; sel.appendChild(o); }); if(matFiltro) sel.value=matFiltro; }
  const mapaSal={}; funcs.forEach(f=>mapaSal[f.matricula]=parseFloat(f.salario||0));
  const grupo={};
  pontos.forEach(p=>{ const m=p.funcionario_matricula||'SEM'; if(!grupo[m]) grupo[m]={mat:m,horas:0,extras:0,qtd:0}; grupo[m].horas+=parseFloat(p.horas_trabalhadas||0); grupo[m].extras+=parseFloat(p.horas_extras||0); grupo[m].qtd+=1; });
  let totH=0, totE=0, totV=0; let htmlRes='<table class="data-table"><thead><tr><th>Mat</th><th>Horas</th><th>Extras</th><th>Vlr Hora</th><th>A Repassar</th><th></th></tr></thead><tbody>';
  Object.values(grupo).forEach(g=>{ const sal=mapaSal[g.mat]||0; const vh=sal>0? sal/220 : valorHoraPadrao; const valor=(g.horas*vh)+(g.extras*vh*1.5); totH+=g.horas; totE+=g.extras; totV+=valor; htmlRes+='<tr><td>'+g.mat+'</td><td>'+g.horas.toFixed(2)+'</td><td>'+g.extras.toFixed(2)+'</td><td>'+fmt(vh)+'</td><td><b>'+fmt(valor)+'</b></td><td><button class="btn btn-sm btn-secondary" onclick="modalAjustePonto(\''+g.mat+'\')">Ajustar</button></td></tr>'; });
  htmlRes+='</tbody></table><div style="margin-top:10px;padding:12px;background:var(--accent-soft);border-radius:8px;font-weight:700">GERAL '+mes+': Horas '+totH.toFixed(2)+' | Extras '+totE.toFixed(2)+' | TOTAL '+fmt(totV)+'</div>';
  if(!Object.keys(grupo).length) htmlRes='<p style="color:var(--muted)">Sem pontos neste mes.</p>';
  document.getElementById('ptResumo').innerHTML=htmlRes;
  document.getElementById('ptDetalhe').innerHTML=tabelaSimples(pontos,[{chave:'data',titulo:'Data'},{chave:'funcionario_matricula',titulo:'Mat'},{chave:'entrada',titulo:'Ent'},{chave:'saida',titulo:'Sai'},{chave:'horas_trabalhadas',titulo:'Horas'},{chave:'horas_extras',titulo:'Extras'}],d=>'<button class="btn btn-sm btn-secondary" onclick="modalAjustePonto(\''+d.funcionario_matricula+'\','+d.id+',\''+d.data+'\')">Ajustar</button>');
  document.getElementById('ptAtest').innerHTML=tabelaSimples((r.atestados||[]).filter(a=>(a.data||'').startsWith(mes)),[{chave:'funcionario_matricula',titulo:'Mat'},{chave:'data',titulo:'Data'},{chave:'dias',titulo:'Dias'},{chave:'motivo',titulo:'Motivo'}]);
  const pend=(r.ajustes||[]).filter(a=>a.status==='PENDENTE');
  document.getElementById('ptAjust').innerHTML=tabelaSimples(pend,[{chave:'funcionario_matricula',titulo:'Mat'},{chave:'campo',titulo:'Campo'},{chave:'valor_novo',titulo:'Novo'},{chave:'motivo',titulo:'Motivo'}]);
}
function modalPonto(){ document.getElementById('modalContainer').innerHTML='<div class="modal-overlay" onclick="if(event.target===this)this.remove()"><div class="modal"><h3>Registrar Ponto</h3><div class="form-grid"><div class="form-group"><label>Matricula</label><input id="ptMat"></div><div class="form-group"><label>Data</label><input id="ptData" type="date" value="'+new Date().toISOString().slice(0,10)+'"></div><div class="form-group"><label>Entrada</label><input id="ptEnt" type="time" value="08:00"></div><div class="form-group"><label>Saida</label><input id="ptSai" type="time" value="17:00"></div><div class="form-group"><label>Horas</label><input id="ptHoras" type="number" value="8"></div><div class="form-group"><label>Extras</label><input id="ptExt" type="number" value="0"></div></div><div class="form-actions"><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Cancelar</button><button class="btn btn-primary" onclick="salvarPonto()">Salvar</button></div></div></div>'; }
async function salvarPonto(){ const r=await apiPOST('/api/rh/ponto/registrar2',{...userPayload(),funcionario_matricula:document.getElementById('ptMat').value,data:document.getElementById('ptData').value,entrada:document.getElementById('ptEnt').value,saida:document.getElementById('ptSai').value,horas_trabalhadas:document.getElementById('ptHoras').value,horas_extras:document.getElementById('ptExt').value}); if(r.sucesso){document.querySelector('.modal-overlay').remove();carregarDadosPonto();toast('Salvo!');}else toast(r.erro||'Erro','error'); }
function modalAjustePonto(mat,ponto_id,data){ ponto_id=ponto_id||''; data=data||''; document.getElementById('modalContainer').innerHTML='<div class="modal-overlay" onclick="if(event.target===this)this.remove()"><div class="modal"><h3>Ajustar '+mat+'</h3><div class="form-grid"><div class="form-group"><label>Campo</label><select id="ajCampo"><option>entrada</option><option>saida</option><option>horas_trabalhadas</option><option>horas_extras</option></select></div><div class="form-group"><label>Valor novo</label><input id="ajNovo"></div><div class="form-group" style="grid-column:1/-1"><label>Motivo</label><input id="ajMot"></div></div><div class="form-actions"><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Cancelar</button><button class="btn btn-primary" onclick="salvarAjuste(\''+mat+'\','+(ponto_id===''?'null':ponto_id)+',\''+data+'\')">Solicitar</button></div></div></div>'; }
async function salvarAjuste(mat,ponto_id,data){ const r=await apiPOST('/api/rh/ponto/ajustar',{...userPayload(),ponto_id:ponto_id,funcionario_matricula:mat,data_ref:data,campo:document.getElementById('ajCampo').value,valor_novo:document.getElementById('ajNovo').value,motivo:document.getElementById('ajMot').value}); if(r.sucesso){document.querySelector('.modal-overlay').remove();carregarDadosPonto();toast('Ajuste enviado!');} }
function modalAtestado(){ document.getElementById('modalContainer').innerHTML='<div class="modal-overlay" onclick="if(event.target===this)this.remove()"><div class="modal"><h3>Atestado</h3><div class="form-grid"><div class="form-group"><label>Matricula</label><input id="atMat"></div><div class="form-group"><label>Data</label><input id="atData" type="date" value="'+new Date().toISOString().slice(0,10)+'"></div><div class="form-group"><label>Dias</label><input id="atDias" type="number" value="1"></div><div class="form-group"><label>Motivo</label><input id="atMot"></div></div><div class="form-actions"><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Cancelar</button><button class="btn btn-primary" onclick="salvarAtestado()">Salvar</button></div></div></div>'; }
async function salvarAtestado(){ const r=await apiPOST('/api/rh/atestados/criar',{...userPayload(),funcionario_matricula:document.getElementById('atMat').value,data:document.getElementById('atData').value,dias:document.getElementById('atDias').value,motivo:document.getElementById('atMot').value}); if(r.sucesso){document.querySelector('.modal-overlay').remove();carregarDadosPonto();toast('Salvo!');} }