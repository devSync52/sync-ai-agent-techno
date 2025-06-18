from langchain.tools import tool
from supabase import create_client
import os


# 🔗 Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@tool
def estimate_lead_time_by_destination(input: str) -> str:
    """
    Estimates total lead time to a destination. If no transport mode is specified,
    it returns all available transport modes (air, sea, truck) for that destination.
    Example: 'How long to deliver to Denmark' or 'Delivery time to Germany by sea'.
    """

    try:
        print(f"[DEBUG] Input received: {input}")

        lowered = input.lower()

        # 🔍 Detect transport mode (optional)
        mode = None
        for m in ["air", "sea", "truck"]:
            if m in lowered:
                mode = m
                break

        print(f"[DEBUG] Transport mode: {mode if mode else 'Not specified'}")

        # 🔍 Detect destination country
        country = None
        country_map = {
            "united states": "US", "usa": "US", "us": "US",
            "brazil": "BR", "brasil": "BR", "br": "BR",
            "germany": "DE", "deutschland": "DE", "de": "DE",
            "mexico": "MX", "mx": "MX",
            "turkey": "TR", "tr": "TR",
            "denmark": "DK", "dk": "DK",
            "china": "CN", "cn": "CN",
            "spain": "ES", "es": "ES",
            "italy": "IT", "it": "IT",
            "france": "FR", "fr": "FR"
        }

        for name, code in country_map.items():
            if name in lowered:
                country = code
                break

        if not country:
            return "❌ Please specify a destination country in your question."

        print(f"[DEBUG] Destination country: {country}")

        # 🔍 Query
        query = (
            supabase
            .table("view_logistics_lead_time")
            .select("*")
            .eq("destination_country", country)
            .eq("season", "standard")
        )
        if mode:
            query = query.eq("transport_mode", mode)

        res = query.execute()

        data = res.data or []
        if not data:
            return f"❌ No lead time data found for {country} {'via ' + mode if mode else ''}."

        lines = [
            f"🚚 **Lead Time to {country} – Standard Season**\n"
        ]

        for row in data:
            tmode = row["transport_mode"].capitalize()
            total = row["total_lead_time"]
            notes = row.get("notes", "")

            # 🔢 Breakdown
            domestic_handling = row.get("domestic_handling_origin_days", 0)
            export_clearance = row.get("export_clearance_days", 0)
            transit = row.get("international_transit_days", 0)
            import_clearance = row.get("import_clearance_days", 0)
            domestic_destination = row.get("domestic_transport_destination_days", 0)
            receiving = row.get("receiving_days", 0)
            adjustment = row.get("lead_time_adjustment_days", 0)

            lines.append(
                f"\n✈️ **{tmode} Freight:** **{total} days**\n"
                f"- 🏗️ Domestic Handling (Origin): {domestic_handling} days\n"
                f"- 📑 Export Clearance: {export_clearance} days\n"
                f"- 🚢 Transit ({tmode}): {transit} days\n"
                f"- 🏛️ Import Clearance: {import_clearance} days\n"
                f"- 🚚 Final Domestic Transport: {domestic_destination} days\n"
                f"- 📦 Receiving & Unloading: {receiving} days\n"
                f"- ⚙️ Adjustments: {adjustment} days\n"
                + (f"📝 Notes: {notes}\n" if notes else "")
            )

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error calculating lead time: {str(e)}"


# ✅ Exporta a tool
estimate_lead_time_by_destination_tool = estimate_lead_time_by_destination