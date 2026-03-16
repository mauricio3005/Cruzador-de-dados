import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import base64
import json
from datetime import datetime
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

    prompt_instrucao = (
        "Analise esta nota fiscal ou comprovante de pagamento e extraia as "
        "informações abaixo. Retorne SOMENTE um JSON válido, sem texto adicional.\n\n"
        "{\n"
        '  "FORNECEDOR": "nome do fornecedor ou empresa emissora",\n'
        '  "VALOR_TOTAL": <número float, ex: 310.50>,\n'
        '  "DATA": "YYYY-MM-DD",\n'
        '  "DESCRICAO": "descrição resumida do serviço ou material adquirido",\n'
        '  "TIPO": "Mão de Obra" ou "Materiais" ou "Geral",\n'
        '  "FORMA": "PIX" ou "Boleto" ou "Cartão" ou "Dinheiro" ou "Transferência" ou ""\n'
        "}\n\n"
        "Use null para campos que não consiga identificar com clareza."
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

    response = supabase.table("relatorios").select("*").execute()
    data = response.data

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if 'ORçamento_ESTIMADO' in df.columns:
        df.rename(columns={'ORçamento_ESTIMADO': 'ORÇAMENTO_ESTIMADO'}, inplace=True)
    elif 'ORAMENTO_ESTIMADO' in df.columns:
        df.rename(columns={'ORAMENTO_ESTIMADO': 'ORÇAMENTO_ESTIMADO'}, inplace=True)

    cols_default = ['OBRA', 'ETAPA', 'TIPO_CUSTO', 'ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']
    for c in cols_default:
        if c not in df.columns:
            if c == 'TIPO_CUSTO': df['TIPO_CUSTO'] = 'Geral'
            else: df[c] = 0.0

    df['ORÇAMENTO_ESTIMADO'] = pd.to_numeric(df['ORÇAMENTO_ESTIMADO'], errors='coerce').fillna(0)
    df['GASTO_REALIZADO'] = pd.to_numeric(df['GASTO_REALIZADO'], errors='coerce').fillna(0)
    df['SALDO_ETAPA'] = pd.to_numeric(df['SALDO_ETAPA'], errors='coerce').fillna(0)

    return df

def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

@st.cache_data(ttl=300)
def load_despesas():
    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        return pd.DataFrame()
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = supabase.table("despesas").select("*").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

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
        obra_rel = st.selectbox(
            "Obra para o relatório",
            sorted(df_raw['OBRA'].dropna().unique().tolist()),
            key="selectbox_relatorio",
        )

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
                    pdf_bytes = gerar_relatorio_administrativo(df_desp_adm, obra_rel, data_ini_adm, data_fim_adm)
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
                        pdf_bytes = gerar_relatorio_detalhado(df_raw, obra_rel, df_desp_semana)
                    else:
                        pdf_bytes = gerar_relatorio_simples(df_raw, obra_rel, df_desp_semana)
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
tab_dash, tab_desp = st.tabs(["📊 Dashboard", "📋 Despesas"])

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

with tab_desp:
    st.markdown("""
    <div class="main-header">
        <h1>Cadastro de Despesas</h1>
        <p>Registre uma nova despesa diretamente no banco de dados.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    if df_raw.empty:
        st.warning("Sem conexão com o banco de dados.")
    else:
        obras_list = sorted(df_raw['OBRA'].dropna().unique().tolist())

        st.markdown('<p class="section-header">Nova Despesa</p>', unsafe_allow_html=True)

        # ── Seletores fora do form para atualização dinâmica ──────────────────
        col_obra, col_nota, _ = st.columns([1, 1, 1])
        with col_obra:
            obra_form = st.selectbox("Obra *", obras_list, key="cad_obra")
        with col_nota:
            tem_nota = st.checkbox("📄 Tem nota fiscal?", key="cad_tem_nota")

        etapas_obra_form = sorted(df_raw[df_raw['OBRA'] == obra_form]['ETAPA'].dropna().unique().tolist())

        # ── Nota fiscal + extração IA (fora do form para permitir botão) ──────
        comprovante_form = None
        if tem_nota:
            upload_key = f"cad_comprovante_{st.session_state.get('cad_upload_key', 0)}"
            col_file, col_ia = st.columns([3, 1])
            with col_file:
                comprovante_form = st.file_uploader(
                    "Nota Fiscal *",
                    type=["pdf", "jpg", "jpeg", "png"],
                    help="Anexe a nota fiscal da despesa",
                    key=upload_key,
                )
            with col_ia:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🤖 Extrair com IA", disabled=comprovante_form is None, use_container_width=True):
                    with st.spinner("Analisando nota fiscal com IA..."):
                        try:
                            resultado = _extrair_com_ia(comprovante_form.getvalue(), comprovante_form.type)
                            st.session_state['ia_resultado'] = resultado
                            st.success("✅ Dados extraídos! Revise os campos abaixo.")
                        except Exception as e_ia:
                            st.error(f"Erro na extração: {e_ia}")

        # ── Pré-preenchimento via IA ───────────────────────────────────────────
        ia = st.session_state.get('ia_resultado') or {}
        if ia:
            st.info("🤖 Campos pré-preenchidos pela IA — revise antes de cadastrar.")

        _tipos = ["Mão de Obra", "Materiais", "Geral"]
        _formas = ["", "PIX", "Boleto", "Cartão", "Dinheiro", "Transferência", "Outro"]
        ia_tipo_idx = _tipos.index(ia['TIPO']) if ia.get('TIPO') in _tipos else 0
        ia_forma_idx = _formas.index(ia['FORMA']) if ia.get('FORMA') in _formas else 0
        ia_data = None
        if ia.get('DATA'):
            try:
                ia_data = datetime.strptime(ia['DATA'], '%Y-%m-%d').date()
            except Exception:
                pass
        ia_valor = float(ia['VALOR_TOTAL']) if ia.get('VALOR_TOTAL') else 0.0
        ia_fornecedor = str(ia.get('FORNECEDOR') or '')
        ia_descricao = str(ia.get('DESCRICAO') or '')

        with st.form("form_despesa", clear_on_submit=True):
            # ── Campos obrigatórios ───────────────────────────────────────────
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
                fornecedor_form = st.text_input("Fornecedor *", value=ia_fornecedor)
            with col5:
                valor_form = st.number_input("Valor Total (R$) *", min_value=0.0, value=ia_valor, step=0.01, format="%.2f")
            with col6:
                despesa_form = st.text_input("Despesa")

            descricao_form = st.text_area("Descrição *", value=ia_descricao, max_chars=500, placeholder="Descrição detalhada da despesa...")

            # ── Campos opcionais ──────────────────────────────────────────────
            st.caption("Campos opcionais")
            col7, col8, col9, col10 = st.columns(4)
            with col7:
                valor_unit_form = st.number_input("Valor Unitário (R$)", min_value=0.0, step=0.01, format="%.2f")
            with col8:
                qtd_form = st.number_input("Quantidade", min_value=1, step=1, value=1)
            with col9:
                banco_form = st.text_input("Banco")
            with col10:
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
                        comprovante_url = supabase.storage.from_("comprovantes").get_public_url(nome_arq)
                    except Exception as e_storage:
                        st.warning(f"Nota fiscal não pôde ser salva: {e_storage}")
                record = {
                    "OBRA":            obra_form,
                    "ETAPA":           etapa_form,
                    "TIPO":            tipo_form,
                    "FORNECEDOR":      fornecedor_form.strip() or None,
                    "VALOR_TOTAL":     float(valor_form),
                    "DATA":            data_form.strftime('%Y-%m-%d'),
                    "DESCRICAO":       descricao_form.strip() or None,
                    "DESPESA":         despesa_form.strip() or None,
                    "VALOR_UNITARIO":  float(valor_unit_form) if valor_unit_form > 0 else None,
                    "QUANTIDADE":      int(qtd_form),
                    "BANCO":           banco_form.strip() or None,
                    "FORMA":           forma_form or None,
                    "TEM_NOTA_FISCAL": tem_nota,
                    "COMPROVANTE_URL": comprovante_url,
                }
                try:
                    supabase.table("despesas").insert(record).execute()
                    load_despesas.clear()
                    st.session_state.pop('ia_resultado', None)
                    st.session_state['cad_upload_key'] = st.session_state.get('cad_upload_key', 0) + 1
                    st.success("✅ Despesa cadastrada com sucesso!")
                except Exception as e_ins:
                    st.error(f"Erro ao cadastrar: {e_ins}")

        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
        st.markdown('<p class="section-header">Despesas Registradas</p>', unsafe_allow_html=True)

        df_hist = load_despesas()
        if df_hist.empty:
            st.info("Nenhuma despesa registrada ainda.")
        else:
            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
            with col_h1:
                obras_hist = ["Todas"] + sorted(df_hist['OBRA'].dropna().unique().tolist())
                obra_hist = st.selectbox("Obra", obras_hist, key="hist_obra")
            with col_h2:
                data_ini_hist = st.date_input("De", value=datetime.today().replace(day=1), key="hist_ini")
            with col_h3:
                data_fim_hist = st.date_input("Até", value=datetime.today(), key="hist_fim")
            with col_h4:
                tipo_hist = st.selectbox("Tipo", ["Todos", "Mão de Obra", "Materiais", "Geral"], key="hist_tipo")

            df_view = df_hist.copy()
            if obra_hist != "Todas":
                df_view = df_view[df_view['OBRA'] == obra_hist]
            if tipo_hist != "Todos":
                df_view = df_view[df_view['TIPO'] == tipo_hist]
            df_view = df_view[
                (df_view['DATA'] >= pd.Timestamp(data_ini_hist)) &
                (df_view['DATA'] <= pd.Timestamp(data_fim_hist))
            ]

            total_hist = df_view['VALOR_TOTAL'].sum() if 'VALOR_TOTAL' in df_view.columns else 0
            st.metric("Total no período", format_currency(total_hist))

            if df_view.empty:
                st.info("Nenhuma despesa no período selecionado.")
            else:
                cols_show = [c for c in ['DATA', 'OBRA', 'ETAPA', 'TIPO', 'FORNECEDOR', 'DESCRICAO', 'VALOR_TOTAL'] if c in df_view.columns]
                df_disp = df_view[cols_show].copy()
                if 'DATA' in df_disp.columns:
                    df_disp['DATA'] = df_disp['DATA'].dt.strftime('%d/%m/%Y')
                if 'VALOR_TOTAL' in df_disp.columns:
                    df_disp['VALOR_TOTAL'] = df_disp['VALOR_TOTAL'].apply(format_currency)
                df_disp.rename(columns={
                    'DATA': 'Data', 'OBRA': 'Obra', 'ETAPA': 'Etapa', 'TIPO': 'Tipo',
                    'FORNECEDOR': 'Fornecedor', 'DESCRICAO': 'Descrição', 'VALOR_TOTAL': 'Valor'
                }, inplace=True)
                st.dataframe(df_disp, use_container_width=True, hide_index=True)

                csv_data = df_view.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "⬇️ Exportar CSV",
                    csv_data,
                    f"despesas_{data_ini_hist.strftime('%Y%m%d')}_{data_fim_hist.strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True,
                )
