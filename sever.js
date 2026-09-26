require('dotenv').config();
const express = require('express');
const { Pool } = require('pg');
const bot = require('./bot');

const app = express();
app.use(express.json());
app.use(express.static('public'));

// Banco — pega da variável do Render/Supabase
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

// Teste de conexão
async function testar() {
  try {
    const c = await pool.connect();
    console.log('✅ Banco conectado!');
    c.release();
  } catch(e) {
    console.error('❌ Banco:', e.message);
  }
}
testar();

// Inicializa o Bot
bot.init(app, pool);

const PORTA = process.env.PORT || 3000;
app.listen(PORTA, () => {
  console.log(`🚀 Servidor: porta ${PORTA}`);
  console.log(`📡 Webhook: https://SEU-DOMINIO/api/bot/webhook`);
});