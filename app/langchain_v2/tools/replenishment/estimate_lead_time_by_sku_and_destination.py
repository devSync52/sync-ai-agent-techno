from langchain.tools import tool
import re
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()


@tool
def estimate_lead_time_by_sku_and_destination(input: str) -> str:
    """
    Estimates the total lead time for a SKU considering its client (destination) and transport mode.
    Example: 'How long to deliver SKU PT001UF to Denmark by air'.
    """

    try:
        print(f"[DEBUG] Input received: {input}")

        lowered = input.lower()

        # 🔍 Detect transport mode
        mode = None
        for m in ["air", "sea", "truck"]:
            if m in lowered:
                mode = m
                break
        if not mode:
            return "❌ Please specify a transport mode (air, sea, or truck) in your question."

        print(f"[DEBUG] Transport mode: {mode}")

        # 🔍 Detect SKU
        sku_match = re.search(r"(sku\s*)([a-z0-9\-_.]+)", lowered)
        sku = None
        if sku_match:
            sku = sku_match.group(2).upper()
        else:
            matches = re.findall(r"\b[A-Z0-9\-_.]{3,}\b", input.upper())
            if matches:
                sku = matches[0]
        if not sku:
            return "❌ Please specify a valid SKU in your question."

        print(f"[DEBUG] Detected SKU: {sku}")

        # 🔍 Find destination country based on SKU → client mapping
        channel_res = (
            supabase
            .table("ai_products_dashboard")
            .select("sku, client_name, destination_country")
            .eq("sku", sku)
            .execute()
        )

        products = channel_res.data or []
        if not products:
            return f"❌ No product data found for SKU `{sku}`."

        destination = products[0].get("destination_country")
        client = products[0].get("client_name")

        if not destination:
            return f"❌ Could not determine destination country for SKU `{sku}`."

        print(f"[DEBUG] Destination country: {destination}, Client: {client}")

        # 🔍 Query lead time view
        res = (
            supabase
            .table("view_logistics_lead_time_by_client")
            .select("*")
            .eq("destination_country", destination)
            .eq("transport_mode", mode)
            .eq("season", "standard")
            .execute()
        )

        data = res.data or []
        if not data:
            return f"❌ No lead time data found for {destination} via {mode}."

        row = data[0]

        # 🔢 Break down stages
        total = row["total_lead_time"]
        notes = row.get("notes", "")

        domestic_handling = row.get("domestic_handling_origin_days", 0)
        export_clearance = row.get("export_clearance_days", 0)
        transit = row.get("international_transit_days", 0)
        import_clearance = row.get("import_clearance_days", 0)
        domestic_destination = row.get("domestic_transport_destination_days", 0)
        receiving = row.get("receiving_days", 0)
        adjustment = row.get("lead_time_adjustment_days", 0)

        lines = [
            f"🚚 **Lead Time for SKU `{sku}` – {mode.upper()} freight to {destination} (Client: {client}) – Standard Conditions**\n",
            f"🔸 **Total Estimated Lead Time:** **{total} days**\n",
            "**This includes:**",
            f"1. **Domestic Handling at Origin:** {domestic_handling} days",
            f"2. **Export Clearance:** {export_clearance} days",
            f"3. **International Transit ({mode.upper()}):** {transit} days",
            f"4. **Import Clearance at Destination:** {import_clearance} days",
            f"5. **Final Domestic Transport:** {domestic_destination} days",
            f"6. **Receiving & Unloading:** {receiving} days",
            f"7. **Lead Time Adjustments:** {adjustment} days",
        ]

        if notes:
            lines.append(f"\n📝 **Notes:** {notes}")

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error calculating lead time: {str(e)}"


# ✅ Exporta a tool
estimate_lead_time_by_sku_and_destination_tool = estimate_lead_time_by_sku_and_destination