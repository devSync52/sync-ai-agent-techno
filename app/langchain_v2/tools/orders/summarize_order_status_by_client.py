from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from supabase import create_client
import os


# 🔗 Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@tool
def summarize_order_status_by_client(input: str = "") -> str:
    """
    Provides a summary of orders grouped by client and order status.
    """
    try:
        response = (
            supabase.table("ai_order_status_by_client")
            .select("*")
            .order("client_name")
            .execute()
        )

        data = response.data or []

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
        lines = ["📦 **Order Status Summary by Client:**\n"]
        for client, statuses in grouped.items():
            lines.append(f"**{client}**")
            for s in statuses:
                lines.append(
                    f"• {s['status']} - Orders: {s['orders']} | Revenue: ${s['revenue']:,.2f}"
                )
            lines.append("")  # 🔥 Linha vazia entre clientes

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error summarizing order status by client: {str(e)}"


# ✅ Export
summarize_order_status_by_client_tool = summarize_order_status_by_client