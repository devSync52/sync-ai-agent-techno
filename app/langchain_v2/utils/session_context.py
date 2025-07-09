from typing import Optional, Dict
import contextvars

# 📌 Contexto armazenado localmente por execução
_current_session_context: contextvars.ContextVar[Optional[Dict[str, str]]] = contextvars.ContextVar(
    "current_session_context", default=None
)

def set_current_session_context(ctx: Dict[str, str]):
    """Define os dados da sessão atual no contexto (ex: account_id, user_type)."""
    _current_session_context.set(ctx)

def get_current_session_context() -> Dict[str, str]:
    """Recupera o contexto atual da sessão."""
    ctx = _current_session_context.get()
    return ctx or {}