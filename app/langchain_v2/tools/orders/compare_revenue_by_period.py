from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input, get_previous_period
from app.langchain_v2.utils.session_context import get_current_session_context
import os
from app.utils.supabase_client import get_supabase_client

def _run_sum_revenue(supabase, sql: str) -> float:
    """Execute a SUM(...) SQL via raw_sql RPC and return a float safely.

    Note: This query returns a single aggregated row and is NOT affected by the 1000-row cap.
    """
    base_sql = (sql or "").strip().rstrip(";")
    res = supabase.rpc("raw_sql", {"sql": base_sql}).execute()
    data = res.data or []
    if not data:
        return 0.0
    row0 = data[0]
    if isinstance(row0, dict):
        return float(row0.get("total_revenue") or 0)
    try:
        return float(row0[0] or 0)
    except Exception:
        return 0.0

@tool
def compare_revenue_by_period(input: str) -> str:
    """
    Compare total revenue between a period and its previous period.
    Example: 'Compare revenue this month' or 'Revenue from May'.
    """
        
    supabase = get_supabase_client()
    session = get_current_session_context()
    account_id = session.get("account_id")
    user_type = session.get("user_type")
    
    try:
        start, end = parse_period_input(input)
        prev_start, prev_end = get_previous_period(start, end)

        if user_type == "client":
            account_filter = f"channel_id = '{account_id}'"
        else:
            account_filter = f"account_id = '{account_id}'"

        current_query = f"""
            SELECT COALESCE(sum(total_amount), 0) AS total_revenue
            FROM view_all_orders_v4
            WHERE order_date >= date '{start}' AND order_date < (date '{end}' + interval '1 day')
            AND {account_filter}
        """
        previous_query = f"""
            SELECT COALESCE(sum(total_amount), 0) AS total_revenue
            FROM view_all_orders_v4
            WHERE order_date >= date '{prev_start}' AND order_date < (date '{prev_end}' + interval '1 day')
            AND {account_filter}
        """

        current = _run_sum_revenue(supabase, current_query)
        previous = _run_sum_revenue(supabase, previous_query)

        diff = current - previous
        trend = "📈 increase" if diff > 0 else "📉 decrease" if diff < 0 else "➖ no change"

        return (
            f"**Revenue Comparison**\n"
            f"- {start} to {end}: **${current:,.2f}**\n"
            f"- {prev_start} to {prev_end}: **${previous:,.2f}**\n"
            f"- Difference: **${diff:,.2f}** ({trend})"
        )

    except Exception as e:
        return f"❌ Error comparing revenue: {str(e)}"


compare_revenue_by_period_tool = compare_revenue_by_period
