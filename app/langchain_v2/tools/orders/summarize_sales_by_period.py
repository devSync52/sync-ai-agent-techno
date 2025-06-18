from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()


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
    try:
        start_date, end_date = parse_period_input(input_text)

        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        response = supabase.rpc("summarize_sales_by_period", {
            "start_date": start_date,
            "end_date": end_date
        }).execute()

        data = response.data[0] if response.data else {}

        total_orders = data.get("total_orders", 0)
        total_revenue = data.get("total_revenue", 0)

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