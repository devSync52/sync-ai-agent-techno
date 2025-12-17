from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
import os
from app.utils.supabase_client import get_supabase_client
from app.langchain_v2.utils.session_context import get_current_session_context

def _fetch_all_rows(query, batch_size: int = 1000):
    """Fetches all rows from a Supabase query using pagination (PostgREST default page size is 1000 rows)."""
    all_rows = []
    offset = 0

    while True:
        batch = query.range(offset, offset + batch_size - 1).execute()
        data = batch.data or []
        all_rows.extend(data)

        if len(data) < batch_size:
            break

        offset += batch_size

    return all_rows

@tool
def summarize_order_status_by_client(input: str = "") -> str:
    """
    Provides a summary of orders grouped by client and order status.
    """
        
    supabase = get_supabase_client()
    context = get_current_session_context()
    account_id = context.get("account_id")
    user_type = context.get("user_type")
    
    try:
        query = supabase.table("ai_order_status_by_client_v2").select("*")
        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)
        query = query.order("client_name")
        data = _fetch_all_rows(query)

        if not data:
            return "No order data found."

        # 🔥 Agrupamento dos dados por cliente
        grouped = {}
        for row in data:
            client = row.get("client_name", "Unknown Client")
            status = row.get("order_status", "Unknown Status")
            orders = int(row.get("total_orders", 0))
            revenue = float(row.get("total_revenue", 0))

            if client not in grouped:
                grouped[client] = []

            grouped[client].append({
                "status": status,
                "orders": orders,
                "revenue": revenue
            })

        # 🔥 Construção da resposta formatada
        lines = ["**Order Status Summary by Client:**\n"]
        for client, statuses in grouped.items():
            lines.append(f"**{client}**")
            for s in statuses:
                lines.append(
                    f"• {s['status']} - Orders: {s['orders']} | Revenue: ${s['revenue']:,.2f}"
                )
            lines.append("")  # Linha vazia entre clientes

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error summarizing order status by client: {str(e)}"


# ✅ Export
summarize_order_status_by_client_tool = summarize_order_status_by_client