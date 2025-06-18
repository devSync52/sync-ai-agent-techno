# 🚀 SynC AI Agent

Intelligent AI Agent powered by **LangChain**, **FastAPI**, **OpenAI** and **Supabase**, designed for advanced inventory, order, and sales management queries.

## 📦 Stack

- 🐍 Python 3.11
- ⚡ FastAPI + Uvicorn
- 🔗 LangChain (OpenAI)
- 🔥 Supabase (Database + Auth)
- 🐳 Docker (optional)
- 🚀 Railway (Deployment)

---

## 🔧 Environment Variables

Crie um arquivo `.env` na raiz com:

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxx
OPENAI_API_KEY=sk-xxxxxx
APP_URL=http://localhost:8000
```

---

## 🏗️ Run Locally with Docker

### ✅ Build & Run

```bash
docker-compose up --build
```

### 🚀 Check health

[http://localhost:8000/health](http://localhost:8000/health)

Resposta:

```json
{ "status": "ok" }
```

---

## 🧠 API Endpoints

### ➕ POST `/chat`

> Faz uma pergunta para o agente de IA

**Body:**

```json
{
  "question": "How much stock do I have for SKU ABC?",
  "account_id": "your-account-id",
  "user_id": "your-user-id",
  "session_id": "your-session-id",
  "user_type": "owner"
}
```

**Response:**  
Streaming de texto com a resposta.

---

### 📜 GET `/chat/history`

> Retorna o histórico da sessão de chat.

**Params:**

```
session_id=uuid
user_id=uuid (opcional)
limit=20 (opcional)
```

---

### 📂 GET `/chat/sessions`

> Lista as últimas sessões do usuário.

**Params:**

```
user_id=uuid
```

---

### ❤️ GET `/health`

> Health check.

Resposta:

```json
{ "status": "ok" }
```

---

## 🏗️ Estrutura de pastas

```
/app
  ├── langchain_v2
  │   ├── agent/
  │   ├── memory/
  │   └── tools/
  ├── utils/
  │   └── supabase_client.py
  └── main.py
```

---

## 🚀 Deploy Railway ou Render

1. Cria um projeto Docker.
2. Configura as variáveis de ambiente.
3. Railway detecta automaticamente o `Dockerfile`.
4. O comando padrão já funciona:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
   ```

---

## 🐳 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🐳 docker-compose.yml

```yaml
services:
  sync-ai-agent:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
```

---

## 🚀 Comandos Git Bonitos

```bash
git init
git remote add origin https://github.com/SEU-USUARIO/SEU-REPO.git
git add .
git commit -m "🚀 Initial commit - SynC AI Agent"
git branch -M main
git push -u origin main
```

---

## ✨ Features Futuras

- [ ] 🔐 Autenticação via API Key
- [ ] 📝 Logs no Supabase com mais detalhes
- [ ] 📊 Painel Web para consumir os endpoints
- [ ] 🤖 Agente com RAG (Retrieval-Augmented Generation)
- [ ] 🌍 Tradução automática das respostas

---

## 🏆 Feito com amor pela equipe SynC AI 🚀