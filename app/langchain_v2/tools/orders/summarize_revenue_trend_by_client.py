from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input, get_previous_period
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()


@tool
def summarize_revenue_trend_by_client(input_text: str, client_name: str = None) -> str:
    """
    Shows revenue trend grouped by client for a given period compared to the previous period.
    You can optionally specify a client name to filter.
    Example input: 'last 30 days', 'May', 'this week'
    """
    try:
        start_date, end_date = parse_period_input(input_text)
        prev_start_date, prev_end_date = get_previous_period(start_date, end_date)

        print(f"[DEBUG] Current: {start_date} to {end_date}")
        print(f"[DEBUG] Previous: {prev_start_date} to {prev_end_date}")

        query_current = (
            supabase.table("ai_revenue_trend_by_client_daily")
            .select("*")
            .gte("period", start_date)
            .lte("period", end_date)
        )

        query_previous = (
            supabase.table("ai_revenue_trend_by_client_daily")
            .select("*")
            .gte("period", prev_start_date)
            .lte("period", prev_end_date)
        )

        # 🔥 Se cliente foi especificado, aplica o filtro
        if client_name:
            query_current = query_current.eq("client_name", client_name)
            query_previous = query_previous.eq("client_name", client_name)

        current_data = query_current.execute().data or []
        previous_data = query_previous.execute().data or []

        # 🔥 Agrupar e somar
        def aggregate(data):
            result = {}
            for row in data:
                client = row.get("client_name", "Unknown Client")
                result.setdefault(client, {"orders": 0, "revenue": 0.0})
                result[client]["orders"] += int(row.get("total_orders", 0))
                result[client]["revenue"] += float(row.get("total_revenue", 0) or 0)
            return result

        current_map = aggregate(current_data)
        previous_map = aggregate(previous_data)

        all_clients = set(current_map.keys()).union(set(previous_map.keys()))

        if client_name and not all_clients:
            return f"No data found for client '{client_name}' in the specified period."

        lines = [
            f"📈 **Revenue Trend by Client:**\nPeriod: {start_date} to {end_date}\nCompared to: {prev_start_date} to {prev_end_date}\n"
        ]

        for client in all_clients:
            curr = current_map.get(client, {"orders": 0, "revenue": 0})
            prev = previous_map.get(client, {"orders": 0, "revenue": 0})

            curr_orders = curr["orders"]
            curr_revenue = curr["revenue"]

            prev_orders = prev["orders"]
            prev_revenue = prev["revenue"]

            growth = (
                ((curr_revenue - prev_revenue) / prev_revenue) * 100
                if prev_revenue != 0
                else 100 if curr_revenue > 0 else 0
            )
            growth_str = f"{growth:+.1f}%" if prev_revenue != 0 else "N/A"

            lines.append(f"**{client}**")
            lines.append(
                f"• Current Period - Orders: {curr_orders} | Revenue: ${curr_revenue:,.2f}"
            )
            lines.append(
                f"• Previous Period - Orders: {prev_orders} | Revenue: ${prev_revenue:,.2f}"
            )
            lines.append(f"• 📈 Growth: {growth_str}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error summarizing revenue trend by client: {str(e)}"


# ✅ Export
summarize_revenue_trend_by_client_tool = summarize_revenue_trend_by_client