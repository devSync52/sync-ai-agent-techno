from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input, get_previous_period
from app.langchain_v2.utils.session_context import get_current_session_context
import os
from app.utils.supabase_client import get_supabase_client

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
                SELECT count(distinct order_id) AS total_orders
                FROM view_all_orders_v2
                WHERE order_date >= '{start}' AND order_date <= '{end}'
                  AND channel_id = '{account_id}'
            """
            previous_query = f"""
                SELECT count(distinct order_id) AS total_orders
                FROM view_all_orders_v2
                WHERE order_date >= '{prev_start}' AND order_date <= '{prev_end}'
                  AND channel_id = '{account_id}'
            """
        else:
            current_query = f"""
                SELECT count(distinct order_id) AS total_orders
                FROM view_all_orders_v2
                WHERE order_date >= '{start}' AND order_date <= '{end}'
                  AND account_id = '{account_id}'
            """
            previous_query = f"""
                SELECT count(distinct order_id) AS total_orders
                FROM view_all_orders_v2
                WHERE order_date >= '{prev_start}' AND order_date <= '{prev_end}'
                  AND account_id = '{account_id}'
            """

        current_res = supabase.rpc("raw_sql", {"sql": current_query}).execute()
        current = current_res.data[0]["total_orders"] or 0

        previous_res = supabase.rpc("raw_sql", {"sql": previous_query}).execute()
        previous = previous_res.data[0]["total_orders"] or 0

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