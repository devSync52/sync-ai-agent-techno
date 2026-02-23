from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input, get_previous_period
from app.langchain_v2.utils.session_context import get_current_session_context
import os
from app.utils.supabase_client import get_supabase_client

def _run_count_distinct_orders(supabase, sql: str) -> int:
    """Execute a COUNT(DISTINCT ...) SQL via raw_sql RPC and return an integer safely.

    Note: This tool is NOT impacted by PostgREST's 1000-row cap because it returns a single aggregated row.
    """
    base_sql = (sql or "").strip().rstrip(";")
    res = supabase.rpc("raw_sql", {"sql": base_sql}).execute()
    data = res.data or []
    if not data:
        return 0
    # Accept either dict row or list-like row
    row0 = data[0]
    if isinstance(row0, dict):
        return int(row0.get("total_orders") or 0)
    try:
        return int(row0[0] or 0)
    except Exception:
        return 0

@tool
def compare_sales_by_period(input: str) -> str:
    """
    Compare total orders between a period and its previous period.
    Example: 'Compare sales this month' or 'Compare orders from May'.
    """
        
    supabase = get_supabase_client()
    
    try:
        session = get_current_session_context()
        account_id = session.get("account_id")
        user_type = session.get("user_type")

        start, end = parse_period_input(input)
        prev_start, prev_end = get_previous_period(start, end)

        if user_type == "client":
            current_query = f"""
                SELECT COALESCE(count(distinct order_id), 0) AS total_orders
                FROM view_all_orders_v4
                WHERE order_date >= date '{start}' AND order_date < (date '{end}' + interval '1 day')
                  AND channel_id = '{account_id}'
            """
            previous_query = f"""
                SELECT COALESCE(count(distinct order_id), 0) AS total_orders
                FROM view_all_orders_v4
                WHERE order_date >= date '{prev_start}' AND order_date < (date '{prev_end}' + interval '1 day')
                  AND channel_id = '{account_id}'
            """
        else:
            current_query = f"""
                SELECT COALESCE(count(distinct order_id), 0) AS total_orders
                FROM view_all_orders_v4
                WHERE order_date >= date '{start}' AND order_date < (date '{end}' + interval '1 day')
                  AND account_id = '{account_id}'
            """
            previous_query = f"""
                SELECT COALESCE(count(distinct order_id), 0) AS total_orders
                FROM view_all_orders_v4
                WHERE order_date >= date '{prev_start}' AND order_date < (date '{prev_end}' + interval '1 day')
                  AND account_id = '{account_id}'
            """

        current = _run_count_distinct_orders(supabase, current_query)
        previous = _run_count_distinct_orders(supabase, previous_query)

        diff = current - previous
        trend = "📈 increase" if diff > 0 else "📉 decrease" if diff < 0 else "➖ no change"

        return (
            f"📦 **Order Comparison**\n"
            f"- {start} to {end}: **{current} orders**\n"
            f"- {prev_start} to {prev_end}: **{previous} orders**\n"
            f"- Difference: **{diff} orders** ({trend})"
        )

    except Exception as e:
        return f"❌ Error comparing sales: {str(e)}"


compare_sales_by_period_tool = compare_sales_by_period
