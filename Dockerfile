FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install httpx mysql-connector-python fastapi uvicorn
CMD ["python", "main.py"]