require('dotenv').config();
const { Pool } = require('pg');
const axios = require('axios');
const crypto = require('crypto');

const CARDAPIO_TEXTO = `🍱 Nosso cardápio de hoje:
• Marmita P — R$ 18,90
• Marmita M — R$ 23,90
• Marmita G — R$ 28,90
🥤 Refrigerante — R$ 5,00
🧃 Suco Natural — R$ 7,50
É só dizer o que quer!`;

const PRODUTOS_BOT = [
  { id: 'p1', keywords: ['marmita p','pequena','p'], nome: 'Marmita P', preco: 18.90 },
  { id: 'p2', keywords: ['marmita m','media','média','m'], nome: 'Marmita M', preco: 23.90 },
  { id: 'p3', keywords: ['marmita g','grande','g'], nome: 'Marmita G', preco: 28.90 },
  { id: 'p4', keywords: ['refri','coca','guarana','fanta'], nome: 'Refrigerante Lata', preco: 5.00 },
  { id: 'p5', keywords: ['suco','laranja','maracuja'], nome: 'Suco Natural', preco: 7.50 },
  { id: 'p6', keywords: ['sobremesa','pudim'], nome: 'Sobremesa', preco: 8.00 }
];

function limparTel(t) { return String(t).replace(/\D/g,''); }
function carrinhoTexto(c) { return c.map(i=>`• ${i.qtd}x ${i.nome} — R$ ${(i.qtd*i.preco).toFixed(2).replace('.',',')}`).join('\n'); }
function carrinhoTotal(c) { return c.reduce((s,i)=>s+i.qtd*i.preco,0); }

function interpretarPedido(texto) {
  const t = texto.toLowerCase();
  const carrinho = [];
  const qtdMap = { um:1,uma:1,dois:2,duas:2,tres:3,três:3 };
  const regex = /(\d+|um|uma|dois|duas|tres|três)\s?([a-zçãéúíó\s]+?)(?=\s*(e|,|$|\d))/gi;
  let m;
  while ((m = regex.exec(t)) !== null) {
    const qtd = qtdMap[m[1]] || parseInt(m[1]) || 1;
    const prod = PRODUTOS_BOT.find(p => p.keywords.some(k => m[2].trim().includes(k)));
    if (prod) {
      const exist = carrinho.find(c => c.id === prod.id);
      exist ? exist.qtd += qtd : carrinho.push({...prod, qtd});
    }
  }
  if (!carrinho.length) {
    PRODUTOS_BOT.forEach(prod => {
      if (prod.keywords.some(k => t.includes(k)) && !carrinho.find(c => c.id === prod.id))
        carrinho.push({...prod, qtd:1});
    });
  }
  return carrinho;
}

const PALAVRAS_STATUS = ['pedido','status','pronto','demora','quanto tempo','ainda','a caminho','onde esta','meu pedido'];
function clientePerguntouStatus(t) { return PALAVRAS_STATUS.some(p => t.toLowerCase().includes(p)); }

function statusTexto(status, estimado) {
  const min = estimado ? Math.max(0, Math.round((new Date(estimado)-Date.now())/60000)) : null;
  switch(status) {
    case 'FILA': return `🕐 Na fila${min!==null?` — ~${min} min`:''}. Assim que começar aviso!`;
    case 'PREPARANDO': return `👨‍🍳 Preparando agora${min!==null?` — ~${min} min`:''}!`;
    case 'PRONTO': return `✅ PRONTO! Pode retirar no balcão! 🍱`;
    case 'RETIRADO': return `📦 Já retirado! Obrigado! 😊`;
    default: return `Processando...`;
  }
}

