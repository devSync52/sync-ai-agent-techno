from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
import os

from app.langchain_v2.agent.sync_guardian_agent import createSyncGuardianAgent
from app.langchain_v2.memory.session_memory import get_session_history_from_db
from app.langchain_v2.tools.extensiv import summarize_order_lifecycle_by_warehouse
from app.utils.supabase_client import get_supabase_client, run_sql_query
from app.langchain_v2.utils.session_context import set_current_session_context

from langchain_openai import ChatOpenAI
from datetime import datetime, timezone
import logging
import re
import unicodedata
from typing import Optional, Tuple

load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync-ai-agent")

VALID_USER_TYPES = {"owner", "client", "end_client"}
OWNER_ROLES = {"admin", "staff-admin", "staff-user"}
CLIENT_ROLES = {"client", "staff-client"}
END_CLIENT_ROLES = {"customer"}
VALID_INTEGRATION_SOURCES = {"sellercloud", "extensiv", "mixed", "unknown"}
DEFAULT_COMPANY_NAME = "SynC Fulfillment"


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


def normalize_user_type(user_type: Optional[str]) -> Optional[str]:
    normalized = (user_type or "").strip().lower()
    return normalized if normalized in VALID_USER_TYPES else None


def map_role_to_user_type(role: Optional[str]) -> Optional[str]:
    normalized_role = (role or "").strip().lower()
    if normalized_role in OWNER_ROLES:
        return "owner"
    if normalized_role in CLIENT_ROLES:
        return "client"
    if normalized_role in END_CLIENT_ROLES:
        return "end_client"
    return None


def normalize_integration_source(source: Optional[str]) -> str:
    normalized = (source or "").strip().lower()
    return normalized if normalized in VALID_INTEGRATION_SOURCES else "unknown"


def resolve_parent_account_id(account_id: Optional[str]) -> Optional[str]:
    if not account_id:
        return None

    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("accounts")
            .select("id,parent_account_id")
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        if not row:
            return account_id

        return row.get("parent_account_id") or row.get("id") or account_id
    except Exception as e:
        logger.warning(f"[Integrations] Could not resolve parent account for account_id={account_id}: {e}")
        return account_id


def resolve_integration_source(account_id: Optional[str]) -> str:
    parent_account_id = resolve_parent_account_id(account_id)
    if not parent_account_id:
        return "unknown"

    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("account_integrations")
            .select("type,status")
            .eq("account_id", parent_account_id)
            .execute()
        )
        rows = response.data or []

        integration_types = []
        for row in rows:
            status = str(row.get("status") or "").strip().lower()
            if status in {"inactive", "disabled"}:
                continue
            integration_type = str(row.get("type") or "").strip().lower()
            if integration_type:
                integration_types.append(integration_type)

        if not integration_types:
            return "unknown"

        has_extensiv = any(t == "extensiv" for t in integration_types)
        has_sellercloud = any(t == "sellercloud" for t in integration_types)

        if has_extensiv and has_sellercloud:
            return "mixed"
        if has_extensiv:
            return "extensiv"
        if has_sellercloud:
            return "sellercloud"
        return "unknown"
    except Exception as e:
        logger.warning(f"[Integrations] Could not resolve integration source for parent_account_id={parent_account_id}: {e}")
        return "unknown"


def resolve_company_name(account_id: Optional[str]) -> str:
    parent_account_id = resolve_parent_account_id(account_id)
    if not parent_account_id:
        return DEFAULT_COMPANY_NAME

    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("accounts")
            .select("name")
            .eq("id", parent_account_id)
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        company_name = str((row or {}).get("name") or "").strip()
        return company_name or DEFAULT_COMPANY_NAME
    except Exception as e:
        logger.warning(f"[Company] Could not resolve parent company name for account_id={account_id}: {e}")
        return DEFAULT_COMPANY_NAME


def resolve_user_context(user_id: str, account_id: str, request_user_type: Optional[str]) -> Tuple[str, str, str, str]:
    """
    Resolve user_type/account_id with DB as source of truth when possible.
    Falls back to request payload if user lookup is unavailable.
    """
    payload_user_type = normalize_user_type(request_user_type)
    resolved_user_type = payload_user_type or "client"
    resolved_account_id = account_id

    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("users")
            .select("role, account_id")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        if row:
            db_user_type = map_role_to_user_type(row.get("role"))
            db_account_id = row.get("account_id")

            if db_user_type:
                resolved_user_type = db_user_type
                if payload_user_type and payload_user_type != db_user_type:
                    logger.warning(
                        f"[Auth] user_type payload mismatch for user_id={user_id}: payload={payload_user_type}, db={db_user_type}. Using db value."
                    )
            else:
                resolved_user_type = "client"
                logger.warning(
                    f"[Auth] Unknown role for user_id={user_id}. Using restricted user_type=client."
                )

            if db_account_id:
                resolved_account_id = db_account_id
                if account_id and account_id != db_account_id:
                    logger.warning(
                        f"[Auth] account_id payload mismatch for user_id={user_id}: payload={account_id}, db={db_account_id}. Using db value."
                    )
    except Exception as e:
        logger.warning(f"[Auth] Could not resolve role/account from users table. Using payload fallback. Error: {e}")

    resolved_integration_source = normalize_integration_source(
        resolve_integration_source(resolved_account_id)
    )
    resolved_company_name = resolve_company_name(resolved_account_id)

    return resolved_user_type, resolved_account_id, resolved_integration_source, resolved_company_name


