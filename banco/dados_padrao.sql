-- DADOS PADRAO - PANIFICADORA
-- Execute DEPOIS do banco.sql

-- Fornecedores
INSERT INTO fornecedores (nome, cnpj, telefone, email, status) VALUES
('Farinha Premium Ltda','12.345.678/0001-90','(11) 3333-1111','contato@farinhapremium.com.br','ATIVO'),
('Laticinios Sol','23.456.789/0001-10','(11) 3333-2222','vendas@lactiniosol.com','ATIVO'),
('Acucar Doce SA','34.567.890/0001-20','(11) 3333-3333','pedidos@acucardoce.com','ATIVO'),
('Cafe Grao Nobre','45.678.901/0001-30','(11) 3333-4444','contato@graonobre.com','ATIVO'),
('Embalagens Pro','56.789.012/0001-40','(11) 3333-5555','vendas@embalagenspro.com','ATIVO');

-- Produtos
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

-- Funcionarios (senha: 123)
INSERT INTO funcionarios (matricula, nome, cargo, role, senha_hash, permissoes, status, salario) VALUES
('AP-2026-0001','Administrador','Gerente Geral','admin','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","fornecedores","produtos","clientes","funcionarios","wms","caixa","comandas","rh","tesouraria","contabilidade","bancos","logistica","sites"]','ATIVO',8000),
('OP-2026-0002','Maria Silva','Padeiro','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","produtos","wms","caixa","comandas"]','ATIVO',2500),
('OP-2026-0003','Joao Santos','Atendente de Caixa','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","caixa","comandas","clientes"]','ATIVO',1800),
('OP-2026-0004','Ana Costa','Confeiteira','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","produtos","wms"]','ATIVO',2800),
('OP-2026-0005','Carlos Oliveira','Entregador','operador','a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3','["dashboard","logistica"]','ATIVO',1600);

-- Clientes
INSERT INTO clientes (nome, cpf_cnpj, telefone, email, endereco, status) VALUES
('Joao da Silva','123.456.789-00','(11) 99999-1111','joao@email.com','Rua A, 100','ATIVO'),
('Maria Souza','234.567.890-11','(11) 99999-2222','maria@email.com','Rua B, 200','ATIVO'),
('Empresa XYZ Ltda','12.345.678/0001-99','(11) 3333-9999','contato@xyz.com','Av. Central, 500','ATIVO'),
('Ana Paula','345.678.901-22','(11) 99999-3333','ana@email.com','Rua C, 300','ATIVO'),
('Pedro Henrique','456.789.012-33','(11) 99999-4444','pedro@email.com','Rua D, 400','ATIVO');

-- Bancos
INSERT INTO bancos_comerciais (nome, codigo, agencia, conta, saldo, status) VALUES
('Banco do Brasil','001','1234','12345-6',5000.00,'ATIVO'),
('Bradesco','237','5678','98765-4',3000.00,'ATIVO'),
('Caixa Economica','104','9012','11223-3',2000.00,'ATIVO');

-- Estoque WMS
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

-- Vendas de exemplo
INSERT INTO vendas (cliente_nome, total, forma_pagamento, origem, status, operador_matricula, descricao) VALUES
('Balcão',45.50,'DINHEIRO','loja','CONFIRMADA','OP-2026-0003','Venda balcão manhã'),
('Joao da Silva',32.00,'PIX','loja','CONFIRMADA','OP-2026-0003','Bolo de chocolate'),
('Maria Souza',18.90,'CARTAO','loja','CONFIRMADA','OP-2026-0003','Cafés e pães'),
('Balcão',120.00,'PIX','site','CONFIRMADA','OP-2026-0003','Pedido delivery'),
('Empresa XYZ',250.00,'BOLETO','loja','CONFIRMADA','OP-2026-0003','Pedido corporativo');

-- Contas a pagar/receber
INSERT INTO contas_financeiras (tipo, descricao, pessoa, valor, vencimento, status, categoria) VALUES
('PAGAR','Aluguel','Imobiliaria Central',3500.00, DATE_ADD(CURDATE(), INTERVAL 5 DAY),'ABERTO','Aluguel'),
('PAGAR','Energia Eletrica','Enel',450.00, DATE_SUB(CURDATE(), INTERVAL 2 DAY),'ABERTO','Utilidades'),
('PAGAR','Fornecedor Farinha','Farinha Premium Ltda',1200.00, DATE_ADD(CURDATE(), INTERVAL 10 DAY),'ABERTO','Insumos'),
('RECEBER','Pedido Corporativo','Empresa XYZ Ltda',250.00, CURDATE(),'ABERTO','Vendas'),
('RECEBER','Cliente Fiado','Joao da Silva',80.00, DATE_ADD(CURDATE(), INTERVAL 3 DAY),'ABERTO','Vendas');

-- Site config (já criado pelo schema, mas garante)
INSERT IGNORE INTO sites (nome, dominio, status, config) VALUES
('Padaria Online','padaria.local','PUBLICADO','{"tema":"padrao"}');

SELECT 'DADOS CARREGADOS COM SUCESSO!' AS resultado;
