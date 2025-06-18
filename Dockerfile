# 🔥 Usa imagem otimizada
FROM python:3.11-slim-bullseye

# 🏗 Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 🗂️ Diretório de trabalho
WORKDIR /app

# 📜 Copia arquivos
COPY requirements.txt .
COPY . .

# 📦 Instala dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 🔥 Porta
EXPOSE 8000

# 🚀 Comando pra rodar
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]