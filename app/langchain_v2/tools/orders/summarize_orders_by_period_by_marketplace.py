from datetime import datetime
from langchain.tools import tool
from supabase import create_client, Client
import os

from app.langchain_v2.utils.date_parser import parse_period_input


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@tool
def summarize_orders_by_period_by_marketplace(input_text: str) -> str:
    """
    Summarizes orders by marketplace for a given period.
    Accepts periods like 'last week', 'this month', 'June', 'May 2024', or date ranges like 'May 1 to May 10'.
    """
    try:
        start_str, end_str = parse_period_input(input_text)
        start_date = datetime.fromisoformat(start_str)
        end_date = datetime.fromisoformat(end_str)

        query = f"""
            select
              marketplace_name,
              count(*) as total_orders,
              sum(grand_total)::numeric(10,2) as total_revenue,
              sum(case when status_code = 2 then 1 else 0 end) as total_processing,
              sum(case when status_code = 3 then 1 else 0 end) as total_shipped,
              sum(case when status_code = -1 then 1 else 0 end) as total_cancelled
            from public.ai_orders_unified
            where order_date between '{start_date}' and '{end_date}'
            group by marketplace_name
            order by total_orders desc
        """

        result = supabase.rpc("raw_sql", {"sql": query}).execute()
        rows = result.data

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