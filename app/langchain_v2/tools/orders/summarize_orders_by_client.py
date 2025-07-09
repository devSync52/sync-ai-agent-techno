from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
import os
from app.utils.supabase_client import get_supabase_client
from app.langchain_v2.utils.session_context import get_current_session_context

@tool
def summarize_orders_by_client(input: str = "") -> str:
    """
    Provides a summary of orders grouped by client, with marketplaces nested below.
    """
        
    supabase = get_supabase_client()
    session_context = get_current_session_context()
    account_id = session_context.get("account_id")
    user_type = session_context.get("user_type")
    user_id = session_context.get("user_id")
    
    try:
        query = supabase.table("ai_orders_summary_by_client_v2").select("*")
        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)
        response = query.order("client_name").execute()

        data = response.data or []

        if not data:
            return "No orders found."

        # 🔥 Agrupamento dos dados
        grouped = {}
        for row in data:
            client = row.get("client_name", "Unknown Client")
            marketplace = row.get("marketplace_name", "Unknown Marketplace")
            orders = row.get("total_orders", 0)
            revenue = float(row.get("total_revenue", 0))

            if client not in grouped:
                grouped[client] = {}

            if marketplace not in grouped[client]:
                grouped[client][marketplace] = {"orders": 0, "revenue": 0.0}

            grouped[client][marketplace]["orders"] += orders
            grouped[client][marketplace]["revenue"] += revenue

        # 🔥 Construção da resposta formatada
        lines = ["📦 **Order Summary by Client:**\n"]
        for client, marketplaces in grouped.items():
            lines.append(f"**{client}**")
            for marketplace, stats in marketplaces.items():
                orders = stats["orders"]
                revenue = stats["revenue"]
                lines.append(
                    f"• {marketplace} - Orders: {orders} | Revenue: ${revenue:,.2f}"
                )
            lines.append("")  # 🔥 Linha vazia entre clientes

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error summarizing orders by client: {str(e)}"


# ✅ Export
summarize_orders_by_client_tool = summarize_orders_by_client