from langchain.tools import tool
from app.langchain_v2.utils.date_parser import parse_period_input
import os
from app.utils.supabase_client import get_supabase_client

@tool
def list_sales_by_period(input_text: str) -> str:
    """
    Lists orders for a given period with order ID, date, client name, and total.
    Example: 'List sales yesterday', 'List sales this week', 'List sales in May'.
    """
        
    supabase = get_supabase_client()
    
    try:
        start_date, end_date = parse_period_input(input_text)

        print(f"[DEBUG] Parsed period: {start_date} to {end_date}")

        # 🔥 Lógica sniper — se for um único dia, usa EQ
        if start_date == end_date:
            response = (
                supabase.table("ai_orders_unified")
                .select("order_id, order_date, client_name, grand_total")
                .eq("order_date", start_date)
                .order("order_date", desc=False)
                .execute()
            )
        else:
            response = (
                supabase.table("ai_orders_unified")
                .select("order_id, order_date, client_name, grand_total")
                .gte("order_date", start_date)
                .lte("order_date", end_date)
                .order("order_date", desc=False)
                .execute()
            )

        data = response.data or []

        if not data:
            return f"❌ No sales found between {start_date} and {end_date}."

        lines = [
            f"📦 **Sales from {start_date} to {end_date}:**\n"
        ]

        for order in data:
            lines.append(
                f"- {order.get('order_id')} | 📅 {order.get('order_date')} | "
                f" {order.get('client_name')} | 💰 ${float(order.get('grand_total', 0)):,.2f}"
            )

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error listing sales: {str(e)}"


# ✅ Exporta a tool
list_sales_by_period_tool = list_sales_by_period