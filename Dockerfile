FROM python:3.10-slim

WORKDIR /app

# Copia os arquivos de dependência e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Expõe a porta de execução
EXPOSE 5000

# Executa a aplicação ligando no 0.0.0.0
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"])

