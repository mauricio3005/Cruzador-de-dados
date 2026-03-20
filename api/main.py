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