module.exports.init = function(app, pool) {

  async function enviarWhatsApp(tel, txt) {
    if (!process.env.EVO_URL) return console.log('📤 Simulado →', tel, ':', txt);
    try {
      await axios.post(`${process.env.EVO_URL}/message/sendText/${process.env.EVO_INSTANCE}`,
        { number: tel, text: txt }, { headers: { apikey: process.env.EVO_KEY } });
    } catch(e) { console.error('Erro envio:', e.message); }
  }

  async function buscarCliente(tel) {
    const r = await pool.query('SELECT * FROM customers WHERE REPLACE(phone,\' \',\'\') ILIKE $1 LIMIT 1', ['%'+limparTel(tel).slice(-8)+'%']);
    return r.rows[0];
  }

  async function cadastrarCliente(tel, nome) {
    const id = crypto.randomUUID();
    await pool.query(
      'INSERT INTO customers (id, company_id, name, phone) VALUES ($1, $2, $3, $4)',
      [id, '00000000-0000-0000-0000-000000000001', nome, tel]
    );
    return id;
  }

  async function buscarOuCriarConversa(tel, cid) {
    const r = await pool.query('SELECT * FROM bot_chat WHERE phone = $1 ORDER BY last_message_at DESC LIMIT 1', [tel]);
    if (r.rows[0]) return r.rows[0];
    const id = crypto.randomUUID();
    await pool.query(
      'INSERT INTO bot_chat (id, company_id, customer_id, phone, stage) VALUES ($1, $2, $3, $4, $5)',
      [id, '00000000-0000-0000-0000-000000000001', cid, tel, 'INICIO']
    );
    return { id, stage: 'INICIO', awaiting_name: false };
  }

  async function salvarMsg(cid, dir, txt) {
    await pool.query(
      'INSERT INTO bot_messages (id, chat_id, direction, content) VALUES ($1, $2, $3, $4)',
      [crypto.randomUUID(), cid, dir, txt]
    );
  }

  async function buscarUltimoPedido(cid, tel) {
    const r = await pool.query(`
      SELECT id, status, total_value, estimated_ready_at, created_at,
        (SELECT STRING_AGG(oi.quantity||'x '||p.name, ', ')
         FROM order_items oi JOIN products p ON oi.product_id = p.id
         WHERE oi.order_id = orders.id) AS itens
      FROM orders WHERE customer_id = $1 AND status IN ('FILA','PREPARANDO','PRONTO')
      ORDER BY created_at DESC LIMIT 1`, [cid]);
    return r.rows[0];
  }

  async function finalizarPedido(tel, cid, carrinho, nomeCli) {
    const total = carrinhoTotal(carrinho);
    const orderId = crypto.randomUUID();
    const tempo = carrinho.length * 10;
    const prontoEm = new Date(Date.now() + tempo * 60000);

    await pool.query('BEGIN');
    try {
      await pool.query(`
        INSERT INTO orders (id, company_id, customer_id, customer_name, total_value, status, estimated_ready_at)
        VALUES ($1, $2, $3, $4, $5, 'FILA', $6)`,
        [orderId, '00000000-0000-0000-0000-000000000001', cid, nomeCli, total, prontoEm]
      );
      for (const item of carrinho) {
        await pool.query(`
          INSERT INTO order_items (id, order_id, product_id, quantity, unit_price, subtotal)
          VALUES ($1, $2, $3, $4, $5, $6)`,
          [crypto.randomUUID(), orderId, item.id, item.qtd, item.preco, item.qtd*item.preco]
        );
        await pool.query('UPDATE products SET quantity_stock = quantity_stock - $1 WHERE id = $2', [item.qtd, item.id]);
      }
      await pool.query('UPDATE customers SET last_purchase_date = CURRENT_DATE WHERE id = $1', [cid]);
      await pool.query('COMMIT');
      return { orderId, total, tempo };
    } catch(e) { await pool.query('ROLLBACK'); throw e; }
  }

  // WEBHOOK PRINCIPAL
  app.post('/api/bot/webhook', async (req, res) => {
    try {
      const { data } = req.body;
      if (!data?.message) return res.json({ok:true});

      const tel = data.key.remoteJid.replace('@s.whatsapp.net','');
      const texto = (data.message.conversation || data.message.extendedTextMessage?.text || '').trim();
      if (!texto) return res.json({ok:true});

      let cliente = await buscarCliente(tel);
      const conv = await buscarOuCriarConversa(tel, cliente?.id);
      await salvarMsg(conv.id, 'ENTRADA', texto);

      let resposta;
      const confirmou = /^(sim|s|confirmo|pode|ok|certo)/i.test(texto);
      const cancelou = /^(nao|não|n|cancela|erro)/i.test(texto);

      // STATUS
      if (cliente && clientePerguntouStatus(texto)) {
        const ped = await buscarUltimoPedido(cliente.id, tel);
        resposta = ped
          ? `${cliente.name}, seu pedido:\n📦 ${ped.itens}\n${statusTexto(ped.status, ped.estimated_ready_at)}`
          : `${cliente.name}, não achei pedido ativo. Quer fazer um novo?\n${CARDAPIO_TEXTO}`;
      }
      // CADASTRAR NOME
      else if (conv.awaiting_name) {
        const nome = texto.split(' ').map(p=>p.charAt(0).toUpperCase()+p.slice(1).toLowerCase()).join(' ').slice(0,100);
        if (!cliente) cliente = {id: await cadastrarCliente(tel, nome), name: nome};
        else await pool.query('UPDATE customers SET name = $1 WHERE id = $2', [nome, cliente.id]);
        await pool.query('UPDATE bot_chat SET awaiting_name = false, stage = $1 WHERE id = $2', ['ESCOLHENDO', conv.id]);
        resposta = `Prazer, ${nome}! ✅ Cadastrado!\n\n${CARDAPIO_TEXTO}\n\nÉ só me dizer o que quer!`;
      }
      // CONFIRMAR PEDIDO
      else if (conv.cart_data && confirmou) {
        const carrinho = JSON.parse(conv.cart_data);
        const res = await finalizarPedido(tel, cliente?.id, carrinho, cliente?.name || 'Cliente');
        await pool.query('UPDATE bot_chat SET cart_data = NULL, stage = $1 WHERE id = $2', ['PEDIDO_FEITO', conv.id]);
        resposta = `✅ PEDIDO CONFIRMADO!\n\n${carrinhoTexto(carrinho)}\n\n💰 Total: R$ ${res.total.toFixed(2).replace('.',',')}\n⏱️ ~${res.tempo} min\n📦 Pedido: ${res.orderId.slice(0,8).toUpperCase()}`;
      }
      // CANCELAR
      else if (conv.cart_data && cancelou) {
        await pool.query('UPDATE bot_chat SET cart_data = NULL, stage = $1 WHERE id = $2', ['ESCOLHENDO', conv.id]);
        resposta = `Tudo bem! Pode escolher:\n${CARDAPIO_TEXTO}`;
      }
      // NOVO PEDIDO
      else if (cliente) {
        const carrinho = interpretarPedido(texto);
        if (carrinho.length) {
          const total = carrinhoTotal(carrinho);
          await pool.query('UPDATE bot_chat SET cart_data = $1, stage = $2 WHERE id = $3',
            [JSON.stringify(carrinho), 'CONFIRMANDO', conv.id]);
          resposta = `${cliente.name}, anotei:\n\n${carrinhoTexto(carrinho)}\n\n💰 Total: R$ ${total.toFixed(2).replace('.',',')}\n\n✅ Confirma? (SIM/NÃO)`;
        } else {
          resposta = `${cliente.name}, não entendi. ${CARDAPIO_TEXTO}`;
        }
      }
      // PERGUNTAR NOME
      else {
        await pool.query('UPDATE bot_chat SET awaiting_name = true, stage = $1 WHERE id = $2', ['PERGUNTANDO_NOME', conv.id]);
        resposta = `Olá! 👋 Como posso te chamar? Me diga seu nome!`;
      }

      await enviarWhatsApp(tel, resposta);
      await salvarMsg(conv.id, 'SAIDA', resposta);
      await pool.query('UPDATE bot_chat SET last_message_at = NOW() WHERE id = $1', [conv.id]);
      res.json({ok:true});
    } catch(e) {
      console.error('Erro:', e);
      res.status(500).json({erro: e.message});
    }
  });

  // Notificação quando pedido fica PRONTO
  app.patch('/api/pedidos/:id/status', async (req, res) => {
    const { status } = req.body;
    const { id } = req.params;
    await pool.query('UPDATE orders SET status = $1 WHERE id = $2', [status, id]);

    if (status === 'PRONTO') {
      const r = await pool.query(`
        SELECT c.name, c.phone FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.id = $1`, [id]);
      if (r.rows[0]?.phone) {
        await enviarWhatsApp(r.rows[0].phone,
          `Olá ${r.rows[0].name}! 🍱✅ SEU PEDIDO ESTÁ PRONTO! Pode retirar no balcão agora!`);
      }
    }
    res.json({ok:true});
  });

  console.log('🤖 Bot carregado! Webhook: /api/bot/webhook');
};