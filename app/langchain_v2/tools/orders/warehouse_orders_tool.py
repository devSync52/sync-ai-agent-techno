from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from supabase import create_client, Client
from app.utils.supabase_client import get_supabase_client

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
            response = (
                supabase.table("ai_orders_by_warehouse")
                .select("warehouse_name")
                .neq("warehouse_name", None)
                .execute()
            )

            warehouses = sorted(set([row["warehouse_name"].title() for row in response.data]))

            if not warehouses:
                return "No warehouses found."

            lines = ["🏬 **Available Warehouses:**"]
            for w in warehouses:
                lines.append(f"- {w}")
            return "\n".join(lines)

        # 🔍 Se for consulta de quantidade
        response = (
            supabase.table("ai_orders_by_warehouse")
            .select("warehouse_name")
            .neq("warehouse_name", None)
            .execute()
        )
        warehouse_list = sorted(set([row["warehouse_name"] for row in response.data]))

        print(f"[DEBUG] Warehouses found: {warehouse_list}")

        warehouse_match = None
        for w in warehouse_list:
            # Faz o fuzzy matching usando contains
            if any(word.strip() in input_lower for word in w.lower().split()):
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

        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        # 🔍 Query SQL
        query = f"""
            SELECT count(DISTINCT order_id) AS total_orders
            FROM ai_orders_by_warehouse
            WHERE warehouse_name = '{warehouse_match.lower()}'
              AND order_date >= '{start_date}'
              AND order_date <= '{end_date}'
        """

        print(f"[DEBUG] Running SQL: {query}")

        res = supabase.rpc("raw_sql", {"sql": query}).execute()

        total = res.data[0]["total_orders"] if res.data else 0

        return (
            f"🚚 **{total} orders** were shipped from **'{warehouse_match.title()}'** "
            f"between **{start_date}** and **{end_date}**."
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ An error occurred: {str(e)}"


warehouse_orders_tool = warehouse_orders_tool