
-- ================================
-- INIT COMPLETO SUPABASE - BASE TOTAL
-- Roda inteiro no SQL Editor sem erro de customers
-- ================================

-- 1. EXTENSÕES
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. BASE - companies (precisa existir antes de tudo)
CREATE TABLE IF NOT EXISTS companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  business_type TEXT DEFAULT 'panificadora', -- panificadora | mercearia | mercado | loja
  cnpj TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO companies (id, name, business_type) VALUES 
('00000000-0000-0000-0000-000000000001', 'Panificadora Afonso Pena', 'panificadora')
ON CONFLICT (id) DO NOTHING;

-- 3. BASE - customers (que estava faltando)
CREATE TABLE IF NOT EXISTS customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  document TEXT,
  last_purchase TIMESTAMPTZ DEFAULT NOW() - INTERVAL '40 days',
  opt_out BOOLEAN DEFAULT FALSE,
  opt_out_reason TEXT,
  has_crediario BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. BASE - products
CREATE TABLE IF NOT EXISTS products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  sku TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT,
  price NUMERIC(10,2) DEFAULT 0,
  cost NUMERIC(10,2) DEFAULT 0,
  stock_qty NUMERIC(10,2) DEFAULT 0,
  active BOOLEAN DEFAULT TRUE,
  featured BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. BASE - financial_titles (para trava de inadimplência)
CREATE TABLE IF NOT EXISTS financial_titles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  customer_id UUID REFERENCES customers(id),
  type TEXT DEFAULT 'receber', -- receber | pagar
  amount NUMERIC(10,2) DEFAULT 0,
  due_date DATE,
  status TEXT DEFAULT 'Aberto', -- Aberto | Pago | Atrasado | Antecipado
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. BASE - sales_orders (para trava de pedido aberto)
CREATE TABLE IF NOT EXISTS sales_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  customer_id UUID REFERENCES customers(id),
  order_number TEXT,
  status TEXT DEFAULT 'Aberto', -- Aberto | Aprovado | Separacao | Embalado | Faturado | Cancelado
  total NUMERIC(10,2) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. BASE - site_settings (white label que altera site pelo sistema)
