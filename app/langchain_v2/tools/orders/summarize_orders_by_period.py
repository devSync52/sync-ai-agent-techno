from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
import os
from app.utils.supabase_client import get_supabase_client

@tool
def summarize_orders_by_period(input_text: str) -> str:
    """
    Provides an overview of the number of orders and total revenue in a given period, grouped by status.
    Example: 'Overview last month', 'Overview this week', 'Overview in May'.
    """
        
    supabase = get_supabase_client()
    
    try:
        print(f"[DEBUG] Input received: {input_text}")

        start_date, end_date = parse_period_input(input_text)
        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        response = supabase.rpc("summarize_orders_overview", {
            "start_date": start_date,
            "end_date": end_date
        }).execute()

        data = response.data or []

        if not data:
            return f"No orders found between {start_date} and {end_date}."

        # 🔥 Formatting
        lines = [f"📦 **Order Overview from {start_date} to {end_date}:**\n"]
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