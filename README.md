# Panificadora ERP

Sistema completo de gestão para padaria com **3 Grids de Inteligência Artificial**, desenvolvido em Python + MySQL/PostgreSQL + HTML.

## Funcionalidades

- **Dashboard** com KPIs, gráficos de vendas e alertas em tempo real
- **PDV / Caixa** — abrir/fechar caixa, vendas com múltiplos itens, sangria, suprimento
- **Cadastros** — Produtos, Clientes, Fornecedores, Funcionários (CRUD completo)
- **Vendas, Comandas, Pedidos do Site**
- **Estoque WMS** — entrada/saída por endereço, movimentações
- **Financeiro** — contas a pagar/receber, tesouraria, autorizações
- **RH** — ponto, férias, holerites
- **Logística** — entregas

## 3 Grids de IA

| Grid | Módulo | Descrição |
|------|--------|-----------|
| **Grid 1** | Configuração do Bot | Personalize nome, saudação, horário, endereço e regras de resposta sem mexer no código |
| **Grid 2** | Gerente do Ambiente | Monitora 14 módulos, alertas automáticos (estoque baixo, contas vencidas, pedidos pendentes), relatório de vendas |
| **Grid 3** | IA de Vendas | Chatbot que recomenda produtos, monta combos, cria pedido e dá baixa automática no estoque WMS |

## Como rodar

### Opção A — Supabase (PostgreSQL) ☁️ (recomendado)

1. Crie um projeto no [Supabase](https://supabase.com)
2. No **SQL Editor**, cole e execute o conteúdo de `supabase_banco.sql`
3. Copie a **Connection string** (Project Settings → Database) e cole no arquivo `.env`:
   ```
   DATABASE_URI=postgresql://postgres.xxxx:senha@aws-0-xxxx.pooler.supabase.com:5432/postgres
   PORT=8080
   ```
4. Instale e rode:
   ```bash
   pip install psycopg2-binary python-dotenv
   python servidor_supabase.py
   ```

### Opção B — MySQL local 🖥️

1. Crie o banco e carregue os dados:
   ```bash
   mysql -u root -proot123 < banco.sql
   mysql -u root -proot123 panificadora_db < dados_padrao.sql
   ```
2. Configure o `.env` (MySQL):
   ```
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASS=root123
   DB_NAME=panificadora_db
   PORT=8080
   ```
3. Instale e rode:
   ```bash
   pip install pymysql python-dotenv
   python servidor_local.py
   ```

### Acessar o sistema

Abra o arquivo `dashboard.html` no navegador (dê 2 cliques).

**Login padrão:** `AP-2026-0001` / senha `123`

## Estrutura do projeto

```
├── dashboard.html          # Frontend (tudo num arquivo só)
├── servidor_local.py       # API Python - MySQL
├── servidor_supabase.py    # API Python - Supabase/PostgreSQL
├── banco.sql               # Cria banco MySQL
├── dados_padrao.sql        # Dados iniciais MySQL
├── supabase_banco.sql      # Schema + dados p/ Supabase (PostgreSQL)
├── requirements.txt        # Dependências MySQL
├── requirements_supabase.txt # Dependências Supabase
├── .env                    # Suas credenciais (NÃO commitar!)
└── LEIA-ME.txt             # Guia rápido
```

## Tecnologias

- **Backend:** Python 3 (http.server nativo, sem framework)
- **Banco:** MySQL ou PostgreSQL/Supabase
- **Frontend:** HTML + CSS + JS vanilla, ECharts (gráficos), Lucide (ícones)
- **Fonte:** Quicksand (Google Fonts)

## Observações

- O `.env` contém senhas — adicione no `.gitignore`
- O iFood e emissão de NF são placeholders (precisam de credenciais reais)
- Senhas em SHA256 sem salt (uso local — para produção use bcrypt/argon2)
