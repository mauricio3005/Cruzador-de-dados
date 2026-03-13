import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Configuração da Página
st.set_page_config(page_title="Dashboard Financeiro Gerencial", layout="wide", page_icon="📊")

# --- CSS Personalizado ---
# Tentando manter o aspecto clean pedido
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #A0AEC0;
    }
    .stProgress .st-bo {
        background-color: #3182ce;
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

@st.cache_data(ttl=300) # Cache por 5 minutos
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
    
    # Tratamento de chaves (lidando com possíveis problemas de encoding vistos no app.js)
    if 'ORçamento_ESTIMADO' in df.columns:
        df.rename(columns={'ORçamento_ESTIMADO': 'ORÇAMENTO_ESTIMADO'}, inplace=True)
    elif 'ORAMENTO_ESTIMADO' in df.columns:
        df.rename(columns={'ORAMENTO_ESTIMADO': 'ORÇAMENTO_ESTIMADO'}, inplace=True)
        
    # Garantir colunas essenciais
    cols_default = ['OBRA', 'ETAPA', 'TIPO_CUSTO', 'ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']
    for c in cols_default:
        if c not in df.columns:
            if c == 'TIPO_CUSTO': df['TIPO_CUSTO'] = 'Geral'
            else: df[c] = 0.0
            
    # Conversões numéricas
    df['ORÇAMENTO_ESTIMADO'] = pd.to_numeric(df['ORÇAMENTO_ESTIMADO'], errors='coerce').fillna(0)
    df['GASTO_REALIZADO'] = pd.to_numeric(df['GASTO_REALIZADO'], errors='coerce').fillna(0)
    df['SALDO_ETAPA'] = pd.to_numeric(df['SALDO_ETAPA'], errors='coerce').fillna(0)
    
    return df

# Formatador de moeda
def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- INTERFACE ---
df_raw = load_data()

if df_raw.empty:
    st.warning("Nenhum dado encontrado no Supabase ou as credenciais estão incorretas.")
else:
    # Sidebar: Filtros
    st.sidebar.title("Filtros")
    
    obras = sorted(df_raw['OBRA'].dropna().unique().tolist())
    etapas_todas = sorted(df_raw['ETAPA'].dropna().unique().tolist())
    tipos_todos = sorted(df_raw['TIPO_CUSTO'].dropna().unique().tolist())
    
    sel_obras = st.sidebar.multiselect("Selecionar Obra(s)", obras, default=obras)
    
    # Filtra as etapas disponíveis com base nas obras selecionadas
    df_temp_etapas = df_raw[df_raw['OBRA'].isin(sel_obras)]
    etapas_disp = sorted(df_temp_etapas['ETAPA'].dropna().unique().tolist())
    sel_etapas = st.sidebar.multiselect("Selecionar Etapa(s)", etapas_disp, default=etapas_disp)
    
    sel_tipos = st.sidebar.multiselect("Selecionar Tipo(s)", tipos_todos, default=tipos_todos)
    
    # Filtragem Global
    df_filtered = df_raw[
        (df_raw['OBRA'].isin(sel_obras)) &
        (df_raw['ETAPA'].isin(sel_etapas)) &
        (df_raw['TIPO_CUSTO'].isin(sel_tipos))
    ]
    
    # Header
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.title("Visão Geral do Portfólio" if len(sel_obras) == len(obras) else "Filtro Específico")
        st.markdown("*Acompanhamento consolidado de custos vs orçamentos*")
    with col_btn:
        if st.button("🔄 Atualizar Dados"):
            load_data.clear()
            st.rerun()

    st.markdown("---")

    # KPIs
    orcamento_total = df_filtered['ORÇAMENTO_ESTIMADO'].sum()
    gasto_total = df_filtered['GASTO_REALIZADO'].sum()
    saldo_total = orcamento_total - gasto_total
    percentual_consumo = (gasto_total / orcamento_total * 100) if orcamento_total > 0 else 0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric(label="Orçamento Total (Estimado)", value=format_currency(orcamento_total))
    with kpi2:
        st.metric(label="Custo Realizado", value=format_currency(gasto_total))
    with kpi3:
        st.metric(label="Saldo Financeiro", value=format_currency(saldo_total), delta=format_currency(saldo_total))
    with kpi4:
        st.metric(label="% de Consumo", value=f"{percentual_consumo:.1f}%", delta=f"{percentual_consumo-100:.1f}%" if percentual_consumo > 100 else None, delta_color="inverse")
        st.progress(min(percentual_consumo / 100, 1.0))

    st.markdown("---")

    # Gráficos
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.subheader("Previsto vs. Realizado (Por Etapa estrutural)")
        df_etapa = df_filtered.groupby('ETAPA')[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']].sum().reset_index()
        
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_etapa['ETAPA'], y=df_etapa['ORÇAMENTO_ESTIMADO'],
            name='Orçamento Estimado', marker_color='#D1D5DB'
        ))
        
        colors_realizado = ['#EF4444' if row['GASTO_REALIZADO'] > row['ORÇAMENTO_ESTIMADO'] else '#10B981' for _, row in df_etapa.iterrows()]
        
        fig_bar.add_trace(go.Bar(
            x=df_etapa['ETAPA'], y=df_etapa['GASTO_REALIZADO'],
            name='Gasto Realizado', marker_color=colors_realizado
        ))
        fig_bar.update_layout(barmode='group', margin=dict(t=30), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        st.subheader("Distribuição de Custos")
        df_rosca = df_filtered[df_filtered['GASTO_REALIZADO'] > 0].groupby('ETAPA')['GASTO_REALIZADO'].sum().reset_index()
        fig_pie = px.pie(df_rosca, values='GASTO_REALIZADO', names='ETAPA', hole=0.7, 
                         color_discrete_sequence=px.colors.qualitative.Prism)
        fig_pie.update_layout(margin=dict(t=30), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    
    st.subheader("Comparativo (Orçamento vs Gasto vs Saldo)")
    label_key = 'ETAPA' if len(sel_obras) == 1 else 'OBRA'
    df_ranking = df_filtered.groupby(label_key)[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']].sum().reset_index()
    df_ranking = df_ranking.sort_values(by='ORÇAMENTO_ESTIMADO', ascending=True) # Ascendente para barra horizontal
    
    fig_rank = go.Figure()
    fig_rank.add_trace(go.Bar(
        y=df_ranking[label_key], x=df_ranking['ORÇAMENTO_ESTIMADO'],
        name='Orçamento Estimado', orientation='h', marker_color='#D1D5DB'
    ))
    fig_rank.add_trace(go.Bar(
        y=df_ranking[label_key], x=df_ranking['GASTO_REALIZADO'],
        name='Gasto Realizado', orientation='h', marker_color='#8B5CF6'
    ))
    
    colors_saldo = ['#EF4444' if val < 0 else '#10B981' for val in df_ranking['SALDO_ETAPA']]
    fig_rank.add_trace(go.Bar(
        y=df_ranking[label_key], x=df_ranking['SALDO_ETAPA'],
        name='Saldo', orientation='h', marker_color=colors_saldo
    ))
    fig_rank.update_layout(barmode='group', height=500, margin=dict(t=30), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_rank, use_container_width=True)

    st.markdown("---")

    # Matriz Financeira (Tabela)
    st.subheader("Detalhamento Financeiro (Matriz)")
    
    # Criando a tabela customizada
    df_table = df_filtered.copy()
    df_table['% Consumido'] = df_table.apply(lambda r: f"{(r['GASTO_REALIZADO']/r['ORÇAMENTO_ESTIMADO']*100):.1f}%" if r['ORÇAMENTO_ESTIMADO'] > 0 else "0.0%", axis=1)
    
    # Agrupando para apresentação
    # Streamlit não possui uma TreeTable nativa perfeita, então usaremos um dataframe agrupado
    df_display = df_table.groupby(['OBRA', 'ETAPA']).agg({
        'ORÇAMENTO_ESTIMADO': 'sum',
        'GASTO_REALIZADO': 'sum',
        'SALDO_ETAPA': 'sum'
    }).reset_index()
    
    df_display['% Consumido'] = df_display.apply(lambda r: f"{(r['GASTO_REALIZADO']/r['ORÇAMENTO_ESTIMADO']*100):.1f}%" if r['ORÇAMENTO_ESTIMADO'] > 0 else "0.0%", axis=1)
    
    # Formatação das colunas financeiras
    cols_monetarias = ['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']
    for c in cols_monetarias:
        df_display[c] = df_display[c].apply(format_currency)
        
    df_display.rename(columns={
        'ORÇAMENTO_ESTIMADO': 'Orçamento Estimado',
        'GASTO_REALIZADO': 'Gasto Realizado',
        'SALDO_ETAPA': 'Saldo'
    }, inplace=True)
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)
