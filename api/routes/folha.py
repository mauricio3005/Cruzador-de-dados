import base64
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_current_user
from api.logger import get_logger
from api.supabase_client import get_supabase

router = APIRouter()
logger = get_logger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class FolhaFecharRequest(BaseModel):
    folha_id: int
    obra: str
    quinzena: str                              # "YYYY-MM-DD"
    comprovantes: Optional[List[str]] = []     # lista de base64 strings
    comprovantes_tipos: Optional[List[str]] = []  # content_types correspondentes


@router.post("/fechar")
def fechar_folha(req: FolhaFecharRequest, user=Depends(get_current_user)):
    """
    Operação de fechamento de folha com rollback compensatório:
    1. Agrupa folha_funcionarios por etapa e calcula totais
    2. Insere registros em c_despesas por etapa
    3. Faz upload dos comprovantes para Supabase Storage
    4. Vincula comprovantes a todas as despesas geradas
    5. Atualiza folhas.status = 'fechada'
    Em caso de falha: reverte despesas inseridas e arquivos enviados.
    """
    sb = get_supabase()

    # Validação de tamanho de comprovantes
    for i, b64_str in enumerate(req.comprovantes or []):
        raw_size = len(b64_str) * 3 // 4
        if raw_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"Comprovante {i+1} maior que 10 MB")

    # 1. Carrega funcionários da folha
    res = sb.table("folha_funcionarios").select("*").eq("folha_id", req.folha_id).execute()
    funcionarios = res.data or []
    if not funcionarios:
        raise HTTPException(status_code=400, detail="Folha sem funcionários")

    # 2. Agrupa por etapa
    por_etapa: dict[str | None, float] = {}
    for f in funcionarios:
        etapa = f.get("etapa") or None
        por_etapa[etapa] = por_etapa.get(etapa, 0.0) + float(f.get("valor") or 0)

    despesa_ids = []
    arquivos_enviados = []

    try:
        # 3. Insere uma despesa por etapa em c_despesas
        for etapa, valor in por_etapa.items():
            if valor <= 0:
                continue
            rec = {
                "obra":            req.obra,
                "etapa":           etapa,
                "tipo":            "Mão de Obra",
                "despesa":         "SALÁRIO PESSOAL",
                "descricao":       f"Folha quinzenal — {req.quinzena}",
                "fornecedor":      "FOLHA",
                "valor_total":     round(valor, 2),
                "data":            req.quinzena,
                "tem_nota_fiscal": len(req.comprovantes) > 0,
                "folha_id":        req.folha_id,
            }
            insert_res = sb.table("c_despesas").insert(rec).execute()
            if insert_res.data:
                despesa_ids.append(insert_res.data[0]["id"])

        if not despesa_ids:
            raise HTTPException(status_code=400, detail="Nenhuma despesa gerada (todos os valores são zero)")

        # 4. Upload de comprovantes e vinculação
        comp_urls = []
        for i, (b64_str, content_type) in enumerate(
            zip(req.comprovantes, req.comprovantes_tipos or ["image/jpeg"] * len(req.comprovantes))
        ):
            file_bytes = base64.b64decode(b64_str)
            ext = content_type.split("/")[-1].replace("jpeg", "jpg")
            filename = f"folha_{req.quinzena}_{req.obra[:15].replace(' ', '_')}_{uuid.uuid4().hex[:8]}.{ext}"

            sb.storage.from_("comprovantes").upload(
                filename,
                file_bytes,
                {"content-type": content_type, "upsert": "true"},
            )
            arquivos_enviados.append(filename)
            url = sb.storage.from_("comprovantes").get_public_url(filename)
            comp_urls.append(url)

            for desp_id in despesa_ids:
                sb.table("comprovantes_despesa").insert({
                    "despesa_id":   desp_id,
                    "url":          url,
                    "nome_arquivo": filename,
                }).execute()

        # 5. Atualiza status da folha
        sb.table("folhas").update({"status": "fechada"}).eq("id", req.folha_id).execute()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro no fechamento de folha — iniciando rollback: %s", e, exc_info=True)
        if despesa_ids:
            try:
                sb.table("c_despesas").delete().in_("id", despesa_ids).execute()
            except Exception as rb_err:
                logger.error("Falha no rollback de despesas: %s", rb_err)
        for nome in arquivos_enviados:
            try:
                sb.storage.from_("comprovantes").remove([nome])
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Falha no fechamento — operação revertida")

    return {
        "success":      True,
        "despesa_ids":  despesa_ids,
        "comprovantes": comp_urls,
    }
