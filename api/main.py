from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import ai, documentos, folha, relatorio

app = FastAPI(title="Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai.router,        prefix="/api/ai",         tags=["IA"])
app.include_router(documentos.router,prefix="/api/documentos", tags=["Documentos"])
app.include_router(folha.router,    prefix="/api/folha",    tags=["Folha"])
app.include_router(relatorio.router,prefix="/api/relatorio",tags=["Relatório"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/debug/supabase")
def debug_supabase():
    """Debug endpoint — testa conexão Supabase e retorna erro se falhar."""
    import os, traceback
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    try:
        db = create_client(url, key)
        r = db.table("c_despesas").select("obra, valor_total").limit(3).execute()
        r2 = db.table("fornecedores").select("nome").limit(3).execute()
        r_all = db.table("c_despesas").select("valor_total").limit(200).execute()
        total = sum(x.get("valor_total") or 0 for x in (r_all.data or []))
        return {
            "ok": True,
            "despesas_sample": r.data,
            "fornecedores_sample": r2.data,
            "total_despesas_200": total,
            "rows_fetched": len(r_all.data or []),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "trace": traceback.format_exc()}


@app.get("/api/debug/chat-context")
def debug_chat_context():
    """Debug: expõe o contexto financeiro completo que será enviado ao GPT no /api/ai/chat."""
    from api.routes.ai import _get_supabase
    try:
        db = _get_supabase()
        obras_list  = [r["nome"] for r in (db.table("obras").select("nome").execute().data or [])]
        despesas_rows = db.table("c_despesas").select("obra, despesa, valor_total, fornecedor").limit(200).execute().data or []
        total_despesas = sum(r.get("valor_total") or 0 for r in despesas_rows)
        forn_totais: dict = {}
        for r in despesas_rows:
            f = r.get("fornecedor") or "N/D"
            forn_totais[f] = forn_totais.get(f, 0) + (r.get("valor_total") or 0)
        top_forn = sorted(forn_totais.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "obras": obras_list,
            "total_despesas": total_despesas,
            "rows": len(despesas_rows),
            "top_fornecedores": top_forn,
        }
    except Exception as e:
        import traceback
        return {"ok": False, "error": str(e), "trace": traceback.format_exc()}
