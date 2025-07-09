from app.langchain_v2.utils.session_context import get_current_session_context
from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client


@tool
def get_inventory_by_sku(input: str) -> str:
    """
    Retrieve inventory level, warehouse, lead time, and reorder point for a specific SKU.
    Input must be the SKU code (string).
    """
    sku = input.strip().upper()

    supabase = get_supabase_client()

    try:
        session = get_current_session_context()
        account_id = session.get("account_id")
        user_type = session.get("user_type")

        query = (
            supabase.table("ai_products_unified_v3")
            .select("sku, quantity_available, company_name, lead_time_days, reorder_point")
            .eq("sku", sku)
        )

        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        response = query.limit(1).execute()

        if response.data and len(response.data) > 0:
            item = response.data[0]
            qty = float(item.get("quantity_available", 0))
            warehouse = item.get("company_name", "Unknown")
            lead_time = item.get("lead_time_days", "N/A")
            reorder_point = float(item.get("reorder_point", 0))

            if qty == 0:
                stock_status = "Stockout"
            elif qty <= reorder_point:
                stock_status = "Below reorder point"
            else:
                stock_status = "Stock level OK"

            return (
                f"SKU **{sku}** has **{qty} units** available at **{warehouse}**.\n"
                f"Lead time: **{lead_time} days**.\n"
                f"Reorder point: **{reorder_point} units**.\n"
                f"{stock_status}"
            )
        else:
            return f"No inventory data found for SKU {sku}."

    except Exception as e:
        return f"❌ Error retrieving inventory for SKU {sku}: {str(e)}"
    
get_inventory_by_sku_tool = get_inventory_by_sku