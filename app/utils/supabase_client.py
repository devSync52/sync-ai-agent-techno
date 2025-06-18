import os
import requests
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_sql_query(query: str):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    response = requests.post(f"{SUPABASE_URL}/rest/v1/rpc/exe_sql_query", json=payload, headers=headers)

    if response.status_code != 200:
        return f"Error: {response.text}"

    return response.json()