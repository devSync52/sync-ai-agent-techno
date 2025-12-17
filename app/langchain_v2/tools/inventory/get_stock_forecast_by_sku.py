import os
from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client
from app.langchain_v2.utils.session_context import get_current_session_context





@tool
def get_stock_forecast_by_sku(sku: str) -> str:
    """
    Estimate inventory coverage and stockout date for a given SKU.
    Sales velocity.
    """
    context = get_current_session_context()
    account_id = context.get("account_id")
    user_type = context.get("user_type")
    supabase = get_supabase_client()
    try:
        query = (
            supabase
            .table("ai_stock_coverage_sellercloud_v4")
            .select("*")
            .eq("sku", sku)
        )

        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        response = query.limit(1).execute()

        if not response.data:
            return f"SKU {sku} not found in inventory data."

        record = response.data[0]
        coverage_days = record.get("estimated_coverage_days")
        stockout_date = record.get("estimated_stockout_date")
        velocity = record.get("daily_sales_velocity")
        available = record.get("quantity_available")
        product = record.get("product_name")

        return (
            f"{sku} ({product}) has {available} units available. "
            f"Daily sales velocity is {round(velocity, 2)} units/day. "
            f"Estimated coverage: {coverage_days} days. "
            f"Expected stockout date: {stockout_date}."
        )

    except Exception as e:
        return f"❌ Error retrieving forecast for SKU {sku}: {str(e)}"

# Register the tool (optional alias)
get_stock_forecast_by_sku_tool = get_stock_forecast_by_sku