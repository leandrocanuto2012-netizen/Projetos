-- =====================================================
-- PANIFICADORA ERP - SUPABASE (PostgreSQL)
-- Cole tudo no SQL Editor do Supabase e execute.
-- =====================================================

-- TABELAS

CREATE TABLE IF NOT EXISTS fornecedores (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(200) NOT NULL,
  cnpj VARCHAR(30),
  telefone VARCHAR(30),
  email VARCHAR(120),
  endereco TEXT,
  status VARCHAR(20) DEFAULT 'ATIVO',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS produtos (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(200) NOT NULL,
  sku VARCHAR(50) UNIQUE,
  categoria VARCHAR(80),
  preco_venda NUMERIC(12,2) DEFAULT 0,
  custo NUMERIC(12,2) DEFAULT 0,
  unidade VARCHAR(10) DEFAULT 'UN',
  estoque_minimo NUMERIC(10,3) DEFAULT 0,
  prateleira VARCHAR(50),
  status VARCHAR(20) DEFAULT 'ATIVO',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clientes (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(200) NOT NULL,
  cpf_cnpj VARCHAR(30),
  telefone VARCHAR(30),
  email VARCHAR(120),
  endereco TEXT,
  status VARCHAR(20) DEFAULT 'ATIVO',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS funcionarios (
  id SERIAL PRIMARY KEY,
  matricula VARCHAR(20) UNIQUE NOT NULL,
  nome VARCHAR(200) NOT NULL,
  cargo VARCHAR(100),
  role VARCHAR(30) DEFAULT 'operador',
  senha_hash VARCHAR(64),
  permissoes TEXT,
  status VARCHAR(20) DEFAULT 'ATIVO',
  salario NUMERIC(12,2) DEFAULT 0,
  telefone VARCHAR(30),
  email VARCHAR(120),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS livro_caixa (
  id SERIAL PRIMARY KEY,
  status VARCHAR(20) DEFAULT 'ABERTO',
  operator_matricula VARCHAR(20),
  fundo_inicial NUMERIC(12,2) DEFAULT 0,
  valor_fechamento NUMERIC(12,2),
  observacao_fechamento TEXT,
  data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  closed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS caixa_movimentos (
  id SERIAL PRIMARY KEY,
  caixa_id INT,
  tipo VARCHAR(30) NOT NULL,
  valor NUMERIC(12,2) NOT NULL DEFAULT 0,
  descricao VARCHAR(255),
  status VARCHAR(20) DEFAULT 'APROVADO',
  operator_matricula VARCHAR(20),
  autorizado_por VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS autorizacoes (
  id SERIAL PRIMARY KEY,
  tipo VARCHAR(40) NOT NULL,
  referencia_tabela VARCHAR(40),
  referencia_id INT,
  valor NUMERIC(12,2) DEFAULT 0,
  motivo VARCHAR(255),
  solicitado_por VARCHAR(20),
  aprovado_por VARCHAR(20),
  status VARCHAR(20) DEFAULT 'PENDENTE',
  payload TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  decidido_em TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comandas (
  id SERIAL PRIMARY KEY,
  numero VARCHAR(30) UNIQUE NOT NULL,
  qr_payload VARCHAR(255),
  cliente_nome VARCHAR(200),
  cliente_documento VARCHAR(50),
  status VARCHAR(20) DEFAULT 'ABERTA',
  funcionario_entrada VARCHAR(20),
  funcionario_saida VARCHAR(20),
  funcionario_pagamento VARCHAR(20),
  caixa_id INT,
  venda_id INT,
  total NUMERIC(12,2) DEFAULT 0,
  entrada_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  pago_at TIMESTAMP,
  saida_at TIMESTAMP,
  observacao TEXT
);

CREATE TABLE IF NOT EXISTS comanda_itens (
  id SERIAL PRIMARY KEY,
  comanda_id INT NOT NULL,
  product_id INT,
  produto_nome VARCHAR(200),
  sku VARCHAR(50),
  prateleira VARCHAR(50),
  qty NUMERIC(10,3) DEFAULT 1,
  unit_price NUMERIC(10,2) DEFAULT 0,
  total NUMERIC(12,2) DEFAULT 0,
  funcionario_matricula VARCHAR(20),
  plataforma VARCHAR(50) DEFAULT 'loja',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rh_ferias (
  id SERIAL PRIMARY KEY,
  funcionario_matricula VARCHAR(20) NOT NULL,
  inicio DATE NOT NULL,
  fim DATE NOT NULL,
  dias INT DEFAULT 0,
  status VARCHAR(20) DEFAULT 'PENDENTE',
  observacao TEXT,
  solicitado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  validado_por VARCHAR(20),
  validado_em TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rh_ponto (
  id SERIAL PRIMARY KEY,
  funcionario_matricula VARCHAR(20) NOT NULL,
  data DATE NOT NULL,
  entrada TIME,
  saida TIME,
  pausa_min INT DEFAULT 0,
  horas_trabalhadas NUMERIC(6,2) DEFAULT 0,
  horas_extras NUMERIC(6,2) DEFAULT 0,
  banco_horas NUMERIC(6,2) DEFAULT 0,
  falta BOOLEAN DEFAULT FALSE,
  producao_qtd NUMERIC(10,2) DEFAULT 0,
  observacao TEXT,
  registrado_por VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rh_holerites (
  id SERIAL PRIMARY KEY,
  funcionario_matricula VARCHAR(20) NOT NULL,
  competencia VARCHAR(7) NOT NULL,
  salario_base NUMERIC(12,2) DEFAULT 0,
  horas_extras_valor NUMERIC(12,2) DEFAULT 0,
  premios NUMERIC(12,2) DEFAULT 0,
  plr NUMERIC(12,2) DEFAULT 0,
  descontos NUMERIC(12,2) DEFAULT 0,
  inss NUMERIC(12,2) DEFAULT 0,
  fgts NUMERIC(12,2) DEFAULT 0,
  plano_saude NUMERIC(12,2) DEFAULT 0,
  sindicato NUMERIC(12,2) DEFAULT 0,
  ajustes_fiscais NUMERIC(12,2) DEFAULT 0,
  liquido NUMERIC(12,2) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'ABERTO',
  observacao TEXT,
  criado_por VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rh_eventos (
  id SERIAL PRIMARY KEY,
  funcionario_matricula VARCHAR(20) NOT NULL,
  tipo VARCHAR(40) NOT NULL,
  titulo VARCHAR(120),
  descricao TEXT,
  valor NUMERIC(12,2) DEFAULT 0,
  data_inicio DATE,
  data_fim DATE,
  status VARCHAR(20) DEFAULT 'REGISTRADO',
  anexo_nome VARCHAR(255),
  anexo_ref VARCHAR(255),
  criado_por VARCHAR(20),
  validado_por VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  validado_em TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wms_movimentos (
  id SERIAL PRIMARY KEY,
  product_id INT,
  sku VARCHAR(50),
  produto_nome VARCHAR(200),
  tipo VARCHAR(20) DEFAULT 'ENTRADA',
  qty NUMERIC(10,3) DEFAULT 0,
  valor_unitario NUMERIC(12,2) DEFAULT 0,
  valor_total NUMERIC(12,2) DEFAULT 0,
  origem VARCHAR(50),
  documento VARCHAR(80),
  funcionario_matricula VARCHAR(20),
  location_code VARCHAR(20) DEFAULT 'A-01-01-01',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wms_estoque (
  id SERIAL PRIMARY KEY,
  product_id INT NOT NULL,
  sku VARCHAR(50),
  produto_nome VARCHAR(200),
  location_code VARCHAR(20) DEFAULT 'A-01-01-01' NOT NULL,
  qty NUMERIC(10,3) DEFAULT 0,
  valor_unitario NUMERIC(12,2) DEFAULT 0,
  valor_total NUMERIC(12,2) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (product_id, location_code)
);

CREATE TABLE IF NOT EXISTS notas_fiscais_entrada (
  id SERIAL PRIMARY KEY,
  numero VARCHAR(50),
  fornecedor_id INT,
  valor NUMERIC(12,2) DEFAULT 0,
  data_emissao DATE,
  status VARCHAR(20) DEFAULT 'REGISTRADA',
  produto_ref VARCHAR(200),
  product_id INT,
  qty NUMERIC(10,3) DEFAULT 0,
  wms_movimento_id INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notas_fiscais_saida (
  id SERIAL PRIMARY KEY,
  numero VARCHAR(50),
  chave VARCHAR(100),
  chave_44 VARCHAR(100),
  cliente VARCHAR(200),
  valor NUMERIC(12,2) DEFAULT 0,
  data_emissao DATE,
  status VARCHAR(20) DEFAULT 'REGISTRADA',
  produto_ref VARCHAR(200),
  product_id INT,
  qty NUMERIC(10,3) DEFAULT 0,
  wms_movimento_id INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contas_financeiras (
  id SERIAL PRIMARY KEY,
  tipo VARCHAR(30) NOT NULL,
  descricao VARCHAR(255),
  pessoa VARCHAR(200),
  valor NUMERIC(12,2) DEFAULT 0,
  vencimento DATE,
  pagamento_data DATE,
  status VARCHAR(30) DEFAULT 'ABERTO',
  categoria VARCHAR(80),
  banco_id INT,
  observacao TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bancos_comerciais (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  codigo VARCHAR(10),
  agencia VARCHAR(20),
  conta VARCHAR(30),
  saldo NUMERIC(12,2) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'ATIVO'
);

CREATE TABLE IF NOT EXISTS banco_movimentos (
  id SERIAL PRIMARY KEY,
  banco_id INT,
  tipo VARCHAR(20) NOT NULL,
  descricao VARCHAR(255),
  valor NUMERIC(12,2) DEFAULT 0,
  data_movimento DATE,
  origem VARCHAR(60) DEFAULT 'MANUAL',
  referencia_id INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tipos_lancamento (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  tipo VARCHAR(20) DEFAULT 'DESPESA',
  categoria VARCHAR(80)
);

CREATE TABLE IF NOT EXISTS contadores (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(200) NOT NULL,
  telefone VARCHAR(30),
  crc VARCHAR(50),
  email VARCHAR(120),
  remuneracao NUMERIC(12,2) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'ATIVO',
  observacao TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contador_contatos (
  id SERIAL PRIMARY KEY,
  contador_id INT NOT NULL,
  data_contato DATE,
  tipo VARCHAR(40) DEFAULT 'CONTATO',
  descricao TEXT,
  realizado_por VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS logistica_movimentos (
  id SERIAL PRIMARY KEY,
  tipo VARCHAR(30) NOT NULL,
  product_id INT,
  produto_nome VARCHAR(200),
  sku VARCHAR(50),
  qty NUMERIC(10,3) DEFAULT 0,
  valor_unitario NUMERIC(12,2) DEFAULT 0,
  valor_total NUMERIC(12,2) DEFAULT 0,
  origem VARCHAR(120),
  destino VARCHAR(120),
  transportadora VARCHAR(120),
  motorista VARCHAR(120),
  placa VARCHAR(30),
  cliente_id INT,
  pedido_site_id INT,
  status VARCHAR(30) DEFAULT 'ABERTO',
  observacao TEXT,
  wms_movimento_id INT,
  criado_por VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  concluido_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_config_grid (
  id SERIAL PRIMARY KEY,
  secao VARCHAR(60) DEFAULT 'home',
  nome VARCHAR(120) NOT NULL,
  valor TEXT,
  tipo VARCHAR(40) DEFAULT 'texto',
  anexo_ref VARCHAR(255),
  hospedagem_ref VARCHAR(255),
  dados_ref VARCHAR(255),
  ativo BOOLEAN DEFAULT TRUE,
  ordem INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_marketing (
  id SERIAL PRIMARY KEY,
  titulo VARCHAR(160) NOT NULL,
  canal VARCHAR(60) DEFAULT 'site',
  conteudo TEXT,
  anexo_ref VARCHAR(255),
  ativo BOOLEAN DEFAULT TRUE,
  inicio DATE,
  fim DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formas_pagamento_taxas (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  tipo VARCHAR(40) DEFAULT 'PIX',
  taxa_percentual NUMERIC(7,4) DEFAULT 0,
  taxa_fixa NUMERIC(12,2) DEFAULT 0,
  banco_id INT,
  chave_pix VARCHAR(255),
  boleto_convenio VARCHAR(80),
  operacao VARCHAR(20) DEFAULT 'RECEBIMENTO',
  ativo BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_clientes (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(200) NOT NULL,
  email VARCHAR(120) UNIQUE,
  telefone VARCHAR(30),
  cpf_cnpj VARCHAR(30),
  endereco TEXT,
  senha_hash VARCHAR(64),
  status VARCHAR(20) DEFAULT 'ATIVO',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_pedidos (
  id SERIAL PRIMARY KEY,
  site_cliente_id INT,
  cliente_nome VARCHAR(200),
  telefone VARCHAR(30),
  entrega_endereco TEXT,
  forma_pagamento VARCHAR(100),
  subtotal NUMERIC(12,2) DEFAULT 0,
  taxa_entrega NUMERIC(12,2) DEFAULT 0,
  taxa_pagamento NUMERIC(12,2) DEFAULT 0,
  total NUMERIC(12,2) DEFAULT 0,
  status VARCHAR(30) DEFAULT 'SOLICITADO',
  logistica_id INT,
  venda_id INT,
  nota_saida_id INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_pedido_itens (
  id SERIAL PRIMARY KEY,
  pedido_id INT NOT NULL,
  product_id INT,
  produto_nome VARCHAR(200),
  sku VARCHAR(50),
  qty NUMERIC(10,3) DEFAULT 1,
  unit_price NUMERIC(12,2) DEFAULT 0,
  total NUMERIC(12,2) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS integracoes_ifood (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(120) DEFAULT 'iFood',
  merchant_id VARCHAR(120),
  client_id VARCHAR(255),
  client_secret VARCHAR(255),
  token_ref TEXT,
  webhook_url VARCHAR(255),
  ambiente VARCHAR(20) DEFAULT 'sandbox',
  status VARCHAR(20) DEFAULT 'INATIVO',
  observacao TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vendas (
  id SERIAL PRIMARY KEY,
  cliente_id INT,
  cliente_nome VARCHAR(200),
  total NUMERIC(12,2) DEFAULT 0,
  forma_pagamento VARCHAR(50),
  origem VARCHAR(20) DEFAULT 'loja',
  status VARCHAR(20) DEFAULT 'CONFIRMADA',
  data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  caixa_id INT,
  comanda_id INT,
  operador_matricula VARCHAR(20),
  descricao VARCHAR(200),
  editado_por VARCHAR(20),
  autorizado_por VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS maquinas_recebimento (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100),
  bandeira VARCHAR(50),
  taxa NUMERIC(7,4) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'ATIVO'
);

CREATE TABLE IF NOT EXISTS sites (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(120),
  dominio VARCHAR(200),
  status VARCHAR(20) DEFAULT 'RASCUNHO',
  config TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- DADOS INICIAIS
-- =====================================================

INSERT INTO fornecedores (nome, cnpj, telefone, email, status) VALUES
('Farinha Premium Ltda','12.345.678/0001-90','(11) 3333-1111','contato@farinhapremium.com.br','ATIVO'),
('Laticinios Sol','23.456.789/0001-10','(11) 3333-2222','vendas@lactiniosol.com','ATIVO'),
('Acucar Doce SA','34.567.890/0001-20','(11) 3333-3333','pedidos@acucardoce.com','ATIVO'),
('Cafe Grao Nobre','45.678.901/0001-30','(11) 3333-4444','contato@graonobre.com','ATIVO'),
('Embalagens Pro','56.789.012/0001-40','(11) 3333-5555','vendas@embalagenspro.com','ATIVO');

INSERT INTO produtos (nome, sku, categoria, preco_venda, custo, unidade, estoque_minimo, status) VALUES
('Pao Frances','PAO-001','Pães',0.80,0.30,'UN',50,'ATIVO'),
('Pao de Forma','PAO-002','Pães',8.50,4.00,'UN',10,'ATIVO'),
('Pao Integral','PAO-003','Pães',9.90,4.50,'UN',10,'ATIVO'),
('Pao Doce','PAO-004','Pães',1.20,0.50,'UN',30,'ATIVO'),
('Croissant','PAO-005','Pães',4.50,1.80,'UN',20,'ATIVO'),
('Baguete','PAO-006','Pães',6.00,2.50,'UN',15,'ATIVO'),
('Bolo de Chocolate','BOL-001','Bolos',32.00,12.00,'UN',5,'ATIVO'),
('Bolo de Fuba','BOL-002','Bolos',28.00,10.00,'UN',5,'ATIVO'),
('Bolo de Cenoura','BOL-003','Bolos',30.00,11.00,'UN',5,'ATIVO'),
('Brigadeiro','DOC-001','Doces',2.50,0.80,'UN',50,'ATIVO'),
('Beijinho','DOC-002','Doces',2.50,0.80,'UN',50,'ATIVO'),
('Sonho','DOC-003','Doces',5.00,2.00,'UN',20,'ATIVO'),
('Cafe Expresso','BEB-001','Bebidas',3.50,0.80,'UN',0,'ATIVO'),
('Cafe com Leite','BEB-002','Bebidas',4.50,1.20,'UN',0,'ATIVO'),
('Cappuccino','BEB-003','Bebidas',6.00,1.80,'UN',0,'ATIVO'),
('Suco de Laranja','BEB-004','Bebidas',7.00,2.50,'UN',0,'ATIVO'),
('Refrigerante Lata','BEB-005','Bebidas',5.00,2.00,'UN',24,'ATIVO'),
('Misto Quente','SAL-001','Salgados',6.50,2.50,'UN',15,'ATIVO'),
('Hamburguer Artesanal','SAL-002','Salgados',15.00,6.00,'UN',10,'ATIVO'),
('Coxinha','SAL-003','Salgados',5.00,1.80,'UN',30,'ATIVO'),
('Pastel','SAL-004','Salgados',6.00,2.00,'UN',25,'ATIVO'),
('Torta Salgada Fatia','SAL-005','Salgados',8.00,3.00,'UN',15,'ATIVO'),
('Sanduiche Natural','SAL-006','Salgados',9.50,3.50,'UN',10,'ATIVO'),
('Farinha de Trigo 1kg','INS-001','Insumos',5.50,3.50,'UN',20,'ATIVO'),
('Acucar 1kg','INS-002','Insumos',4.00,2.50,'UN',20,'ATIVO'),
('Leite 1L','INS-003','Insumos',5.00,3.20,'UN',30,'ATIVO'),
('Ovos Duzia','INS-004','Insumos',12.00,8.00,'UN',15,'ATIVO'),
('Manteiga 500g','INS-005','Insumos',15.00,9.00,'UN',10,'ATIVO');

-- Senha 123 = a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3
INSERT INTO funcionarios (matricula, nome, cargo, role, senha_hash, permissoes, status, salario) VALUES
('AP-2026-0001','Administrador','Gerente Geral','admin','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","fornecedores","produtos","clientes","funcionarios","wms","caixa","comandas","rh","tesouraria","contabilidade","bancos","logistica","sites"]','ATIVO',8000),
('OP-2026-0002','Maria Silva','Padeiro','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","produtos","wms","caixa","comandas"]','ATIVO',2500),
('OP-2026-0003','Joao Santos','Atendente de Caixa','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","caixa","comandas","clientes"]','ATIVO',1800),
('OP-2026-0004','Ana Costa','Confeiteira','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","produtos","wms"]','ATIVO',2800),
('OP-2026-0005','Carlos Oliveira','Entregador','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","logistica"]','ATIVO',1600);

INSERT INTO clientes (nome, cpf_cnpj, telefone, email, endereco, status) VALUES
('Joao da Silva','123.456.789-00','(11) 99999-1111','joao@email.com','Rua A, 100','ATIVO'),
('Maria Souza','234.567.890-11','(11) 99999-2222','maria@email.com','Rua B, 200','ATIVO'),
('Empresa XYZ Ltda','12.345.678/0001-99','(11) 3333-9999','contato@xyz.com','Av. Central, 500','ATIVO'),
('Ana Paula','345.678.901-22','(11) 99999-3333','ana@email.com','Rua C, 300','ATIVO'),
('Pedro Henrique','456.789.012-33','(11) 99999-4444','pedro@email.com','Rua D, 400','ATIVO');

INSERT INTO bancos_comerciais (nome, codigo, agencia, conta, saldo, status) VALUES
('Banco do Brasil','001','1234','12345-6',5000.00,'ATIVO'),
('Bradesco','237','5678','98765-4',3000.00,'ATIVO'),
('Caixa Economica','104','9012','11223-3',2000.00,'ATIVO');

INSERT INTO wms_estoque (product_id, sku, produto_nome, location_code, qty, valor_unitario, valor_total) VALUES
(1,'PAO-001','Pao Frances','A-01-01-01',100,0.30,30.00),
(2,'PAO-002','Pao de Forma','A-01-01-02',30,4.00,120.00),
(3,'PAO-003','Pao Integral','A-01-01-03',25,4.50,112.50),
(4,'PAO-004','Pao Doce','A-01-01-04',60,0.50,30.00),
(5,'PAO-005','Croissant','A-01-02-01',40,1.80,72.00),
(7,'BOL-001','Bolo de Chocolate','A-02-01-01',8,12.00,96.00),
(10,'DOC-001','Brigadeiro','A-02-02-01',100,0.80,80.00),
(13,'BEB-001','Cafe Expresso','B-01-01-01',500,0.80,400.00),
(15,'BEB-003','Cappuccino','B-01-01-02',200,1.80,360.00),
(18,'SAL-001','Misto Quente','A-03-01-01',20,2.50,50.00),
(24,'INS-001','Farinha de Trigo 1kg','C-01-01-01',50,3.50,175.00),
(26,'INS-003','Leite 1L','C-01-02-01',40,3.20,128.00);

INSERT INTO vendas (cliente_nome, total, forma_pagamento, origem, status, operador_matricula, descricao) VALUES
('Balcão',45.50,'DINHEIRO','loja','CONFIRMADA','OP-2026-0003','Venda balcão manhã'),
('Joao da Silva',32.00,'PIX','loja','CONFIRMADA','OP-2026-0003','Bolo de chocolate'),
('Maria Souza',18.90,'CARTAO','loja','CONFIRMADA','OP-2026-0003','Cafés e pães'),
('Balcão',120.00,'PIX','site','CONFIRMADA','OP-2026-0003','Pedido delivery'),
('Empresa XYZ',250.00,'BOLETO','loja','CONFIRMADA','OP-2026-0003','Pedido corporativo');

INSERT INTO contas_financeiras (tipo, descricao, pessoa, valor, vencimento, status, categoria) VALUES
('PAGAR','Aluguel','Imobiliaria Central',3500.00, CURRENT_DATE + INTERVAL '5 days','ABERTO','Aluguel'),
('PAGAR','Energia Eletrica','Enel',450.00, CURRENT_DATE - INTERVAL '2 days','ABERTO','Utilidades'),
('PAGAR','Fornecedor Farinha','Farinha Premium Ltda',1200.00, CURRENT_DATE + INTERVAL '10 days','ABERTO','Insumos'),
('RECEBER','Pedido Corporativo','Empresa XYZ Ltda',250.00, CURRENT_DATE,'ABERTO','Vendas'),
('RECEBER','Cliente Fiado','Joao da Silva',80.00, CURRENT_DATE + INTERVAL '3 days','ABERTO','Vendas');

INSERT INTO formas_pagamento_taxas (nome, tipo, taxa_percentual, taxa_fixa, operacao, ativo) VALUES
('PIX padrao','PIX',0,0,'RECEBIMENTO',TRUE),
('Boleto padrao','BOLETO',1.5,0,'RECEBIMENTO',TRUE),
('Cartao credito','CREDITO',3.5,0,'RECEBIMENTO',TRUE),
('Dinheiro','DINHEIRO',0,0,'RECEBIMENTO',TRUE);

INSERT INTO site_config_grid (secao, nome, valor, tipo, ativo, ordem) VALUES
('vitrine','Produtos em destaque','Mostrar produtos ativos','produto',TRUE,1),
('vendas','Pedido online','Pedido online com baixa estoque','pedido',TRUE,2),
('marketing','Campanhas','Banners e cupons','banner',TRUE,3),
('pagamento','PIX e boleto','Formas de recebimento','pagamento',TRUE,4),
('logistica','Entrega e retirada','Entrega conectada ao WMS','logistica',TRUE,5),
('bot_geral','nome_bot','Dona Padaria','texto',TRUE,1),
('bot_geral','saudacao','Olá! Bem-vindo à Padaria! Como posso ajudar?','texto',TRUE,2),
('bot_geral','horario_atendimento','Seg-Sáb 6h às 20h, Dom 7h às 13h','texto',TRUE,3),
('bot_geral','endereco','Rua das Flores, 123 - Centro','texto',TRUE,4),
('bot_regras','oi|ola|olá|bom dia|boa tarde|boa noite','Saudação','regra_bot',TRUE,10),
('bot_regras','preco|valor|quanto custa|preço','Consulta preço','regra_bot',TRUE,11),
('bot_regras','horario|horário|abre|fecha|funcionamento','Horário','regra_bot',TRUE,12),
('bot_regras','endereco|endereço|onde fica|localizacao','Endereço','regra_bot',TRUE,13),
('bot_regras','pedido|comprar|quero|encomendar','Fazer pedido','regra_bot',TRUE,14);

INSERT INTO sites (nome, dominio, status, config) VALUES
('Padaria Online','padaria.local','PUBLICADO','{"tema":"padrao"}');

SELECT 'SUPABASE PANIFICADORA CRIADO COM SUCESSO!' AS resultado;
