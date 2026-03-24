import asyncio
from api.supabase_client import supabase

async def main():
    resp = supabase.table('tipos_custo').select('nome').execute()
    print("Tipos de custo permitidos:", [r['nome'] for r in resp.data])

if __name__ == '__main__':
    asyncio.run(main())
