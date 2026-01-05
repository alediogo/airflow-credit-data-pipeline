# Usa Python 3.9 (versão estável para Airflow)
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Instala ferramentas básicas do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do projeto
COPY . .

# Define uma variável de ambiente para o Airflow (opcional, boa prática)
ENV AIRFLOW_HOME=/app/airflow

# Comando padrão (ajuste 'main.py' se seu script principal tiver outro nome)
# Se for apenas para deixar o container rodando, pode usar: CMD ["python3"]
CMD ["python", "main.py"]