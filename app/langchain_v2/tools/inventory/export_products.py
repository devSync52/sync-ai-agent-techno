from app.langchain_v2.utils.session_context import get_session_context
import os
import pandas as pd
from datetime import datetime
from langchain.tools import tool

from app.utils.supabase_client import get_supabase_client

# 🔗 Supabase client


# 🔖 App URL para gerar link de download
APP_URL = os.getenv("APP_URL")

# 📂 Pasta de exportação local
EXPORT_FOLDER = "./exports"
os.makedirs(EXPORT_FOLDER, exist_ok=True)


@tool
def export_products(_: str = "Export products") -> str:
    """
    Export the full product catalog (filtered by user type) to an Excel file and provide a download link.
    """
    supabase = get_supabase_client()

    try:
        # 🔐 Pegar dados da sessão
        context = get_session_context()
        account_id = context.account_id
        user_type = context.user_type

        # 🧠 Filtragem condicional
        query = supabase.table("ai_products_unified_v3").select("*").limit(1000)
        if user_type == "client":
            query = query.eq("channel_account_id", account_id)
        else:
            query = query.eq("account_id", account_id)

        res = query.execute()

        if not res.data:
            return "⚠️ No products found to export."

        df = pd.DataFrame(res.data)

        filename = f"products_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(EXPORT_FOLDER, filename)
        df.to_excel(filepath, index=False)

        if not APP_URL:
            return f"✅ File saved as `{filename}` in the server. But `APP_URL` env variable is not set to generate a link."

        download_link = f"{APP_URL}/exports/{filename}"

        return (
            f"✅ Export completed successfully!\n\n"
            f"➡️ [Download your Excel file here]({download_link})"
        )

    except Exception as e:
        return f"❌ Error exporting products: {str(e)}"