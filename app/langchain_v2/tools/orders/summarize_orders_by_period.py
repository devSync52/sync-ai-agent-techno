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
def summarize_orders_by_period(input_text: str, account_id: str = None, user_type: str = None, user_id: str = None) -> str:
    """
    Provides an overview of the number of orders and total revenue in a given period, grouped by status.
    Example: 'Overview last month', 'Overview this week', 'Overview in May'.
    """
        
    supabase = get_supabase_client()
    
    try:
        print(f"[DEBUG] Input received: {input_text}")
        
        # ✅ Usar parâmetros recebidos, com fallback para contexto
        context = get_current_session_context()
        account_id = account_id or context.get("account_id")
        user_type = user_type or context.get("user_type")
        user_id = user_id or context.get("user_id")
        print(f"[DEBUG] Session context - account_id: {account_id} | user_type: {user_type}")

        start_date, end_date = parse_period_input(input_text)
        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        if user_type not in ("owner", "client"):
            return f"❌ Unknown user type: {user_type}"

        # ✅ Prefer server-side aggregation via RPC (faster, avoids row limits/pagination)
        rpc_payload = {
            "p_account_id": account_id,
            "p_user_type": user_type,
            "p_start_date": str(start_date),
            "p_end_date": str(end_date),
        }

        resp = supabase.rpc("summarize_orders_by_period", rpc_payload).execute()
        data = resp.data or []

        if not data:
            return f"No orders found between {start_date} and {end_date}."

        # Normalize keys expected in formatting below
        # Each row should have: status, total_orders, total_revenue
        for row in data:
            if "order_status" in row and "status" not in row:
                row["status"] = row.get("order_status")
            row["total_orders"] = int(row.get("total_orders") or 0)
            row["total_revenue"] = float(row.get("total_revenue") or 0)

        # 🔥 Formatting
        count_label = ""
        lines = [f"📦 **Order Overview from {start_date} to {end_date}{count_label}:**\n"]
        total_revenue_all = sum(float(row.get("total_revenue", 0)) for row in data)
        total_orders_all = sum(int(row.get("total_orders", 0)) for row in data)

        lines.append(f"🧾 Total Revenue: ${total_revenue_all:,.2f}")
        lines.append(f"📦 Total Orders: {total_orders_all}")

        lines.append("\n🔎 Breakdown by Status:")
        for row in data:
            status = row.get("status", "Unknown")
            total = row.get("total_orders", 0)
            revenue = float(row.get("total_revenue", 0))

            lines.append(f"• {status}: {total} orders | ${revenue:,.2f}")

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ An error occurred while summarizing orders: {str(e)}"


# ✅ Export
summarize_orders_by_period_tool = summarize_orders_by_period