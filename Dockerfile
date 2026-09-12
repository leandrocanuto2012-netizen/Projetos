FROM python:3.10-slim

WORKDIR /app

# Instala as dependências do sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala os requisitos do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto
COPY . .

# Expõe a porta que o script Python vai usar
EXPOSE 5000

# Executa o servidor Flask ou FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"])

