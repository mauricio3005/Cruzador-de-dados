import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import base64
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Configuração da Página
st.set_page_config(page_title="Dashboard Financeiro Gerencial", layout="wide", page_icon="📊")

# --- CSS Customizado (Design System inspirado no WEB/style.css) ---
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<style>
/* ---- Reset e Tipografia ----- */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ---- Background ----- */
.stApp {
    background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
    min-height: 100vh;
}

/* ---- Sidebar ----- */
[data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.82) !important;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-right: 1px solid rgba(255, 255, 255, 0.5) !important;
    box-shadow: 4px 0 24px rgba(31, 38, 135, 0.06);
}

[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7280;
    font-weight: 600;
    margin-bottom: 12px;
}

/* Brand no sidebar */
.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(0,0,0,0.07);
}
.sidebar-logo {
    width: 34px;
    height: 34px;
    background: linear-gradient(135deg, #2563EB, #60A5FA);
    border-radius: 9px;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.30);
    flex-shrink: 0;
}
.sidebar-title {
    font-size: 1.0rem;
    font-weight: 700;
    color: #1F2937;
    letter-spacing: -0.01em;
}

/* ---- Header (título principal) ----- */
.main-header {
    margin-bottom: 8px;
}
.main-header h1 {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1F2937;
    letter-spacing: -0.02em;
    margin: 0;
}
.main-header p {
    font-size: 0.9rem;
    color: #6B7280;
    margin: 4px 0 0 0;
}

/* ---- KPI Cards ----- */
[data-testid="metric-container"] {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.55) !important;
    border-radius: 16px !important;
    padding: 20px 24px !important;
    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.06);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}

[data-testid="metric-container"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 16px 40px rgba(31, 38, 135, 0.10);
}

[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
    text-transform: none;
    letter-spacing: 0;
}

[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #1F2937 !important;
    letter-spacing: -0.02em;
}

[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}

/* ---- Divisor customizado ----- */
.custom-divider {
    height: 1px;
    background: linear-gradient(to right, transparent, rgba(0,0,0,0.08), transparent);
    margin: 20px 0;
    border: none;
}

/* ---- Section Headers ----- */
.section-header {
    font-size: 1.05rem;
    font-weight: 600;
    color: #1F2937;
    letter-spacing: -0.01em;
    margin-bottom: 12px;
    margin-top: 4px;
}

/* ---- Chart Cards ----- */
[data-testid="stPlotlyChart"] {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.55);
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.06);
    padding: 16px;
}

/* ---- Dataframe / Tabela ----- */
[data-testid="stDataFrame"] {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.55) !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.06);
    overflow: hidden;
}

