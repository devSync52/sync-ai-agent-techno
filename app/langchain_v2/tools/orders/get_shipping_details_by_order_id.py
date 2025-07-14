from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client


@tool
def get_shipping_details_by_order_id(order_id: str) -> str:
    """
    Returns shipping details for an order, including carrier, service, tracking number,
    warehouse origin, destination, and estimated delivery date.
    Example: "How was order 123456 shipped?"
    """
    supabase = get_supabase_client()

    try:
        from app.langchain_v2.utils.session_context import get_current_session_context
        session = get_current_session_context()
        account_id = session.get("account_id")
        user_type = session.get("user_type")

        print(f"[DEBUG] Fetching shipping details for ID: {order_id}")

        response = supabase.table("ai_shipping_info_sc") \
            .select("*") \
            .eq("order_id", order_id) \
            .eq("account_id" if user_type == "owner" else "channel_account_id", account_id) \
            .maybe_single() \
            .execute()

        data = response.data if response else None

        if not data:
            response = supabase.table("ai_shipping_info_sc") \
                .select("*") \
                .eq("marketplace_order_id", order_id) \
                .eq("account_id" if user_type == "owner" else "channel_account_id", account_id) \
                .maybe_single() \
                .execute()
            data = response.data if response else None
            if not data:
                return f"No shipping information found for order `{order_id}`."

        ship_date = data.get("ship_date", "N/A")
        estimated_delivery_date = data.get("estimated_delivery_date", "N/A")
        shipping_carrier = data.get("shipping_carrier", "N/A")
        shipping_service = data.get("shipping_service", "N/A")
        tracking = data.get("tracking_number") or "N/A"
        ship_from_warehouse = data.get("ship_from_warehouse", "N/A")
        destination_state = data.get("destination_state", "N/A")
        destination_country = data.get("destination_country", "N/A")

        # Montar link de rastreio se possível
        if tracking != "N/A":
            if "fedex" in shipping_carrier.lower():
                tracking_link = f"https://www.fedex.com/fedextrack/?tracknumbers={tracking}"
            elif "ups" in shipping_carrier.lower():
                tracking_link = f"https://www.ups.com/track?tracknum={tracking}"
            elif "usps" in shipping_carrier.lower():
                tracking_link = f"https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking}"
            else:
                tracking_link = "N/A (carrier not recognized)"
        else:
            tracking_link = "N/A"

        return (
            f"- Ship Date: {ship_date}\n"
            f"- Estimated Delivery: {estimated_delivery_date}\n"
            f"- Carrier: {shipping_carrier}\n"
            f"- Service: {shipping_service}\n"
            f"- Tracking: {tracking} ({tracking_link})\n"
            f"- Warehouse: {ship_from_warehouse}\n"
            f"- Destination: {destination_state}, {destination_country}"
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error while fetching shipping details for order `{order_id}`: {str(e)}"
    

