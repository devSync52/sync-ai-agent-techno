import os
from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()


@tool
def get_stock_forecast_by_sku(sku: str) -> str:
    """
    Estimate inventory coverage and stockout date for a given SKU.
    Sales velocity.
    """
    try:
        response = (
            supabase
            .table("ai_stock_coverage_unified")
            .select("*")
            .eq("sku", sku)
            .limit(1)
            .execute()
        )

        if not response.data:
            return f"⚠️ SKU {sku} not found in inventory data."

        record = response.data[0]
        coverage_days = record.get("estimated_coverage_days")
        stockout_date = record.get("estimated_stockout_date")
        velocity = record.get("daily_sales_velocity")
        available = record.get("quantity_available")
        product = record.get("product_name")

        return (
            f"📦 {sku} ({product}) has {available} units available. "
            f"Daily sales velocity is {round(velocity, 2)} units/day. "
            f"Estimated coverage: {coverage_days} days. "
            f"Expected stockout date: {stockout_date}."
        )

    except Exception as e:
        return f"❌ Error retrieving forecast for SKU {sku}: {str(e)}"

# Register the tool (optional alias)
get_stock_forecast_by_sku_tool = get_stock_forecast_by_sku