import os
from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
import re
from collections import defaultdict
from app.utils.supabase_client import get_supabase_client
from app.langchain_v2.utils.session_context import get_current_session_context

@tool
def get_top_revenue_skus_by_period(input_text: str) -> str:
    """Get top SKUs by revenue between a specified date range (e.g., 'May 1 to May 10')."""
        
    supabase = get_supabase_client()
    
    try:
         # 🎯 Parse de data
        start_date, end_date = parse_period_input(input_text)

        print(f"[DEBUG] Fetching sales from {start_date} to {end_date}")

        session = get_current_session_context()
        account_id = session.get("account_id")
        user_type = session.get("user_type")

        query = (
            supabase
            .table("ai_sku_sales_per_day_unified_v2")
            .select("sku, quantity_sold, total_revenue")
            .gte("sales_date", start_date)
            .lte("sales_date", end_date)
        )

        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        response = query.execute()

        if not response.data:
            return f"⚠️ No sales data found between {start_date} and {end_date}."

        totals = defaultdict(lambda: {"units": 0, "revenue": 0.0})
        for row in response.data:
            sku = row["sku"]
            totals[sku]["units"] += int(row.get("quantity_sold", 0))
            totals[sku]["revenue"] += float(row.get("total_revenue", 0))

        top_skus = sorted(totals.items(), key=lambda x: x[1]["revenue"], reverse=True)[:5]

        lines = [f"Period: {start_date} to {end_date}\nTop SKUs by Revenue:"]
        for sku, data in top_skus:
            lines.append(f"{sku}: {data['units']} units sold, revenue: ${data['revenue']:.2f}")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Error: {str(e)}"
    
get_top_revenue_skus_by_period_tool = get_top_revenue_skus_by_period