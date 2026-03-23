import os
import sys
import io
from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

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


def _importar_relatorio():
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    import relatorio as rel
    return rel


@router.get("/pdf")
def gerar_pdf(
    obra: str = Query(..., description="Nome da obra"),
    tipo: str = Query("simples", description="simples | detalhado | administrativo"),
    data_ini: str = Query(None, description="Data inicial YYYY-MM-DD (só administrativo)"),
    data_fim: str = Query(None, description="Data final YYYY-MM-DD (só administrativo)"),
    por_etapa: bool = Query(True, description="Detalhamento por etapa (detalhado/administrativo)"),
):
    """Gera relatório PDF da obra e retorna como download."""
    sb  = _get_supabase()
    rel = _importar_relatorio()

    try:
        # ── Dados da obra ────────────────────────────────────────────────────
        res_obras = sb.table("obras").select("nome, descricao, contrato, art").eq("nome", obra).execute()
        obra_row  = (res_obras.data or [{}])[0]
        obra_info = {
            "descricao": obra_row.get("descricao") or obra,
            "contrato":  obra_row.get("contrato"),
            "art":       obra_row.get("art"),
        }

        # ── Orçamentos ───────────────────────────────────────────────────────
        res_orc = sb.table("orcamentos").select("obra, etapa, tipo_custo, valor_estimado").eq("obra", obra).execute()
        df_orc  = pd.DataFrame(res_orc.data or [])

        # ── Despesas (todas) ─────────────────────────────────────────────────
        res_desp = sb.table("c_despesas").select("obra, etapa, tipo, valor_total, data, fornecedor, descricao").eq("obra", obra).execute()
        df_desp  = pd.DataFrame(res_desp.data or [])

        # ── Recebimentos ────────────────────────────────────────────────────
        res_receb = sb.table("recebimentos").select("data, valor, fornecedor, descricao, forma, parcela_num, total_parcelas").eq("obra", obra).execute()
        df_receb  = pd.DataFrame(res_receb.data or [])
        if not df_receb.empty:
            df_receb = df_receb.rename(columns={
                "data": "DATA", "valor": "VALOR", "fornecedor": "FORNECEDOR",
                "descricao": "DESCRICAO", "forma": "FORMA",
                "parcela_num": "PARCELA_NUM", "total_parcelas": "TOTAL_PARCELAS",
            })
            df_receb["VALOR"] = pd.to_numeric(df_receb["VALOR"], errors="coerce").fillna(0)

        # ── Montar df_raw (formato esperado por relatorio.py) ─────────────────
        if not df_orc.empty:
            df_orc = df_orc.rename(columns={
                "obra": "OBRA", "etapa": "ETAPA", "tipo_custo": "TIPO_CUSTO",
                "valor_estimado": "ORÇAMENTO_ESTIMADO",
            })
            df_orc["ORÇAMENTO_ESTIMADO"] = pd.to_numeric(df_orc["ORÇAMENTO_ESTIMADO"], errors="coerce").fillna(0)
        else:
            df_orc = pd.DataFrame(columns=["OBRA", "ETAPA", "TIPO_CUSTO", "ORÇAMENTO_ESTIMADO"])

        if not df_desp.empty:
            df_desp = df_desp.rename(columns={
                "obra": "OBRA", "etapa": "ETAPA", "tipo": "TIPO_CUSTO",
                "valor_total": "VALOR_TOTAL", "data": "DATA",
                "fornecedor": "FORNECEDOR", "descricao": "DESCRICAO",
            })
            df_desp["VALOR_TOTAL"] = pd.to_numeric(df_desp["VALOR_TOTAL"], errors="coerce").fillna(0)
        else:
            df_desp = pd.DataFrame(columns=["OBRA", "ETAPA", "TIPO_CUSTO", "VALOR_TOTAL", "DATA", "FORNECEDOR", "DESCRICAO"])

        # Gastos agregados por obra/etapa/tipo
        gastos = (
            df_desp.groupby(["OBRA", "ETAPA", "TIPO_CUSTO"])["VALOR_TOTAL"].sum().reset_index()
            .rename(columns={"VALOR_TOTAL": "GASTO_REALIZADO"})
        )

        if not df_orc.empty and not gastos.empty:
            df_raw = pd.merge(df_orc, gastos, on=["OBRA", "ETAPA", "TIPO_CUSTO"], how="outer")
            df_raw["ORÇAMENTO_ESTIMADO"] = df_raw["ORÇAMENTO_ESTIMADO"].fillna(0)
            df_raw["OBRA"] = df_raw["OBRA"].fillna(obra)
        elif not df_orc.empty:
            df_raw = df_orc.copy()
            df_raw["GASTO_REALIZADO"] = 0
        elif not gastos.empty:
            df_raw = gastos.copy()
            df_raw["ORÇAMENTO_ESTIMADO"] = 0
        else:
            raise HTTPException(status_code=404, detail=f"Obra '{obra}' não encontrada ou sem dados")

        df_raw["GASTO_REALIZADO"] = df_raw["GASTO_REALIZADO"].fillna(0)

        # ── Taxa de conclusão por etapa ───────────────────────────────────────
        res_taxa = sb.table("taxa_conclusao").select("obra, etapa, taxa").eq("obra", obra).execute()
        if res_taxa.data:
            df_taxa = pd.DataFrame(res_taxa.data).rename(
                columns={"obra": "OBRA", "etapa": "ETAPA", "taxa": "TAXA_CONCLUSAO"}
            )
            df_taxa["TAXA_CONCLUSAO"] = pd.to_numeric(df_taxa["TAXA_CONCLUSAO"], errors="coerce").fillna(0)
            df_raw = pd.merge(df_raw, df_taxa, on=["OBRA", "ETAPA"], how="left")
        df_raw["TAXA_CONCLUSAO"] = df_raw.get("TAXA_CONCLUSAO", pd.Series(dtype=float)).fillna(0)

        # ── Despesas da última semana ─────────────────────────────────────────
        sete_dias_atras = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        df_semana = df_desp[df_desp["DATA"] >= sete_dias_atras].copy() if not df_desp.empty else pd.DataFrame()

        # ── Chamar função de relatório ────────────────────────────────────────
        df_receb_param = df_receb if not df_receb.empty else None

        if tipo == "detalhado":
            pdf_bytes = rel.gerar_relatorio_detalhado(
                df_raw, obra,
                df_semana if not df_semana.empty else None,
                obra_info,
                por_etapa=por_etapa,
                df_despesas_todas=df_desp if not df_desp.empty else None,
                df_recebimentos=df_receb_param,
            )
        elif tipo == "administrativo":
            if not data_ini or not data_fim:
                raise HTTPException(status_code=422, detail="data_ini e data_fim obrigatórios para relatório administrativo")
            dt_ini = datetime.strptime(data_ini, "%Y-%m-%d")
            dt_fim = datetime.strptime(data_fim, "%Y-%m-%d")
            pdf_bytes = rel.gerar_relatorio_administrativo(df_desp, obra, dt_ini, dt_fim, obra_info, por_etapa=por_etapa, df_recebimentos=df_receb_param)
        else:
            pdf_bytes = rel.gerar_relatorio_simples(df_raw, obra, df_semana if not df_semana.empty else None, obra_info, df_recebimentos=df_receb_param)

        nome_arquivo = f"relatorio_{obra.replace(' ', '_')}_{tipo}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
