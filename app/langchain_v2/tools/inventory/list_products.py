import os
from langchain.tools import tool
from supabase import create_client, Client

APP_URL = os.getenv("APP_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@tool
def list_products(input: str = "View products") -> str:
    """
    Lists the first 10 products in the catalog and informs where to view, manage, or download the full list.
    """
    try:
        res = (
            supabase
            .table("ai_products_unified")
            .select("sku, product_name, quantity_available")
            .limit(10)
            .execute()
        )

        if not res.data:
            return "⚠️ No products found in your catalog."

        lines = ["Here are the first 10 products in your catalog:\n"]
        for product in res.data:
            sku = product.get("sku", "N/A")
            name = product.get("product_name", "Unnamed")
            qty = product.get("quantity_available", 0)
            lines.append(f"🔹 {sku} (Available: {qty})")

        lines.append("\n➡️ To view all products, apply filters, or export to Excel, visit your dashboard:")
        lines.append(f"{APP_URL}/products")

        lines.append("There, you can:\n"
                     "- Search by SKU, name, or brand\n"
                     "- Filter by inventory, status, or warehouse\n"
                     "- Export the full list in Excel format\n")

        return "\n".join(lines)

    except Exception as e:
        print(f"[ERROR] {e}")
        return f"❌ Error fetching products: {str(e)}"


# 🔥 Export
list_products_tool = list_products