def should_force_extensiv_lifecycle_summary(question: str, integration_source: str) -> bool:
    """
    Deterministic routing to avoid fabricated lifecycle summaries.
    Applies only to Extensiv contexts.
    """
    if normalize_integration_source(integration_source) != "extensiv":
        return False

    lowered = (question or "").strip().lower()
    if not lowered:
        return False

    lifecycle_keywords = [
        "lifecycle",
        "order lifecycle",
        "ciclo de pedidos",
        "ciclo do pedido",
    ]
    warehouse_keywords = [
        "warehouse",
        "warehouses",
        "facility",
        "facilities",
        "armazem",
        "armazém",
        "deposito",
        "depósito",
    ]
    summary_keywords = [
        "summary",
        "summarize",
        "resuma",
        "resumir",
        "resumo",
        "mostrar",
        "mostre",
        "show",
    ]

    has_lifecycle = any(keyword in lowered for keyword in lifecycle_keywords)
    has_warehouse = any(keyword in lowered for keyword in warehouse_keywords)
    has_summary_intent = any(keyword in lowered for keyword in summary_keywords)

    return has_lifecycle and has_warehouse and has_summary_intent


def _normalize_question_text(question: str) -> str:
    lowered = (question or "").strip().lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def is_capability_question(question: str) -> bool:
    normalized = _normalize_question_text(question)
    if not normalized:
        return False

    patterns = [
        "what can you do",
        "what can you do for me",
        "how can you help",
        "what are your capabilities",
        "o que voce pode fazer",
        "o que pode fazer por mim",
        "como voce pode me ajudar",
        "como pode me ajudar",
        "no que voce pode me ajudar",
        "que puedes hacer",
        "que puedes hacer por mi",
        "como puedes ayudarme",
    ]
    return any(pattern in normalized for pattern in patterns)


def _detect_question_language(question: str) -> str:
    normalized = _normalize_question_text(question)
    if any(token in normalized for token in [" o que ", " voce ", " ajudar", " por mim", "ola", "olá"]):
        return "pt"
    if any(token in normalized for token in [" que ", " ayudar", " por mi", "hola", "puedes"]):
        return "es"
    return "en"


def build_non_extensiv_capability_response(question: str, integration_source: str, company_name: str) -> str:
    language = _detect_question_language(question)
    company = (company_name or DEFAULT_COMPANY_NAME).strip() or DEFAULT_COMPANY_NAME

    if language == "pt":
        return (
            f"Claro. Sou sua assistente na {company}.\n"
            "\n"
            "Posso ajudar agora com:\n"
            "- status de pedidos por ID\n"
            "- tracking e detalhes de envio\n"
            "- itens/SKUs de um pedido\n"
            "- resumos de pedidos e vendas por período\n"
            "- comparativos por período, marketplace e SKU\n"
            "- consultas de inventário por SKU e produtos em risco"
        )

    if language == "es":
        return (
            f"Claro. Soy tu asistente en {company}.\n"
            "\n"
            "Ahora puedo ayudarte con:\n"
            "- estado de pedidos por ID\n"
            "- tracking y detalles de envío\n"
            "- artículos/SKUs de un pedido\n"
            "- resúmenes de pedidos y ventas por período\n"
            "- comparativos por período, marketplace y SKU\n"
            "- consultas de inventario por SKU y productos en riesgo"
        )

    return (
        f"Sure. I am your assistant at {company}.\n"
        "\n"
        "I can help right now with:\n"
        "- order status by ID\n"
        "- tracking and shipping details\n"
        "- order items/SKUs\n"
        "- order and sales summaries by period\n"
        "- comparisons by period, marketplace, and SKU\n"
        "- SKU inventory checks and products at risk"
    )


def resolve_forced_response(question: str, integration_source: str, company_name: str) -> Optional[str]:
    if should_force_extensiv_lifecycle_summary(question, integration_source):
        logger.info("[Router] Forced tool path: summarize_order_lifecycle_by_warehouse")
        return summarize_order_lifecycle_by_warehouse(question)

    if normalize_integration_source(integration_source) != "extensiv" and is_capability_question(question):
        logger.info("[Router] Forced non-extensiv capability response")
        return build_non_extensiv_capability_response(question, integration_source, company_name)

    return None


