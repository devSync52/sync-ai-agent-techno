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
    Export the full product catalog to an Excel file and provide a download link.
    """
    supabase = get_supabase_client()
    try:
        res = (
            supabase
            .table("ai_products_unified")
            .select("*")
            .limit(1000)  # 🔥 Ajuste conforme necessidade
            .execute()
        )

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