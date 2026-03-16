"""
migrar_excel_para_supabase.py
─────────────────────────────────────────────────────────────────────────────
Script de migracao ONE-SHOT: popula as tabelas de referencia do Supabase
a partir da planilha Excel e de dados fixos.

Tabelas populadas:
  obras            - 3 obras do sistema
  etapas           - nomes + ordem (da aba Etapas)
  orcamentos       - valores estimados por obra+etapa+tipo (da aba Etapas)
  taxa_conclusao   - % de conclusao por obra+etapa (da aba Taxa_Conc)
  fornecedores     - fornecedores unicos (da aba C Despesas)

Uso:
  python migrar_excel_para_supabase.py

Seguro para re-rodar: usa upsert (on_conflict) em todas as insercoes.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

CAMINHO_EXCEL = r"C:\Users\mauri\OneDrive\Controle de obra\Controle de obras.xlsx"


# ── Dados fixos das obras ──────────────────────────────────────────────────
OBRAS = [
    {
        "nome":      "Creche Teoflandia",
        "descricao": "Creche proinfancia tipo 01 no municipio de Teofilandia",
        "contrato":  "0252/2025",
        "art":       "BA20240905989",
    },
    {
        "nome":      "Creche apuarema",
        "descricao": None,
        "contrato":  None,
        "art":       None,
    },
    {
        "nome":      "Casa Busca vida",
        "descricao": None,
        "contrato":  None,
        "art":       None,
    },
]

# Mapeamento coluna Excel -> nome da obra (para orcamentos e taxa)
COL_OBRA_MAP = {
    "ESTIM MAO DE OBRA APUA": ("Creche apuarema",   "Mao de Obra"),
    "ESTIM MATERIAL APUA":    ("Creche apuarema",   "Materiais"),
    "ESTIM MAO DE OBRA TEOF": ("Creche Teoflandia", "Mao de Obra"),
    "ESTIM MATERIAL TEOF":    ("Creche Teoflandia", "Materiais"),
}

TAXA_COL_MAP = {
    "Conc_Apua": "Creche apuarema",
    "Conc_Teof": "Creche Teoflandia",
}


def _normaliza_col(col: str) -> str:
    """Remove acentos basicos para comparacao flexivel de colunas."""
    return (col.strip()
               .upper()
               .replace("A\u00c3O", "AO")
               .replace("\u00c3", "A")
               .replace("\u00c2", "A")
               .replace("\u00ca", "E")
               .replace("\u00cd", "I")
               .replace("\u00d3", "O")
               .replace("\u00da", "U")
               .replace("\u00c7", "C"))


def conectar():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_KEY")
           or os.getenv("SUPABASE_ANON_KEY"))
    if not url or not key:
        raise RuntimeError("Credenciais do Supabase nao encontradas no .env")
    return create_client(url, key)


def migrar_obras(sb):
    print("\n[1/5] Migrando obras...")
    sb.table("obras").upsert(OBRAS, on_conflict="nome").execute()
    print(f"  -> {len(OBRAS)} obras inseridas/atualizadas.")


def migrar_etapas_e_orcamentos(sb):
    print("\n[2/5] Migrando etapas e orcamentos (aba Etapas)...")

    df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Etapas", header=1)
    df.columns = df.columns.str.strip()
    df.dropna(subset=["Nome da Etapa"], inplace=True)

    # Mapeia colunas com normalizacao (ignora acentos e case)
    col_map = {}
    for col in df.columns:
        col_norm = _normaliza_col(col)
        for chave in COL_OBRA_MAP:
            if _normaliza_col(chave) == col_norm:
                col_map[col] = COL_OBRA_MAP[chave]

    # Etapas
    etapas_rows = []
    for ordem, (_, row) in enumerate(df.iterrows()):
        etapas_rows.append({
            "nome":  str(row["Nome da Etapa"]).strip(),
            "ordem": ordem,
        })

    sb.table("etapas").upsert(etapas_rows, on_conflict="nome").execute()
    print(f"  -> {len(etapas_rows)} etapas inseridas/atualizadas.")

    # Orcamentos
    orc_rows = []
    for _, row in df.iterrows():
        etapa = str(row["Nome da Etapa"]).strip()
        for col_excel, (obra, tipo_raw) in col_map.items():
            val = pd.to_numeric(row.get(col_excel, 0), errors="coerce") or 0
            # Normaliza tipo para valores aceitos na tabela
            tipo = "Mao de Obra" if "MAO" in tipo_raw.upper() else "Materiais"
            # Usa o valor com acento para corresponder ao CHECK constraint
            tipo_db = "Mão de Obra" if tipo == "Mao de Obra" else "Materiais"
            orc_rows.append({
                "obra":           obra,
                "etapa":          etapa,
                "tipo_custo":     tipo_db,
                "valor_estimado": float(val),
            })

    # Adiciona Casa Busca Vida com orcamento zero para todas as etapas
    for etapa_row in etapas_rows:
        for tipo_db in ("Mão de Obra", "Materiais"):
            orc_rows.append({
                "obra":           "Casa Busca vida",
                "etapa":          etapa_row["nome"],
                "tipo_custo":     tipo_db,
                "valor_estimado": 0.0,
            })

    if orc_rows:
        sb.table("orcamentos").upsert(
            orc_rows, on_conflict="obra,etapa,tipo_custo"
        ).execute()
        print(f"  -> {len(orc_rows)} orcamentos inseridos/atualizados.")


def migrar_taxa_conclusao(sb):
    print("\n[3/5] Migrando taxa de conclusao (aba Taxa_Conc)...")

    df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Taxa_Conc", header=0)
    df.columns = df.columns.str.strip()
    df["Nome da Etapa"] = df["Nome da Etapa"].str.strip()

    taxa_rows = []
    for _, row in df.iterrows():
        etapa = str(row["Nome da Etapa"]).strip()
        for col, obra in TAXA_COL_MAP.items():
            if col not in df.columns:
                continue
            val = pd.to_numeric(row.get(col, 0), errors="coerce")
            val = float(val) if pd.notna(val) else 0.0
            taxa_rows.append({"obra": obra, "etapa": etapa, "taxa": val})

    # Adiciona Casa Busca Vida com taxa zero para todas as etapas do Excel
    etapas_unicas = list(dict.fromkeys(r["etapa"] for r in taxa_rows))
    for etapa in etapas_unicas:
        taxa_rows.append({"obra": "Casa Busca vida", "etapa": etapa, "taxa": 0.0})

    if taxa_rows:
        sb.table("taxa_conclusao").upsert(
            taxa_rows, on_conflict="obra,etapa"
        ).execute()
        print(f"  -> {len(taxa_rows)} taxas inseridas/atualizadas.")


def migrar_fornecedores(sb):
    print("\n[4/5] Migrando fornecedores (aba C Despesas)...")

    df = pd.read_excel(CAMINHO_EXCEL, sheet_name="C Despesas")
    df.columns = df.columns.str.strip()

    col_forn = next(
        (c for c in df.columns if c.strip().upper() == "FORNECEDOR"), None
    )
    if col_forn is None:
        print("  -> Coluna FORNECEDOR nao encontrada. Pulando.")
        return

    nomes = (
        df[col_forn]
        .dropna()
        .str.strip()
        .loc[lambda s: s != ""]
        .unique()
        .tolist()
    )

    # Busca fornecedores ja existentes para evitar conflito
    existentes_res = sb.table("fornecedores").select("nome").execute()
    existentes = {r["nome"] for r in existentes_res.data}

    novos = [{"nome": n} for n in nomes if n not in existentes]
    if novos:
        sb.table("fornecedores").insert(novos).execute()
        print(f"  -> {len(novos)} fornecedores novos inseridos "
              f"({len(nomes) - len(novos)} ja existiam).")
    else:
        print(f"  -> Todos os {len(nomes)} fornecedores ja existem.")


def resumo_final(sb):
    print("\n[5/5] Verificando contagens finais no Supabase...")
    for tabela in ["obras", "etapas", "orcamentos", "taxa_conclusao", "fornecedores"]:
        res = sb.table(tabela).select("id", count="exact").execute()
        print(f"  {tabela:20s}: {res.count} registros")


def main():
    if not os.path.exists(CAMINHO_EXCEL):
        print(f"ERRO: Excel nao encontrado em:\n  {CAMINHO_EXCEL}")
        return

    print("Conectando ao Supabase...")
    sb = conectar()
    print("Conectado.")

    migrar_obras(sb)
    migrar_etapas_e_orcamentos(sb)
    migrar_taxa_conclusao(sb)
    migrar_fornecedores(sb)
    resumo_final(sb)

    print("\nMigracao concluida com sucesso!")
    print("Pode rodar novamente com seguranca (upsert em todas as tabelas).")


if __name__ == "__main__":
    main()
