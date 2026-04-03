from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_current_user
from api.logger import get_logger
from api.supabase_client import get_supabase

router = APIRouter()
logger = get_logger(__name__)


@router.delete("/nf/{nf_id}")
def remover_nf(nf_id: int, user=Depends(get_current_user)):
    """
    Remove uma NF de comprovantes_despesa:
    1. Busca o registro para obter URL e despesa_id
    2. Remove o arquivo do bucket 'comprovantes'
    3. Remove o registro de comprovantes_despesa
    4. Se não restam NFs para a despesa, seta tem_nota_fiscal=False em c_despesas
    """
    sb = get_supabase()

    res = sb.table("comprovantes_despesa") \
            .select("id, url, nome_arquivo, despesa_id") \
            .eq("id", nf_id) \
            .execute()

    if not res.data:
        raise HTTPException(status_code=404, detail="NF não encontrada")

    nf = res.data[0]

    # Remove do bucket (usa service key — tem permissão total)
    nome_arquivo = nf.get("nome_arquivo")
    if nome_arquivo:
        try:
            sb.storage.from_("comprovantes").remove([nome_arquivo])
        except Exception as e:
            logger.warning("Não foi possível remover '%s' do bucket: %s", nome_arquivo, e)

    # Remove o registro
    sb.table("comprovantes_despesa").delete().eq("id", nf_id).execute()

    # Verifica se ainda restam NFs para a despesa
    restantes = sb.table("comprovantes_despesa") \
                  .select("id") \
                  .eq("despesa_id", nf["despesa_id"]) \
                  .execute()

    if not restantes.data:
        sb.table("c_despesas") \
          .update({"tem_nota_fiscal": False}) \
          .eq("id", nf["despesa_id"]) \
          .execute()

    return {"success": True, "despesa_id": nf["despesa_id"], "restantes": len(restantes.data or [])}
