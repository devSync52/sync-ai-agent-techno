from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from app.utils.supabase_client import get_supabase_client

@tool
def summarize_sales_by_period(input_text: str) -> str:
    """
Summarizes total orders and total revenue for a given period.
Understands questions like:
- 'How many sales yesterday?'
- 'How many sales this week?'
- 'Sales last month'
- 'How much revenue yesterday?'
"""
        
    supabase = get_supabase_client()
    
    from app.langchain_v2.utils.session_context import get_current_session_context
    ctx = get_current_session_context()

    if not ctx or not ctx.get("account_id") or not ctx.get("user_type"):
        return "❌ Session context not available. Please log in."

    account_id = ctx["account_id"]
    user_type = ctx["user_type"]
    
    try:
        start_date, end_date = parse_period_input(input_text)

        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        query = (
            supabase
            .from_("ai_orders_unified_4")
            .select("grand_total")
            .gte("order_date", start_date)
            .lte("order_date", end_date)
            .in_("status_code", [3, 4])
        )

        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        response = query.execute()
        rows = response.data or []

        total_orders = len(rows)
        total_revenue = sum(order.get("grand_total", 0) for order in rows)

        if total_orders == 0:
            return f"❌ No sales found between {start_date} and {end_date}."

        return (
            f"📊 **Sales Summary from {start_date} to {end_date}:**\n"
            f"- Total Orders: {total_orders}\n"
            f"- Total Revenue: ${total_revenue:,.2f}"
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error summarizing sales: {str(e)}"


# ✅ Exporta a tool
summarize_sales_by_period_tool = summarize_sales_by_period