import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.utils.supabase_client import get_supabase_client

# Substitua por um account_id real (pai ou filho)
REAL_ACCOUNT_ID = "c34776aa-6006-4726-96ce-50463867e58f"

supabase = get_supabase_client()

try:
    # 🔍 Determinar tipo de usuário (account_id será usado como channel_account_id se for client)
    # Simulação de user_type para fins de teste
    user_type = "client"  # Altere para "admin" para testar ambos os fluxos
    account_id = REAL_ACCOUNT_ID
    if user_type == "client":
        print(f"[list_products] 👤 Client detected. Using channel_account_id = {account_id}")
        query = supabase.table("ai_products_unified_v3").select("sku, product_name, quantity_available").eq("channel_account_id", account_id)
    else:
        # Buscar parent_account_id e incluir ambos na busca
        print(f"[list_products] 🧩 Buscando parent_account_id de {account_id}")
        parent_resp = supabase.table("accounts").select("parent_account_id").eq("id", account_id).maybe_single().execute()
        parent_id = parent_resp.data.get("parent_account_id") if parent_resp.data else None
        ids_to_search = [account_id]
        if parent_id:
            ids_to_search.append(parent_id)
        print(f"[list_products] 🔎 Buscando por account_id IN {ids_to_search}")
        query = supabase.table("ai_products_unified_v3").select("sku, product_name, quantity_available").in_("account_id", ids_to_search)

    result = query.limit(10).execute()

    print("✅ Produtos encontrados:")
    for p in result.data:
        print(f"- {p['sku']} | {p['product_name']} | Quantidade: {p['quantity_available']}")

except Exception as e:
    print(f"❌ Erro durante a execução: {e}")