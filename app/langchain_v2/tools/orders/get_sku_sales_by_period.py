import os
import re
from collections import defaultdict
from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
from app.utils.supabase_client import get_supabase_client


supabase = get_supabase_client()


@tool
def get_sku_sales_by_period(input_text: str) -> str:
    """
    Get total sales (units and revenue) for a specific SKU in a given period.
    You must specify the SKU and a time period in the input.
    Example: 'Sales of SKU PT001UF last week'
    """
    try:

        pattern = re.compile(r"(sku\s*)([a-z0-9\-_.]+)", re.IGNORECASE)
        match = pattern.search(input_text)

        if match:
            sku = match.group(2).upper()
        else:
            matches = re.findall(r"\b[A-Z0-9\-_.]{3,}\b", input_text.upper())
            if matches:
                sku = matches[0]
            else:
                return "❌ Please provide a valid SKU in your question."


        start_date, end_date = parse_period_input(input_text)
        print(f"[DEBUG] Fetching sales for {sku} from {start_date} to {end_date}")


        response = (
            supabase
            .table("ai_sku_sales_per_day_unified")
            .select("quantity_sold, total_revenue")
            .eq("sku", sku)
            .gte("sales_date", start_date)
            .lte("sales_date", end_date)
            .execute()
        )

        data = response.data or []
        if not data:
            return f"No sales found for SKU `{sku}` between {start_date} and {end_date}."

        total_units = sum(item.get("quantity_sold", 0) or 0 for item in data)
        total_revenue = sum(item.get("total_revenue", 0) or 0 for item in data)

        return (
            f"**Sales Report for SKU `{sku}`**\n"
            f"- **Units Sold:** {total_units}\n"
            f"- **Revenue:** ${total_revenue:.2f}\n"
            f"- **Period:** {start_date} to {end_date}"
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"Error while retrieving sales for `{input_text}`: {str(e)}"


get_sku_sales_by_period_tool = get_sku_sales_by_period