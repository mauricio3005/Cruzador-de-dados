import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

sb = create_client(url, key)

try:
    print("Testing contas_a_pagar query...")
    res = sb.table("contas_a_pagar").select("*").limit(1).execute()
    print("Success:", res.data)
except Exception as e:
    print("Error querying contas_a_pagar:", str(e))
