import asyncio
import os
import sys
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import get_current_user
from api.logger import get_logger
from api.routes import ai, documentos, folha, relatorio, recorrentes

# Corrige WinError 10054 no Windows com Python 3.8+ (ProactorEventLoop)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = get_logger(__name__)

app = FastAPI(title="Dashboard API", version="1.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

app.include_router(ai.router,          prefix="/api/ai",         tags=["IA"])
app.include_router(documentos.router,  prefix="/api/documentos", tags=["Documentos"])
app.include_router(folha.router,       prefix="/api/folha",      tags=["Folha"])
app.include_router(relatorio.router,   prefix="/api/relatorio",  tags=["Relatório"])
app.include_router(recorrentes.router, prefix="/api/recorrentes",tags=["Recorrentes"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


DEBUG_ENABLED = os.getenv("DEBUG_ENDPOINTS", "false").lower() == "true"


@app.get("/api/debug/supabase")
def debug_supabase(user=Depends(get_current_user)):
    if not DEBUG_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    from api.supabase_client import get_supabase
    try:
        db    = get_supabase()
        r     = db.table("c_despesas").select("obra, valor_total").limit(3).execute()
        r2    = db.table("fornecedores").select("nome").limit(3).execute()
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
        logger.error("debug_supabase error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


@app.get("/api/debug/chat-context")
def debug_chat_context(user=Depends(get_current_user)):
    if not DEBUG_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    from api.supabase_client import get_supabase
    try:
        db = get_supabase()
        obras_list    = [r["nome"] for r in (db.table("obras").select("nome").execute().data or [])]
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
        logger.error("debug_chat_context error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")
