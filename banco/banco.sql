-- BANCO PANIFICADORA_DB
-- Crie o banco e depois execute: python servidor_local.py (ele cria as tabelas automaticamente)

CREATE DATABASE IF NOT EXISTS panificadora_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE panificadora_db;

-- Tabelas base (o servidor cria automaticamente via garantir_schema())
-- Este arquivo garante o banco e o usuário de acesso.

-- Usuário (opcional - use root se preferir)
-- CREATE USER IF NOT EXISTS 'panificadora'@'localhost' IDENTIFIED BY 'pan123';
-- GRANT ALL PRIVILEGES ON panificadora_db.* TO 'panificadora'@'localhost';
-- FLUSH PRIVILEGES;

SELECT 'Banco panificadora_db criado! Agora execute: python servidor_local.py' AS mensagem;
