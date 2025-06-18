from langchain.tools import tool
from supabase import create_client
from datetime import datetime, timedelta
import os
import re


# 🔗 Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@tool
def get_replenishment_recommendation(input: str) -> str:
    """
    Provides a replenishment recommendation for a SKU based on recent sales, current stock, and lead time.
    Example: 'When should I reorder SKU PT001UF from China?'
    """

    try:
        print(f"[DEBUG] Input received: {input}")

        # 🔍 Detect SKU
        sku_candidates = re.findall(r'\b[A-Z0-9\-_\.]{3,}\b', input.upper())
        sku = None
        for candidate in sku_candidates:
            res = supabase.table("ai_products_unified").select("sku").eq("sku", candidate).limit(1).execute()
            if res.data:
                sku = candidate
                break

        if sku:
            print(f"[DEBUG] Detected SKU: {sku}")
        else:
            print(f"[DEBUG] No SKU detected")
        
        # 🔍 Detect Country (se presente na frase)
        countries = {
            "China": "CN", "Denmark": "DK", "Germany": "DE", "Turkey": "TR", "Mexico": "MX",
            "Brazil": "BR", "United States": "US", "USA": "US", "US": "US"
        }
        country_match = None
        for name in countries.keys():
            if name.lower() in input.lower():
                country_match = countries[name]
                break

        print(f"[DEBUG] Detected Country: {country_match}")

        # 🔍 Se SKU foi detectado, pega info do produto
        if sku:
            prod_res = (
                supabase.table("ai_products_unified")
                .select("quantity_available, company_id, company_name")
                .eq("sku", sku)
                .limit(1)
                .execute()
            )

            if not prod_res.data:
                return f"❌ No product found with SKU `{sku}`."

            product = prod_res.data[0]
            current_stock = product.get("quantity_available", 0)
            warehouse = product.get("company_name", "Unknown")
            warehouse_id = product.get("company_id", "Unknown")

            # 🔍 Detecta o país do warehouse
            ch_res = (
                supabase.table("channels")
                .select("country")
                .ilike("company_name", f"%{warehouse}%")
                .limit(1)
                .execute()
            )
            warehouse_country = (ch_res.data[0]["country"] if ch_res.data else "Unknown").upper()

            print(f"[DEBUG] Warehouse: {warehouse} ({warehouse_country})")
            print(f"[DEBUG] Current stock: {current_stock}")

        else:
            current_stock = None
            warehouse = None
            warehouse_country = None

        # 🔥 Sales (se tiver SKU)
        if sku:
            sales_res = (
                supabase.table("ai_sku_sales_per_day_unified")
                .select("quantity_sold")
                .eq("sku", sku)
                .order("sales_date", desc=True)
                .limit(30)
                .execute()
            )

            sales_data = sales_res.data or []
            total_sold = sum(item["quantity_sold"] for item in sales_data)
            avg_daily_sales = total_sold / 30 if total_sold > 0 else 0

            print(f"[DEBUG] Avg daily sales: {avg_daily_sales}")
        else:
            avg_daily_sales = None

        # 🔥 Lead Time
        destination_country = country_match or warehouse_country

        if not destination_country:
            return "❌ Could not detect a destination country to calculate lead time."

        lt_res = (
            supabase.table("view_logistics_lead_time")
            .select("*")
            .eq("destination_country", destination_country)
            .eq("season", "standard")
            .order("total_lead_time")
            .limit(1)
            .execute()
        )

        if not lt_res.data:
            return f"❌ Lead time data for `{destination_country}` not found."

        lead_time_days = lt_res.data[0]["total_lead_time"]
        print(f"[DEBUG] Lead time: {lead_time_days} days")

        # 🔥 Resposta Condicional
        if sku and avg_daily_sales == 0:
            return (
                f"ℹ️ SKU `{sku}` has no sales in the last 30 days.\n"
                "Cannot provide a replenishment recommendation based on recent sales."
            )

        if sku and avg_daily_sales:
            days_until_stockout = current_stock / avg_daily_sales if avg_daily_sales else 0
            stockout_date = datetime.utcnow() + timedelta(days=days_until_stockout)
            reorder_date = stockout_date - timedelta(days=lead_time_days)

            location_note = ""
            if not country_match:
                location_note = (
                    f"\n\n📍 Since no origin was specified, this calculation is based on the warehouse location: **{warehouse} ({warehouse_country})**."
                )

            return (
                f"📦 **Replenishment Recommendation for SKU `{sku}`**\n"
                f"- **Current Stock:** {current_stock}\n"
                f"- **Avg Daily Sales (last 30 days):** {avg_daily_sales:.2f} units/day\n"
                f"- **Lead Time from {destination_country}:** {lead_time_days} days\n"
                f"- **Estimated Stockout Date:** {stockout_date.date()}\n"
                f"➡️ **Recommended Reorder Date:** {reorder_date.date()}\n"
                "✅ Place the reorder by the recommended date to avoid stockouts."
                + location_note
            )

        # 🔥 Caso SKU não seja encontrado mas país foi
        if not sku and country_match:
            return (
                f"ℹ️ I couldn't detect a valid SKU in your request.\n"
                f"However, I can confirm the lead time to **{country_match}** is **{lead_time_days} days**.\n"
                "If you'd like, please provide the SKU to calculate the replenishment recommendation."
            )

        # 🔥 Caso SKU e local ambos estejam faltando
        if not sku and not country_match:
            return (
                "❌ I couldn't detect a SKU or destination in your request.\n"
                "Please specify the SKU and/or destination country so I can calculate a proper replenishment recommendation."
            )

        return "❌ Unexpected error."

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error generating replenishment recommendation: {str(e)}"


# 🔥 Export
get_replenishment_recommendation_tool = get_replenishment_recommendation