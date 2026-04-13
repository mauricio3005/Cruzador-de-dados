import os
import sys
import io
import json
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.config import OPENAI_MINI_MODEL
from api.dependencies import get_current_user
from api.logger import get_logger
from api.supabase_client import get_supabase

router = APIRouter()
logger = get_logger(__name__)


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
    banco: str = Query(None, description="Nome do banco/conta para relatório por banco"),
    _user=Depends(get_current_user),
):
    """Gera relatório PDF da obra e retorna como download."""
    sb  = get_supabase()
    rel = _importar_relatorio()

    try:
        # ── Dados da obra ────────────────────────────────────────────────────
        res_obras = sb.table("obras").select("nome, descricao, contrato, art, empresa_id, empresas(nome, logo_url)").eq("nome", obra).execute()
        obra_row  = (res_obras.data or [{}])[0]
        empresa   = obra_row.get("empresas") or {}
        obra_info = {
            "descricao":      obra_row.get("descricao") or obra,
            "contrato":       obra_row.get("contrato"),
            "art":            obra_row.get("art"),
            "empresa_nome":   empresa.get("nome"),
            "empresa_logo":   empresa.get("logo_url"),
        }

        # ── Orçamentos ───────────────────────────────────────────────────────
        res_orc = sb.table("orcamentos").select("obra, etapa, tipo_custo, valor_estimado").eq("obra", obra).execute()
        df_orc  = pd.DataFrame(res_orc.data or [])

        # ── Despesas (todas) ─────────────────────────────────────────────────
        res_desp = sb.table("c_despesas").select("obra, etapa, tipo, valor_total, data, fornecedor, descricao, banco").eq("obra", obra).execute()
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
                "banco": "BANCO",
            })
            df_desp["VALOR_TOTAL"] = pd.to_numeric(df_desp["VALOR_TOTAL"], errors="coerce").fillna(0)
        else:
            df_desp = pd.DataFrame(columns=["OBRA", "ETAPA", "TIPO_CUSTO", "VALOR_TOTAL", "DATA", "FORNECEDOR", "DESCRICAO", "BANCO"])

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
            if banco:
                # Relatório por banco: filtra despesas pelo campo banco
                df_banco = df_desp[df_desp["BANCO"].str.strip().str.lower() == banco.strip().lower()] if not df_desp.empty and "BANCO" in df_desp.columns else pd.DataFrame()
                pdf_bytes = rel.gerar_relatorio_administrativo_banco(df_banco, obra, dt_ini, dt_fim, obra_info, banco_nome=banco)
            else:
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
        logger.error("gerar_pdf error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISE INTELIGENTE (IA)
# ─────────────────────────────────────────────────────────────────────────────

class AnalisarPayload(BaseModel):
    obras: List[str]
    data_ini: Optional[str] = None
    data_fim: Optional[str] = None


def _parse_json_ia(text: str):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


@router.post("/analisar")
def analisar_relatorio(payload: AnalisarPayload, _user=Depends(get_current_user)):
    """
    Analisa dados financeiros de uma ou mais obras com GPT e retorna insights.
    Modo comparativo quando len(obras) > 1.
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não configurada")

    sb = get_supabase()
    obras_list = payload.obras
    data_ini   = payload.data_ini
    data_fim   = payload.data_fim

    try:
        contexto_obras = []

        for obra_nome in obras_list:
            # Dados da obra (com empresa)
            res_obra = sb.table("obras").select(
                "nome, descricao, contrato, art, empresa_id, empresas(nome, logo_url)"
            ).eq("nome", obra_nome).execute()
            obra_row = (res_obra.data or [{}])[0]
            empresa_nome = (obra_row.get("empresas") or {}).get("nome") if obra_row.get("empresas") else None

            # Orçamentos
            res_orc = sb.table("orcamentos").select("etapa, tipo_custo, valor_estimado").eq("obra", obra_nome).execute()
            df_orc  = pd.DataFrame(res_orc.data or [])

            # Despesas (filtradas por período se informado)
            q_desp = sb.table("c_despesas").select(
                "etapa, tipo, fornecedor, valor_total, data, despesa"
            ).eq("obra", obra_nome)
            if data_ini:
                q_desp = q_desp.gte("data", data_ini)
            if data_fim:
                q_desp = q_desp.lte("data", data_fim)
            res_desp = q_desp.execute()
            df_desp  = pd.DataFrame(res_desp.data or [])

            if not df_desp.empty:
                df_desp["valor_total"] = pd.to_numeric(df_desp["valor_total"], errors="coerce").fillna(0)

            # Recebimentos
            res_rec = sb.table("recebimentos").select("valor").eq("obra", obra_nome).execute()
            total_recebido = sum(float(r.get("valor") or 0) for r in (res_rec.data or []))

            # Contas a pagar = c_despesas com vencimento preenchido e não pagas
            res_cap = sb.table("c_despesas").select("valor_total, paga").eq("obra", obra_nome).not_.is_("vencimento", "null").eq("paga", False).execute()
            total_a_pagar = sum(float(r.get("valor_total") or 0) for r in (res_cap.data or []))

            # Taxa de conclusão
            res_taxa = sb.table("taxa_conclusao").select("etapa, taxa").eq("obra", obra_nome).execute()
            taxa_map = {r["etapa"]: float(r.get("taxa") or 0) for r in (res_taxa.data or [])}

            # Cálculos agregados
            total_orcado   = float(df_orc["valor_estimado"].sum()) if not df_orc.empty else 0
            total_realizado = float(df_desp["valor_total"].sum())  if not df_desp.empty else 0
            pct_consumo    = round((total_realizado / total_orcado * 100), 1) if total_orcado > 0 else 0
            pct_conclusao  = round(sum(taxa_map.values()) / len(taxa_map), 1) if taxa_map else 0
            saldo_caixa    = total_recebido - total_realizado - total_a_pagar

            # Por etapa
            por_etapa = []
            etapas_set = set()
            if not df_orc.empty:
                etapas_set.update(df_orc["etapa"].unique())
            if not df_desp.empty:
                etapas_set.update(df_desp["etapa"].dropna().unique())
            for et in sorted(etapas_set):
                orc_et  = float(df_orc[df_orc["etapa"] == et]["valor_estimado"].sum()) if not df_orc.empty else 0
                real_et = float(df_desp[df_desp["etapa"] == et]["valor_total"].sum())  if not df_desp.empty else 0
                pct_et  = round((real_et / orc_et * 100), 1) if orc_et > 0 else 0
                por_etapa.append({
                    "etapa":    et,
                    "orcado":   round(orc_et, 2),
                    "realizado": round(real_et, 2),
                    "pct":      pct_et,
                    "conclusao": taxa_map.get(et, 0),
                })

            # Por tipo de custo
            por_tipo = {}
            if not df_desp.empty:
                for tipo, grp in df_desp.groupby("tipo"):
                    por_tipo[tipo] = round(float(grp["valor_total"].sum()), 2)

            # Top 5 fornecedores
            top_fornecedores = []
            if not df_desp.empty:
                top = df_desp.groupby("fornecedor")["valor_total"].sum().nlargest(5).reset_index()
                top_fornecedores = [
                    {"nome": r["fornecedor"], "total": round(float(r["valor_total"]), 2)}
                    for _, r in top.iterrows()
                ]

            # Evolução mensal (últimos 6 meses)
            evolucao_mensal = []
            if not df_desp.empty and "data" in df_desp.columns:
                df_m = df_desp.copy()
                df_m["mes"] = pd.to_datetime(df_m["data"], errors="coerce").dt.to_period("M").astype(str)
                df_m = df_m.dropna(subset=["mes"])
                mensal = df_m.groupby("mes")["valor_total"].sum().sort_index().tail(6)
                evolucao_mensal = [{"mes": m, "total": round(float(v), 2)} for m, v in mensal.items()]

            contexto_obras.append({
                "nome":              obra_nome,
                "empresa":           empresa_nome,
                "orcamento_total":   round(total_orcado, 2),
                "realizado_total":   round(total_realizado, 2),
                "pct_consumo":       pct_consumo,
                "pct_conclusao_media": pct_conclusao,
                "total_recebido":    round(total_recebido, 2),
                "a_pagar_pendente":  round(total_a_pagar, 2),
                "saldo_caixa":       round(saldo_caixa, 2),
                "por_etapa":         por_etapa,
                "por_tipo":          por_tipo,
                "top_fornecedores":  top_fornecedores,
                "evolucao_mensal":   evolucao_mensal,
            })

        modo = "comparativo" if len(obras_list) > 1 else "unico"

        system_prompt = """Você é um consultor financeiro especializado em obras de construção civil.
Analise os dados financeiros fornecidos e gere insights acionáveis, objetivos e práticos.
Identifique riscos, desvios de orçamento, concentração de fornecedores e oportunidades de melhoria.
Use linguagem clara e direta, adequada para gestores de obras.
Responda APENAS com JSON válido, sem texto extra antes ou depois."""

        user_msg = f"""Dados financeiros (modo: {modo}):
{json.dumps(contexto_obras, ensure_ascii=False, indent=2)}

Responda com JSON exatamente neste formato:
{{
  "resumo_executivo": "resumo de 2-3 frases sobre a situação geral",
  "saude_financeira": <número 0-100 representando a saúde financeira geral>,
  "alertas": [
    {{"titulo": "...", "descricao": "...", "severidade": "alta|media|baixa"}}
  ],
  "recomendacoes": [
    {{"acao": "...", "justificativa": "..."}}
  ],
  "destaques_positivos": ["..."],
  "comparativo": null
}}

Para modo comparativo, preencha o campo "comparativo" com análise cruzada entre as obras.
Limite: máximo 3 alertas, 3 recomendações, 3 destaques. Seja conciso e específico."""

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=OPENAI_MINI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=1200,
        )

        raw = resp.choices[0].message.content or "{}"
        analise = _parse_json_ia(raw)

        return {
            "modo":    modo,
            "obras":   contexto_obras,
            "analise": analise,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("analisar_relatorio error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")
