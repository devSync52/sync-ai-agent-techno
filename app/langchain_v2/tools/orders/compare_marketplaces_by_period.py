from app.langchain_v2.utils.session_context import get_current_session_context
from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input, get_previous_period
import os
from app.utils.supabase_client import get_supabase_client

def _fetch_all_rows_via_raw_sql(supabase, sql: str, batch_size: int = 1000):
    """Fetch all rows from a raw_sql RPC by paginating with LIMIT/OFFSET."""
    all_rows = []
    offset = 0

    # Ensure we don't end with a semicolon before appending LIMIT/OFFSET
    base_sql = (sql or "").strip().rstrip(";")

    while True:
        paged_sql = f"{base_sql}\nLIMIT {batch_size} OFFSET {offset}"
        res = supabase.rpc("raw_sql", {"sql": paged_sql}).execute()
        batch = res.data or []
        all_rows.extend(batch)

        if len(batch) < batch_size:
            break

        offset += batch_size

    return all_rows

@tool
def compare_marketplaces_by_period(input: str) -> dict:
    """
    Compare total orders by marketplace between a period and its previous period.
    Example: 'Compare marketplace sales this month'.
    Returns both summary text and chart data.
    """
        
    supabase = get_supabase_client()
    context = get_current_session_context()
    if not context:
        return {
            "type": "error",
            "message": "❌ Missing session context"
        }
    account_id = context["account_id"]
    user_type = context["user_type"]
    
    try:
        parsed = parse_period_input(input)
        if (
            not parsed
            or not isinstance(parsed, (list, tuple))
            or len(parsed) != 2
            or any(p is None for p in parsed)
        ):
            raise ValueError("Could not parse period input")
        start, end = parsed
        prev_start, prev_end = get_previous_period(start, end)
        # Validate that all dates are non-empty strings
        if not all(isinstance(d, str) and d for d in [start, end, prev_start, prev_end]):
            raise ValueError("Invalid period dates received. Dates must be non-empty strings.")

        # 🚀 Query atual
        current_query = f"""
            SELECT marketplace_name, COALESCE(count(distinct order_id), 0) as orders
            FROM view_all_orders_v4
            WHERE order_date >= date '{start}' AND order_date < (date '{end}' + interval '1 day')
            {f"AND {'channel_id' if user_type == 'client' else 'account_id'} = '{account_id}'"}
            GROUP BY marketplace_name
        """

        # 🚀 Query anterior
        previous_query = f"""
            SELECT marketplace_name, COALESCE(count(distinct order_id), 0) as orders
            FROM view_all_orders_v4
            WHERE order_date >= date '{prev_start}' AND order_date < (date '{prev_end}' + interval '1 day')
            {f"AND {'channel_id' if user_type == 'client' else 'account_id'} = '{account_id}'"}
            GROUP BY marketplace_name
        """

        current_res = _fetch_all_rows_via_raw_sql(supabase, current_query)
        previous_res = _fetch_all_rows_via_raw_sql(supabase, previous_query)

        current_map = {r.get("marketplace_name") or "(unknown)": r.get("orders") or 0 for r in current_res}
        previous_map = {r.get("marketplace_name") or "(unknown)": r.get("orders") or 0 for r in previous_res}

        marketplaces = sorted(set(current_map.keys()) | set(previous_map.keys()))

        # 📜 Texto resumo
        lines = [
            f"**Marketplace Comparison**",
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
