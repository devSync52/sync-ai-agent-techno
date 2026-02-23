from langchain.tools import tool
import os

from app.langchain_v2.utils.date_parser import parse_period_input
from app.utils.supabase_client import get_supabase_client

def _fetch_all_rows_via_raw_sql(supabase, sql: str, batch_size: int = 1000):
    """Fetch all rows from a raw_sql RPC by paginating with LIMIT/OFFSET."""
    all_rows = []
    offset = 0

    # Ensure we don't end with a semicolon before appending LIMIT/OFFSET
    base_sql = sql.strip().rstrip(";")

    while True:
        paged_sql = f"{base_sql}\nLIMIT {batch_size} OFFSET {offset}"
        res = supabase.rpc("raw_sql", {"sql": paged_sql}).execute()
        batch = res.data or []
        all_rows.extend(batch)

        if len(batch) < batch_size:
            break

        offset += batch_size

    return all_rows

@tool
def summarize_orders_by_period_by_marketplace(input_text: str) -> str:
    """
    Summarizes orders by marketplace for a given period.
    Accepts periods like 'last week', 'this month', 'June', 'May 2024', or date ranges like 'May 1 to May 10'.
    """
        
    supabase = get_supabase_client()
    
    try:
        from app.langchain_v2.utils.session_context import get_current_session_context
        context = get_current_session_context()
        account_id = context.get("account_id")
        user_type = context.get("user_type")

        if not account_id:
            return "❌ Missing account ID in session context."

        filter_column = "account_id" if user_type == "owner" else "channel_account_id"

        start_str, end_str = parse_period_input(input_text)

        query = f"""
            select
              marketplace_name,
              count(*) as total_orders,
              sum(grand_total)::numeric(10,2) as total_revenue,
              sum(case when status_code = 2 then 1 else 0 end) as total_processing,
              sum(case when status_code = 3 then 1 else 0 end) as total_shipped,
              sum(case when status_code = -1 then 1 else 0 end) as total_cancelled
            from public.ai_orders_unified_6
            where order_date >= date '{start_str}'
              and order_date < (date '{end_str}' + interval '1 day')
              and {filter_column} = '{account_id}'
            group by marketplace_name
            order by total_orders desc
        """

        rows = _fetch_all_rows_via_raw_sql(supabase, query)

        if not rows:
            return f"No orders found between {start_str} and {end_str}."

        lines = [f"📊 Order summary by marketplace from {start_str} to {end_str}:"]
        for row in rows:
            lines.append(
                f"\n🛒 {row['marketplace_name']}\n"
                f"• Total Orders: {row['total_orders']}\n"
                f"• Revenue: ${row['total_revenue']}\n"
                f"• Processing: {row['total_processing']}, "
                f"Shipped: {row['total_shipped']}, "
                f"Cancelled: {row['total_cancelled']}"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Error while summarizing orders: {str(e)}"
    
summarize_orders_by_period_by_marketplace_tool = summarize_orders_by_period_by_marketplace
