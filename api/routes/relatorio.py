import os
import sys
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

router = APIRouter()


@router.get("/pdf")
def gerar_pdf(
    obra: str = Query(..., description="Nome da obra"),
    tipo: str = Query("simples", description="Tipo: simples ou detalhado"),
    data_ini: str = Query(None, description="Data inicial YYYY-MM-DD"),
    data_fim: str = Query(None, description="Data final YYYY-MM-DD"),
):
    """Gera um relatório PDF e retorna como download."""
    # Adiciona o diretório raiz ao path para importar relatorio.py
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        import relatorio as rel
        from dotenv import load_dotenv
        from supabase import create_client
        load_dotenv()

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise HTTPException(status_code=500, detail="Supabase não configurado")

        sb = create_client(url, key)
        pdf_bytes = rel.gerar_relatorio(sb, obra=obra, tipo=tipo, data_ini=data_ini, data_fim=data_fim)

        nome_arquivo = f"relatorio_{obra.replace(' ', '_')}_{tipo}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
        )
    except AttributeError:
        raise HTTPException(status_code=501, detail="Função gerar_relatorio não encontrada em relatorio.py")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
