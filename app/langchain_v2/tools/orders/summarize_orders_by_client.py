from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from supabase import create_client
import os


# 🔗 Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@tool
def summarize_orders_by_client(input: str = "") -> str:
    """
    Provides a summary of orders grouped by client, with marketplaces nested below.
    """
    try:
        response = (
            supabase.table("ai_orders_summary_by_client")
            .select("*")
            .execute()
        )

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