/* ---- Expanders (Acordeão de Obras) ----- */
[data-testid="stExpander"] {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.55) !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 20px rgba(31, 38, 135, 0.05);
    margin-bottom: 10px !important;
    overflow: hidden;
    transition: box-shadow 0.2s ease;
}
[data-testid="stExpander"]:hover {
    box-shadow: 0 8px 28px rgba(31, 38, 135, 0.09);
}
[data-testid="stExpander"] summary {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #1F2937 !important;
    padding: 14px 18px !important;
    border-radius: 14px !important;
}
[data-testid="stExpander"] summary:hover {
    background: rgba(37, 99, 235, 0.04) !important;
}
/* Badge de resumo dentro do expander */
.obra-summary {
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    align-items: center;
}
.obra-badge {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 1px;
}
.obra-badge-label {
    font-size: 0.68rem;
    font-weight: 500;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.obra-badge-value {
    font-size: 0.9rem;
    font-weight: 700;
    color: #1F2937;
}
.obra-badge-value.green { color: #10B981; }
.obra-badge-value.red   { color: #EF4444; }
.obra-badge-value.blue  { color: #2563EB; }
.obra-divider {
    width: 1px;
    height: 28px;
    background: rgba(0,0,0,0.08);
}
/* Progress mini */
.mini-progress-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
}
.mini-progress-bar {
    width: 80px;
    height: 5px;
    background: rgba(0,0,0,0.1);
    border-radius: 99px;
    overflow: hidden;
}
.mini-progress-fill {
    height: 100%;
    border-radius: 99px;
    background: #2563EB;
    transition: width 0.4s ease;
}
.mini-progress-fill.over { background: #EF4444; }

/* ---- Botões ----- */
[data-testid="stButton"] > button {
    background-color: #2563EB !important;
    color: white !important;
    border: none !important;
    border-radius: 9px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 10px 18px !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0;
}

[data-testid="stButton"] > button:hover {
    background-color: #1D4ED8 !important;
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(37, 99, 235, 0.35) !important;
}

/* ---- Progress Bar ----- */
[data-testid="stProgress"] > div > div {
    border-radius: 99px;
}
[data-testid="stProgress"] > div {
    border-radius: 99px;
    height: 7px;
}

/* ---- Multiselect (Filtros) ----- */
[data-testid="stMultiSelect"] > div > div {
    border-radius: 9px !important;
    border-color: rgba(37, 99, 235, 0.25) !important;
    background: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    color: #1F2937 !important;
}

/* Chips/tags do multiselect — forçar azul em vez do vermelho padrão */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background-color: #EFF6FF !important;
    border: 1px solid #BFDBFE !important;
    border-radius: 6px !important;
    color: #1D4ED8 !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
}
/* Ícone de remover (×) do chip */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] span[role="img"],
[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {
    color: #2563EB !important;
    fill: #2563EB !important;
}

/* Texto dentro do campo de busca do multiselect */
[data-testid="stMultiSelect"] input {
    color: #1F2937 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Dropdown de opções */
[data-baseweb="menu"] {
    background: #ffffff !important;
    border-radius: 10px !important;
    border: 1px solid rgba(0,0,0,0.08) !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.10) !important;
}
[data-baseweb="menu"] li {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    color: #1F2937 !important;
}
[data-baseweb="menu"] li:hover {
    background-color: #EFF6FF !important;
}

/* ---- Sidebar: forçar fundo claro sempre ----- */
[data-testid="stSidebar"] > div:first-child {
    background: #f8fafd !important;
}
[data-testid="stSidebar"] * {
    color: #1F2937 !important;
}
/* Exceção: manter chips azuis mesmo dentro do sidebar */
[data-testid="stSidebar"] span[data-baseweb="tag"] {
    background-color: #EFF6FF !important;
    border: 1px solid #BFDBFE !important;
    color: #1D4ED8 !important;
}
[data-testid="stSidebar"] span[data-baseweb="tag"] span,
[data-testid="stSidebar"] span[data-baseweb="tag"] svg {
    color: #2563EB !important;
    fill: #2563EB !important;
}

/* ---- Streamlit toolbar/header superior ----- */
[data-testid="stHeader"] {
    background: rgba(240, 244, 248, 0.95) !important;
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(0,0,0,0.06) !important;
}
[data-testid="stHeader"] * {
    color: #1F2937 !important;
}

/* ---- Warning / Error Messages ----- */
[data-testid="stAlert"] {
    border-radius: 12px !important;
}

/* ---- Remove padding padrão do main block ----- */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
}

/* ---- Status badge ----- */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    font-weight: 500;
    color: #6B7280;
    background: rgba(255,255,255,0.7);
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 99px;
    padding: 4px 12px;
    backdrop-filter: blur(8px);
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10B981;
    box-shadow: 0 0 8px #10B981;
    display: inline-block;
}

/* Kpi icon overlay */
.kpi-icon-overlay {
    position: absolute;
    top: 16px;
    right: 18px;
    opacity: 0.12;
    color: #2563EB;
}

/* ---- Histórico: fonte maior na tabela de despesas ---- */
[data-testid="stDataEditor"] .ag-cell,
[data-testid="stDataEditor"] .ag-cell-value {
    font-size: 0.92rem !important;
    line-height: 1.5 !important;
}
[data-testid="stDataEditor"] .ag-header-cell-text {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
}
[data-testid="stDataEditor"] .ag-row {
    min-height: 36px !important;
}
</style>
""", unsafe_allow_html=True)

# --- EXTRAÇÃO DE NOTA FISCAL VIA IA ---
def _extrair_com_ia(file_bytes: bytes, media_type: str) -> dict:
    """Envia nota fiscal à OpenAI e retorna dados extraídos como dicionário."""
    import io
    import pypdf
    from openai import OpenAI

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY não encontrada no .env")

    client = OpenAI(api_key=api_key)

    _opcoes_despesa = (
        "AREIA COLCHÃO, BLOCO INTERTRAVADO, CALCETEIRO, ESTACAS, MEIO-FIO, PARALELEPÍPEDO, "
        "PEDRA CORTADA, PÓ DE PEDRA, SOLO-BRITA, AÇO / VERGALHÃO, ADITIVOS, AREIA LAVADA, "
        "ARGAMASSA, BLOCO CERÂMICO, BLOCO DE CIMENTO, BRITA GRAVILHÃO, CIMENTO, COMBOGÓ, "
        "FERRO, MADERITE, PREGO, TÁBUA, BLOCO CALHA, MADEIRA P/ TELHADO, TELHA CERÂMICA, "
        "TELHA FIBROCIMENTO, BOMBA, CABOS, CAIXA D'ÁGUA, DISJUNTORES, ELETRODUTO E CONEXÕES, "
        "EMPREITEIRO ELETRICISTA, EMPREITEIRO ENCANADOR, TUBO ÁGUA E CONEXÕES, "
        "TUBO ESGOTO E CONEXÕES, ESQUADRIA DE FERRO, ESQUADRIA DE MADEIRA, GESSO ACARTONADO, "
        "LOUÇAS, LUMINÁRIAS, SOLDA, COMPRA EQUIPAMENTOS, DIVERSOS, EMPREITEIRO, ENTULHO, "
        "EQUIPAMENTOS URBANOS, FARDAS E EPIS, LOCAÇÃO EQUIPAMENTOS, MADEIRA LOCAÇÃO OBRA, "
        "MADEIRA TRATADA, PAISAGISMO, PROJETOS, ÁGUA, ALUGUEL, CONDOMÍNIO, CONTABILIDADE, "
        "ENERGIA, IMPRESSÃO / GRÁFICA, INTERNET / TI, MANUTENÇÃO, MATERIAL PARA ESCRITÓRIO, "
        "TELEFONIA FIXA, TELEFONIA MÓVEL, ALIMENTAÇÃO, COMBUSTÍVEL, DIÁRIA, "
        "FERRYBOAT / BALSA, HOSPEDAGEM, PEDÁGIO, SALÁRIO PESSOAL, TRANSPORTE, "
        "IMPOSTOS, JUROS, RECEITA, REPOSIÇÃO DE CAIXA"
    )
    prompt_instrucao = (
        "Analise o documento anexado — pode ser uma nota fiscal ou um comprovante de pagamento.\n\n"
        "REGRA IMPORTANTE: Se o documento for um comprovante de pagamento (ex: comprovante PIX, "
        "recibo, transferência bancária), preencha APENAS os campos VALOR_TOTAL, DATA e FORMA. "
        "Deixe os demais campos como null, pois comprovantes não contêm essas informações.\n\n"
        "Se for uma nota fiscal completa, extraia todos os campos possíveis.\n\n"
        "Retorne SOMENTE um JSON válido, sem texto adicional:\n\n"
        "{\n"
        '  "FORNECEDOR": "nome do fornecedor ou empresa emissora (null se comprovante)",\n'
        '  "VALOR_TOTAL": <número float obrigatório, ex: 310.50>,\n'
        '  "DATA": "YYYY-MM-DD",\n'
        '  "DESCRICAO": "descrição do serviço ou material (null se comprovante)",\n'
        '  "TIPO": "Mão de Obra" ou "Materiais" ou "Geral" (null se comprovante),\n'
        '  "FORMA": "PIX" ou "Boleto" ou "Cartão" ou "Dinheiro" ou "Transferência" ou "",\n'
        f'  "DESPESA": escolha da lista [{_opcoes_despesa}] ou null\n'
        "}"
    )

    if media_type == "application/pdf":
        # OpenAI Chat Completions não aceita PDF direto — extrai o texto primeiro
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        texto_pdf = "\n".join(page.extract_text() or "" for page in reader.pages)
        messages = [{"role": "user", "content": f"{prompt_instrucao}\n\nConteúdo do documento:\n{texto_pdf}"}]
    else:
        b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                {"type": "text", "text": prompt_instrucao},
            ],
        }]

    resp = client.chat.completions.create(model="gpt-4.1-mini", max_tokens=1024, messages=messages)

    texto = resp.choices[0].message.content.strip()
    if texto.startswith("```"):
        linhas = texto.splitlines()
        texto = "\n".join(linhas[1:-1] if linhas[-1].strip() == "```" else linhas[1:])
    return json.loads(texto)


# --- INICIALIZAÇÃO E DADOS ---
@st.cache_resource
def init_supabase():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

@st.cache_data(ttl=300)
def load_data():
    supabase = init_supabase()
    if not supabase:
        st.error("Chaves do Supabase não encontradas no .env")
        return pd.DataFrame()

    # ── 1. Orçamentos por obra + etapa + tipo ────────────────────────────────
    res_orc = supabase.table("orcamentos").select("obra,etapa,tipo_custo,valor_estimado").execute()
    if not res_orc.data:
        return pd.DataFrame()
    df_orc = pd.DataFrame(res_orc.data)
    df_orc.rename(columns={"obra": "OBRA", "etapa": "ETAPA",
                            "tipo_custo": "TIPO_CUSTO",
                            "valor_estimado": "ORÇAMENTO_ESTIMADO"}, inplace=True)
    df_orc["ORÇAMENTO_ESTIMADO"] = pd.to_numeric(df_orc["ORÇAMENTO_ESTIMADO"], errors="coerce").fillna(0)

    # ── 2. Gastos realizados (c_despesas agrupadas) ──────────────────────────
    res_desp = supabase.table("c_despesas").select("obra,etapa,tipo,valor_total").execute()
    df_desp_raw = pd.DataFrame(res_desp.data) if res_desp.data else pd.DataFrame()

    if not df_desp_raw.empty:
        df_desp_raw["tipo"] = df_desp_raw["tipo"].fillna("Geral").str.strip()
        df_desp_raw["valor_total"] = pd.to_numeric(df_desp_raw["valor_total"], errors="coerce").fillna(0)
        df_gastos = (
            df_desp_raw.groupby(["obra", "etapa", "tipo"])["valor_total"]
            .sum()
            .reset_index()
            .rename(columns={"obra": "OBRA", "etapa": "ETAPA",
                             "tipo": "TIPO_CUSTO", "valor_total": "GASTO_REALIZADO"})
        )
    else:
        df_gastos = pd.DataFrame(columns=["OBRA", "ETAPA", "TIPO_CUSTO", "GASTO_REALIZADO"])

    # ── 3. Merge orçamento x gastos ─────────────────────────────────────────
    df = pd.merge(df_orc, df_gastos, on=["OBRA", "ETAPA", "TIPO_CUSTO"], how="outer")
    df[["ORÇAMENTO_ESTIMADO", "GASTO_REALIZADO"]] = (
        df[["ORÇAMENTO_ESTIMADO", "GASTO_REALIZADO"]].fillna(0)
    )
    df["TIPO_CUSTO"] = df["TIPO_CUSTO"].fillna("Geral").str.strip()
    df["SALDO_ETAPA"] = df["ORÇAMENTO_ESTIMADO"] - df["GASTO_REALIZADO"]

    # ── 4. Ordem das etapas ──────────────────────────────────────────────────
    res_etapas = supabase.table("etapas").select("nome,ordem").execute()
    if res_etapas.data:
        df_etapas = pd.DataFrame(res_etapas.data).rename(columns={"nome": "ETAPA", "ordem": "ORDEM_ETAPA"})
        df = pd.merge(df, df_etapas, on="ETAPA", how="left")
        df["ORDEM_ETAPA"] = df["ORDEM_ETAPA"].fillna(999).astype(int)
    else:
        df["ORDEM_ETAPA"] = 999

    # ── 5. Taxa de conclusão ─────────────────────────────────────────────────
    res_taxa = supabase.table("taxa_conclusao").select("obra,etapa,taxa").execute()
    if res_taxa.data:
        df_taxa = pd.DataFrame(res_taxa.data).rename(
            columns={"obra": "OBRA", "etapa": "ETAPA", "taxa": "TAXA_CONCLUSAO"}
        )
        df_taxa["TAXA_CONCLUSAO"] = pd.to_numeric(df_taxa["TAXA_CONCLUSAO"], errors="coerce").fillna(0)
        df = pd.merge(df, df_taxa, on=["OBRA", "ETAPA"], how="left")
        df["TAXA_CONCLUSAO"] = df["TAXA_CONCLUSAO"].fillna(0)
    else:
        df["TAXA_CONCLUSAO"] = 0

    return df

@st.cache_data(ttl=300)
def load_obras():
    supabase = init_supabase()
    if not supabase:
        return pd.DataFrame()
    res = supabase.table("obras").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

@st.cache_data(ttl=300)
def load_despesas():
    supabase = init_supabase()
    if not supabase:
        return pd.DataFrame()
    try:
        res = supabase.table("c_despesas").select("*").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            # Renomeia para maiúsculas para compatibilidade com relatorio.py
            df.rename(columns={
                "obra": "OBRA", "etapa": "ETAPA", "tipo": "TIPO",
                "fornecedor": "FORNECEDOR", "despesa": "DESPESA",
                "valor_total": "VALOR_TOTAL", "data": "DATA",
                "descricao": "DESCRICAO", "banco": "BANCO",
                "forma": "FORMA", "tem_nota_fiscal": "TEM_NOTA_FISCAL",
            }, inplace=True)
            df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()




@st.cache_data(ttl=300)
def load_categorias():
    supabase = init_supabase()
    if not supabase:
        return [""]
    try:
        res = supabase.table("categorias_despesa").select("nome").order("nome").execute()
        return [""] + [r["nome"] for r in res.data] if res.data else [""]
    except Exception:
        return [""]


@st.cache_data(ttl=300)
def load_etapas():
    supabase = init_supabase()
    if not supabase:
        return []
    try:
        res = supabase.table("etapas").select("nome,ordem").order("ordem").execute()
        return [r["nome"] for r in res.data] if res.data else []
    except Exception:
        return []


@st.cache_data(ttl=300)
def load_tipos_custo():
    supabase = init_supabase()
    if not supabase:
        return []
    try:
        res = supabase.table("tipos_custo").select("nome").order("nome").execute()
        return [r["nome"] for r in res.data] if res.data else []
    except Exception:
        return []


def load_contas_pagar(obra=None):
    sb = init_supabase()
    if not sb:
        return pd.DataFrame()
    try:
        q = sb.table("contas_pagar").select("*").order("vencimento")
        if obra:
            q = q.eq("obra", obra)
        res = q.execute()
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        hoje = datetime.today().date()
        df["vencimento"] = pd.to_datetime(df["vencimento"]).dt.date
        df["status_display"] = df.apply(
            lambda r: "pago" if r["pago"]
                      else ("vencido" if r["vencimento"] < hoje else "pendente"),
            axis=1
        )
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_folha_regras():
    sb = init_supabase()
    if not sb:
        return pd.DataFrame()
    try:
        res = sb.table("folha_regras").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(
            columns=["id", "obra", "servico", "tipo", "valor"])
    except Exception:
        return pd.DataFrame()

def load_folha(obra, quinzena):
    """Retorna (folha_row_dict, df_funcionarios) ou (None, DataFrame vazio)."""
    sb = init_supabase()
    if not sb:
        return None, pd.DataFrame()
    try:
        res = sb.table("folhas").select("*").eq("obra", obra).eq("quinzena", str(quinzena)).execute()
        if not res.data:
            return None, pd.DataFrame()
        folha = res.data[0]
        res2 = sb.table("folha_funcionarios").select("*").eq("folha_id", folha["id"]).execute()
        df = pd.DataFrame(res2.data) if res2.data else pd.DataFrame(
            columns=["id", "folha_id", "nome", "pix", "nome_conta", "servico", "etapa", "diarias", "valor"])
        return folha, df
    except Exception:
        return None, pd.DataFrame()

def load_folhas_by_obra(obra):
    """Retorna lista de dicts de folhas da obra, ordenadas por quinzena desc."""
    sb = init_supabase()
    if not sb:
        return []
    try:
        res = sb.table("folhas").select("*").eq("obra", obra).order("quinzena", desc=True).execute()
        return res.data if res.data else []
    except Exception:
        return []

def load_folha_funcionarios(folha_id):
    """Retorna DataFrame de funcionários de uma folha pelo id."""
    sb = init_supabase()
    if not sb:
        return pd.DataFrame()
    try:
        res = sb.table("folha_funcionarios").select("*").eq("folha_id", folha_id).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(
            columns=["id", "folha_id", "nome", "pix", "nome_conta", "servico", "etapa", "diarias", "valor"])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_formas_pagamento():
    supabase = init_supabase()
    if not supabase:
        return [""]
    try:
        res = supabase.table("formas_pagamento").select("nome").order("nome").execute()
        return [""] + [r["nome"] for r in res.data] if res.data else [""]
    except Exception:
        return [""]


# Template base para todos os gráficos Plotly
CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Inter, sans-serif', color='#374151'),
    margin=dict(t=30, b=30, l=10, r=10),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=12)
    ),
    xaxis=dict(gridcolor='rgba(0,0,0,0.05)', zeroline=False),
    yaxis=dict(gridcolor='rgba(0,0,0,0.05)', zeroline=False),
)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <div class="sidebar-logo"></div>
        <span class="sidebar-title">Financeiro Obras</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**FILTROS**")

# Carrega dados antes dos filtros para preencher as opções
df_raw = load_data()

with st.sidebar:
    if not df_raw.empty:
        obras = sorted(df_raw['OBRA'].dropna().unique().tolist())
        tipos_todos = sorted(df_raw['TIPO_CUSTO'].dropna().unique().tolist())

        sel_obras = st.multiselect("Obra(s)", obras, default=[])

        df_temp_etapas = df_raw[df_raw['OBRA'].isin(sel_obras)]
        etapas_ord = (
            df_temp_etapas.dropna(subset=['ETAPA'])
            .groupby('ETAPA')['ORDEM_ETAPA'].min()
            .sort_values()
            .index.tolist()
        ) if 'ORDEM_ETAPA' in df_temp_etapas.columns else sorted(df_temp_etapas['ETAPA'].dropna().unique().tolist())
        sel_etapas = st.multiselect("Etapa(s)", etapas_ord, default=etapas_ord)

        sel_tipos = st.multiselect("Tipo(s) de Custo", tipos_todos, default=tipos_todos)
    else:
        sel_obras, sel_etapas, sel_tipos = [], [], []

    st.markdown("---")

    # ── Geração de Relatório ──────────────────────────────────────────────────
    st.markdown("**RELATÓRIOS**")

    if not df_raw.empty:
        # Usa load_obras() para incluir obras sem gastos ainda
        _df_obras_rel = load_obras()
        _obras_rel_list = (
            sorted(_df_obras_rel['nome'].dropna().tolist())
            if not _df_obras_rel.empty
            else sorted(df_raw['OBRA'].dropna().unique().tolist())
        )
        obra_rel = st.selectbox(
            "Obra para o relatório",
            _obras_rel_list,
            key="selectbox_relatorio",
        )

        # Lookup obra_info para o timbrado do PDF
        _obra_info = {}
        if not _df_obras_rel.empty:
            _row = _df_obras_rel[_df_obras_rel['nome'] == obra_rel]
            if not _row.empty:
                _obra_info = _row.iloc[0].to_dict()

        if obra_rel == "Administrativo":
            col_di, col_df = st.columns(2)
            with col_di:
                data_ini_adm = st.date_input("De", value=datetime.today().replace(day=1), key="adm_data_ini")
            with col_df:
                data_fim_adm = st.date_input("Até", value=datetime.today(), key="adm_data_fim")

            if st.button("📄 Gerar Relatório PDF"):
                with st.spinner("Gerando PDF…"):
                    from relatorio import gerar_relatorio_administrativo
                    df_desp = load_despesas()
                    df_desp_adm = df_desp[df_desp['OBRA'] == obra_rel].copy() if not df_desp.empty else pd.DataFrame()
                    pdf_bytes = gerar_relatorio_administrativo(df_desp_adm, obra_rel, data_ini_adm, data_fim_adm, obra_info=_obra_info)
                    nome_arquivo = (
                        f"relatorio_administrativo_{data_ini_adm.strftime('%Y%m%d')}"
                        f"_{data_fim_adm.strftime('%Y%m%d')}.pdf"
                    )
                st.download_button(
                    label="⬇️ Baixar PDF",
                    data=pdf_bytes,
                    file_name=nome_arquivo,
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            tipo_rel = st.radio(
                "Tipo de relatório",
                ["Detalhado", "Simples"],
                horizontal=True,
                key="radio_tipo_relatorio",
            )

            # Preview de etapas que entrarão no relatório
            df_preview = df_raw[df_raw['OBRA'] == obra_rel]
            if tipo_rel == "Simples":
                col_filtro = df_preview.groupby('ETAPA')['ORÇAMENTO_ESTIMADO'].sum()
                etapas_preview = col_filtro[col_filtro > 0].index.tolist()
                label_vazio = "⚠️ Nenhuma etapa com orçamento encontrada para esta obra."
            else:
                col_filtro = df_preview.groupby('ETAPA')['GASTO_REALIZADO'].sum()
                etapas_preview = col_filtro[col_filtro > 0].index.tolist()
                label_vazio = "⚠️ Nenhuma etapa com gasto realizado encontrada para esta obra."
            if etapas_preview:
                st.caption(f"✅ {len(etapas_preview)} etapa(s): {', '.join(etapas_preview)}")
            else:
                st.caption(label_vazio)

            if st.button("📄 Gerar Relatório PDF", disabled=not etapas_preview):
                with st.spinner("Gerando PDF…"):
                    from relatorio import gerar_relatorio_detalhado, gerar_relatorio_simples
                    df_desp = load_despesas()
                    df_desp_semana = pd.DataFrame()
                    if not df_desp.empty:
                        hoje = pd.Timestamp.today().normalize()
                        sete_dias = hoje - pd.Timedelta(days=7)
                        df_desp_semana = df_desp[
                            (df_desp['OBRA'] == obra_rel) &
                            (df_desp['DATA'] >= sete_dias)
                        ].copy()
                    if tipo_rel == "Detalhado":
                        pdf_bytes = gerar_relatorio_detalhado(df_raw, obra_rel, df_desp_semana, obra_info=_obra_info)
                    else:
                        pdf_bytes = gerar_relatorio_simples(df_raw, obra_rel, df_desp_semana, obra_info=_obra_info)
                    nome_arquivo = (
                        f"relatorio_{tipo_rel.lower()}_{obra_rel.replace(' ', '_')}_"
                        f"{datetime.now().strftime('%Y%m%d')}.pdf"
                    )
                st.download_button(
                    label="⬇️ Baixar PDF",
                    data=pdf_bytes,
                    file_name=nome_arquivo,
                    mime="application/pdf",
                    use_container_width=True,
                )

    st.markdown("---")
    st.markdown("""
    <div class="status-badge">
        <span class="status-dot"></span> Online · Supabase
    </div>
    """, unsafe_allow_html=True)

# --- CONTEÚDO PRINCIPAL ---
tab_dash, tab_desp, tab_hist, tab_folha, tab_contas, tab_conf = st.tabs(["📊 Dashboard", "📋 Despesas", "🗂️ Histórico", "👥 Folha", "💳 Contas a Pagar", "⚙️ Configurações"])

with tab_dash:
    if df_raw.empty:
        st.warning("Nenhum dado encontrado no Supabase ou as credenciais estão incorretas.")
    elif not sel_obras:
        col_title, col_btn = st.columns([5, 1])
        with col_title:
            st.markdown("""
            <div class="main-header">
                <h1>Financeiro Obras</h1>
                <p>Selecione uma ou mais obras na barra lateral para visualizar os dados.</p>
            </div>
            """, unsafe_allow_html=True)
        with col_btn:
            st.markdown("<div style='padding-top:14px'></div>", unsafe_allow_html=True)
            if st.button("🔄 Atualizar"):
                load_data.clear()
                st.rerun()
    else:
        # Filtro global
        df_filtered = df_raw[
            (df_raw['OBRA'].isin(sel_obras)) &
            (df_raw['ETAPA'].isin(sel_etapas)) &
            (df_raw['TIPO_CUSTO'].isin(sel_tipos))
        ]
        is_adm_only = len(sel_obras) == 1 and sel_obras[0] == "Administrativo"

        # ---- Header ----
        col_title, col_btn = st.columns([5, 1])
        with col_title:
            titulo = "Visão Geral do Portfólio" if len(sel_obras) == len(obras) else "Filtro Específico"
            st.markdown(f"""
            <div class="main-header">
                <h1>{titulo}</h1>
                <p>Acompanhamento consolidado de custos vs orçamentos</p>
            </div>
            """, unsafe_allow_html=True)
        with col_btn:
            st.markdown("<div style='padding-top:14px'></div>", unsafe_allow_html=True)
            if st.button("🔄 Atualizar"):
                load_data.clear()
                st.rerun()

        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

        # ---- KPIs ----
        orcamento_total = df_filtered['ORÇAMENTO_ESTIMADO'].sum()
        gasto_total     = df_filtered['GASTO_REALIZADO'].sum()
        saldo_total     = orcamento_total - gasto_total
        pct_consumo     = (gasto_total / orcamento_total * 100) if orcamento_total > 0 else 0
        if 'TAXA_CONCLUSAO' in df_filtered.columns:
            df_pct = df_filtered.groupby(['OBRA', 'ETAPA'])['TAXA_CONCLUSAO'].first().reset_index()
            pct_realizacao = df_pct['TAXA_CONCLUSAO'].mean()
        else:
            pct_realizacao = 0.0

        uma_obra_sel = len(sel_obras) == 1

        if is_adm_only:
            kpi_l, kpi_adm, kpi_r = st.columns(3)
            with kpi_adm:
                st.metric(label="💸 Custo Realizado", value=format_currency(gasto_total))
        else:
            if uma_obra_sel:
                kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            else:
                kpi1, kpi2, kpi3 = st.columns(3)

            with kpi1:
                st.metric(label="💼 Orçamento Total Estimado", value=format_currency(orcamento_total))
            with kpi2:
                st.metric(label="💸 Custo Realizado", value=format_currency(gasto_total))
            with kpi3:
                delta_color = "normal" if saldo_total >= 0 else "inverse"
                st.metric(
                    label="🏦 Saldo Financeiro",
                    value=format_currency(saldo_total),
                    delta=f"{'+ ' if saldo_total >= 0 else '- '}{format_currency(abs(saldo_total))}",
                    delta_color=delta_color
                )
            if uma_obra_sel:
                with kpi4:
                    st.metric(
                        label="📊 % de Consumo",
                        value=f"{pct_consumo:.1f}%",
                        delta=f"{pct_consumo - 100:.1f}% do orçamento" if pct_consumo > 100 else None,
                        delta_color="inverse"
                    )
                    st.progress(min(pct_consumo / 100, 1.0))
                with kpi5:
                    st.metric(label="🏗️ % de Realização", value=f"{pct_realizacao:.1f}%")
                    st.progress(min(pct_realizacao / 100, 1.0))

        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

        # ---- Detalhamento Financeiro por Obra ----
        st.markdown('<p class="section-header">Detalhamento Financeiro por Obra</p>', unsafe_allow_html=True)

        obras_visiveis = sorted(df_filtered['OBRA'].dropna().unique().tolist())
        uma_obra       = len(obras_visiveis) == 1

        def _render_detalhe_obra(nome_obra):
            tipos_obra = sorted(df_raw[df_raw['OBRA'] == nome_obra]['TIPO_CUSTO'].dropna().unique().tolist())
            sel_tipos_det = st.multiselect(
                "Tipo(s) de Custo",
                tipos_obra,
                default=tipos_obra,
                key=f"tipo_det_{nome_obra}"
            )

            df_obra_det = df_filtered[
                (df_filtered['OBRA'] == nome_obra) &
                (df_filtered['TIPO_CUSTO'].isin(sel_tipos_det))
            ]

            gasto_obra = df_obra_det['GASTO_REALIZADO'].sum()

            if is_adm_only or nome_obra == "Administrativo":
                # Centro de custos: exibe apenas total realizado
                st.markdown(f"""
                <div class="obra-summary" style="margin-bottom:16px; padding:12px 4px; border-bottom:1px solid rgba(0,0,0,0.06);">
                    <div class="obra-badge">
                        <span class="obra-badge-label">Custo Realizado</span>
                        <span class="obra-badge-value">{format_currency(gasto_obra)}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                agg_cols = {'GASTO_REALIZADO': 'sum'}
                if 'ORDEM_ETAPA' in df_obra_det.columns:
                    agg_cols['ORDEM_ETAPA'] = 'min'
                df_tab = df_obra_det.groupby('ETAPA').agg(agg_cols).reset_index().copy()
                if 'ORDEM_ETAPA' in df_tab.columns:
                    df_tab = df_tab.sort_values('ORDEM_ETAPA').drop(columns=['ORDEM_ETAPA'])
                df_tab['GASTO_REALIZADO'] = df_tab['GASTO_REALIZADO'].apply(format_currency)
                df_tab.rename(columns={'ETAPA': 'Etapa', 'GASTO_REALIZADO': 'Custo Realizado'}, inplace=True)
                col_config = {
                    "Etapa":          st.column_config.TextColumn("Etapa",          width="large"),
                    "Custo Realizado":st.column_config.TextColumn("Custo Realizado",width="medium"),
                }
                st.dataframe(df_tab, use_container_width=True, hide_index=True, column_config=col_config)
            else:
                # Obras normais
                orc_obra   = df_obra_det['ORÇAMENTO_ESTIMADO'].sum()
                saldo_obra = orc_obra - gasto_obra
                pct_obra   = (gasto_obra / orc_obra * 100) if orc_obra > 0 else 0
                pct_width  = int(min(pct_obra / 100, 1.0) * 100)
                saldo_class = 'green' if saldo_obra >= 0 else 'red'
                pct_class   = 'over' if pct_obra > 100 else ''

                st.markdown(f"""
                <div class="obra-summary" style="margin-bottom:16px; padding:12px 4px; border-bottom:1px solid rgba(0,0,0,0.06);">
                    <div class="obra-badge">
                        <span class="obra-badge-label">Orçamento</span>
                        <span class="obra-badge-value blue">{format_currency(orc_obra)}</span>
                    </div>
                    <div class="obra-divider"></div>
                    <div class="obra-badge">
                        <span class="obra-badge-label">Realizado</span>
                        <span class="obra-badge-value">{format_currency(gasto_obra)}</span>
                    </div>
                    <div class="obra-divider"></div>
                    <div class="obra-badge">
                        <span class="obra-badge-label">Saldo</span>
                        <span class="obra-badge-value {saldo_class}">{format_currency(saldo_obra)}</span>
                    </div>
                    <div class="obra-divider"></div>
                    <div class="obra-badge">
                        <span class="obra-badge-label">% Consumido</span>
                        <div class="mini-progress-wrap">
                            <div class="mini-progress-bar">
                                <div class="mini-progress-fill {pct_class}" style="width:{pct_width}%"></div>
                            </div>
                            <span class="obra-badge-value" style="color:{'#EF4444' if pct_obra > 100 else '#374151'}">{pct_obra:.1f}%</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                agg_cols = {'ORÇAMENTO_ESTIMADO': 'sum', 'GASTO_REALIZADO': 'sum', 'SALDO_ETAPA': 'sum'}
                if 'ORDEM_ETAPA' in df_obra_det.columns:
                    agg_cols['ORDEM_ETAPA'] = 'min'
                if 'TAXA_CONCLUSAO' in df_obra_det.columns:
                    agg_cols['TAXA_CONCLUSAO'] = 'first'
                df_tab = df_obra_det.groupby('ETAPA').agg(agg_cols).reset_index().copy()
                if 'ORDEM_ETAPA' in df_tab.columns:
                    df_tab = df_tab.sort_values('ORDEM_ETAPA').drop(columns=['ORDEM_ETAPA'])

                df_tab['% Consumido'] = df_tab.apply(
                    lambda r: f"{(r['GASTO_REALIZADO'] / r['ORÇAMENTO_ESTIMADO'] * 100):.1f}%"
                    if r['ORÇAMENTO_ESTIMADO'] > 0 else "0.0%", axis=1
                )
                if 'TAXA_CONCLUSAO' in df_tab.columns:
                    df_tab['% Realização'] = df_tab['TAXA_CONCLUSAO'].apply(lambda v: f"{v:.1f}%")
                    df_tab.drop(columns=['TAXA_CONCLUSAO'], inplace=True)
                for col in ['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']:
                    df_tab[col] = df_tab[col].apply(format_currency)
                df_tab.rename(columns={
                    'ETAPA': 'Etapa',
                    'ORÇAMENTO_ESTIMADO': 'Orçamento Estimado',
                    'GASTO_REALIZADO': 'Gasto Realizado',
                    'SALDO_ETAPA': 'Saldo'
                }, inplace=True)

                col_config = {
                    "Etapa":             st.column_config.TextColumn("Etapa",       width="large"),
                    "Orçamento Estimado":st.column_config.TextColumn("Orçamento",   width="medium"),
                    "Gasto Realizado":   st.column_config.TextColumn("Realizado",   width="medium"),
                    "Saldo":             st.column_config.TextColumn("Saldo",       width="medium"),
                    "% Consumido":       st.column_config.TextColumn("% Consumido", width="small"),
                    "% Realização":      st.column_config.TextColumn("% Realização",width="small"),
                }
                st.dataframe(df_tab, use_container_width=True, hide_index=True, column_config=col_config)

        if uma_obra:
            _render_detalhe_obra(obras_visiveis[0])
        else:
            for nome_obra in obras_visiveis:
                with st.expander(f"🏗️  {nome_obra}", expanded=False):
                    _render_detalhe_obra(nome_obra)

        if not is_adm_only:
            st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

        # ---- Gráfico Comparativo Full Width ----
        if not is_adm_only:
            st.markdown('<p class="section-header">Comparativo — Orçamento · Gasto · Saldo</p>', unsafe_allow_html=True)

        if not is_adm_only:
            label_key = 'ETAPA' if len(sel_obras) == 1 else 'OBRA'
            df_ranking = df_filtered.groupby(label_key)[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']].sum().reset_index()
            df_ranking = df_ranking.sort_values(by='ORÇAMENTO_ESTIMADO', ascending=True)

            colors_saldo = ['#EF4444' if val < 0 else '#10B981' for val in df_ranking['SALDO_ETAPA']]

            fig_rank = go.Figure()
            fig_rank.add_trace(go.Bar(
                y=df_ranking[label_key], x=df_ranking['ORÇAMENTO_ESTIMADO'],
                name='Orçamento Estimado', orientation='h',
                marker=dict(color='#D1D5DB', line=dict(width=0)),
                hovertemplate='<b>%{y}</b><br>Orçamento: R$ %{x:,.2f}<extra></extra>'
            ))
            fig_rank.add_trace(go.Bar(
                y=df_ranking[label_key], x=df_ranking['GASTO_REALIZADO'],
                name='Gasto Realizado', orientation='h',
                marker=dict(color='#8B5CF6', line=dict(width=0)),
                hovertemplate='<b>%{y}</b><br>Realizado: R$ %{x:,.2f}<extra></extra>'
            ))
            fig_rank.add_trace(go.Bar(
                y=df_ranking[label_key], x=df_ranking['SALDO_ETAPA'],
                name='Saldo', orientation='h',
                marker=dict(color=colors_saldo, line=dict(width=0)),
                hovertemplate='<b>%{y}</b><br>Saldo: R$ %{x:,.2f}<extra></extra>'
            ))
            fig_rank.update_layout(
                barmode='group',
                height=max(350, len(df_ranking) * 70),
                bargap=0.2,
                bargroupgap=0.05,
                **CHART_LAYOUT
            )
            st.plotly_chart(fig_rank, use_container_width=True)


@st.fragment
def _render_historico(sel_obras, sel_etapas):
    st.markdown("""
    <div class="main-header">
        <h1>Histórico de Despesas</h1>
        <p>Consulte e corrija despesas registradas.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    df_hist = load_despesas()
    if df_hist.empty:
        st.info("Nenhuma despesa registrada ainda.")
        return

    df_view = df_hist.copy()
    if sel_obras:
        df_view = df_view[df_view['OBRA'].isin(sel_obras)]
    if sel_etapas:
        df_view = df_view[df_view['ETAPA'].isin(sel_etapas)]

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        data_ini_hist = st.date_input("De", value=datetime.today().replace(day=1), key="hist_ini")
    with col_d2:
        data_fim_hist = st.date_input("Até", value=datetime.today(), key="hist_fim")
    with col_d3:
        tipo_hist = st.selectbox("Tipo", ["Todos"] + load_tipos_custo(), key="hist_tipo")

    if tipo_hist != "Todos":
        df_view = df_view[df_view['TIPO'] == tipo_hist]
    df_view = df_view[
        (df_view['DATA'] >= pd.Timestamp(data_ini_hist)) &
        (df_view['DATA'] <= pd.Timestamp(data_fim_hist))
    ].sort_values('DATA', ascending=False)

    total_hist = df_view['VALOR_TOTAL'].sum() if 'VALOR_TOTAL' in df_view.columns else 0
    st.metric("Total no período", format_currency(total_hist))

    if df_view.empty:
        st.info("Nenhuma despesa no período selecionado.")
        return

    _COL_MAP = {
        'DATA': 'data', 'OBRA': 'obra', 'ETAPA': 'etapa', 'TIPO': 'tipo',
        'DESPESA': 'despesa', 'FORNECEDOR': 'fornecedor',
        'DESCRICAO': 'descricao', 'VALOR_TOTAL': 'valor_total',
        'FORMA': 'forma', 'BANCO': 'banco',
    }
    cols_editor = [c for c in ['id'] + list(_COL_MAP.keys()) if c in df_view.columns]
    df_editor = df_view[cols_editor].copy().reset_index(drop=True)

    _cats_opts   = load_categorias()
    _formas_opts = load_formas_pagamento()
    _obras_df    = load_obras()
    _obras_opts  = _obras_df['nome'].tolist() if not _obras_df.empty else []
    _etapas_opts = load_etapas()
    _tipos_opts  = load_tipos_custo()

    st.data_editor(
        df_editor,
        column_config={
            "id":          st.column_config.TextColumn("id", disabled=True),
            "OBRA":        st.column_config.SelectboxColumn("Obra", options=_obras_opts),
            "ETAPA":       st.column_config.SelectboxColumn("Etapa", options=_etapas_opts),
            "TIPO":        st.column_config.SelectboxColumn("Tipo", options=_tipos_opts),
            "DATA":        st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "VALOR_TOTAL": st.column_config.NumberColumn("Valor (R$)", min_value=0, format="R$ %.2f"),
            "DESPESA":     st.column_config.SelectboxColumn("Despesa", options=_cats_opts),
            "FORNECEDOR":  st.column_config.TextColumn("Fornecedor"),
            "DESCRICAO":   st.column_config.TextColumn("Descrição"),
            "FORMA":       st.column_config.SelectboxColumn("Forma Pgto", options=_formas_opts),
            "BANCO":       st.column_config.TextColumn("Banco"),
        },
        column_order=[c for c in cols_editor if c != 'id'],
        use_container_width=True,
        hide_index=True,
        height=600,
        key="editor_desp_hist",
    )

    col_save, col_csv = st.columns([1, 2])
    with col_save:
        if st.button("💾 Salvar alterações", type="primary", use_container_width=True):
            changes = st.session_state.get("editor_desp_hist", {}).get("edited_rows", {})
            if not changes:
                st.info("Nenhuma alteração detectada.")
            else:
                _sb_edit = init_supabase()
                erros_edit = []
                for idx, vals in changes.items():
                    row_id = df_editor.iloc[idx]["id"]
                    payload = {
                        _COL_MAP[k]: (v.isoformat() if hasattr(v, 'isoformat') else v)
                        for k, v in vals.items() if k in _COL_MAP
                    }
                    try:
                        _sb_edit.table("c_despesas").update(payload).eq("id", row_id).execute()
                    except Exception as e_upd:
                        erros_edit.append(str(e_upd))
                if erros_edit:
                    st.error("Erros: " + "; ".join(erros_edit))
                else:
                    load_despesas.clear()
                    st.success(f"{len(changes)} despesa(s) atualizada(s)!")
                    st.rerun(scope="fragment")

    with col_csv:
        csv_data = df_view.to_csv(index=False).encode('utf-8')
        st.download_button(
            "⬇️ Exportar CSV",
            csv_data,
            f"despesas_{data_ini_hist.strftime('%Y%m%d')}_{data_fim_hist.strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True,
        )


@st.fragment
def _render_despesas(df_raw):
    st.markdown("""
    <div class="main-header">
        <h1>Cadastro de Despesas</h1>
        <p>Registre uma nova despesa diretamente no banco de dados.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    if df_raw.empty:
        st.warning("Sem conexão com o banco de dados.")
        return

    df_obras_ref = load_obras()
    obras_list = sorted(df_obras_ref['nome'].dropna().tolist()) if not df_obras_ref.empty else sorted(df_raw['OBRA'].dropna().unique().tolist())

    st.markdown('<p class="section-header">Nova Despesa</p>', unsafe_allow_html=True)

    modo = st.radio("Modo de cadastro", ["📝 Individual", "📦 Lote (IA)", "🧾 Folha de Pagamento"],
                    horizontal=True, key="cad_modo")

    # ══════════════════════════════════════════════════════════════════════════
    # MODO INDIVIDUAL
    # ══════════════════════════════════════════════════════════════════════════
    if modo == "📝 Individual":
        col_obra, col_nota, _ = st.columns([1, 1, 1])
        with col_obra:
            obra_form = st.selectbox("Obra *", obras_list, key="cad_obra")
        with col_nota:
            tem_nota = st.checkbox("📄 Tem nota fiscal?", key="cad_tem_nota")

        etapas_obra_form = load_etapas()

        upload_key = f"cad_comprovante_{st.session_state.get('cad_upload_key', 0)}"
        col_file, col_ia = st.columns([3, 1])
        with col_file:
            comprovante_form = st.file_uploader(
                "Nota Fiscal" + (" *" if tem_nota else ""),
                type=["pdf", "jpg", "jpeg", "png"],
                help="Anexe a nota fiscal da despesa",
                key=upload_key,
                disabled=not tem_nota,
            )
        with col_ia:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🤖 Extrair com IA", disabled=(not tem_nota or comprovante_form is None), use_container_width=True):
                with st.spinner("Analisando nota fiscal com IA..."):
                    try:
                        resultado = _extrair_com_ia(comprovante_form.getvalue(), comprovante_form.type)
                        st.session_state['ia_resultado'] = resultado
                        st.success("✅ Dados extraídos! Revise os campos abaixo.")
                    except Exception as e_ia:
                        st.error(f"Erro na extração: {e_ia}")

        ia = st.session_state.get('ia_resultado') or {}
        if ia:
            st.info("🤖 Campos pré-preenchidos pela IA — revise antes de cadastrar.")

        _tipos    = load_tipos_custo()
        _formas   = load_formas_pagamento()
        _despesas = load_categorias()

        ia_tipo_idx    = _tipos.index(ia['TIPO'])    if ia.get('TIPO')    in _tipos    else 0
        ia_forma_idx   = _formas.index(ia['FORMA'])  if ia.get('FORMA')   in _formas   else 0
        ia_despesa_idx = _despesas.index(ia['DESPESA']) if ia.get('DESPESA') in _despesas else 0
        ia_data = None
        if ia.get('DATA'):
            try:
                ia_data = datetime.strptime(ia['DATA'], '%Y-%m-%d').date()
            except Exception:
                pass
        ia_valor      = float(ia['VALOR_TOTAL']) if ia.get('VALOR_TOTAL') else 0.0
        ia_fornecedor = str(ia.get('FORNECEDOR') or '')
        ia_descricao  = str(ia.get('DESCRICAO') or '')

        _draft_fornecedor = st.session_state.pop('_draft_fornecedor', None)
        _draft_descricao  = st.session_state.pop('_draft_descricao', None)
        _draft_banco      = st.session_state.pop('_draft_banco', None)
        fornecedor_init   = _draft_fornecedor if _draft_fornecedor is not None else ia_fornecedor
        descricao_init    = _draft_descricao  if _draft_descricao  is not None else ia_descricao
        banco_init        = _draft_banco      if _draft_banco       is not None else ''

        with st.form("form_despesa", clear_on_submit=False):
            st.caption("Campos obrigatórios *")
            col1, col2, col3 = st.columns(3)
            with col1:
                etapa_form = st.selectbox("Etapa *", etapas_obra_form)
            with col2:
                tipo_form = st.selectbox("Tipo *", _tipos, index=ia_tipo_idx)
            with col3:
                data_form = st.date_input("Data *", value=ia_data or datetime.today())

            col4, col5, col6 = st.columns([2, 1, 1])
            with col4:
                fornecedor_form = st.text_input("Fornecedor *", value=fornecedor_init)
            with col5:
                valor_form = st.number_input("Valor Total (R$) *", min_value=0.0, value=ia_valor, step=0.01, format="%.2f")
            with col6:
                despesa_form = st.selectbox("Despesa", _despesas, index=ia_despesa_idx)

            descricao_form = st.text_area("Descrição *", value=descricao_init, max_chars=500, placeholder="Descrição detalhada da despesa...")

            st.caption("Campos opcionais")
            col7, col8 = st.columns(2)
            with col7:
                banco_form = st.text_input("Banco", value=banco_init)
            with col8:
                forma_form = st.selectbox("Forma Pagamento", _formas, index=ia_forma_idx)

            submitted = st.form_submit_button("✅ Cadastrar Despesa", use_container_width=True, type="primary")

        if submitted:
            erros = []
            if not fornecedor_form.strip():
                erros.append("Fornecedor é obrigatório.")
            if valor_form <= 0:
                erros.append("Valor Total deve ser maior que zero.")
            if not descricao_form.strip():
                erros.append("Descrição é obrigatória.")
            if not etapas_obra_form:
                erros.append("Nenhuma etapa encontrada para esta obra.")
            if tem_nota and comprovante_form is None:
                erros.append("Nota fiscal marcada mas nenhum arquivo foi anexado.")
            if erros:
                for e in erros:
                    st.error(e)
            else:
                supabase = init_supabase()
                comprovante_url = None
                if comprovante_form is not None:
                    try:
                        ext = comprovante_form.name.rsplit('.', 1)[-1].lower()
                        def _slug(s): return str(s).strip().replace(' ', '_')[:30]
                        valor_slug = f"R${valor_form:.2f}".replace('.', ',')
                        nome_arq = (
                            f"{data_form.strftime('%Y-%m-%d')}"
                            f"_{_slug(obra_form)}"
                            f"_{_slug(etapa_form)}"
                            f"_{_slug(fornecedor_form)}"
                            f"_{valor_slug}"
                            f"_{datetime.now().strftime('%H%M%S')}.{ext}"
                        )
                        supabase.storage.from_("comprovantes").upload(
                            nome_arq,
                            comprovante_form.getvalue(),
                            {"content-type": comprovante_form.type}
                        )
                        _sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
                        comprovante_url = f"{_sb_url}/storage/v1/object/public/comprovantes/{nome_arq}"
                    except Exception as e_storage:
                        st.warning(f"Nota fiscal não pôde ser salva: {e_storage}")
                if fornecedor_form.strip():
                    supabase.table("fornecedores").upsert(
                        {"nome": fornecedor_form.strip()}, on_conflict="nome"
                    ).execute()
                record = {
                    "obra":            obra_form,
                    "etapa":           etapa_form,
                    "tipo":            tipo_form,
                    "fornecedor":      fornecedor_form.strip() or None,
                    "valor_total":     float(valor_form),
                    "data":            data_form.strftime('%Y-%m-%d'),
                    "descricao":       descricao_form.strip() or None,
                    "despesa":         despesa_form or None,
                    "banco":           banco_form.strip() or None,
                    "forma":           forma_form or None,
                    "tem_nota_fiscal": tem_nota,
                    "comprovante_url": comprovante_url,
                }
                try:
                    supabase.table("c_despesas").insert(record).execute()
                    load_despesas.clear()
                    st.session_state.pop('ia_resultado', None)
                    st.session_state['cad_upload_key'] = st.session_state.get('cad_upload_key', 0) + 1
                    st.success("✅ Despesa cadastrada com sucesso!")
                    st.rerun(scope="fragment")
                except Exception as e_ins:
                    st.session_state['_draft_fornecedor'] = fornecedor_form
                    st.session_state['_draft_descricao']  = descricao_form
                    st.session_state['_draft_banco']      = banco_form
                    st.error(f"Erro ao cadastrar: {e_ins}")

    # ══════════════════════════════════════════════════════════════════════════
    # MODO LOTE (IA)
    # ══════════════════════════════════════════════════════════════════════════
    elif modo == "📦 Lote (IA)":
        st.info("Selecione a obra e etapa comuns ao lote, depois envie as notas fiscais.")

        col_lo, col_le = st.columns(2)
        with col_lo:
            obra_lote  = st.selectbox("Obra (todo o lote) *", obras_list, key="lote_obra")
        with col_le:
            etapa_lote = st.selectbox("Etapa (todo o lote) *", load_etapas(), key="lote_etapa")

        arquivos_lote = st.file_uploader(
            "Notas fiscais",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="lote_arquivos",
        )
        st.caption(f"{len(arquivos_lote)} arquivo(s) selecionado(s)")

        if st.button("🤖 Extrair todas com IA",
                     disabled=(not arquivos_lote),
                     type="primary", key="btn_lote_ia"):
            barra = st.progress(0, text="Iniciando extração...")
            resultados_lote = []
            for i, f in enumerate(arquivos_lote):
                barra.progress((i) / len(arquivos_lote),
                               text=f"Extraindo {i+1}/{len(arquivos_lote)}: {f.name}")
                try:
                    r = _extrair_com_ia(f.getvalue(), f.type)
                except Exception:
                    r = {}
                r['_file_name']  = f.name
                r['_file_bytes'] = f.getvalue()
                r['_file_type']  = f.type
                resultados_lote.append(r)
            barra.progress(1.0, text="Extração concluída!")
            st.session_state['batch_results']  = resultados_lote
            st.session_state['batch_obra']     = obra_lote
            st.session_state['batch_etapa']    = etapa_lote
            st.success(f"✅ {len(resultados_lote)} nota(s) extraída(s). Revise a tabela abaixo.")

        # ── Tabela de revisão ──────────────────────────────────────────────────
        batch = st.session_state.get('batch_results', [])
        if batch:
            _obra_orig  = st.session_state.get('batch_obra',  obra_lote)
            _etapa_orig = st.session_state.get('batch_etapa', etapa_lote)

            _tipos_b    = load_tipos_custo()
            _formas_b   = load_formas_pagamento()
            _despesas_b = load_categorias()
            _obras_b    = load_obras()['nome'].tolist() if not load_obras().empty else obras_list
            _etapas_b   = load_etapas()

            df_batch = pd.DataFrame([{
                'OBRA':        r.get('OBRA',        _obra_orig),
                'ETAPA':       r.get('ETAPA',       _etapa_orig),
                'TIPO':        r.get('TIPO',        ''),
                'DATA':        r.get('DATA',        None),
                'DESPESA':     r.get('DESPESA',     ''),
                'FORNECEDOR':  r.get('FORNECEDOR',  ''),
                'DESCRICAO':   r.get('DESCRICAO',   ''),
                'VALOR_TOTAL': float(r.get('VALOR_TOTAL') or 0),
                'FORMA':       r.get('FORMA',       ''),
                'BANCO':       r.get('BANCO',       ''),
            } for r in batch])

            df_batch['OBRA']  = df_batch['OBRA'].fillna(_obra_orig)
            df_batch['ETAPA'] = df_batch['ETAPA'].fillna(_etapa_orig)
            df_batch['DATA']  = pd.to_datetime(df_batch['DATA'], errors='coerce').dt.date

            st.markdown("#### Revisão do lote — edite antes de cadastrar")
            edited_batch = st.data_editor(
                df_batch,
                column_config={
                    'OBRA':        st.column_config.SelectboxColumn("Obra",       options=_obras_b),
                    'ETAPA':       st.column_config.SelectboxColumn("Etapa",      options=_etapas_b),
                    'TIPO':        st.column_config.SelectboxColumn("Tipo",       options=_tipos_b),
                    'DATA':        st.column_config.DateColumn("Data",            format="DD/MM/YYYY"),
                    'DESPESA':     st.column_config.SelectboxColumn("Despesa",    options=_despesas_b),
                    'FORNECEDOR':  st.column_config.TextColumn("Fornecedor"),
                    'DESCRICAO':   st.column_config.TextColumn("Descrição"),
                    'VALOR_TOTAL': st.column_config.NumberColumn("Valor (R$)",   min_value=0, format="R$ %.2f"),
                    'FORMA':       st.column_config.SelectboxColumn("Forma Pgto", options=_formas_b),
                    'BANCO':       st.column_config.TextColumn("Banco"),
                },
                use_container_width=True,
                hide_index=True,
                key="editor_batch",
            )

            col_salvar, col_limpar = st.columns([2, 1])
            with col_salvar:
                if st.button("✅ Cadastrar todas", type="primary",
                             use_container_width=True, key="btn_lote_save"):
                    sb = init_supabase()
                    ok_lote, erros_lote = 0, []
                    for i, row in edited_batch.iterrows():
                        orig = batch[i]
                        try:
                            comp_url = None
                            if orig.get('_file_bytes'):
                                try:
                                    ext_l = orig['_file_name'].rsplit('.', 1)[-1].lower()
                                    _sl = lambda s: str(s).strip().replace(' ', '_')[:20]
                                    nome_l = (
                                        f"{row['DATA']}_{_sl(row['OBRA'])}"
                                        f"_{_sl(row['FORNECEDOR'] or 'sem_forn')}"
                                        f"_{i}_{datetime.now().strftime('%H%M%S')}.{ext_l}"
                                    )
                                    sb.storage.from_("comprovantes").upload(
                                        nome_l, orig['_file_bytes'],
                                        {"content-type": orig['_file_type']}
                                    )
                                    _sb_url_l = os.environ.get("SUPABASE_URL", "").rstrip("/")
                                    comp_url = f"{_sb_url_l}/storage/v1/object/public/comprovantes/{nome_l}"
                                except Exception:
                                    pass

                            rec = {
                                "obra":            row['OBRA'],
                                "etapa":           row['ETAPA'],
                                "tipo":            row['TIPO']       or None,
                                "data":            str(row['DATA'])  if row['DATA'] else None,
                                "despesa":         row['DESPESA']    or None,
                                "fornecedor":      row['FORNECEDOR'] or None,
                                "descricao":       row['DESCRICAO']  or None,
                                "valor_total":     float(row['VALOR_TOTAL']),
                                "forma":           row['FORMA']      or None,
                                "banco":           row['BANCO']      or None,
                                "tem_nota_fiscal": True,
                                "comprovante_url": comp_url,
                            }
                            if row['FORNECEDOR']:
                                sb.table("fornecedores").upsert(
                                    {"nome": str(row['FORNECEDOR'])}, on_conflict="nome"
                                ).execute()
                            sb.table("c_despesas").insert(rec).execute()
                            ok_lote += 1
                        except Exception as e_lote:
                            erros_lote.append(f"Linha {i+1} ({orig.get('_file_name','')}): {e_lote}")

                    load_despesas.clear()
                    st.session_state.pop('batch_results', None)
                    for msg in erros_lote:
                        st.error(msg)
                    st.success(f"✅ {ok_lote}/{len(edited_batch)} despesas cadastradas!")
                    st.rerun(scope="fragment")

            with col_limpar:
                if st.button("🗑️ Limpar lote", use_container_width=True, key="btn_lote_clear"):
                    st.session_state.pop('batch_results', None)
                    st.rerun(scope="fragment")

    # ══════════════════════════════════════════════════════════════════════════
    # MODO FOLHA DE PAGAMENTO
    # ══════════════════════════════════════════════════════════════════════════
    elif modo == "🧾 Folha de Pagamento":
        st.info("Distribua o valor da folha por etapa. Cada etapa com valor > 0 gera um registro separado.")

        col_fo, col_fd = st.columns(2)
        with col_fo:
            obra_folha = st.selectbox("Obra *", obras_list, key="folha_obra")
        with col_fd:
            data_folha = st.date_input("Data da quinzena *", value=datetime.today(), key="folha_data")

        # ── Tabela de distribuição por etapa ──────────────────────────────────
        etapas_folha = load_etapas()
        st.markdown("#### Distribuição por etapa")

        etapas_selecionadas = st.multiselect(
            "Selecione as etapas com trabalhadores nesta quinzena",
            options=etapas_folha,
            key="folha_etapas_sel",
        )

        _valores_etapa = {}
        _total_folha = 0.0
        if etapas_selecionadas:
            st.caption("Informe o valor de cada etapa:")
            for etapa in etapas_selecionadas:
                _val = st.number_input(
                    etapa, min_value=0.0, value=0.0,
                    step=0.01, format="%.2f", key=f"folha_val_{etapa}"
                )
                _valores_etapa[etapa] = _val
            _total_folha = sum(_valores_etapa.values())
            st.metric("Total da folha", f"R$ {_total_folha:,.2f}")

        st.markdown("---")

        # ── Comprovantes e opções finais ──────────────────────────────────────
        comprovantes_folha = st.file_uploader(
            "Comprovantes dos funcionários (PIX, recibos...)",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="folha_arquivos",
        )
        st.caption(f"{len(comprovantes_folha)} comprovante(s) selecionado(s)")

        with st.form("form_folha", clear_on_submit=False):
            forma_folha = st.selectbox("Forma de pagamento", load_formas_pagamento(), key="folha_forma")
            desc_folha  = st.text_area(
                "Descrição",
                value=f"Folha de pagamento quinzenal — {data_folha.strftime('%d/%m/%Y')}",
                max_chars=500,
            )
            submitted_folha = st.form_submit_button("✅ Registrar Folha", type="primary", use_container_width=True)

        if submitted_folha:
            etapas_preenchidas = {e: v for e, v in _valores_etapa.items() if v > 0}
            erros_f = []
            if not etapas_preenchidas:
                erros_f.append("Informe o valor de ao menos uma etapa.")
            if not comprovantes_folha:
                erros_f.append("Anexe ao menos um comprovante.")
            if erros_f:
                for e in erros_f:
                    st.error(e)
            else:
                sb_f    = init_supabase()
                _sb_url_f = os.environ.get("SUPABASE_URL", "").rstrip("/")

                # 1. Faz upload de todos os comprovantes uma única vez
                urls_comp = []
                erros_comp = []
                for i, comp in enumerate(comprovantes_folha):
                    try:
                        ext_f = comp.name.rsplit('.', 1)[-1].lower()
                        nome_comp = (
                            f"folha_{data_folha.strftime('%Y-%m-%d')}"
                            f"_{obra_folha[:20].replace(' ', '_')}"
                            f"_{i}_{datetime.now().strftime('%H%M%S')}.{ext_f}"
                        )
                        sb_f.storage.from_("comprovantes").upload(
                            nome_comp, comp.getvalue(),
                            {"content-type": comp.type}
                        )
                        urls_comp.append((nome_comp, comp.name,
                            f"{_sb_url_f}/storage/v1/object/public/comprovantes/{nome_comp}"))
                    except Exception as e_comp:
                        erros_comp.append(f"{comp.name}: {e_comp}")

                # 2. Cria um registro em c_despesas por etapa preenchida
                ids_inseridos = []
                try:
                    for etapa, valor in etapas_preenchidas.items():
                        rec_f = {
                            "obra":            obra_folha,
                            "etapa":           etapa,
                            "tipo":            "Mão de Obra",
                            "data":            data_folha.strftime('%Y-%m-%d'),
                            "despesa":         "SALÁRIO PESSOAL",
                            "fornecedor":      None,
                            "descricao":       desc_folha.strip() or f"Folha quinzenal — {etapa}",
                            "valor_total":     float(valor),
                            "forma":           forma_folha or None,
                            "banco":           None,
                            "tem_nota_fiscal": True,
                            "comprovante_url": None,
                        }
                        res_f = sb_f.table("c_despesas").insert(rec_f).execute()
                        ids_inseridos.append(res_f.data[0]['id'])

                    # 3. Vincula todos os comprovantes a todos os registros criados
                    for despesa_id in ids_inseridos:
                        for nome_comp, nome_orig, url_comp in urls_comp:
                            sb_f.table("comprovantes_despesa").insert({
                                "despesa_id":   despesa_id,
                                "url":          url_comp,
                                "nome_arquivo": nome_orig,
                            }).execute()

                    load_despesas.clear()
                    for msg in erros_comp:
                        st.warning(f"Comprovante não salvo — {msg}")
                    n_ok = len(comprovantes_folha) - len(erros_comp)
                    st.success(
                        f"✅ Folha registrada em {len(ids_inseridos)} etapa(s) — "
                        f"{n_ok}/{len(comprovantes_folha)} comprovantes salvos. "
                        f"Total: R$ {_total_folha:,.2f}"
                    )
                    st.rerun(scope="fragment")
                except Exception as e_folha:
                    st.error(f"Erro ao registrar folha: {e_folha}")

with tab_desp:
    _render_despesas(df_raw)

with tab_hist:
    _render_historico(sel_obras, sel_etapas)

# ── Funções auxiliares da Folha ────────────────────────────────────────────────

def _salvar_folha(folha, edited, calcular_valor_fn, col_map):
    sb = init_supabase()
    changes     = st.session_state.get("editor_folha", {})
    added       = changes.get("added_rows", [])
    edited_rows = changes.get("edited_rows", {})
    deleted     = changes.get("deleted_rows", [])
    erros = []

    for row in added:
        diarias = row.get("DIÁRIAS", 0)
        servico = row.get("SERVIÇO", "")
        valor   = calcular_valor_fn(servico, diarias)
        rec = {col_map[k]: v for k, v in row.items() if k in col_map and k != "VALOR"}
        rec["valor"]    = valor
        rec["folha_id"] = folha["id"]
        try:
            sb.table("folha_funcionarios").insert(rec).execute()
        except Exception as e:
            erros.append(str(e))

    for idx, vals in edited_rows.items():
        row_id  = edited.iloc[idx]["id"]
        diarias = vals.get("DIÁRIAS", edited.iloc[idx].get("DIÁRIAS", 0))
        servico = vals.get("SERVIÇO", edited.iloc[idx].get("SERVIÇO", ""))
        payload = {col_map[k]: v for k, v in vals.items() if k in col_map and k != "VALOR"}
        payload["valor"] = calcular_valor_fn(servico, diarias)
        try:
            sb.table("folha_funcionarios").update(payload).eq("id", int(row_id)).execute()
        except Exception as e:
            erros.append(str(e))

    for idx in deleted:
        row_id = edited.iloc[idx]["id"]
        try:
            sb.table("folha_funcionarios").delete().eq("id", int(row_id)).execute()
        except Exception as e:
            erros.append(str(e))

    if erros:
        st.error("Erros ao salvar: " + "; ".join(erros))
    else:
        st.success("✅ Folha salva!")
        st.rerun(scope="fragment")


def _gerar_mensagem(obra, quinzena, df, total):
    # Agrupa por PIX somando valores — trabalhador com diárias + empreitada aparece uma só vez
    grupos = {}
    for _, row in df.iterrows():
        pix   = row.get("PIX") or "—"
        nome  = row.get("NOME") or "—"
        conta = row.get("NOME DA CONTA") or "—"
        valor = float(row.get("VALOR") or 0)
        if pix not in grupos:
            grupos[pix] = {"nome": nome, "conta": conta, "valor": 0.0}
        grupos[pix]["valor"] += valor

    linhas = ["📋 FOLHA DE PAGAMENTO", f"Obra: {obra}",
              f"Quinzena: {quinzena.strftime('%d/%m/%Y')}", ""]
    for i, (pix, dados) in enumerate(grupos.items()):
        linhas.append(f"{i+1}. {dados['nome']}")
        linhas.append(f"   PIX: {pix}")
        linhas.append(f"   Conta: {dados['conta']}")
        linhas.append(f"   Valor: R$ {dados['valor']:,.2f}")
        linhas.append("")
    linhas.append(f"TOTAL: R$ {total:,.2f}")
    return "\n".join(linhas)


def _fechar_folha(folha, df, obra, quinzena, comprovantes=None):
    sb = init_supabase()
    etapas_vals = df.groupby("ETAPA")["VALOR"].sum().to_dict()
    erros = []
    despesa_ids = []
    for etapa, valor in etapas_vals.items():
        if not etapa or valor <= 0:
            continue
        try:
            res_ins = sb.table("c_despesas").insert({
                "obra":            obra,
                "etapa":           etapa,
                "tipo":            "Mão de Obra",
                "data":            str(quinzena),
                "despesa":         "SALÁRIO PESSOAL",
                "descricao":       f"Folha quinzenal — {quinzena.strftime('%d/%m/%Y')}",
                "valor_total":     float(valor),
                "tem_nota_fiscal": False,
                "folha_id":        folha["id"],
            }).execute()
            if res_ins.data:
                despesa_ids.append(res_ins.data[0]["id"])
        except Exception as e:
            erros.append(f"{etapa}: {e}")

    if erros:
        st.error("Erros ao gerar despesas: " + "; ".join(erros))
        return

    # Upload comprovantes para todos os registros gerados
    if comprovantes and despesa_ids:
        bucket = "comprovantes"
        for comp in comprovantes:
            try:
                path = (f"folha_{quinzena.strftime('%Y-%m-%d')}"
                        f"_{obra[:20].replace(' ', '_')}"
                        f"_{comp.name}")
                sb.storage.from_(bucket).upload(path, comp.getvalue(),
                    file_options={"content-type": comp.type, "upsert": "true"})
                url = sb.storage.from_(bucket).get_public_url(path)
                for did in despesa_ids:
                    sb.table("comprovantes_despesa").insert({
                        "despesa_id":   did,
                        "url":          url,
                        "nome_arquivo": comp.name,
                    }).execute()
            except Exception as e_up:
                st.warning(f"Comprovante '{comp.name}' não salvo: {e_up}")

    sb.table("folhas").update({"status": "fechada"}).eq("id", folha["id"]).execute()
    load_despesas.clear()
    st.success(f"✅ Folha fechada! {len(despesa_ids)} lançamento(s) em c_despesas."
               + (f" {len(comprovantes)} comprovante(s) enviado(s)." if comprovantes else ""))
    st.rerun(scope="fragment")


@st.fragment
def _render_folha():
    st.markdown("""
    <div class="main-header">
        <h1>Folha de Pagamento</h1>
        <p>Gerencie a folha quinzenal por obra.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    _STATUS_COLOR = {"rascunho": "🟡", "enviada": "🔵", "fechada": "🟢"}

    obras_list = sorted(load_obras()["nome"].dropna().tolist()) if not load_obras().empty else []
    col_o, col_n = st.columns([3, 1])
    with col_o:
        obra_f = st.selectbox("Obra", obras_list, key="folha_obra_sel")
    with col_n:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Nova folha", key="btn_nova_folha", use_container_width=True):
            st.session_state["folha_criar_modo"] = True

    # Modo criação de nova folha
    if st.session_state.get("folha_criar_modo"):
        nova_data = st.date_input("Data da quinzena", value=datetime.today(), key="folha_nova_data")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Criar", key="btn_criar_confirm", type="primary"):
                sb = init_supabase()
                try:
                    sb.table("folhas").insert({"obra": obra_f, "quinzena": str(nova_data)}).execute()
                    st.session_state.pop("folha_criar_modo", None)
                    st.rerun(scope="fragment")
                except Exception as e_cf:
                    st.error(f"Erro: {e_cf}")
        with c2:
            if st.button("❌ Cancelar", key="btn_criar_cancel"):
                st.session_state.pop("folha_criar_modo", None)
                st.rerun(scope="fragment")
        return

    folhas_obra = load_folhas_by_obra(obra_f)
    if not folhas_obra:
        st.info("Nenhuma folha cadastrada para esta obra.")
        return

    opcoes_label = {
        f"{f['quinzena']}  {_STATUS_COLOR.get(f['status'], '⚪')} {f['status'].upper()}": f
        for f in folhas_obra
    }
    sel_label = st.selectbox("Quinzena", list(opcoes_label.keys()), key="folha_sel")
    folha = opcoes_label[sel_label]

    df_func = load_folha_funcionarios(folha["id"])
    quinzena_f = (datetime.strptime(folha["quinzena"], "%Y-%m-%d").date()
                  if isinstance(folha["quinzena"], str) else folha["quinzena"])

    st.markdown(f"**Status:** {_STATUS_COLOR.get(folha['status'], '⚪')} `{folha['status'].upper()}`")

    # Regras da obra
    df_regras  = load_folha_regras()
    regras_obra = (df_regras[df_regras["obra"] == obra_f].set_index("servico")
                   if not df_regras.empty else pd.DataFrame())

    def _calc(servico, diarias):
        if regras_obra.empty or servico not in regras_obra.index:
            return 0.0
        r = regras_obra.loc[servico]
        return float(r["valor"]) if r["tipo"] == "fixo" else float(r["valor"]) * float(diarias or 0)

    _COL_MAP_F = {
        "NOME": "nome", "PIX": "pix", "NOME DA CONTA": "nome_conta",
        "SERVIÇO": "servico", "ETAPA": "etapa", "DIÁRIAS": "diarias", "VALOR": "valor",
    }
    etapas_opts = load_etapas()

    if not df_func.empty:
        df_view = df_func.rename(columns={v: k for k, v in _COL_MAP_F.items()})
        df_view["VALOR"] = df_view.apply(lambda r: _calc(r["SERVIÇO"], r["DIÁRIAS"]), axis=1)
    else:
        df_view = pd.DataFrame(columns=["id", "folha_id"] + list(_COL_MAP_F.keys()))

    cols_show   = [c for c in list(_COL_MAP_F.keys()) if c in df_view.columns]
    df_editor   = df_view[["id"] + cols_show].copy().reset_index(drop=True)

    edited = st.data_editor(
        df_editor,
        column_config={
            "id":            st.column_config.NumberColumn("id", disabled=True),
            "NOME":          st.column_config.TextColumn("Nome"),
            "PIX":           st.column_config.TextColumn("PIX"),
            "NOME DA CONTA": st.column_config.TextColumn("Nome da Conta"),
            "SERVIÇO":       st.column_config.SelectboxColumn("Serviço", options=regras_obra.index.tolist() if not regras_obra.empty else []),
            "ETAPA":         st.column_config.SelectboxColumn("Etapa", options=etapas_opts),
            "DIÁRIAS":       st.column_config.NumberColumn("Diárias", min_value=0, step=0.5, format="%.1f"),
            "VALOR":         st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", disabled=True),
        },
        column_order=cols_show,
        use_container_width=True,
        hide_index=True,
        disabled=False,
        num_rows="dynamic",
        key="editor_folha",
    )

    total_folha = float(edited["VALOR"].sum()) if "VALOR" in edited.columns else 0.0
    st.metric("Total da quinzena", f"R$ {total_folha:,.2f}")

    col_s, col_m, col_f = st.columns(3)
    with col_s:
        if st.button("💾 Salvar", use_container_width=True, key="btn_folha_salvar"):
            _salvar_folha(folha, df_editor, _calc, _COL_MAP_F)
    with col_m:
        if st.button("📋 Criar Mensagem", use_container_width=True,
                     type="primary", key="btn_folha_msg"):
            st.session_state["folha_msg"] = _gerar_mensagem(obra_f, quinzena_f, edited, total_folha)
    with col_f:
        if folha["status"] != "fechada":
            comprovantes_fechar = st.file_uploader(
                "Comprovantes de pagamento",
                type=["jpg", "jpeg", "png", "pdf"],
                accept_multiple_files=True,
                key="folha_comprovantes",
            )
            if st.button("✅ Fechar Folha", use_container_width=True, key="btn_folha_fechar", type="primary"):
                _fechar_folha(folha, edited, obra_f, quinzena_f, comprovantes_fechar)
        else:
            if st.button("🔓 Reabrir Folha", use_container_width=True, key="btn_folha_reabrir"):
                sb = init_supabase()
                sb.table("c_despesas").delete().eq("folha_id", folha["id"]).execute()
                sb.table("folhas").update({"status": "rascunho"}).eq("id", folha["id"]).execute()
                load_despesas.clear()
                st.rerun(scope="fragment")

    if st.session_state.get("folha_msg"):
        st.markdown("#### Mensagem para o pagador")
        st.code(st.session_state["folha_msg"], language=None)
        st.caption("Copie o texto acima e envie ao pagador.")
        if st.button("🗑️ Limpar mensagem", key="btn_clear_msg"):
            st.session_state.pop("folha_msg")
            st.rerun(scope="fragment")


def _form_nova_conta(obras_list):
    with st.form("form_nova_conta", clear_on_submit=True):
        obra_nc      = st.selectbox("Obra *", obras_list, key="nc_obra")
        etapa_nc     = st.selectbox("Etapa", [""] + load_etapas(), key="nc_etapa")
        desc_nc      = st.text_input("Descrição *", key="nc_desc")
        fornec_nc    = st.text_input("Fornecedor / Credor", key="nc_fornec")
        cat_nc       = st.selectbox("Categoria", load_categorias(), key="nc_cat")
        tipo_nc      = st.selectbox("Tipo", [""] + load_tipos_custo(), key="nc_tipo")
        col_v, col_d = st.columns(2)
        with col_v:
            valor_nc = st.number_input("Valor Total (R$) *", min_value=0.01, step=0.01, format="%.2f", key="nc_valor")
        with col_d:
            venc_nc = st.date_input("Vencimento *", value=datetime.today(), key="nc_venc")
        col_p, col_r = st.columns(2)
        with col_p:
            parc_nc = st.number_input("Nº Parcelas", min_value=1, max_value=60, value=1, step=1, key="nc_parc")
        with col_r:
            recorr_nc = st.checkbox("Recorrente", key="nc_recorr")
        freq_nc = None
        if recorr_nc:
            freq_nc = st.selectbox("Frequência", ["mensal", "quinzenal"], key="nc_freq")
        obs_nc    = st.text_area("Observação", key="nc_obs")
        submitted = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)

    if submitted:
        if not desc_nc or valor_nc <= 0:
            st.error("Descrição e valor são obrigatórios.")
            return
        sb = init_supabase()
        valor_parcela = round(valor_nc / parc_nc, 2)
        ids_inseridos = []
        for i in range(int(parc_nc)):
            venc_i = venc_nc + relativedelta(months=i)
            rec = {
                "obra":           obra_nc,
                "etapa":          etapa_nc or None,
                "descricao":      desc_nc,
                "fornecedor":     fornec_nc or None,
                "categoria":      cat_nc or None,
                "tipo":           tipo_nc or None,
                "valor":          float(valor_parcela),
                "vencimento":     str(venc_i),
                "pago":           False,
                "recorrente":     recorr_nc,
                "frequencia":     freq_nc,
                "parcela_num":    i + 1,
                "total_parcelas": int(parc_nc),
                "observacao":     obs_nc or None,
            }
            res = sb.table("contas_pagar").insert(rec).execute()
            if res.data:
                ids_inseridos.append(res.data[0]["id"])
        if len(ids_inseridos) > 1:
            for rid in ids_inseridos:
                sb.table("contas_pagar").update({"grupo_id": ids_inseridos[0]}).eq("id", rid).execute()
        st.success(f"✅ {int(parc_nc)} conta(s) cadastrada(s)!")
        st.rerun(scope="fragment")


def _form_pagar_conta(df):
    if df.empty:
        st.info("Nenhuma conta para pagar.")
        return
    pendentes = df[df["status_display"].isin(["pendente", "vencido"])]
    if pendentes.empty:
        st.info("Sem contas pendentes.")
        return
    opcoes = {
        f"{r['descricao']} — R$ {r['valor']:,.2f} (venc. {r['vencimento']})": r["id"]
        for _, r in pendentes.iterrows()
    }
    sel_label = st.selectbox("Conta a pagar", list(opcoes.keys()), key="cp_sel_pagar")
    conta_id  = opcoes[sel_label]
    conta_row = pendentes[pendentes["id"] == conta_id].iloc[0]

    with st.form("form_pagar", clear_on_submit=True):
        data_pgto = st.date_input("Data do pagamento", value=datetime.today(), key="cp_data_pgto")
        forma_pg  = st.selectbox("Forma de pagamento", load_formas_pagamento(), key="cp_forma")
        banco_pg  = st.text_input("Banco / Conta", key="cp_banco")
        submitted = st.form_submit_button("✅ Confirmar Pagamento", type="primary", use_container_width=True)

    if submitted:
        sb = init_supabase()
        try:
            res_desp = sb.table("c_despesas").insert({
                "obra":            conta_row["obra"],
                "etapa":           conta_row.get("etapa") or "",
                "tipo":            conta_row.get("tipo") or "Outros",
                "despesa":         conta_row.get("categoria") or conta_row["descricao"],
                "descricao":       conta_row["descricao"],
                "fornecedor":      conta_row.get("fornecedor") or "",
                "valor_total":     float(conta_row["valor"]),
                "data":            str(data_pgto),
                "forma":           forma_pg or None,
                "banco":           banco_pg or None,
                "tem_nota_fiscal": False,
            }).execute()
            despesa_id = res_desp.data[0]["id"] if res_desp.data else None
            sb.table("contas_pagar").update({
                "pago":           True,
                "data_pagamento": str(data_pgto),
                "despesa_id":     despesa_id,
            }).eq("id", int(conta_id)).execute()
            if conta_row.get("recorrente"):
                freq  = conta_row.get("frequencia", "mensal")
                delta = relativedelta(months=1) if freq == "mensal" else relativedelta(weeks=2)
                novo_venc = conta_row["vencimento"] + delta
                sb.table("contas_pagar").insert({
                    "obra":           conta_row["obra"],
                    "etapa":          conta_row.get("etapa"),
                    "descricao":      conta_row["descricao"],
                    "fornecedor":     conta_row.get("fornecedor"),
                    "categoria":      conta_row.get("categoria"),
                    "tipo":           conta_row.get("tipo"),
                    "valor":          float(conta_row["valor"]),
                    "vencimento":     str(novo_venc),
                    "pago":           False,
                    "recorrente":     True,
                    "frequencia":     freq,
                    "parcela_num":    1,
                    "total_parcelas": 1,
                }).execute()
                st.info(f"Nova ocorrência criada para {novo_venc.strftime('%d/%m/%Y')}.")
            load_despesas.clear()
            st.success("✅ Pagamento registrado! Despesa gerada em c_despesas.")
            st.rerun(scope="fragment")
        except Exception as e:
            st.error(f"Erro ao registrar pagamento: {e}")


@st.fragment
def _render_contas_pagar():
    st.markdown("""
    <div class="main-header">
        <h1>Contas a Pagar</h1>
        <p>Controle de vencimentos e pagamentos por obra.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    obras_list = sorted(load_obras()["nome"].dropna().tolist()) if not load_obras().empty else []

    col_o, col_s = st.columns(2)
    with col_o:
        filtro_obra = st.selectbox("Obra", ["Todas"] + obras_list, key="cp_obra")
    with col_s:
        filtro_status = st.selectbox(
            "Status", ["Todos", "pendente", "vencido", "pago"], key="cp_status"
        )

    obra_query = None if filtro_obra == "Todas" else filtro_obra
    df = load_contas_pagar(obra_query)

    if not df.empty and filtro_status != "Todos":
        df = df[df["status_display"] == filtro_status]

    if not df.empty:
        hoje       = datetime.today().date()
        total_pend = df[df["status_display"] == "pendente"]["valor"].sum()
        total_venc = df[df["status_display"] == "vencido"]["valor"].sum()
        em_7_dias  = df[
            (df["status_display"] == "pendente") &
            (df["vencimento"] <= hoje + timedelta(days=7))
        ]["valor"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Pendente",     f"R$ {total_pend:,.2f}")
        c2.metric("Vencido",      f"R$ {total_venc:,.2f}")
        c3.metric("Próx. 7 dias", f"R$ {em_7_dias:,.2f}")

    _COLS_SHOW = ["obra", "etapa", "descricao", "fornecedor", "valor",
                  "vencimento", "parcela_num", "total_parcelas", "status_display"]
    _COL_CONFIG = {
        "obra":          st.column_config.TextColumn("Obra",        disabled=True),
        "etapa":         st.column_config.TextColumn("Etapa",       disabled=True),
        "descricao":     st.column_config.TextColumn("Descrição",   disabled=True),
        "fornecedor":    st.column_config.TextColumn("Fornecedor",  disabled=True),
        "valor":         st.column_config.NumberColumn("Valor", format="R$ %.2f", disabled=True),
        "vencimento":    st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY", disabled=True),
        "parcela_num":   st.column_config.NumberColumn("Parcela",   disabled=True),
        "total_parcelas":st.column_config.NumberColumn("Total Parc.", disabled=True),
        "status_display":st.column_config.TextColumn("Status",     disabled=True),
    }
    df_show = df[[c for c in ["id"] + _COLS_SHOW if c in df.columns]].copy() if not df.empty \
              else pd.DataFrame(columns=["id"] + _COLS_SHOW)

    st.data_editor(
        df_show,
        column_config=_COL_CONFIG,
        column_order=_COLS_SHOW,
        use_container_width=True,
        hide_index=True,
        disabled=True,
        key="editor_contas",
    )

    st.divider()
    col_nova, col_pagar = st.columns(2)
    with col_nova:
        with st.expander("➕ Nova Conta a Pagar"):
            _form_nova_conta(obras_list)
    with col_pagar:
        with st.expander("✅ Registrar Pagamento"):
            _form_pagar_conta(df)


with tab_folha:
    _render_folha()

with tab_contas:
    _render_contas_pagar()


@st.fragment
def _render_conf():
    st.markdown("""
    <div class="main-header">
        <h1>Configurações</h1>
        <p>Gerencie obras, etapas, orçamentos e taxas de conclusão.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    sub_obras, sub_etapas, sub_orc, sub_taxa, sub_formas, sub_cat, sub_regras = st.tabs(
        ["🏗️ Obras", "🔧 Etapas", "💼 Orçamentos", "📊 Taxa de Conclusão",
         "💳 Formas de Pagamento", "🏷️ Categorias de Despesa", "📐 Regras de Diária"]
    )

    # ── Sub-aba Obras ──────────────────────────────────────────────────────────
    with sub_obras:
        df_obras_conf = load_obras()
        if not df_obras_conf.empty:
            cols_show = [c for c in ['nome', 'descricao', 'contrato', 'art'] if c in df_obras_conf.columns]
            st.dataframe(df_obras_conf[cols_show], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma obra cadastrada ainda.")

        st.markdown("#### Nova Obra")
        with st.form("form_nova_obra"):
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                nova_obra_nome = st.text_input("Nome *")
                nova_obra_contrato = st.text_input("Contrato")
            with col_n2:
                nova_obra_descricao = st.text_input("Descrição")
                nova_obra_art = st.text_input("ART")
            if st.form_submit_button("➕ Adicionar Obra", type="primary"):
                if not nova_obra_nome.strip():
                    st.error("Nome é obrigatório.")
                else:
                    try:
                        _sb = init_supabase()
                        _sb.table("obras").insert({
                            "nome": nova_obra_nome.strip(),
                            "descricao": nova_obra_descricao.strip() or None,
                            "contrato": nova_obra_contrato.strip() or None,
                            "art": nova_obra_art.strip() or None,
                        }).execute()
                        load_obras.clear()
                        load_data.clear()
                        st.success(f"Obra '{nova_obra_nome.strip()}' adicionada!")
                        st.rerun(scope="fragment")
                    except Exception as e_obra:
                        st.error(f"Erro ao adicionar obra: {e_obra}")

        if not df_obras_conf.empty:
            st.markdown("#### Editar Obra")
            obra_edit_nome = st.selectbox("Selecione a obra", df_obras_conf['nome'].tolist(), key="conf_edit_obra")
            row_edit = df_obras_conf[df_obras_conf['nome'] == obra_edit_nome].iloc[0]
            with st.form("form_editar_obra"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    edit_descricao = st.text_input("Descrição", value=row_edit.get('descricao') or '')
                    edit_contrato = st.text_input("Contrato", value=row_edit.get('contrato') or '')
                with col_e2:
                    edit_art = st.text_input("ART", value=row_edit.get('art') or '')
                if st.form_submit_button("💾 Salvar Alterações", type="primary"):
                    try:
                        _sb = init_supabase()
                        _sb.table("obras").update({
                            "descricao": edit_descricao.strip() or None,
                            "contrato": edit_contrato.strip() or None,
                            "art": edit_art.strip() or None,
                        }).eq("nome", obra_edit_nome).execute()
                        load_obras.clear()
                        load_data.clear()
                        st.success("Obra atualizada!")
                        st.rerun(scope="fragment")
                    except Exception as e_edit:
                        st.error(f"Erro ao editar obra: {e_edit}")

            st.markdown("#### Remover Obra")
            obra_remover = st.selectbox("Obra a remover", df_obras_conf['nome'].tolist(), key="conf_rm_obra")
            if st.button("🗑️ Remover obra", key="btn_rm_obra", type="secondary"):
                try:
                    _sb = init_supabase()
                    _sb.table("obras").delete().eq("nome", obra_remover).execute()
                    load_obras.clear()
                    load_data.clear()
                    st.success(f"Obra '{obra_remover}' removida!")
                    st.rerun(scope="fragment")
                except Exception as e_rm:
                    st.error(f"Erro ao remover: {e_rm}")

    # ── Sub-aba Etapas ─────────────────────────────────────────────────────────
    with sub_etapas:
        _sb_etapas = init_supabase()
        if _sb_etapas:
            _res_etapas = _sb_etapas.table("etapas").select("nome,ordem").order("ordem").execute()
            df_etapas_conf = pd.DataFrame(_res_etapas.data) if _res_etapas.data else pd.DataFrame(columns=["nome", "ordem"])
        else:
            df_etapas_conf = pd.DataFrame(columns=["nome", "ordem"])

        if not df_etapas_conf.empty:
            st.markdown("#### Ordem das Etapas")
            df_etapas_edit = st.data_editor(
                df_etapas_conf,
                column_config={
                    "nome": st.column_config.TextColumn("Etapa", disabled=True),
                    "ordem": st.column_config.NumberColumn("Ordem", min_value=0, step=1),
                },
                use_container_width=True,
                hide_index=True,
                key="editor_etapas",
            )
            if st.button("💾 Salvar Ordem das Etapas", type="primary"):
                try:
                    _sb2 = init_supabase()
                    rows_upsert = df_etapas_edit[['nome', 'ordem']].to_dict(orient='records')
                    _sb2.table("etapas").upsert(rows_upsert, on_conflict="nome").execute()
                    load_data.clear()
                    st.success("Ordem salva!")
                    st.rerun(scope="fragment")
                except Exception as e_et:
                    st.error(f"Erro ao salvar etapas: {e_et}")

        st.markdown("#### Nova Etapa")
        with st.form("form_nova_etapa"):
            col_et1, col_et2 = st.columns([3, 1])
            with col_et1:
                nova_etapa_nome = st.text_input("Nome *")
            with col_et2:
                nova_etapa_ordem = st.number_input("Ordem", min_value=0, value=999, step=1)
            if st.form_submit_button("➕ Adicionar Etapa", type="primary"):
                if not nova_etapa_nome.strip():
                    st.error("Nome é obrigatório.")
                else:
                    try:
                        _sb3 = init_supabase()
                        _sb3.table("etapas").insert({
                            "nome": nova_etapa_nome.strip(),
                            "ordem": int(nova_etapa_ordem),
                        }).execute()
                        load_data.clear()
                        st.success(f"Etapa '{nova_etapa_nome.strip()}' adicionada!")
                        st.rerun(scope="fragment")
                    except Exception as e_novaet:
                        st.error(f"Erro ao adicionar etapa: {e_novaet}")

    # ── Sub-aba Orçamentos ─────────────────────────────────────────────────────
    with sub_orc:
        import itertools as _it
        _todas_obras_orc  = load_obras()
        _todas_etapas_orc = load_etapas()
        _tipos_orc        = load_tipos_custo()

        _sb_orc = init_supabase()
        if _sb_orc and not _todas_obras_orc.empty and _todas_etapas_orc and _tipos_orc:
            _res_orc = _sb_orc.table("orcamentos").select("obra,etapa,tipo_custo,valor_estimado").execute()
            df_orc_conf = pd.DataFrame(_res_orc.data) if _res_orc.data else pd.DataFrame(
                columns=["obra","etapa","tipo_custo","valor_estimado"])

            # Filtro por obra
            _obras_lista_orc = _todas_obras_orc['nome'].tolist()
            _filtro_orc = st.selectbox("Filtrar por obra", ["Todas"] + _obras_lista_orc, key="filtro_orc")

            # Grade completa: todas obras × etapas × tipos
            _obras_grid = [_filtro_orc] if _filtro_orc != "Todas" else _obras_lista_orc
            grid_orc = pd.DataFrame([
                {"obra": o, "etapa": e, "tipo_custo": t, "valor_estimado": 0.0}
                for o, e, t in _it.product(_obras_grid, _todas_etapas_orc, _tipos_orc)
            ])
            if not df_orc_conf.empty:
                df_orc_filtrado = df_orc_conf[df_orc_conf["obra"].isin(_obras_grid)] if _filtro_orc != "Todas" else df_orc_conf
                grid_orc = grid_orc.merge(
                    df_orc_filtrado[["obra","etapa","tipo_custo","valor_estimado"]],
                    on=["obra","etapa","tipo_custo"], how="left", suffixes=("_z","")
                )
                grid_orc["valor_estimado"] = grid_orc["valor_estimado"].fillna(
                    grid_orc.get("valor_estimado_z", 0)
                ).fillna(0)
                grid_orc = grid_orc[["obra","etapa","tipo_custo","valor_estimado"]]

            grid_orc["col_label"] = grid_orc["obra"] + " — " + grid_orc["tipo_custo"]
            pivot_orc = grid_orc.pivot_table(
                index="etapa", columns="col_label", values="valor_estimado", aggfunc="sum"
            ).fillna(0)
            pivot_orc.index.name = "Etapa"
            pivot_orc.columns.name = None

            col_cfg_orc = {
                col: st.column_config.NumberColumn(col, min_value=0, format="R$ %.2f")
                for col in pivot_orc.columns
            }
            pivot_editado = st.data_editor(
                pivot_orc.reset_index(),
                column_config={"Etapa": st.column_config.TextColumn("Etapa", disabled=True), **col_cfg_orc},
                use_container_width=True,
                hide_index=True,
                key="editor_orc",
            )

            if st.button("💾 Salvar Orçamentos", type="primary", key="btn_salvar_orc"):
                try:
                    _sb4 = init_supabase()
                    rows_orc = []
                    for _, row in pivot_editado.iterrows():
                        etapa = row["Etapa"]
                        for col_lbl in pivot_orc.columns:
                            partes = col_lbl.split(" — ", 1)
                            if len(partes) == 2:
                                rows_orc.append({
                                    "obra": partes[0], "etapa": etapa,
                                    "tipo_custo": partes[1],
                                    "valor_estimado": float(row[col_lbl]),
                                })
                    _sb4.table("orcamentos").upsert(rows_orc, on_conflict="obra,etapa,tipo_custo").execute()
                    load_data.clear()
                    st.success("Orçamentos salvos!")
                    st.rerun(scope="fragment")
                except Exception as e_orc:
                    st.error(f"Erro ao salvar orçamentos: {e_orc}")
        else:
            st.info("Configure obras, etapas e tipos de custo primeiro.")

    # ── Sub-aba Taxa de Conclusão ──────────────────────────────────────────────
    with sub_taxa:
        _todas_obras_taxa  = load_obras()
        _todas_etapas_taxa = load_etapas()

        _sb_taxa = init_supabase()
        if _sb_taxa and not _todas_obras_taxa.empty and _todas_etapas_taxa:
            _res_taxa = _sb_taxa.table("taxa_conclusao").select("obra,etapa,taxa").execute()
            df_taxa_conf = pd.DataFrame(_res_taxa.data) if _res_taxa.data else pd.DataFrame(
                columns=["obra","etapa","taxa"])

            # Filtro por obra
            _obras_lista_taxa = _todas_obras_taxa['nome'].tolist()
            _filtro_taxa = st.selectbox("Filtrar por obra", ["Todas"] + _obras_lista_taxa, key="filtro_taxa")

            # Grade completa
            _obras_grid_taxa = [_filtro_taxa] if _filtro_taxa != "Todas" else _obras_lista_taxa
            grid_taxa = pd.DataFrame([
                {"obra": o, "etapa": e, "taxa": 0.0}
                for o, e in _it.product(_obras_grid_taxa, _todas_etapas_taxa)
            ])
            if not df_taxa_conf.empty:
                df_taxa_filtrado = df_taxa_conf[df_taxa_conf["obra"].isin(_obras_grid_taxa)] if _filtro_taxa != "Todas" else df_taxa_conf
                grid_taxa = grid_taxa.merge(
                    df_taxa_filtrado[["obra","etapa","taxa"]],
                    on=["obra","etapa"], how="left", suffixes=("_z","")
                )
                grid_taxa["taxa"] = grid_taxa["taxa"].fillna(grid_taxa.get("taxa_z", 0)).fillna(0)
                grid_taxa = grid_taxa[["obra","etapa","taxa"]]

            pivot_taxa = grid_taxa.pivot_table(
                index="etapa", columns="obra", values="taxa", aggfunc="first"
            ).fillna(0)
            pivot_taxa.index.name = "Etapa"
            pivot_taxa.columns.name = None

            col_cfg_taxa = {
                col: st.column_config.NumberColumn(col, min_value=0, max_value=100, step=0.1, format="%.1f%%")
                for col in pivot_taxa.columns
            }
            pivot_taxa_edit = st.data_editor(
                pivot_taxa.reset_index(),
                column_config={"Etapa": st.column_config.TextColumn("Etapa", disabled=True), **col_cfg_taxa},
                use_container_width=True,
                hide_index=True,
                key="editor_taxa",
            )

            if st.button("💾 Salvar Taxas", type="primary", key="btn_salvar_taxa"):
                try:
                    _sb5 = init_supabase()
                    rows_taxa = []
                    for _, row in pivot_taxa_edit.iterrows():
                        etapa = row["Etapa"]
                        for obra_col in pivot_taxa.columns:
                            rows_taxa.append({
                                "obra": obra_col, "etapa": etapa,
                                "taxa": float(row[obra_col]),
                            })
                    _sb5.table("taxa_conclusao").upsert(rows_taxa, on_conflict="obra,etapa").execute()
                    load_data.clear()
                    st.success("Taxas de conclusão salvas!")
                    st.rerun(scope="fragment")
                except Exception as e_taxa:
                    st.error(f"Erro ao salvar taxas: {e_taxa}")
        else:
            st.info("Configure obras e etapas primeiro.")

    # ── Sub-aba Formas de Pagamento ────────────────────────────────────────────
    with sub_formas:
        _formas_atuais = [f for f in load_formas_pagamento() if f]  # remove string vazia
        st.markdown("**Formas de pagamento cadastradas**")
        st.dataframe({"Forma": _formas_atuais}, use_container_width=True, hide_index=True)

        st.markdown("---")
        with st.form("form_nova_forma"):
            nova_forma = st.text_input("Nova forma *")
            if st.form_submit_button("➕ Adicionar"):
                nova_forma = nova_forma.strip()
                if not nova_forma:
                    st.error("Informe um nome.")
                else:
                    try:
                        init_supabase().table("formas_pagamento").insert({"nome": nova_forma}).execute()
                        load_formas_pagamento.clear()
                        st.success(f"'{nova_forma}' adicionada!")
                        st.rerun(scope="fragment")
                    except Exception as e_f2:
                        st.error(f"Erro: {e_f2}")

        if _formas_atuais:
            st.markdown("---")
            forma_remover = st.selectbox("Remover forma", _formas_atuais, key="sel_rm_forma")
            if st.button("🗑️ Remover", key="btn_rm_forma", type="secondary"):
                try:
                    init_supabase().table("formas_pagamento").delete().eq("nome", forma_remover).execute()
                    load_formas_pagamento.clear()
                    st.success(f"'{forma_remover}' removida!")
                    st.rerun(scope="fragment")
                except Exception as e_f3:
                    st.error(f"Erro: {e_f3}")

    with sub_cat:
        _cats_atuais = [c for c in load_categorias() if c]  # remove string vazia
        st.markdown("**Categorias de despesa cadastradas**")
        st.dataframe({"Categoria": _cats_atuais}, use_container_width=True, hide_index=True)

        st.markdown("---")
        with st.form("form_nova_cat"):
            nova_cat = st.text_input("Nova categoria *")
            if st.form_submit_button("➕ Adicionar"):
                nova_cat = nova_cat.strip().upper()
                if not nova_cat:
                    st.error("Informe um nome.")
                else:
                    try:
                        init_supabase().table("categorias_despesa").insert({"nome": nova_cat}).execute()
                        load_categorias.clear()
                        st.success(f"'{nova_cat}' adicionada!")
                        st.rerun(scope="fragment")
                    except Exception as e_c2:
                        st.error(f"Erro: {e_c2}")

        if _cats_atuais:
            st.markdown("---")
            cat_remover = st.selectbox("Remover categoria", _cats_atuais, key="sel_rm_cat")
            if st.button("🗑️ Remover", key="btn_rm_cat", type="secondary"):
                try:
                    init_supabase().table("categorias_despesa").delete().eq("nome", cat_remover).execute()
                    load_categorias.clear()
                    st.success(f"'{cat_remover}' removida!")
                    st.rerun(scope="fragment")
                except Exception as e_c3:
                    st.error(f"Erro: {e_c3}")

    # ── Sub-aba Regras de Diária ───────────────────────────────────────────────
    with sub_regras:
        _obras_reg = load_obras()
        _obras_reg_list = sorted(_obras_reg["nome"].dropna().tolist()) if not _obras_reg.empty else []
        obra_reg = st.selectbox("Obra", _obras_reg_list, key="reg_obra_sel")

        df_reg_atual = load_folha_regras()
        df_reg_obra  = df_reg_atual[df_reg_atual["obra"] == obra_reg][
            ["servico", "tipo", "valor"]
        ].copy() if not df_reg_atual.empty else pd.DataFrame(columns=["servico", "tipo", "valor"])

        if not df_reg_obra.empty:
            st.markdown(f"**Regras cadastradas para {obra_reg}**")
            df_reg_edit = st.data_editor(
                df_reg_obra.reset_index(drop=True),
                column_config={
                    "servico": st.column_config.TextColumn("Serviço", disabled=True),
                    "tipo":    st.column_config.SelectboxColumn("Tipo", options=["diaria", "fixo"]),
                    "valor":   st.column_config.NumberColumn("Valor (R$)", min_value=0, format="R$ %.2f"),
                },
                use_container_width=True,
                hide_index=True,
                key="editor_regras",
            )
            if st.button("💾 Salvar regras", type="primary", key="btn_salvar_regras"):
                try:
                    _sb_reg = init_supabase()
                    rows_reg = [{"obra": obra_reg, "servico": r["servico"],
                                 "tipo": r["tipo"], "valor": float(r["valor"])}
                                for _, r in df_reg_edit.iterrows()]
                    _sb_reg.table("folha_regras").upsert(rows_reg, on_conflict="obra,servico").execute()
                    load_folha_regras.clear()
                    st.success("Regras salvas!")
                    st.rerun(scope="fragment")
                except Exception as e_reg:
                    st.error(f"Erro: {e_reg}")
        else:
            st.info(f"Nenhuma regra cadastrada para {obra_reg}.")

        st.markdown("---")
        st.markdown("#### Adicionar regra")
        with st.form("form_nova_regra"):
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                novo_servico = st.text_input("Serviço *", key="nova_reg_serv")
            with col_r2:
                novo_tipo = st.selectbox("Tipo", ["diaria", "fixo"], key="nova_reg_tipo")
            with col_r3:
                novo_valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
            if st.form_submit_button("➕ Adicionar"):
                try:
                    init_supabase().table("folha_regras").upsert(
                        {"obra": obra_reg, "servico": novo_servico,
                         "tipo": novo_tipo, "valor": float(novo_valor)},
                        on_conflict="obra,servico"
                    ).execute()
                    load_folha_regras.clear()
                    st.success(f"Regra '{novo_servico}' adicionada!")
                    st.rerun(scope="fragment")
                except Exception as e_nr:
                    st.error(f"Erro: {e_nr}")


with tab_conf:
    _render_conf()
