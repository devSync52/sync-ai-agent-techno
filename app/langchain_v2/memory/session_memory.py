from langchain.schema import AIMessage, HumanMessage
from datetime import datetime, timezone
from app.utils.supabase_client import supabase


class SupabaseConversationMemory:
    """Memória persistente no Supabase"""

    def __init__(self, session_id: str):
        self.session_id = session_id

    @property
    def memory_variables(self):
        """Variáveis que a memória fornece para o agente"""
        return ["history"]

    def load_memory_variables(self, inputs):
        """Carrega o histórico da sessão"""
        res = (
            supabase.table("ai_chat_logs")
            .select("*")
            .eq("session_id", self.session_id)
            .order("timestamp", desc=False)
            .execute()
        )
        data = res.data or []

        history = ""
        for row in data:
            if row["role"] == "user" and row.get("question"):
                history += f"User: {row['question']}\n"
            elif row["role"] in ["ai", "assistant"] and row.get("answer"):
                history += f"AI: {row['answer']}\n"

        return {"history": history}

    def save_context(self, inputs, outputs):
        """Salva pergunta e resposta"""
        question = inputs.get("input") or list(inputs.values())[0]
        answer = outputs.get("output") or list(outputs.values())[0]

        timestamp = datetime.now(timezone.utc)

        if question:
            supabase.table("ai_chat_logs").insert({
                "session_id": self.session_id,
                "question": question,
                "role": "user",
                "timestamp": timestamp
            }).execute()

        if answer:
            supabase.table("ai_chat_logs").insert({
                "session_id": self.session_id,
                "answer": answer,
                "role": "ai",
                "timestamp": timestamp
            }).execute()

    def clear(self):
        """Apaga todo o histórico da sessão"""
        supabase.table("ai_chat_logs").delete().eq("session_id", self.session_id).execute()


# 🚀 Função para criar a memória
async def get_memory(session_id: str):
    return SupabaseConversationMemory(session_id=session_id)


# 🔍 Função para puxar o histórico bruto (para endpoints de histórico/chat logs)
def get_session_history_from_db(session_id: str, limit: int = 20):
    res = (
        supabase.table("ai_chat_logs")
        .select("*")
        .eq("session_id", session_id)
        .order("timestamp", desc=False)
        .limit(limit)
        .execute()
    )
    return res.data or []