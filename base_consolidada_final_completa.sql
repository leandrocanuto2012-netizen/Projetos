-- ============================================
-- SISTEMA CONSOLIDADO FINAL - BASE ÚNICA
-- PostgreSQL 15 + pgcrypto + JSONB + UUID
-- ============================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- CORE
CREATE TABLE companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  business_type TEXT CHECK (business_type IN ('Panificadora','Mercado','Mercearia','Loja','FruitFamily')) DEFAULT 'Panificadora',
  cnpj TEXT UNIQUE,
  config JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE branches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  code TEXT NOT NULL, name TEXT NOT NULL, address JSONB
);
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id UUID REFERENCES branches(id),
  matricula TEXT UNIQUE NOT NULL, -- AP-2026-0001 ou OP-2026-0001
  name TEXT NOT NULL, role TEXT, password_hash TEXT, permissions JSONB DEFAULT '[]'
);

-- RH
CREATE TABLE employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  matricula_rh TEXT UNIQUE, -- AP-2026-0001
  admission DATE, salary NUMERIC(12,2), status TEXT DEFAULT 'ativo',
  trainings_required JSONB DEFAULT '[]'
);
CREATE TABLE employee_trainings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id),
  name TEXT, validade DATE, status TEXT
);
CREATE TABLE wms_activity_requirements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  activity TEXT, training_required TEXT
);

-- ERP GENERICO
CREATE TABLE suppliers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  name TEXT NOT NULL, cnpj TEXT, insc_estadual TEXT,
  address_abnt JSONB, -- logradouro, bairro, cep ABNT
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  name TEXT NOT NULL, cpf_cnpj TEXT,
  has_crediario BOOLEAN DEFAULT false,
  opt_out BOOLEAN DEFAULT false,
  last_purchase_at TIMESTAMPTZ,
  last_product TEXT,
  meta JSONB DEFAULT '{}'
);
CREATE TABLE product_categories (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT, type TEXT);
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  sku TEXT UNIQUE NOT NULL, -- INS-*, PROD-*, REV-*
  product_type TEXT CHECK (product_type IN ('INSUMO','PRODUTO','REVENDA')),
  name TEXT NOT NULL,
  unit TEXT DEFAULT 'KG',
  cost_price NUMERIC(12,4), sale_price NUMERIC(12,2),
  ncm TEXT, pmp NUMERIC(12,4) DEFAULT 0,
  recipe JSONB -- ficha técnica [{insumo_id,qtd}]
);
CREATE TABLE product_recipes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id),
  insumo_id UUID REFERENCES products(id),
  qtd NUMERIC(12,4), custo_estimado NUMERIC(12,2) GENERATED ALWAYS AS (qtd * 0) STORED
);
CREATE TABLE purchase_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  supplier_id UUID REFERENCES suppliers(id),
  chave_nfe TEXT CHECK (char_length(chave_nfe)=44),
  status TEXT, total NUMERIC(12,2), xml JSONB
);

-- WMS
CREATE TABLE warehouses (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), branch_id UUID REFERENCES branches(id), code TEXT, name TEXT);
CREATE TABLE warehouse_areas (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), warehouse_id UUID REFERENCES warehouses(id), code TEXT, type TEXT);
CREATE TABLE storage_locations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  area_id UUID REFERENCES warehouse_areas(id),
  code TEXT UNIQUE NOT NULL, -- A-01-01-01
  type TEXT, is_pick BOOLEAN DEFAULT true
);
CREATE TABLE inventory_stocks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id),
  location_id UUID REFERENCES storage_locations(id),
  qty NUMERIC(12,4) DEFAULT 0,
  lote TEXT, validade DATE,
  UNIQUE(product_id, location_id, lote)
);
CREATE TABLE stock_balances (
  product_id UUID PRIMARY KEY REFERENCES products(id),
  qty_fisica NUMERIC(12,4) DEFAULT 0,
  valor_financeiro NUMERIC(12,2) DEFAULT 0,
  pmp NUMERIC(12,4) DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE stock_movements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id),
  type TEXT CHECK (type IN ('ENTRADA','SAIDA','AJUSTE','TRANSFERENCIA')),
  qty NUMERIC(12,4), cost NUMERIC(12,4),
  origem TEXT, destino TEXT,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- FINANCEIRO + CAIXA
