import re
from typing import Optional
from supabase import create_client, Client
import os

# 🔗 Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# 🚀 Detect SKU
def detect_sku(input_text: str, account_id: str) -> Optional[str]:
    sku_candidates = re.findall(r"\b[A-Z0-9\-_.]{3,}\b", input_text.upper())
    print(f"[DEBUG] SKU candidates: {sku_candidates}")

    for candidate in sku_candidates:
        response = (
            supabase.table("ai_products_unified")
            .select("sku")
            .eq("account_id", account_id)
            .eq("sku", candidate)
            .limit(1)
            .execute()
        )
        if response.data:
            print(f"[DEBUG] Detected SKU: {candidate}")
            return candidate

    print("[DEBUG] No SKU detected.")
    return None


# 🚀 Detect Country (validado)
def detect_country(input_text: str) -> Optional[str]:
    country_list = {
        "UNITED STATES": "US", "US": "US", "USA": "US",
        "BRAZIL": "BR", "BR": "BR",
        "DENMARK": "DK", "DK": "DK",
        "CHINA": "CN", "CN": "CN",
        "MEXICO": "MX", "MX": "MX",
        "GERMANY": "DE", "DE": "DE",
        "TURKEY": "TR", "TR": "TR",
        "FRANCE": "FR", "FR": "FR",
        "SPAIN": "ES", "ES": "ES",
        "UNITED KINGDOM": "GB", "UK": "GB", "GB": "GB",
        "CANADA": "CA", "CA": "CA"
    }

    input_upper = input_text.upper()

    for name, code in country_list.items():
        if name in input_upper:
            print(f"[DEBUG] Detected country: {code}")
            return code

    print("[DEBUG] No valid country detected.")
    return None


# 🚀 Wrapper Full
def parse_input(input_text: str, account_id: str) -> dict:
    sku = detect_sku(input_text, account_id)
    country = detect_country(input_text)

    return {
        "sku": sku,
        "country": country
    }