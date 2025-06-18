from langchain.tools import tool
from supabase import create_client
import os

# 🔗 Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@tool
def get_products_at_risk(input: str = "30") -> str:
    """
    Retrieves products at risk of stockout within the specified number of days.
    Default is 30 days.
    Input example: '30'
    """
    try:
        days_ahead = int(input.strip())

        response = (
            supabase.table("ai_stock_coverage_unified_2")
            .select("*")
            .lte("estimated_coverage_days", days_ahead)
            .order("estimated_coverage_days", desc=False)
            .execute()
        )

        data = response.data or []

        if not data:
            return f"✅ No products are at risk within {days_ahead} days."

        lines = [f"⚠️ Products at risk within {days_ahead} days:\n"]
        for row in data:
            sku = row.get("sku")
            name = row.get("product_name")
            qty = row.get("quantity_available", 0)
            avg_sales = row.get("avg_daily_sales", 0)
            coverage = row.get("estimated_coverage_days")
            stockout_date = row.get("estimated_stockout_date")
            urgency = row.get("urgency_level")
            risk = "✅ At Risk" if row.get("at_risk") else "🟢 Safe"

            coverage_str = f"{coverage:.1f} days" if coverage is not None else "No data"
            stockout_str = f"{stockout_date}" if stockout_date else "Unknown"

            lines.append(
                f"• {sku} - {name}\n"
                f"   Stock: {qty} | Avg sales/day: {avg_sales:.2f} | Coverage: {coverage_str}\n"
                f"   Stockout Date: {stockout_str} | {risk} | Urgency: {urgency.capitalize()}"
            )

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error checking products at risk: {str(e)}"

get_products_at_risk_tool = get_products_at_risk