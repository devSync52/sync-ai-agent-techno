from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from app.langchain_v2.utils.session_context import get_current_session_context
import os
from app.utils.supabase_client import get_supabase_client

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
def list_sales_by_period(input_text: str) -> str:
    """
    Lists orders for a given period with order ID, date, client name, and total.
    Example: 'List sales yesterday', 'List sales this week', 'List sales in May'.
    """
        
    supabase = get_supabase_client()
    
    try:
        start_date, end_date = parse_period_input(input_text)
        session_context = get_current_session_context()
        account_id = session_context.get("account_id")
        user_type = session_context.get("user_type")
        user_id = session_context.get("user_id")

        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        # 🔥 Lógica sniper — se for um único dia, usa EQ
        if start_date == end_date:
            query = (
                supabase.table("ai_orders_unified_6")
                .select("order_id, order_date, client_name, grand_total")
                .eq("order_date", start_date)
                .order("order_date", desc=False)
            )
        else:
            query = (
                supabase.table("ai_orders_unified_6")
                .select("order_id, order_date, client_name, grand_total")
                .gte("order_date", start_date)
                .lte("order_date", end_date)
                .order("order_date", desc=False)
            )

        # 🎯 Filtra por escopo de usuário
        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        data = _fetch_all_rows(query)

        if not data:
            return f"❌ No sales found between {start_date} and {end_date}."

        lines = [
            f"📦 **Sales from {start_date} to {end_date}:**\n"
        ]

        for order in data:
            lines.append(
                f"- {order.get('order_id')} | {order.get('order_date')} | "
                f" {order.get('client_name')} | ${float(order.get('grand_total') or 0):,.2f}"
            )

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error listing sales: {str(e)}"


# ✅ Exporta a tool
list_sales_by_period_tool = list_sales_by_period