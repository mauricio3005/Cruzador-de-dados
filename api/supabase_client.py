"""
Supabase client para o backend.
Usa SUPABASE_SERVICE_KEY (admin) — nunca expor no frontend.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import HTTPException
from supabase import create_client, Client

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="SUPABASE_URL ou SUPABASE_SERVICE_KEY não configuradas no .env")
    return create_client(url, key)
