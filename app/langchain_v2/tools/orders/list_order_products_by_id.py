from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client
import re

@tool
def list_order_products_by_id(order_id: str) -> str:
    """
    Returns the list of products inside a specific order, such as SKUs, names, quantity and unit price.
    Use this tool when the user wants to see the items or products included in an order, not the status or sales summary.
    """
    supabase = get_supabase_client()

    try:
        from app.langchain_v2.utils.session_context import get_current_session_context
        session = get_current_session_context()
        account_id = session.get("account_id")
        user_type = session.get("user_type")

        print(f"[DEBUG] Fetching order items for ID: {order_id}")

        is_uuid = bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", order_id))

        query = supabase.table("view_all_order_items_unified_v2").select("*")
        if is_uuid:
            query = query.eq("order_id", order_id)
        elif order_id.isnumeric():
            query = query.eq("sellercloud_order_id", order_id)
        else:
            query = query.eq("marketplace_order_id", order_id)
        query = query.eq("account_id", account_id) if user_type == "owner" else query.eq("channel_account_id", account_id)
        response = query.execute()
        items = response.data or []

        if not items:
            return f"No items found for order `{order_id}`."

        output = f"📦 Order `{order_id}` contains the following items:\n\n"
        for item in items:
            qty = item.get("quantity", 0)
            name = item.get("product_name") or item.get("sku", "Unnamed")
            sku = item.get("sku", "N/A")
            price = item.get("unit_price") or item.get("site_price") or "N/A"
            total = item.get("line_total", "N/A")
            shipped = item.get("quantity_shipped") or "0"
            weight = item.get("weight") or "-"
            dims = f'{item.get("length") or "?"}x{item.get("width") or "?"}x{item.get("height") or "?"}'
            warehouse = item.get("ship_from_warehouse", "N/A")

            output += (
                f"- {qty}x {name} (SKU: {sku}) @ ${price} each\n"
                f"  ↳ Total: ${total} | Shipped: {shipped} | Weight: {weight} | Size: {dims} | From: {warehouse}\n\n"
            )

        return output.strip()

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Failed to retrieve items for order `{order_id}`: {str(e)}"

list_order_products_by_id_tool = list_order_products_by_id