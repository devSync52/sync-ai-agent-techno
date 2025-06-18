from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input, get_previous_period
import os
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()


@tool
def compare_revenue_by_period(input: str) -> str:
    """
    Compare total revenue between a period and its previous period.
    Example: 'Compare revenue this month' or 'Revenue from May'.
    """

    try:
        start, end = parse_period_input(input)
        prev_start, prev_end = get_previous_period(start, end)

        current_query = f"""
            SELECT sum(total_amount) AS total_revenue
            FROM view_all_orders
            WHERE order_date >= '{start}' AND order_date <= '{end}'
        """
        previous_query = f"""
            SELECT sum(total_amount) AS total_revenue
            FROM view_all_orders
            WHERE order_date >= '{prev_start}' AND order_date <= '{prev_end}'
        """

        current_res = supabase.rpc("raw_sql", {"sql": current_query}).execute()
        previous_res = supabase.rpc("raw_sql", {"sql": previous_query}).execute()

        current = current_res.data[0]["total_revenue"] or 0
        previous = previous_res.data[0]["total_revenue"] or 0

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