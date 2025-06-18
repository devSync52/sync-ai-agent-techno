from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input, get_previous_period
import os
from app.utils.supabase_client import get_supabase_client

@tool
def compare_marketplaces_by_period(input: str) -> dict:
    """
    Compare total orders by marketplace between a period and its previous period.
    Example: 'Compare marketplace sales this month'.
    Returns both summary text and chart data.
    """
        
    supabase = get_supabase_client()
    
    try:
        start, end = parse_period_input(input)
        prev_start, prev_end = get_previous_period(start, end)

        # 🚀 Query atual
        current_query = f"""
            SELECT marketplace_name, count(distinct order_id) as orders
            FROM view_all_orders
            WHERE order_date >= '{start}' AND order_date <= '{end}'
            GROUP BY marketplace_name
        """

        # 🚀 Query anterior
        previous_query = f"""
            SELECT marketplace_name, count(distinct order_id) as orders
            FROM view_all_orders
            WHERE order_date >= '{prev_start}' AND order_date <= '{prev_end}'
            GROUP BY marketplace_name
        """

        current_res = supabase.rpc("raw_sql", {"sql": current_query}).execute().data or []
        previous_res = supabase.rpc("raw_sql", {"sql": previous_query}).execute().data or []

        current_map = {r["marketplace_name"]: r["orders"] for r in current_res}
        previous_map = {r["marketplace_name"]: r["orders"] for r in previous_res}

        marketplaces = sorted(set(current_map.keys()) | set(previous_map.keys()))

        # 📜 Texto resumo
        lines = [
            f"📊 **Marketplace Comparison**",
            f"- Current period: {start} to {end}",
            f"- Previous period: {prev_start} to {prev_end}",
            ""
        ]

        for m in marketplaces:
            curr = current_map.get(m, 0)
            prev = previous_map.get(m, 0)
            diff = curr - prev
            trend = "📈" if diff > 0 else "📉" if diff < 0 else "➖"
            lines.append(f"- **{m}**: {curr} orders vs {prev} ({trend} {diff})")

        summary = "\n".join(lines)

        # 📊 Dados para gráfico
        chart = {
            "type": "chart",
            "title": "Marketplace Orders Comparison",
            "labels": marketplaces,
            "datasets": [
                {"label": "Current Period", "data": [current_map.get(m, 0) for m in marketplaces]},
                {"label": "Previous Period", "data": [previous_map.get(m, 0) for m in marketplaces]},
            ],
            "summary": summary,
        }

        return chart

    except Exception as e:
        return {
            "type": "error",
            "message": f"❌ Error comparing marketplaces: {str(e)}"
        }


# 🔥 Exporta
compare_marketplaces_by_period_tool = compare_marketplaces_by_period