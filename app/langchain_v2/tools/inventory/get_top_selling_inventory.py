import os
from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client

@tool
def get_top_selling_inventory(input: str) -> str:
    """
    Returns the top-selling SKUs with their stock coverage, daily velocity, and stockout date.
    """
        
    supabase = get_supabase_client()
    
    try:
        response = (
            supabase
            .table("ai_stock_coverage_unified")
            .select(
                "sku, product_name, quantity_available, estimated_coverage_days, estimated_stockout_date, daily_sales_velocity, last_30d_sold"
            )
            .order("last_30d_sold", desc=True)
            .limit(5)
            .execute()
        )

        if response.data:
            lines = []
            for item in response.data:
                sku = item.get("sku")
                name = item.get("product_name", "N/A")
                available = item.get("quantity_available", 0)
                velocity = float(item.get("daily_sales_velocity") or 0)
                coverage = item.get("estimated_coverage_days")
                stockout_date = item.get("estimated_stockout_date")

                lines.append(
                    f"{sku} ({name}) – {available} units available, sells approx. {velocity:.2f} units/day, "
                    f"covers approx. {coverage} days, estimated stockout: {stockout_date}."
                )
            return "📦 **Top-selling products:**\n" + "\n".join(lines)
        else:
            return "⚠️ No top-selling product data found."

    except Exception as e:
        return f"❌ Error retrieving top-selling inventory: {str(e)}"
    
get_top_selling_inventory_tool = get_top_selling_inventory