import os

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _get_supabase():
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase não configurado")
    return create_client(url, key)


@router.delete("/nf/{nf_id}")
def remover_nf(nf_id: int):
    """
    Remove uma NF de comprovantes_despesa:
    1. Busca o registro para obter URL e despesa_id
    2. Remove o arquivo do bucket 'comprovantes'
    3. Remove o registro de comprovantes_despesa
    4. Se não restam NFs para a despesa, seta tem_nota_fiscal=False em c_despesas
    """
    sb = _get_supabase()

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
            print(f"[documentos] Aviso: não foi possível remover '{nome_arquivo}' do bucket: {e}")

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
