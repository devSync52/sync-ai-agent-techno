from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from app.langchain_v2.agent.sync_guardian_agent import createSyncGuardianAgent
from app.langchain_v2.memory.session_memory import get_session_history_from_db
from app.utils.supabase_client import get_supabase_client, run_sql_query
from app.langchain_v2.utils.session_context import set_current_session_context

from langchain_openai import ChatOpenAI
from datetime import datetime, timezone
import logging
import re


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync-ai-agent")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos os domínios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def is_valid_uuid(val: str) -> bool:
    return bool(re.match(r"^[a-f0-9-]{36}$", val.strip(), re.I))


class AgentRequest(BaseModel):
    question: str
    account_id: str
    user_id: str
    session_id: str
    user_type: str


@app.post("/chat")
async def chat_with_agent(request: AgentRequest):
    if not is_valid_uuid(request.session_id):
        raise HTTPException(status_code=400, detail="❌ Invalid session_id")

    logger.info(f"[Chat] Session: {request.session_id} | Question: {request.question}")

    logger.info(f"🔍 Dados da sessão recebidos:")
    logger.info(f"  - account_id: {request.account_id}")
    logger.info(f"  - user_id: {request.user_id}")
    logger.info(f"  - session_id: {request.session_id}")
    logger.info(f"  - user_type: {request.user_type}")

    try:
        model = ChatOpenAI(
            model_name="gpt-3.5-turbo-0125",
            temperature=0,
            streaming=True,
        )

        # 📌 Armazena o contexto da sessão para tools futuras
        set_current_session_context({
            "account_id": request.account_id,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "user_type": request.user_type
        })

        agent, chat_history = await createSyncGuardianAgent(
            model=model,
            account_id=request.account_id,
            user_id=request.user_id,
            session_id=request.session_id,
            user_type=request.user_type,
        )

    except Exception as e:
        logger.error(f"❌ Error creating agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create AI agent")

    async def stream_response():
        logger.info(f"🚀 Iniciando stream com dados:")
        logger.info(f"  - question: {request.question}")
        logger.info(f"  - account_id: {request.account_id}")
        logger.info(f"  - user_id: {request.user_id}")
        logger.info(f"  - session_id: {request.session_id}")
        logger.info(f"  - user_type: {request.user_type}")

        final_answer = ""
        try:
            agent_input = {
                "input": request.question,
                "chat_history": chat_history,
                "account_id": request.account_id,
                "user_id": request.user_id,
                "session_id": request.session_id,
                "user_type": request.user_type,
            }
            async for chunk in agent.astream(agent_input):
                if isinstance(chunk, str):
                    final_answer += chunk
                    yield chunk
                elif "output" in chunk:
                    final_answer += chunk["output"]
                    yield chunk["output"]
        except Exception as e:
            logger.error(f"❌ Error in stream: {e}")
            final_answer = f"Error: {str(e)}\n"
            yield final_answer

        try:
            timestamp = datetime.now(timezone.utc).isoformat()

            if request.question.strip():
                supabase = get_supabase_client()
                supabase.table("ai_chat_logs").insert({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "account_id": request.account_id,
                    "role": "user",
                    "question": request.question,
                    "timestamp": timestamp,
                    "metadata": {
                        "model": "gpt-3.5-turbo-0125",
                        "user_type": request.user_type
                    }
                }).execute()

            if final_answer.strip():
                supabase = get_supabase_client()
                supabase.table("ai_chat_logs").insert({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "account_id": request.account_id,
                    "role": "ai",
                    "answer": final_answer.strip(),
                    "timestamp": timestamp,
                    "metadata": {
                        "model": "gpt-3.5-turbo-0125",
                        "user_type": request.user_type
                    }
                }).execute()

        except Exception as e:
            logger.error(f"❌ Error saving logs to Supabase: {e}")

    return StreamingResponse(stream_response(), media_type="text/plain")


@app.get("/chat/history")
async def chat_history(session_id: str, user_id: str = None, limit: int = 20):
    if not is_valid_uuid(session_id):
        raise HTTPException(status_code=400, detail="❌ Invalid session_id")

    logger.info(f"[History] Fetching for Session: {session_id}")

    history = get_session_history_from_db(session_id, limit=limit)
    messages = []
    for h in history:
        if h["role"] == "user" and h.get("question"):
            messages.append({"role": "user", "content": h["question"]})
        elif h["role"] in ("ai", "assistant") and h.get("answer"):
            messages.append({"role": "assistant", "content": h["answer"]})
    return JSONResponse(messages)


@app.get("/chat/sessions")
def list_sessions(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="❌ user_id is required")

    logger.info(f"[Sessions] Fetching sessions for user: {user_id}")

    sql = f"""
    SELECT session_id, MAX(timestamp) as last_activity, MAX(question) as last_question
    FROM ai_chat_logs
    WHERE user_id = '{user_id}'
    GROUP BY session_id
    ORDER BY last_activity DESC
    LIMIT 10
    """
    rows = run_sql_query(sql)
    if not isinstance(rows, list):
        rows = []
    return rows


@app.get("/")
def read_root():
    return {"status": "up"}


@app.get("/health")
def health_check():
    return {"status": "ok"}