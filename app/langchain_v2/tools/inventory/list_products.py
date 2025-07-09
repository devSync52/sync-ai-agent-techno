import os
from langchain.tools import tool
from app.utils.supabase_client import get_supabase_client
from langchain_core.pydantic_v1 import BaseModel
from app.langchain_v2.utils.session_context import get_current_session_context

APP_URL = os.getenv("APP_URL")


@tool
def list_products(account_id: str) -> str:
    """
    Lists the first 10 products in the catalog and informs where to view, manage, or download the full list.
    """
    supabase = get_supabase_client()
    session_ctx = get_current_session_context()
    user_type = session_ctx.get("user_type")
    session_account_id = session_ctx.get("account_id")

    print(f"[list_products] user_type: {user_type} | session_account_id: {session_account_id}")

    if not session_account_id or session_account_id == "123456":
        print("[list_products] ❌ Invalid or missing account_id from session.")
        return "❌ The account ID is invalid or not linked to your session. Please try again later."

    account_id = session_account_id

    try:
        print(f"[list_products] account_id received: {account_id}")
        if account_id == "123456":
            print("[list_products] ⚠️ Invalid test account_id received. Aborting.")
            return "❌ The account ID is invalid or not linked to your session. Please try again later."
        parent_result = (
            supabase.table("accounts")
            .select("parent_account_id")
            .eq("id", account_id)
            .maybe_single()
            .execute()
        )
        if parent_result is None or parent_result.data is None:
            return "❌ Error fetching parent account: response was empty or invalid."

        parent_account_id = parent_result.data.get("parent_account_id")
        print(f"[list_products] parent_account_id resolved: {parent_account_id}")

        query = (
            supabase
            .table("ai_products_unified_v3")
            .select("sku, product_name, quantity_available")
        )

        if session_ctx.get("user_type") == "client":
            print(f"[list_products] (client) Filtering by channel_account_id: {account_id}")
            query = query.eq("channel_account_id", account_id)
        else:
            if parent_account_id:
                print(f"[list_products] Applying query with account_id(s): {[account_id, parent_account_id]}")
                query = query.in_("account_id", [account_id, parent_account_id])
            else:
                print(f"[list_products] Applying query on account_id only: {account_id}")
                query = query.eq("account_id", account_id)

        res = query.limit(10).execute()
        print(f"[list_products] Query response: {res.data}")

        if not res.data:
            return "⚠️ No products found in your catalog."

        lines = ["Here are the first 10 products in your catalog:\n"]
        for product in res.data:
            sku = product.get("sku", "N/A")
            name = product.get("product_name", "Unnamed")
            qty = product.get("quantity_available", 0)
            lines.append(f"{sku} (Available: {qty})")

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