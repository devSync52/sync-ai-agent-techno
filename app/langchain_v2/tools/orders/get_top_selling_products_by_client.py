from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
import os
from app.utils.supabase_client import get_supabase_client

# Import for session context
from app.langchain_v2.utils.session_context import get_current_session_context

@tool
def get_top_selling_products_by_client(input: str = "") -> str:
    """
    Lists the top selling products grouped by client.
    """
    # Get session context for account_id and user_type
    session = get_current_session_context()
    account_id = session.get("account_id")
    user_type = session.get("user_type")

    supabase = get_supabase_client()

    try:
        query = supabase.table("ai_top_selling_products_by_client_v2").select("*")

        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        response = (
            query.order("total_quantity_sold", desc=True)
            .limit(50)  # 🔥 Pode ajustar esse limite
            .execute()
        )

        data = response.data or []

        if not data:
            return "No product sales found."

        # 🔥 Agrupamento dos dados por cliente
        grouped = {}
        for row in data:
            client = row.get("client_name", "Unknown Client")
            sku = row.get("sku")
            qty = int(row.get("total_quantity_sold", 0))
            revenue = float(row.get("total_revenue", 0))

            if client not in grouped:
                grouped[client] = []

            grouped[client].append({
                "sku": sku,
                "qty": qty,
                "revenue": revenue
            })

        # 🔥 Construção da resposta formatada
        lines = ["📦 **Top Selling Products by Client:**\n"]
        for client, products in grouped.items():
            lines.append(f"**{client}**")
            for p in products:
                lines.append(
                    f"   - {p['sku']} | Qty: {p['qty']} | Revenue: ${p['revenue']:,.2f}"
                )
            lines.append("")  # 🔥 Linha vazia entre clientes

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error summarizing top selling products by client: {str(e)}"


# ✅ Export
get_top_selling_products_by_client_tool = get_top_selling_products_by_client