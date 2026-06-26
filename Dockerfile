# Usa uma versão oficial do Python
FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Instala apenas o essencial, mas com um timeout maior e sem as dependências de compilação
# Caso não precise do git dentro do container, ele foi removido para evitar erro
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências e instala as bibliotecas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código
COPY . .

# Copiar a pasta .streamlit com o secrets.toml
COPY .streamlit/ .streamlit/

# Comando para rodar o Streamlit
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
