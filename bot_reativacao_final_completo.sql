-- 📘 DOCUMENTO COMPLETO — Sistema de Reativação de Clientes com Bot Automatizado
-- Versão Final Consolidada | 100% Pronta para Implantação
-- Genérico: Panificadora Afonso Pena / Fruit Family / Mercado / Loja

-- ERD:
-- CUSTOMERS ||--o{ BOT_CONVERSATIONS : possui
-- LEADS ||--o{ BOT_CONVERSATIONS : possui
-- BOT_CAMPAIGNS ||--o{ BOT_CAMPAIGN_EXECUTIONS : dispara
-- BOT_CONVERSATIONS ||--o{ BOT_CAMPAIGN_EXECUTIONS : vincula
-- BOT_CONVERSATIONS ||--o{ BOT_MESSAGES : registra
-- USERS ||--o{ BOT_CONVERSATIONS : assume_atendimento

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- BOT_CAMPAIGNS
CREATE TABLE bot_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    name VARCHAR(150) NOT NULL,
    trigger_event_type VARCHAR(100) NOT NULL,
    days_inactive_trigger INT NOT NULL,
    stage VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_campaigns_trigger ON bot_campaigns(trigger_event_type, active) WHERE active = TRUE;

-- BOT_CONVERSATIONS
CREATE TABLE bot_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    customer_id UUID NULL REFERENCES customers(id) ON DELETE CASCADE,
    lead_id UUID NULL REFERENCES leads(id) ON DELETE CASCADE,
    channel VARCHAR(30) NOT NULL DEFAULT 'WHATSAPP',
    external_chat_id VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'BOT_ACTIVE',
    opt_out BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_user_id UUID NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL
);
CREATE INDEX idx_conversations_external ON bot_conversations(external_chat_id, status);
CREATE INDEX idx_conversations_customer ON bot_conversations(customer_id, lead_id);
CREATE INDEX idx_conversations_optout ON bot_conversations(opt_out) WHERE opt_out = TRUE;

-- BOT_MESSAGES
CREATE TABLE bot_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES bot_conversations(id) ON DELETE CASCADE,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('INBOUND', 'OUTBOUND')),
    message_type VARCHAR(20) NOT NULL DEFAULT 'TEXT',
    message_content TEXT NOT NULL,
    external_message_id VARCHAR(150) NULL,
    delivery_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    metadata JSONB NULL,
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_messages_conversation ON bot_messages(conversation_id, sent_at DESC);
CREATE INDEX idx_messages_status ON bot_messages(delivery_status);

-- BOT_CAMPAIGN_EXECUTIONS
CREATE TABLE bot_campaign_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES bot_campaigns(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES bot_conversations(id) ON DELETE CASCADE,
    trigger_stage VARCHAR(50) NOT NULL,
    execution_status VARCHAR(50) NOT NULL,
    error_log TEXT NULL,
    executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_executions_campaign ON bot_campaign_executions(campaign_id, executed_at DESC);
CREATE INDEX idx_executions_stage ON bot_campaign_executions(trigger_stage, execution_status);

-- IDEMPOTÊNCIA
CREATE TABLE idempotency_keys (
    event_id UUID PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result_json JSONB
);

-- FUNÇÃO BLOQUEIOS
CREATE OR REPLACE FUNCTION check_customer_can_receive_reactivation(p_customer_id UUID)
RETURNS TABLE(can_send BOOLEAN, block_reason VARCHAR) AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM financial_titles WHERE customer_id = p_customer_id AND status = 'Atrasado') THEN
    RETURN QUERY SELECT FALSE, 'BLOCKED_BY_DEBT'::VARCHAR; RETURN;
  END IF;
  IF EXISTS (SELECT 1 FROM sales_orders WHERE customer_id = p_customer_id AND status IN ('Aberto','Aprovado','Separacao','Embalagem')) THEN
    RETURN QUERY SELECT FALSE, 'PAUSED_BY_OPEN_ORDER'::VARCHAR; RETURN;
  END IF;
  IF EXISTS (SELECT 1 FROM bot_conversations WHERE customer_id = p_customer_id AND opt_out = TRUE) THEN
    RETURN QUERY SELECT FALSE, 'BLOCKED_BY_OPT_OUT'::VARCHAR; RETURN;
  END IF;
  IF EXISTS (SELECT 1 FROM bot_messages bm JOIN bot_conversations bc ON bc.id = bm.conversation_id WHERE bc.customer_id = p_customer_id AND bm.sent_at > NOW() - INTERVAL '15 days') THEN
    RETURN QUERY SELECT FALSE, 'DELAYED_BY_COOLDOWN'::VARCHAR; RETURN;
  END IF;
  RETURN QUERY SELECT TRUE, 'OK'::VARCHAR;
END;
$$ LANGUAGE plpgsql;

-- SEEDS RÉGUA 4 ETAPAS
INSERT INTO bot_campaigns (company_id, name, trigger_event_type, days_inactive_trigger, stage) VALUES
('00000000-0000-0000-0000-000000000001', 'Sondagem 30d - Reposição', 'erp.customer.reactivation_triggered', 30, 'SONDAGEM'),
('00000000-0000-0000-0000-000000000001', 'Recomendação 60d - Correlatos', 'erp.customer.reactivation_triggered', 60, 'RECOMENDACAO'),
('00000000-0000-0000-0000-000000000001', 'Incentivo 90d - Cupom', 'erp.customer.reactivation_triggered', 90, 'INCENTIVE_OFFER'),
('00000000-0000-0000-0000-000000000001', 'Feedback 120d - Última tentativa', 'erp.customer.reactivation_triggered', 120, 'FEEDBACK');
