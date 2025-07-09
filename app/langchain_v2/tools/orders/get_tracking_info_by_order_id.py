from langchain.tools import tool
import os
import re
from app.utils.supabase_client import get_supabase_client
from app.langchain_v2.utils.session_context import get_current_session_context

@tool
def get_tracking_info_by_order_id(input: str) -> str:
    """
    Returns the tracking number and shipping carrier for a specific order ID.
    Accepts order numbers like '5011587'.
    """
        
    supabase = get_supabase_client()
    session = get_current_session_context()
    account_id = session.get("account_id")
    user_type = session.get("user_type")
    
    try:
        match = re.search(r'\d{4,}', input)
        if not match:
            return "Please provide a valid order number like '12345'."

        order_id = match.group(0)

        query = supabase.table("sellercloud_orders") \
            .select("order_id, metadata") \
            .eq("order_id", order_id)

        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        response = query.maybe_single().execute()

        data = response.data
        if not data:
            return f"No order found with ID {order_id}."

        metadata = data.get("metadata", {})
        tracking_number = metadata.get("TrackingNumber") or "Not available"
        shipping_carrier = metadata.get("ShippingCarrier") or "Not available"

        return (
            f"Order {order_id} was shipped via {shipping_carrier} "
            f"with tracking number {tracking_number}."
        )
    except Exception as e:
        return f"An error occurred: {str(e)}"