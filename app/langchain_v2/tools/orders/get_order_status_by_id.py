import os
from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client

@tool
def get_order_status_by_id(order_id: str) -> str:
    """
    Retrieves the status and basic details of an order using its order ID.
    Example: 'Check order 102345'
    """
        
    supabase = get_supabase_client()
    
    try:
        print(f"[DEBUG] Fetching order status for ID: {order_id}")

        response = (
            supabase
            .table("view_all_orders")
            .select("*")
            .eq("order_id", order_id)
            .single()
            .execute()
        )
        data = response.data

        if not data:
            return f"No order found with ID `{order_id}`. Please double-check the number."

        status = data.get("status", "Unknown")
        order_date = data.get("order_date", "N/A")
        marketplace_name = data.get("marketplace_name", "N/A")
        client_name = data.get("client_name", "N/A")
        tracking = data.get("tracking_number") or "N/A"

        return (
            f"Order #{order_id} Details:**\n"
            f"Status: {status}\n"
            f"Order Date: {order_date}\n"
            f"Marketplace: {marketplace_name}\n"
            f"Customer: {client_name}\n"
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error while fetching order `{order_id}`: {str(e)}"


get_order_status_by_id_tool = get_order_status_by_id