CREATE TABLE IF NOT EXISTS site_settings (
  company_id UUID PRIMARY KEY REFERENCES companies(id),
  company_name TEXT,
  slogan TEXT,
  logo_url TEXT,
  favicon_url TEXT,
  primary_color TEXT DEFAULT '#D97706',
  secondary_color TEXT DEFAULT '#92400E',
  bg_color TEXT DEFAULT '#FFFBEB',
  text_color TEXT DEFAULT '#1F2937',
  banners JSONB DEFAULT '[]'::jsonb,
  gallery JSONB DEFAULT '[]'::jsonb,
  contacts JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO site_settings (company_id, company_name, slogan, primary_color, secondary_color) VALUES
('00000000-0000-0000-0000-000000000001', 'Panificadora Afonso Pena', 'Pães artesanais desde 1985', '#D97706', '#92400E')
ON CONFLICT (company_id) DO NOTHING;

-- 8. BASE - integration_events + idempotency (WMS 3 réplicas SKIP LOCKED)
CREATE TABLE IF NOT EXISTS integration_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  event_type TEXT NOT NULL,
  aggregate_type TEXT,
  aggregate_id UUID,
  payload_json JSONB DEFAULT '{}'::jsonb,
  status TEXT DEFAULT 'PENDING',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  event_id UUID PRIMARY KEY,
  processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. BOT - bot_conversations (LGPD 3 níveis)
CREATE TABLE IF NOT EXISTS bot_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  customer_id UUID REFERENCES customers(id),
  channel TEXT DEFAULT 'whatsapp', -- whatsapp | teams | telegram
  status TEXT DEFAULT 'active', -- active | paused | closed
  opt_out BOOLEAN DEFAULT FALSE,
  opt_out_at TIMESTAMPTZ,
  last_message_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_optout ON bot_conversations(opt_out) WHERE opt_out = TRUE;
CREATE INDEX IF NOT EXISTS idx_conversations_customer ON bot_conversations(customer_id);

-- 10. BOT - bot_messages
CREATE TABLE IF NOT EXISTS bot_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES bot_conversations(id),
  direction TEXT DEFAULT 'out', -- in | out
  content TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  sent_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON bot_messages(sent_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON bot_messages(conversation_id);

-- 11. BOT - bot_campaigns (4 etapas)
CREATE TABLE IF NOT EXISTS bot_campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  name TEXT NOT NULL,
  trigger_event_type TEXT DEFAULT 'erp.customer.reactivation_triggered',
  days_inactive_trigger INT NOT NULL, -- 30 | 60 | 90 | 120
  stage TEXT NOT NULL, -- SONDAGEM | RECOMENDACAO | INCENTIVO | FEEDBACK
  message_template TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 12. BOT - bot_campaign_executions (log de travas)
CREATE TABLE IF NOT EXISTS bot_campaign_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  campaign_id UUID REFERENCES bot_campaigns(id),
  customer_id UUID REFERENCES customers(id),
  conversation_id UUID REFERENCES bot_conversations(id),
  status TEXT DEFAULT 'PENDING', -- PENDING | SUCCESS | BLOCKED_BY_DEBT | PAUSED_BY_OPEN_ORDER | BLOCKED_BY_OPT_OUT | DELAYED_BY_COOLDOWN | SKIPPED_BY_RESPONSE
  reason TEXT,
  executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- 13. FUNÇÃO DE TRAVAS - check_customer_can_receive_reactivation
CREATE OR REPLACE FUNCTION check_customer_can_receive_reactivation(p_customer_id UUID)
RETURNS TABLE(can_receive BOOLEAN, reason TEXT) AS $$
BEGIN
  -- Trava 1: Opt-Out LGPD
  IF EXISTS (SELECT 1 FROM bot_conversations WHERE customer_id = p_customer_id AND opt_out = TRUE) THEN
    RETURN QUERY SELECT FALSE, 'BLOCKED_BY_OPT_OUT'::TEXT; RETURN;
  END IF;

  -- Trava 2: Inadimplência
  IF EXISTS (SELECT 1 FROM financial_titles WHERE customer_id = p_customer_id AND status = 'Atrasado') THEN
    RETURN QUERY SELECT FALSE, 'BLOCKED_BY_DEBT'::TEXT; RETURN;
  END IF;

  -- Trava 3: Pedido aberto
  IF EXISTS (SELECT 1 FROM sales_orders WHERE customer_id = p_customer_id AND status IN ('Aberto','Aprovado','Separacao','Embalado')) THEN
    RETURN QUERY SELECT FALSE, 'PAUSED_BY_OPEN_ORDER'::TEXT; RETURN;
  END IF;

  -- Trava 4: Cooldown 15 dias
  IF EXISTS (SELECT 1 FROM bot_messages bm JOIN bot_conversations bc ON bc.id = bm.conversation_id WHERE bc.customer_id = p_customer_id AND bm.sent_at > NOW() - INTERVAL '15 days') THEN
    RETURN QUERY SELECT FALSE, 'DELAYED_BY_COOLDOWN'::TEXT; RETURN;
  END IF;

  RETURN QUERY SELECT TRUE, 'OK'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- 14. SEEDS RÉGUA 4 ETAPAS
DELETE FROM bot_campaigns WHERE company_id = '00000000-0000-0000-0000-000000000001';

INSERT INTO bot_campaigns (company_id, name, trigger_event_type, days_inactive_trigger, stage, message_template) VALUES
('00000000-0000-0000-0000-000000000001', 'Sondagem 30d - Reposição', 'erp.customer.reactivation_triggered', 30, 'SONDAGEM', 'Oi {{nome}}! Percebemos que seu {{produto}} deve estar acabando. Tudo bem por aí? Posso ajudar com reposição?'),
('00000000-0000-0000-0000-000000000001', 'Recomendação 60d - Correlatos', 'erp.customer.reactivation_triggered', 60, 'RECOMENDACAO', 'Oi {{nome}}! Que tal experimentar {{produtos_correlatos}}? Clientes que compram {{ultimo_produto}} adoram. Quer que eu separe?'),
('00000000-0000-0000-0000-000000000001', 'Incentivo 90d - VOLTAXX', 'erp.customer.reactivation_triggered', 90, 'INCENTIVO', 'Oi {{nome}}! Sentimos sua falta. Use VOLTAXX e ganhe 10% OFF no seu próximo pedido. Válido 48h. Posso gerar seu link?'),
('00000000-0000-0000-0000-000000000001', 'Feedback 120d - Encerramento', 'erp.customer.reactivation_triggered', 120, 'FEEDBACK', 'Oi {{nome}}! Gostaríamos do seu feedback: o que podemos melhorar? Sua opinião é importante. Depois disso encerramos por aqui. Obrigado!');

-- 15. DADOS TESTE
INSERT INTO customers (company_id, name, phone, last_purchase) VALUES
('00000000-0000-0000-0000-000000000001', 'João Teste 40 dias', '5541999999999', NOW() - INTERVAL '40 days'),
('00000000-0000-0000-0000-000000000001', 'Maria Teste 70 dias', '5541888888888', NOW() - INTERVAL '70 days')
ON CONFLICT DO NOTHING;

-- TESTE DA FUNÇÃO
-- SELECT * FROM check_customer_can_receive_reactivation((SELECT id FROM customers LIMIT 1));