def persist_chat_logs(
    *,
    question: str,
    final_answer: str,
    session_id: str,
    user_id: str,
    account_id: str,
    user_type: str,
    integration_source: str,
    company_name: str,
    model_name: str,
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()

    if question.strip():
        supabase = get_supabase_client()
        supabase.table("ai_chat_logs").insert({
            "session_id": session_id,
            "user_id": user_id,
            "account_id": account_id,
            "role": "user",
            "question": question,
            "timestamp": timestamp,
            "metadata": {
                "model": model_name,
                "user_type": user_type,
                "integration_source": integration_source,
                "company_name": company_name,
            }
        }).execute()

    if final_answer.strip():
        supabase = get_supabase_client()
        supabase.table("ai_chat_logs").insert({
            "session_id": session_id,
            "user_id": user_id,
            "account_id": account_id,
            "role": "ai",
            "answer": final_answer.strip(),
            "timestamp": timestamp,
            "metadata": {
                "model": model_name,
                "user_type": user_type,
                "integration_source": integration_source,
                "company_name": company_name,
            }
        }).execute()


class AgentRequest(BaseModel):
    question: str
    account_id: str
    user_id: str
    session_id: str
    user_type: Optional[str] = None


@app.post("/chat")
async def chat_with_agent(request: AgentRequest):
    if not is_valid_uuid(request.session_id):
        raise HTTPException(status_code=400, detail="❌ Invalid session_id")

    logger.info(f"[Chat] Session: {request.session_id} | Question: {request.question}")

    resolved_user_type, resolved_account_id, resolved_integration_source, resolved_company_name = resolve_user_context(
        user_id=request.user_id,
        account_id=request.account_id,
        request_user_type=request.user_type,
    )

    logger.info("🔍 Dados da sessão (resolvidos):")
    logger.info(f"  - account_id: {resolved_account_id}")
    logger.info(f"  - user_id: {request.user_id}")
    logger.info(f"  - session_id: {request.session_id}")
    logger.info(f"  - user_type: {resolved_user_type}")
    logger.info(f"  - integration_source: {resolved_integration_source}")
    logger.info(f"  - company_name: {resolved_company_name}")

    # Session context is required by Extensiv tools.
    set_current_session_context({
        "account_id": resolved_account_id,
        "user_id": request.user_id,
        "session_id": request.session_id,
        "user_type": resolved_user_type,
        "integration_source": resolved_integration_source,
        "company_name": resolved_company_name,
    })

    forced_answer = resolve_forced_response(
        question=request.question,
        integration_source=resolved_integration_source,
        company_name=resolved_company_name,
    )
    if forced_answer is not None:
        async def forced_stream_response():
            final_answer = forced_answer
            yield final_answer

            try:
                persist_chat_logs(
                    question=request.question,
                    final_answer=final_answer,
                    session_id=request.session_id,
                    user_id=request.user_id,
                    account_id=resolved_account_id,
                    user_type=resolved_user_type,
                    integration_source=resolved_integration_source,
                    company_name=resolved_company_name,
                    model_name="deterministic_tool_router",
                )
            except Exception as e:
                logger.error(f"❌ Error saving forced-route logs to Supabase: {e}")

        return StreamingResponse(forced_stream_response(), media_type="text/plain")

    try:
        model = ChatOpenAI(
            model_name="gpt-3.5-turbo-0125",
            temperature=0,
            streaming=True,
        )

        agent, chat_history = await createSyncGuardianAgent(
            model=model,
            account_id=resolved_account_id,
            user_id=request.user_id,
            session_id=request.session_id,
            user_type=resolved_user_type,
            integration_source=resolved_integration_source,
            company_name=resolved_company_name,
        )

    except Exception as e:
        logger.error(f"❌ Error creating agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create AI agent")

    async def stream_response():
        logger.info(f"🚀 Iniciando stream com dados:")
        logger.info(f"  - question: {request.question}")
        logger.info(f"  - account_id: {resolved_account_id}")
        logger.info(f"  - user_id: {request.user_id}")
        logger.info(f"  - session_id: {request.session_id}")
        logger.info(f"  - user_type: {resolved_user_type}")
        logger.info(f"  - integration_source: {resolved_integration_source}")
        logger.info(f"  - company_name: {resolved_company_name}")

        final_answer = ""
        try:
            agent_input = {
                "input": request.question,
                "chat_history": chat_history,
                "account_id": resolved_account_id,
                "user_id": request.user_id,
                "session_id": request.session_id,
                "user_type": resolved_user_type,
                "integration_source": resolved_integration_source,
                "company_name": resolved_company_name,
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
            persist_chat_logs(
                question=request.question,
                final_answer=final_answer,
                session_id=request.session_id,
                user_id=request.user_id,
                account_id=resolved_account_id,
                user_type=resolved_user_type,
                integration_source=resolved_integration_source,
                company_name=resolved_company_name,
                model_name="gpt-3.5-turbo-0125",
            )
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
