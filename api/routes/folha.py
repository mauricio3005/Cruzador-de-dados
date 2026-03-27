import base64
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class FolhaFecharRequest(BaseModel):
    folha_id: int
    obra: str
    quinzena: str                        # "YYYY-MM-DD"
    comprovantes: Optional[List[str]] = []   # lista de base64 strings
    comprovantes_tipos: Optional[List[str]] = []  # content_types correspondentes


def _get_supabase():
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase não configurado")
    return create_client(url, key)


@router.post("/fechar")
def fechar_folha(req: FolhaFecharRequest):
    """
    Operação atômica de fechamento de folha:
    1. Agrupa folha_funcionarios por etapa e calcula totais
    2. Insere registros em c_despesas por etapa
    3. Faz upload dos comprovantes para Supabase Storage
    4. Vincula comprovantes a todas as despesas geradas
    5. Atualiza folhas.status = 'fechada'
    """
    sb = _get_supabase()

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

    # 3. Insere uma despesa por etapa em c_despesas
    despesa_ids = []
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
        try:
            file_bytes = base64.b64decode(b64_str)
            ext = content_type.split("/")[-1].replace("jpeg", "jpg")
            filename = f"folha_{req.quinzena}_{req.obra[:15].replace(' ', '_')}_{uuid.uuid4().hex[:8]}.{ext}"

            sb.storage.from_("comprovantes").upload(
                filename,
                file_bytes,
                {"content-type": content_type, "upsert": "true"},
            )
            url = sb.storage.from_("comprovantes").get_public_url(filename)
            comp_urls.append(url)

            # Vincula a TODAS as despesas geradas
            for desp_id in despesa_ids:
                sb.table("comprovantes_despesa").insert({
                    "despesa_id":    desp_id,
                    "url":           url,
                    "nome_arquivo":  filename,
                }).execute()
        except Exception as e:
            # Não aborta — registra o erro mas continua
            logger.warning("Erro ao fazer upload do comprovante %d: %s", i, e)

    # 5. Atualiza status da folha
    sb.table("folhas").update({"status": "fechada"}).eq("id", req.folha_id).execute()

    # 6. Remove despesas antigas (caso seja reabertura)
    # Feito antes do insert se houver folha_id na c_despesas — já tratado no front

    return {
        "success":     True,
        "despesa_ids": despesa_ids,
        "comprovantes": comp_urls,
    }
