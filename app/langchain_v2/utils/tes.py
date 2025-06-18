import os
import requests
from supabase import create_client, Client


def get_supabase_client() -> Client:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing environment variables2:")
        print(f"SUPABASE_URL: {SUPABASE_URL}")
        print(f"SUPABASE_SERVICE_ROLE_KEY: {SUPABASE_KEY}")
        raise Exception(
            "❌ Environment variables SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required2!"
        )

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def run_sql_query(query: str):
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception(
            "❌ Environment variables SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required!"
        )

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    payload = {"query": query}

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/exe_sql_query",
        json=payload,
        headers=headers,
    )

    if response.status_code != 200:
        print(f"❌ SQL Query Error: {response.status_code} - {response.text}")
        raise Exception(f"SQL Query failed: {response.text}")

    return response.json()