"""
Módulo de Despesas Recorrentes.

Endpoints:
  GET    /api/recorrentes          — lista todos os templates
  POST   /api/recorrentes          — cria um template
  PUT    /api/recorrentes/{id}     — atualiza um template
  DELETE /api/recorrentes/{id}     — remove um template
  POST   /api/recorrentes/processar — gera c_despesas para templates vencidos
"""
from __future__ import annotations

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from api.supabase_client import get_supabase

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class RecorrenteIn(BaseModel):
    obra:           Optional[str]   = None
    etapa:          Optional[str]   = None
    tipo:           Optional[str]   = None
    fornecedor:     Optional[str]   = None
    despesa:        Optional[str]   = None
    valor_total:    float           = Field(..., gt=0)
    descricao:      Optional[str]   = None
    banco:          Optional[str]   = None
    forma:          Optional[str]   = None
    frequencia:     str             = Field(..., pattern="^(mensal|trimestral|semestral|anual)$")
    proxima_data:   date
    data_fim:       Optional[date]  = None
    ativa:          bool            = True


# ── Helpers ───────────────────────────────────────────────────────────────────

FREQ_DELTA = {
    "mensal":      lambda: relativedelta(months=1),
    "trimestral":  lambda: relativedelta(months=3),
    "semestral":   lambda: relativedelta(months=6),
    "anual":       lambda: relativedelta(years=1),
}


def _avancar_data(d: date, frequencia: str) -> date:
    return d + FREQ_DELTA[frequencia]()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def listar():
    db = get_supabase()
    res = db.table("despesas_recorrentes").select("*").order("proxima_data").execute()
    return res.data or []


@router.post("", status_code=201)
def criar(body: RecorrenteIn):
    import traceback
    db = get_supabase()
    try:
        payload = body.model_dump()
        payload["proxima_data"] = payload["proxima_data"].isoformat()
        if payload.get("data_fim"):
            payload["data_fim"] = payload["data_fim"].isoformat()
        res = db.table("despesas_recorrentes").insert(payload).execute()
        if not res.data:
            raise HTTPException(500, "Supabase retornou sem dados — possível erro de RLS ou constraint")
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print("ERRO /api/recorrentes POST:\n", tb)
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@router.put("/{rec_id}")
def atualizar(rec_id: int, body: RecorrenteIn):
    db = get_supabase()
    payload = body.model_dump()
    payload["proxima_data"] = payload["proxima_data"].isoformat()
    if payload.get("data_fim"):
        payload["data_fim"] = payload["data_fim"].isoformat()
    res = db.table("despesas_recorrentes").update(payload).eq("id", rec_id).execute()
    if not res.data:
        raise HTTPException(404, "Recorrente não encontrado")
    return res.data[0]


@router.delete("/{rec_id}", status_code=204)
def deletar(rec_id: int):
    db = get_supabase()
    db.table("despesas_recorrentes").delete().eq("id", rec_id).execute()


@router.post("/processar")
def processar():
    """
    Para cada template ativo com proxima_data <= hoje:
      1. Cria uma linha em c_despesas com a data de vencimento
      2. Avança proxima_data pela frequência
      3. Desativa se data_fim foi atingida
    Retorna lista de despesas criadas.
    """
    db   = get_supabase()
    hoje = date.today()

    templates = (
        db.table("despesas_recorrentes")
        .select("*")
        .eq("ativa", True)
        .lte("proxima_data", hoje.isoformat())
        .execute()
        .data or []
    )

    criadas = []

    for t in templates:
        proxima = date.fromisoformat(t["proxima_data"])

        # Pode ter mais de um período vencido (ex: não processado por meses)
        while proxima <= hoje:
            despesa_payload = {
                "obra":        t["obra"],
                "etapa":       t["etapa"],
                "tipo":        t["tipo"],
                "fornecedor":  t["fornecedor"],
                "despesa":     t["despesa"],
                "valor_total": t["valor_total"],
                "descricao":   t["descricao"],
                "banco":       t["banco"],
                "forma":       t["forma"],
                "data":        proxima.isoformat(),
            }
            ins = db.table("c_despesas").insert(despesa_payload).execute()
            if ins.data:
                criadas.append(ins.data[0])

            proxima = _avancar_data(proxima, t["frequencia"])

        # Verificar se chegou ao fim
        data_fim = date.fromisoformat(t["data_fim"]) if t.get("data_fim") else None
        nova_ativa = True
        if data_fim and proxima > data_fim:
            nova_ativa = False

        db.table("despesas_recorrentes").update({
            "proxima_data": proxima.isoformat(),
            "ativa": nova_ativa,
        }).eq("id", t["id"]).execute()

    return {"processadas": len(templates), "despesas_criadas": len(criadas), "despesas": criadas}
