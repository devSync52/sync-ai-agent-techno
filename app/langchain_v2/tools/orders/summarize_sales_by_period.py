from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from app.utils.supabase_client import get_supabase_client


def _fetch_all_rows(build_query, batch_size: int = 1000):
    """Fetches all rows from a Supabase query using pagination.

    Notes:
    - Supabase REST has a default limit of 1000 rows per request.
    - The Supabase Python query builder can be stateful; to ensure pagination works reliably,
      this function accepts a `build_query` callable that returns a *fresh* query each loop.

    Args:
        build_query: A zero-arg callable that returns a Supabase query builder.
        batch_size: Page size (Supabase max/default is typically 1000).
    """
    all_rows = []
    offset = 0

    while True:
        # Build a fresh query each iteration to avoid stateful/mutable builder issues.
        query = build_query().range(offset, offset + batch_size - 1)
        batch = query.execute()
        data = batch.data or []
        all_rows.extend(data)

        # If we got fewer than batch_size rows, we've reached the end.
        if len(data) < batch_size:
            break

        offset += batch_size

    return all_rows


@tool
def summarize_sales_by_period(input_text: str) -> str:
    """
Summarizes total orders and total revenue for a given period.
Counts only finalized sales (status_code IN (3,4)).
Understands questions like:
- 'How many sales yesterday?'
- 'How many sales this week?'
- 'Sales last month'
- 'How much revenue yesterday?'
"""

    supabase = get_supabase_client()

    from app.langchain_v2.utils.session_context import get_current_session_context
    ctx = get_current_session_context()

    if not ctx or not ctx.get("account_id") or not ctx.get("user_type"):
        return "❌ Session context not available. Please log in."

    account_id = ctx["account_id"]
    user_type = ctx["user_type"]

    try:
        start_date, end_date = parse_period_input(input_text)

        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        # Prefer server-side aggregation via RPC to avoid large payloads and row limits.
        # Expected RPC signature (example): summarize_sales_by_period(p_account_id, p_user_type, p_start_date, p_end_date)
        rpc_payload = {
            "p_account_id": account_id,
            "p_user_type": user_type,
            "p_start_date": str(start_date),
            "p_end_date": str(end_date),
        }

        resp = supabase.rpc("summarize_sales_by_period", rpc_payload).execute()
        data = resp.data or []
        row = (data or [{}])[0]

        total_orders = int(row.get("total_orders") or 0)
        # total_revenue can come as numeric/str depending on driver
        total_revenue = float(row.get("total_revenue") or 0)

        if total_orders == 0:
            return (
                f"❌ No finalized sales found between {start_date} and {end_date} "
                f"(status_code IN (3,4))."
            )

        return (
            f"📊 **Sales Summary from {start_date} to {end_date}:**\n"
            f"- Scope: status_code IN (3,4)\n"
            f"- Total Orders: {total_orders}\n"
            f"- Total Revenue: ${total_revenue:,.2f}"
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error summarizing sales: {str(e)}"


# ✅ Exporta a tool
summarize_sales_by_period_tool = summarize_sales_by_period
