from langchain.tools import tool
from supabase import create_client
import os


# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_warehouse_list() -> list[str]:
    """
    Internal function to retrieve the list of warehouses.
    """
    response = (
        supabase.table("ai_shipping_info")
        .select("ship_from_warehouse")
        .neq("ship_from_warehouse", None)
        .execute()
    )

    data = response.data or []
    warehouses = set()

    for row in data:
        warehouse = row.get("ship_from_warehouse")
        if warehouse:
            warehouses.add(warehouse.strip())

    return sorted(warehouses)


@tool
def list_available_warehouses() -> str:
    """
    Lists all available warehouses registered in the shipping data.
    """
    try:
        warehouses = get_warehouse_list()

        if not warehouses:
            return "No warehouses were found in the shipping data."

        lines = ["Available Warehouses:"]
        for idx, w in enumerate(warehouses, start=1):
            lines.append(f"{idx}. {w}")

        return "\n".join(lines)

    except Exception as e:
        return f"An error occurred while fetching warehouses: {str(e)}"