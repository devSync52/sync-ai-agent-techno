from langchain.tools import tool
from app.langchain_v2.utils.date_parser import (
    parse_period_input,
    parse_dual_period_input,
    get_comparative_period_smart,
)
import os
import re
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()

@tool
def compare_sku_sales_by_period(input: str) -> str:
    """
    Compare sales of a specific SKU between a period and its previous period.
    Example: 'Compare sales of SKU PT001UF this month' or 'this month versus last month'.
    """
    try:
        # 🔍 Extrair SKU
        sku_match = re.search(r"SKU\s*([A-Za-z0-9\-_\.]+)", input, re.IGNORECASE)

        if not sku_match:
            candidates = re.findall(r"\b([A-Za-z0-9\-_\.]{3,})\b", input)
            if candidates:
                sku = candidates[-1].upper()
            else:
                return "❌ Please specify a SKU in your question."
        else:
            sku = sku_match.group(1).upper()

        # 🔥 Checa se é input comparativo explícito
        if "versus" in input.lower() or "compared to" in input.lower():
            (start, end), (prev_start, prev_end) = parse_dual_period_input(input)
        else:
            start, end = parse_period_input(input)
            prev_start, prev_end = get_comparative_period_smart(input, start, end)

        print(f"[DEBUG] Comparing SKU: {sku} | {start} to {end} vs {prev_start} to {prev_end}")

        # 🚀 Executar function SQL
        response = supabase.rpc("compare_sku_sales_by_period", {
            "sku_input": sku,
            "start_date": start,
            "end_date": end,
            "prev_start_date": prev_start,
            "prev_end_date": prev_end
        }).execute()

        if not response.data or len(response.data) == 0:
            return f"❌ No data found for SKU `{sku}`."

        result = response.data[0]

        curr_units = result.get("period_units") or 0
        curr_revenue = result.get("period_revenue") or 0
        prev_units = result.get("previous_units") or 0
        prev_revenue = result.get("previous_revenue") or 0

        diff_units = curr_units - prev_units
        diff_revenue = curr_revenue - prev_revenue

        trend_units = "📈" if diff_units > 0 else "📉" if diff_units < 0 else "➖"
        trend_revenue = "📈" if diff_revenue > 0 else "📉" if diff_revenue < 0 else "➖"

        return (
            f"📦 **SKU `{sku}` Sales Comparison**\n"
            f"- Units: {curr_units} vs {prev_units} ({trend_units} {diff_units})\n"
            f"- Revenue: ${curr_revenue:,.2f} vs ${prev_revenue:,.2f} ({trend_revenue} ${diff_revenue:,.2f})\n"
            f"- Period: {start} to {end} vs {prev_start} to {prev_end}"
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error comparing SKU sales: {str(e)}"


compare_sku_sales_by_period_tool = compare_sku_sales_by_period