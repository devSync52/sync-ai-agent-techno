# 🔥 Imagem base leve
FROM python:3.11.8-slim

# 📁 Diretório de trabalho
WORKDIR /app

# 🧠 Instala dependências do sistema (para alguns pacotes Python como httpx, uvicorn)
RUN apt-get update && apt-get install -y \
    build-essential \
    && apt-get clean

# 🏗️ Copia os arquivos
COPY . /app

# 📦 Instala dependências Python
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 🚪 Expõe a porta
EXPOSE 8000

# 🚀 Comando para rodar a API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]