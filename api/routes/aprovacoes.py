"""
api/routes/aprovacoes.py

Endpoints para o fluxo de aprovação de despesas submetidas por funcionários.

GET  /api/aprovacoes             → lista despesas_pendentes (filtro por status)
POST /api/aprovacoes/{id}/aprovar  → aprova: cria c_despesas + comprovantes_despesa
POST /api/aprovacoes/{id}/rejeitar → rejeita: grava observação
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_current_user
from api.logger import get_logger
from api.supabase_client import get_supabase

logger = get_logger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RejeitarBody(BaseModel):
    observacao: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _buscar_pendente(sb, id: str) -> dict:
    """Retorna o registro ou lança 404."""
    r = sb.from_("despesas_pendentes").select("*").eq("id", id).single().execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Despesa pendente não encontrada.")
    return r.data


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def listar_aprovacoes(
    status: str = "pendente",
    user=Depends(get_current_user),
):
    """
    Lista despesas pendentes de aprovação.
    Query param `status`: pendente | aprovado | rejeitado | todos
    """
    sb = get_supabase()
    try:
        q = sb.from_("despesas_pendentes").select("*").order("created_at", desc=True)
        if status != "todos":
            q = q.eq("status", status)
        r = q.execute()
        return r.data or []
    except Exception as e:
        logger.error("listar_aprovacoes error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar aprovações.")


@router.post("/{id}/aprovar")
def aprovar_despesa(
    id: str,
    user=Depends(get_current_user),
):
    """
    Aprova uma despesa pendente:
    1. Lê o registro de despesas_pendentes
    2. Insere em c_despesas
    3. Insere em comprovantes_despesa
    4. Atualiza status → aprovado e guarda despesa_id_aprovada
    """
    sb = get_supabase()

    pendente = _buscar_pendente(sb, id)

    if pendente["status"] != "pendente":
        raise HTTPException(
            status_code=409,
            detail=f"Esta despesa já está com status '{pendente['status']}'.",
        )

    # 1. INSERT em c_despesas
    try:
        despesa_payload = {
            "obra":           pendente["obra"],
            "etapa":          pendente["etapa"],
            "tipo":           pendente["tipo"],
            "fornecedor":     pendente["fornecedor"],
            "valor_total":    pendente["valor_total"],
            "data":           pendente["data"],
            "descricao":      pendente["descricao"],
            "despesa":        pendente["despesa"],
            "forma":          pendente["forma"],
            "banco":          pendente["banco"],
            "tem_nota_fiscal": True,
            "paga":           False,
        }
        ins = sb.from_("c_despesas").insert(despesa_payload).execute()
        if not ins.data:
            raise RuntimeError("INSERT em c_despesas não retornou dados.")
        nova_despesa = ins.data[0]
        nova_despesa_id = nova_despesa["id"]
    except Exception as e:
        logger.error("aprovar_despesa: erro ao inserir c_despesas: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao criar despesa aprovada.")

    # 2. INSERT em comprovantes_despesa
    try:
        sb.from_("comprovantes_despesa").insert({
            "despesa_id":      nova_despesa_id,
            "url":             pendente["comprovante_url"],
            "nome_arquivo":    pendente["comprovante_url"].split("/")[-1],
        }).execute()
    except Exception as e:
        # Não aborta a aprovação por falha no comprovante (evita estado inconsistente)
        logger.warning("aprovar_despesa: erro ao inserir comprovantes_despesa: %s", e)

    # 3. UPDATE despesas_pendentes → aprovado
    try:
        sb.from_("despesas_pendentes").update({
            "status":               "aprovado",
            "despesa_id_aprovada":  nova_despesa_id,
            "updated_at":           _agora_iso(),
        }).eq("id", id).execute()
    except Exception as e:
        logger.error("aprovar_despesa: erro ao atualizar status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Despesa criada, mas falha ao atualizar status.")

    logger.info("Despesa pendente %s aprovada → c_despesas %s", id, nova_despesa_id)
    return {
        "ok": True,
        "despesa_id": nova_despesa_id,
        "despesa": nova_despesa,
    }


@router.post("/{id}/rejeitar")
def rejeitar_despesa(
    id: str,
    body: RejeitarBody = RejeitarBody(),
    user=Depends(get_current_user),
):
    """
    Rejeita uma despesa pendente, gravando a observação do admin.
    """
    sb = get_supabase()

    pendente = _buscar_pendente(sb, id)

    if pendente["status"] != "pendente":
        raise HTTPException(
            status_code=409,
            detail=f"Esta despesa já está com status '{pendente['status']}'.",
        )

    try:
        sb.from_("despesas_pendentes").update({
            "status":          "rejeitado",
            "observacao_admin": body.observacao or None,
            "updated_at":      _agora_iso(),
        }).eq("id", id).execute()
    except Exception as e:
        logger.error("rejeitar_despesa error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao rejeitar despesa.")

    logger.info("Despesa pendente %s rejeitada. Motivo: %s", id, body.observacao)
    return {"ok": True}