CREATE TABLE financial_titles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  customer_id UUID REFERENCES customers(id),
  type TEXT CHECK (type IN ('RECEBER','PAGAR')),
  status TEXT CHECK (status IN ('Aberto','Pago','Atrasado')),
  value NUMERIC(12,2), due_date DATE
);
CREATE TABLE cash_registers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id UUID REFERENCES branches(id),
  operator_id UUID REFERENCES users(id),
  fundo_inicial NUMERIC(12,2), opened_at TIMESTAMPTZ, closed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'ABERTO'
);
CREATE TABLE cash_movements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cash_register_id UUID REFERENCES cash_registers(id),
  type TEXT CHECK (type IN ('VENDA','SUPRIMENTO','SANGRIA','TROCO')),
  forma TEXT CHECK (forma IN ('ESPECIE','CARTAO_DEBITO','CARTAO_CREDITO','CARTAO_PARCELADO','PIX','TRANSFERENCIA','BOLETO','CREDIARIO')),
  amount NUMERIC(12,2), taxa NUMERIC(5,2) DEFAULT 0,
  operator TEXT, -- Stone/Cielo
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE sales_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  customer_id UUID REFERENCES customers(id),
  cash_register_id UUID REFERENCES cash_registers(id),
  code TEXT UNIQUE, -- OS-4589
  items JSONB, total NUMERIC(12,2), forma_pagamento TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- OPERACIONAL WMS
CREATE TABLE picking_waves (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), status TEXT DEFAULT 'CRIADA', created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE receipts (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), purchase_order_id UUID REFERENCES purchase_orders(id), status TEXT);

-- INTEGRACAO + IDEMPOTENCIA
CREATE TABLE integration_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type TEXT NOT NULL, -- erp.customer.reactivation_triggered, wms.stock.updated
  aggregate_id UUID, payload JSONB, status TEXT DEFAULT 'PENDING',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_integration_events_status ON integration_events(status);
CREATE INDEX idx_integration_events_type_gin ON integration_events USING GIN(payload);

CREATE TABLE idempotency_keys (
  event_id UUID PRIMARY KEY,
  worker_id TEXT, processed_at TIMESTAMPTZ DEFAULT now(),
  result JSONB
);


-- ============================================
-- BOT REATIVAÇÃO - 4 TABELAS + IDEMPOTENCIA
-- ============================================
CREATE TABLE bot_campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  name TEXT NOT NULL, -- Sondagem 30d
  stage TEXT CHECK (stage IN ('30d','60d','90d','120d')),
  template TEXT NOT NULL,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE bot_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID REFERENCES customers(id),
  campaign_id UUID REFERENCES bot_campaigns(id),
  status TEXT CHECK (status IN ('ATIVA','PAUSADA','FINALIZADA','BLOQUEADA')),
  last_stage TEXT, cooldown_until DATE,
  opt_out BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE bot_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES bot_conversations(id),
  direction TEXT CHECK (direction IN ('BOT','CLIENTE')),
  content TEXT, channel TEXT DEFAULT 'WHATSAPP',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE bot_campaign_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID REFERENCES bot_campaigns(id),
  customer_id UUID REFERENCES customers(id),
  conversation_id UUID REFERENCES bot_conversations(id),
  status TEXT CHECK (status IN ('ENVIADO','FALHA_TRAVAS','RESPONDIDO','BLOQUEADO')),
  trava_aplicada TEXT, -- INADIMPLENCIA, PEDIDO_ANDAMENTO, OPT_OUT, COOLDOWN
  executed_at TIMESTAMPTZ DEFAULT now(),
  idempotency_key UUID REFERENCES idempotency_keys(event_id)
);

-- TRIGGER EXEMPLO
-- Evento gerado pela rotina 02h00
-- {
--   "event_type": "erp.customer.reactivation_triggered",
--   "event_id": "a1b2c3...",
--   "aggregate_id": "customer-uuid",
--   "payload": {
--     "customer_id": "...",
--     "days_inactive": 32,
--     "last_product": "Pão Francês 5kg",
--     "stage": "30d_sondagem"
--   }
-- }


-- docker-compose.yml
version: '3.9'
services:
  postgres:
    image: postgres:15
    environment: [POSTGRES_DB=erp_consolidado, POSTGRES_USER=erp, POSTGRES_PASSWORD=erp123]
    ports: ["5432:5432"]
    volumes: ["./sql:/docker-entrypoint-initdb.d"]
    command: postgres -c max_connections=300

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api-erp:
    build: ./api-erp
    environment: DATABASE_URL=postgresql://erp:erp123@postgres/erp_consolidado
    ports: ["8000:8000"]
    depends_on: [postgres, redis]

  worker-wms:
    build: ./worker-wms
    deploy: {replicas: 3}
    environment: DATABASE_URL=postgresql://erp:erp123@postgres/erp_consolidado
    command: python worker.py --skip-locked

  bot-interno:
    build: ./bot-interno
    environment: [BOT_TYPE=INTERNO]
    depends_on: [postgres, redis]

  bot-externo:
    build: ./bot-externo
    environment: [BOT_TYPE=EXTERNO, CAMPAIGN=REATIVACAO]

  landing:
    build: ./landing
    ports: ["3000:3000"]
    environment: [NEXT_PUBLIC_API_URL=http://api-erp:8000]
