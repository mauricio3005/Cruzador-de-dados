import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
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

        sel_obras = st.multiselect("Obra(s)", obras, default=obras)

        df_temp_etapas = df_raw[df_raw['OBRA'].isin(sel_obras)]
        etapas_disp = sorted(df_temp_etapas['ETAPA'].dropna().unique().tolist())
        sel_etapas = st.multiselect("Etapa(s)", etapas_disp, default=etapas_disp)

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
                if tipo_rel == "Detalhado":
                    pdf_bytes = gerar_relatorio_detalhado(df_raw, obra_rel)
                else:
                    pdf_bytes = gerar_relatorio_simples(df_raw, obra_rel)
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
if df_raw.empty:
    st.warning("Nenhum dado encontrado no Supabase ou as credenciais estão incorretas.")
else:
    # Filtro global
    df_filtered = df_raw[
        (df_raw['OBRA'].isin(sel_obras)) &
        (df_raw['ETAPA'].isin(sel_etapas)) &
        (df_raw['TIPO_CUSTO'].isin(sel_tipos))
    ]

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
    gasto_total = df_filtered['GASTO_REALIZADO'].sum()
    saldo_total = orcamento_total - gasto_total
    percentual_consumo = (gasto_total / orcamento_total * 100) if orcamento_total > 0 else 0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric(label="💼 Orçamento Total Estimado", value=format_currency(orcamento_total))
    with kpi2:
        st.metric(label="💸 Custo Realizado", value=format_currency(gasto_total))
    with kpi3:
        delta_saldo = format_currency(abs(saldo_total))
        delta_color = "normal" if saldo_total >= 0 else "inverse"
        st.metric(
            label="🏦 Saldo Financeiro",
            value=format_currency(saldo_total),
            delta=f"{'+ ' if saldo_total >= 0 else '- '}{delta_saldo}",
            delta_color=delta_color
        )
    with kpi4:
        st.metric(
            label="📊 % de Consumo",
            value=f"{percentual_consumo:.1f}%",
            delta=f"{percentual_consumo - 100:.1f}% do orçamento" if percentual_consumo > 100 else None,
            delta_color="inverse"
        )
        st.progress(min(percentual_consumo / 100, 1.0))

    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # ---- Gráficos ----
    col_chart1, col_chart2 = st.columns([2, 1], gap="medium")

    with col_chart1:
        st.markdown('<p class="section-header">Previsto vs. Realizado — Por Etapa</p>', unsafe_allow_html=True)
        df_etapa = df_filtered.groupby('ETAPA')[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']].sum().reset_index()

        colors_realizado = [
            '#EF4444' if row['GASTO_REALIZADO'] > row['ORÇAMENTO_ESTIMADO'] else '#10B981'
            for _, row in df_etapa.iterrows()
        ]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_etapa['ETAPA'], y=df_etapa['ORÇAMENTO_ESTIMADO'],
            name='Orçamento Estimado',
            marker=dict(color='#D1D5DB', line=dict(width=0)),
            hovertemplate='<b>%{x}</b><br>Orçamento: R$ %{y:,.2f}<extra></extra>'
        ))
        fig_bar.add_trace(go.Bar(
            x=df_etapa['ETAPA'], y=df_etapa['GASTO_REALIZADO'],
            name='Gasto Realizado',
            marker=dict(color=colors_realizado, line=dict(width=0)),
            hovertemplate='<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>'
        ))
        fig_bar.update_layout(
            barmode='group',
            bargap=0.25,
            bargroupgap=0.05,
            **CHART_LAYOUT
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        st.markdown('<p class="section-header">Distribuição de Custos</p>', unsafe_allow_html=True)
        df_rosca = df_filtered[df_filtered['GASTO_REALIZADO'] > 0].groupby('ETAPA')['GASTO_REALIZADO'].sum().reset_index()
        fig_pie = px.pie(
            df_rosca, values='GASTO_REALIZADO', names='ETAPA',
            hole=0.65,
            color_discrete_sequence=['#2563EB','#10B981','#8B5CF6','#F59E0B','#EF4444','#06B6D4','#EC4899']
        )
        fig_pie.update_traces(
            textposition='outside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>',
            pull=[0.04] * len(df_rosca)
        )
        fig_pie.update_layout(
            showlegend=False,
            **{k: v for k, v in CHART_LAYOUT.items() if k not in ['xaxis', 'yaxis', 'legend']}
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # ---- Gráfico de Ranking Full Width ----
    st.markdown('<p class="section-header">Comparativo — Orçamento · Gasto · Saldo</p>', unsafe_allow_html=True)

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

    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # ---- Detalhamento por Obra (Acordeão) ----
    st.markdown('<p class="section-header">Detalhamento Financeiro por Obra</p>', unsafe_allow_html=True)

    # Agrupamento por obra + etapa
    df_detail = df_filtered.groupby(['OBRA', 'ETAPA']).agg({
        'ORÇAMENTO_ESTIMADO': 'sum',
        'GASTO_REALIZADO': 'sum',
        'SALDO_ETAPA': 'sum'
    }).reset_index()

    # Resumo por obra (para o cabeçalho do expander)
    df_obra_summary = df_detail.groupby('OBRA').agg({
        'ORÇAMENTO_ESTIMADO': 'sum',
        'GASTO_REALIZADO': 'sum',
        'SALDO_ETAPA': 'sum'
    }).reset_index()

    for _, obra_row in df_obra_summary.iterrows():
        nome_obra = obra_row['OBRA']
        orc_obra  = obra_row['ORÇAMENTO_ESTIMADO']
        gasto_obra = obra_row['GASTO_REALIZADO']
        saldo_obra = obra_row['SALDO_ETAPA']
        pct_obra = (gasto_obra / orc_obra * 100) if orc_obra > 0 else 0
        pct_capped = min(pct_obra / 100, 1.0)

        saldo_class = 'green' if saldo_obra >= 0 else 'red'
        pct_class = 'over' if pct_obra > 100 else ''
        pct_bar_color = '#EF4444' if pct_obra > 100 else '#2563EB'
        pct_width = int(pct_capped * 100)

        expander_label = f"🏗️  {nome_obra}"

        with st.expander(expander_label, expanded=False):
            # Linha de resumo da obra
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

            # Tabela de etapas da obra
            df_etapas_obra = df_detail[df_detail['OBRA'] == nome_obra].copy()
            df_etapas_obra['% Consumido'] = df_etapas_obra.apply(
                lambda r: f"{(r['GASTO_REALIZADO'] / r['ORÇAMENTO_ESTIMADO'] * 100):.1f}%" if r['ORÇAMENTO_ESTIMADO'] > 0 else "0.0%",
                axis=1
            )
            df_etapas_obra = df_etapas_obra.drop(columns=['OBRA'])
            for col in ['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']:
                df_etapas_obra[col] = df_etapas_obra[col].apply(format_currency)

            df_etapas_obra.rename(columns={
                'ETAPA': 'Etapa',
                'ORÇAMENTO_ESTIMADO': 'Orçamento Estimado',
                'GASTO_REALIZADO': 'Gasto Realizado',
                'SALDO_ETAPA': 'Saldo'
            }, inplace=True)

            st.dataframe(
                df_etapas_obra,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Etapa": st.column_config.TextColumn("Etapa", width="large"),
                    "Orçamento Estimado": st.column_config.TextColumn("Orçamento", width="medium"),
                    "Gasto Realizado": st.column_config.TextColumn("Realizado", width="medium"),
                    "Saldo": st.column_config.TextColumn("Saldo", width="medium"),
                    "% Consumido": st.column_config.TextColumn("% Consumido", width="small"),
                }
            )
