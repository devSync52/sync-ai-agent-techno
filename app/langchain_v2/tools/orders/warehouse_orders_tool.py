from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from datetime import date, timedelta
from app.utils.supabase_client import get_supabase_client

def _fetch_all_rows(query, batch_size: int = 1000):
    """Fetches all rows from a Supabase query using pagination (Supabase default limit is 1000 rows)."""
    all_rows = []
    offset = 0

    while True:
        batch = query.range(offset, offset + batch_size - 1).execute()
        data = batch.data or []
        all_rows.extend(data)

        # Stop when the returned batch is smaller than the page size
        if len(data) < batch_size:
            break

        offset += batch_size

    return all_rows

@tool
def warehouse_orders_tool(input: str) -> str:
    """
    Lists available warehouses or counts how many orders were shipped from a warehouse in a given period.
    Examples:
    - 'List warehouses'
    - 'How many orders were shipped from Miami last month'
    """
        
    supabase = get_supabase_client()
    
    try:
        input_lower = input.lower().strip()

        # 🔍 Se pedir lista de warehouses
        if "list warehouse" in input_lower or "available warehouse" in input_lower:
            base_q = (
                supabase.table("ai_orders_by_warehouse")
                .select("warehouse_name")
                .neq("warehouse_name", None)
            )

            rows = _fetch_all_rows(base_q)
            warehouses = sorted(set([row["warehouse_name"].title() for row in rows if row.get("warehouse_name")]))

            if not warehouses:
                return "No warehouses found."

            lines = ["🏬 **Available Warehouses:**"]
            for w in warehouses:
                lines.append(f"- {w}")
            return "\n".join(lines)

        # 🔍 Se for consulta de quantidade
        base_q = (
            supabase.table("ai_orders_by_warehouse")
            .select("warehouse_name")
            .neq("warehouse_name", None)
        )
        rows = _fetch_all_rows(base_q)
        warehouse_list = sorted(set([row["warehouse_name"] for row in rows if row.get("warehouse_name")]))

        print(f"[DEBUG] Warehouses found: {warehouse_list}")

        warehouse_match = None
        for w in warehouse_list:
            w_lower = w.lower().strip()
            # Prefer phrase match for multi-word warehouse names
            if w_lower and w_lower in input_lower:
                warehouse_match = w
                break

        # Fallback: word-level match (previous behavior)
        if not warehouse_match:
            for w in warehouse_list:
                if any(word.strip() and (word.strip() in input_lower) for word in w.lower().split()):
                    warehouse_match = w
                    break

        if not warehouse_match:
            return (
                "❌ I couldn't detect any warehouse in your request.\n"
                f"Available warehouses: {', '.join([w.title() for w in warehouse_list])}"
            )

        print(f"[DEBUG] Detected warehouse: {warehouse_match}")

        # 🔥 Remove warehouse do input pra parsear o período
        for word in warehouse_match.lower().split():
            input_lower = input_lower.replace(word, "")
        cleaned_input = input_lower.strip()

        start_date, end_date = parse_period_input(cleaned_input)
        start_iso = str(start_date)
        end_exclusive = (date.fromisoformat(str(end_date)) + timedelta(days=1)).isoformat()

        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        # ✅ Count query using PostgREST count header (avoid fetching all rows)
        # supabase-py v2 does not support `head=True` on `.select(...)`; instead, request an exact count
        # and limit the returned payload to a single row.
        count_res = (
            supabase.table("ai_orders_by_warehouse")
            .select("order_id", count="exact")
            .eq("warehouse_name", warehouse_match.lower())
            .gte("order_date", start_iso)
            .lt("order_date", end_exclusive)
            .limit(1)
            .execute()
        )

        total = count_res.count or 0

        return (
            f"🚚 **{total} orders** were shipped from **'{warehouse_match.title()}'** "
            f"between **{start_date}** and **{end_date}**."
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ An error occurred: {str(e)}"


warehouse_orders_tool = warehouse_orders_tool
