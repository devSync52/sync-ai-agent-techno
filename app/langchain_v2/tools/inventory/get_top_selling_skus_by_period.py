import os
from langchain.tools import tool
from collections import defaultdict
from app.langchain_v2.utils.date_parser import parse_period_input
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()


@tool
def get_top_selling_skus_by_period(input_text: str) -> str:
    """
    Get top SKUs by units sold in a period like 'May' or 'May 1 to May 10'.
    """
    try:
        # Parse de data
        start_date, end_date = parse_period_input(input_text)

        print(f"[DEBUG] Fetching sales from {start_date} to {end_date}")

        # Consulta de vendas
        sales_query = (
            supabase
            .table("ai_sku_sales_per_day_unified")
            .select("sku, quantity_sold, total_revenue")
            .gte("sales_date", start_date)
            .lte("sales_date", end_date)
        )

        print(f"[DEBUG] Sales query filters: sales_date >= {start_date} AND sales_date <= {end_date}")

        sales_res = sales_query.execute()

        if not sales_res.data:
            return f"⚠️ No sales data found between {start_date} and {end_date}."

        # Agrega vendas por SKU
        sku_stats = defaultdict(lambda: {"units": 0, "revenue": 0})
        for row in sales_res.data:
            sku = row["sku"]
            sku_stats[sku]["units"] += int(row.get("quantity_sold", 0) or 0)
            sku_stats[sku]["revenue"] += float(row.get("total_revenue", 0) or 0)

        top_skus = sorted(sku_stats.items(), key=lambda x: x[1]["units"], reverse=True)[:5]
        sku_list = [sku for sku, _ in top_skus]

        print(f"[DEBUG] Top SKUs: {sku_list}")

        # Pega nomes dos SKUs
        if sku_list:
            name_query = (
                supabase
                .table("ai_products_unified")
                .select("sku, product_name")
                .in_("sku", sku_list)
            )
            print(f"[DEBUG] Fetching names for SKUs: {sku_list}")
            name_res = name_query.execute()
            name_map = {r["sku"]: r["product_name"] for r in name_res.data}
        else:
            name_map = {}

        # Monta resposta
        lines = [f"Period: {start_date} to {end_date}\nTop-selling SKUs:"]
        for sku, stats in top_skus:
            name = name_map.get(sku, "Unknown")
            lines.append(f"{sku} ({name}) – {stats['units']} units, ${stats['revenue']:.2f}")

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error: {str(e)}"

get_top_selling_skus_by_period_tool = get_top_selling_skus_by_period