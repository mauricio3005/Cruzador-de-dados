"""
funcionario.py — App Streamlit para cadastro de despesas por funcionários.

Executar na porta 8502:
    streamlit run funcionario.py --server.port 8502

Credenciais em .streamlit/secrets.toml:
    SUPABASE_URL = "..."
    SUPABASE_SERVICE_KEY = "..."

    [funcionarios]
    "Kathleen" = "1234"
    "Diego" = "5678"
"""

import streamlit as st
import os
import uuid
from datetime import date
from supabase import create_client, Client
from dotenv import load_dotenv

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Registrar Despesa",
    page_icon="🧾",
    layout="centered",
)

# ── CSS mínimo ────────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #f1f5f9; }
h1 { font-size: 1.4rem !important; font-weight: 700 !important; color: #1e293b !important; }
.obrigatorio { color: #ef4444; font-size: 0.75rem; margin-top: -8px; margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)


# ── Supabase ──────────────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase() -> Client | None:
    load_dotenv()
    # Prefere secrets do Streamlit; fallback para .env
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = (
        st.secrets.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not url or not key:
        return None
    return create_client(url, key)


# ── Dados de referência ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_obras():
    sb = init_supabase()
    if not sb:
        return []
    r = sb.from_("obras").select("nome").order("nome").execute()
    return [o["nome"] for o in (r.data or [])]


@st.cache_data(ttl=300)
def load_etapas():
    sb = init_supabase()
    if not sb:
        return []
    r = sb.from_("etapas").select("nome").order("nome").execute()
    return [e["nome"] for e in (r.data or [])]


@st.cache_data(ttl=300)
def load_categorias():
    sb = init_supabase()
    if not sb:
        return []
    r = sb.from_("categorias_despesa").select("nome").order("nome").execute()
    return [c["nome"] for c in (r.data or [])]


@st.cache_data(ttl=300)
def load_formas():
    sb = init_supabase()
    if not sb:
        return []
    r = sb.from_("formas_pagamento").select("nome").order("nome").execute()
    return [f["nome"] for f in (r.data or [])]


# ── Autenticação simples por PIN ──────────────────────────────────────────────
def tela_login():
    st.markdown("## 🔐 Acesso de Funcionário")
    st.markdown("Selecione seu nome e informe seu PIN para continuar.")

    try:
        funcionarios_dict: dict = dict(st.secrets.get("funcionarios", {}))
    except Exception:
        st.error("Configuração de funcionários não encontrada em secrets.toml.")
        st.stop()

    if not funcionarios_dict:
        st.error("Nenhum funcionário configurado em secrets.toml → [funcionarios].")
        st.stop()

    nomes = sorted(funcionarios_dict.keys())

    with st.form("form_login"):
        nome = st.selectbox("Seu nome", nomes)
        pin  = st.text_input("PIN", type="password", max_chars=20)
        ok   = st.form_submit_button("Entrar", use_container_width=True)

    if ok:
        if pin == str(funcionarios_dict.get(nome, "")):
            st.session_state["autenticado"]   = True
            st.session_state["funcionario"]   = nome
            st.rerun()
        else:
            st.error("PIN incorreto. Tente novamente.")


def btn_sair():
    if st.button("Sair", key="btn_sair"):
        st.session_state.clear()
        st.rerun()


# ── Formulário de despesa ─────────────────────────────────────────────────────
def tela_formulario():
    funcionario = st.session_state["funcionario"]

    col_title, col_sair = st.columns([4, 1])
    with col_title:
        st.markdown(f"## 🧾 Registrar Despesa")
        st.caption(f"Logado como **{funcionario}**")
    with col_sair:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        btn_sair()

    sb = init_supabase()
    if not sb:
        st.error("Não foi possível conectar ao banco de dados.")
        st.stop()

    obras      = load_obras()
    etapas     = load_etapas()
    categorias = load_categorias()
    formas     = load_formas()

    if not obras:
        st.error("Nenhuma obra encontrada no banco. Verifique a conexão.")
        st.stop()

    st.divider()

    with st.form("form_despesa", clear_on_submit=True):
        st.markdown("##### Dados da despesa")

        obra = st.selectbox("Obra *", obras)
        etapa = st.selectbox("Etapa", ["(nenhuma)"] + etapas)

        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo *", ["Materiais", "Mão de Obra", "Geral"])
        with col2:
            data_desp = st.date_input("Data *", value=date.today())

        fornecedor = st.text_input("Fornecedor *", placeholder="Ex: Loja de Materiais XYZ")
        valor      = st.number_input("Valor Total (R$) *", min_value=0.01, step=0.01, format="%.2f")
        descricao  = st.text_area("Descrição *", placeholder="Descreva o que foi comprado/pago...", height=100)

        st.markdown("##### Informações adicionais (opcional)")

        col3, col4 = st.columns(2)
        with col3:
            categoria = st.selectbox("Categoria", ["(nenhuma)"] + categorias)
        with col4:
            forma = st.selectbox("Forma de pagamento", ["(nenhuma)"] + formas)

        banco = st.text_input("Banco / Conta utilizada", placeholder="Ex: Caixa, Nubank...")

        st.markdown("##### Comprovante *")
        st.markdown('<p class="obrigatorio">O envio do comprovante é obrigatório.</p>', unsafe_allow_html=True)
        comprovante = st.file_uploader(
            "Anexar comprovante (JPG, PNG ou PDF)",
            type=["jpg", "jpeg", "png", "pdf"],
            accept_multiple_files=False,
        )

        submitted = st.form_submit_button("Enviar para aprovação", use_container_width=True, type="primary")

    if submitted:
        # ── Validações ──
        erros = []
        if not fornecedor.strip():
            erros.append("Fornecedor é obrigatório.")
        if valor <= 0:
            erros.append("O valor deve ser maior que zero.")
        if not descricao.strip():
            erros.append("Descrição é obrigatória.")
        if comprovante is None:
            erros.append("O comprovante é obrigatório — anexe a foto ou PDF.")

        if erros:
            for e in erros:
                st.error(e)
            st.stop()

        # ── Upload do comprovante ──
        with st.spinner("Enviando comprovante…"):
            try:
                ext  = comprovante.name.rsplit(".", 1)[-1].lower()
                nome_arquivo = f"pend_{uuid.uuid4().hex[:12]}.{ext}"
                sb.storage.from_("comprovantes").upload(
                    nome_arquivo,
                    comprovante.read(),
                    {"content-type": comprovante.type},
                )
                pub = sb.storage.from_("comprovantes").get_public_url(nome_arquivo)
                # SDK v1 retorna string; SDK v2 retorna dict
                comprovante_url = pub if isinstance(pub, str) else pub["publicUrl"]
            except Exception as ex:
                st.error(f"Erro ao fazer upload do comprovante: {ex}")
                st.stop()

        # ── INSERT em despesas_pendentes ──
        with st.spinner("Registrando despesa…"):
            try:
                payload = {
                    "funcionario":   funcionario,
                    "obra":          obra,
                    "etapa":         None if etapa == "(nenhuma)" else etapa,
                    "tipo":          tipo,
                    "fornecedor":    fornecedor.strip(),
                    "valor_total":   float(valor),
                    "data":          str(data_desp),
                    "descricao":     descricao.strip(),
                    "despesa":       None if categoria == "(nenhuma)" else categoria,
                    "forma":         None if forma == "(nenhuma)" else forma,
                    "banco":         banco.strip() or None,
                    "comprovante_url": comprovante_url,
                    "status":        "pendente",
                }
                sb.from_("despesas_pendentes").insert(payload).execute()
            except Exception as ex:
                st.error(f"Erro ao registrar despesa: {ex}")
                st.stop()

        st.success("✅ Despesa enviada com sucesso! Aguarde a aprovação do responsável.")
        st.balloons()


# ── Roteamento principal ──────────────────────────────────────────────────────
def main():
    if not st.session_state.get("autenticado"):
        tela_login()
    else:
        tela_formulario()


if __name__ == "__main__":
    main()
