"""
migrar_despesas_para_c_despesas.py
─────────────────────────────────────────────────────────────────────────────
Lê a aba "C Despesas" do Excel e insere os dados na nova tabela c_despesas,
respeitando os FK com obras, etapas, fornecedores e categorias_despesa.

Estratégia para FK:
  - obra/etapa nao encontradas -> inseridas automaticamente para nao perder dados
  - fornecedor nao encontrado  -> inserido automaticamente
  - categoria (despesa)        -> NULL se nao encontrada (nao queremos lixo na tabela)
  - forma invalida             -> NULL

Seguro para re-rodar: verifica duplicatas por obra+etapa+valor_total+data.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

CAMINHO_EXCEL = r"C:\Users\mauri\OneDrive\Controle de obra\Controle de obras.xlsx"

NORMALIZAR_OBRAS = {
    "Creche de Teoflandia": "Creche Teoflandia",
    "Creche De Teoflandia": "Creche Teoflandia",
}
NORMALIZAR_TIPOS = {
    "MATERIAL":    "Materiais",
    "MÃO DE OBRA": "Mão de Obra",
    "MAO DE OBRA": "Mão de Obra",
    "Mao de Obra": "Mão de Obra",
}
TIPOS_VALIDOS = {"Mão de Obra", "Materiais", "Geral"}
FORMAS_VALIDAS = {"PIX", "Boleto", "Cartão", "Dinheiro", "Transferência", "Outro"}


def conectar():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_KEY")
           or os.getenv("SUPABASE_ANON_KEY"))
    if not url or not key:
        raise RuntimeError("Credenciais do Supabase nao encontradas no .env")
    return create_client(url, key)


def _set_nomes(sb, tabela, campo="nome"):
    res = sb.table(tabela).select(campo).execute()
    return {r[campo] for r in res.data}


def _garantir_obra(sb, obras_set, nome):
    if nome not in obras_set:
        sb.table("obras").insert({"nome": nome}).execute()
        obras_set.add(nome)
        print(f"  [novo] obra inserida: '{nome}'")


def _garantir_etapa(sb, etapas_set, nome):
    if nome not in etapas_set:
        sb.table("etapas").insert({"nome": nome, "ordem": 999}).execute()
        etapas_set.add(nome)
        print(f"  [novo] etapa inserida: '{nome}' (ordem=999)")


def _garantir_fornecedor(sb, forn_set, nome):
    if nome and nome not in forn_set:
        sb.table("fornecedores").insert({"nome": nome}).execute()
        forn_set.add(nome)
        print(f"  [novo] fornecedor inserido: '{nome}'")


def main():
    if not os.path.exists(CAMINHO_EXCEL):
        print(f"ERRO: Excel nao encontrado em:\n  {CAMINHO_EXCEL}")
        return

    print("Conectando ao Supabase...")
    sb = conectar()
    print("Conectado.\n")

    # ── 1. Carrega tabelas de referencia ─────────────────────────────────────
    print("Carregando tabelas de referencia...")
    obras_set      = _set_nomes(sb, "obras")
    etapas_set     = _set_nomes(sb, "etapas")
    forn_set       = _set_nomes(sb, "fornecedores")
    categ_set      = _set_nomes(sb, "categorias_despesa")
    print(f"  obras={len(obras_set)}, etapas={len(etapas_set)}, "
          f"fornecedores={len(forn_set)}, categorias={len(categ_set)}")

    # ── 2. Lê Excel ──────────────────────────────────────────────────────────
    print("\nLendo aba 'C Despesas' do Excel...")
    df = pd.read_excel(CAMINHO_EXCEL, sheet_name="C Despesas")
    df.columns = df.columns.str.strip()
    print(f"  -> {len(df)} linhas lidas.")

    # Detecta colunas dinamicamente
    def _col(keyword, required=False):
        found = next((c for c in df.columns if keyword.lower() in c.lower()), None)
        if required and found is None:
            raise KeyError(f"Coluna com '{keyword}' nao encontrada. Colunas: {list(df.columns)}")
        return found

    col_obra  = _col("obra",  required=True)
    col_etapa = _col("etapa", required=True)
    col_valor = next((c for c in df.columns if "valor" in c.lower() and "total" in c.lower()), None)
    if col_valor is None:
        raise KeyError("Coluna 'VALOR TOTAL' nao encontrada.")
    col_data   = _col("data",      required=True)
    col_tipo   = _col("tipo")
    col_forn   = _col("fornecedor")
    col_desp   = _col("despesa")
    col_desc   = next((c for c in df.columns if "descri" in c.lower()), None)
    col_banco  = _col("banco")
    col_forma  = _col("forma")
    col_nf     = next((c for c in df.columns if "nota" in c.lower() or "nf" in c.lower()), None)

    # ── 3. Converte datas e filtra linhas invalidas ───────────────────────────
    df["_data"] = pd.to_datetime(df[col_data], errors="coerce")
    df["_valor"] = pd.to_numeric(df[col_valor], errors="coerce").fillna(0)
    antes = len(df)
    df = df.dropna(subset=["_data"])
    df = df[df[col_obra].notna() & (df[col_obra].astype(str).str.strip() != "")]
    df = df[df[col_etapa].notna() & (df[col_etapa].astype(str).str.strip() != "")]
    print(f"  -> {len(df)} linhas validas (descartadas {antes - len(df)} sem data/obra/etapa).")

    # ── 4. Verifica duplicatas ja existentes em c_despesas ────────────────────
    res_exist = sb.table("c_despesas").select("obra,etapa,valor_total,data").execute()
    chaves_existentes = set()
    for r in res_exist.data:
        dt = str(r["data"])[:10] if r["data"] else ""
        chaves_existentes.add(f"{r['obra']}|{r['etapa']}|{round(float(r['valor_total']),2)}|{dt}")

    print(f"  -> {len(chaves_existentes)} registros ja existem em c_despesas.")

    # ── 5. Monta registros para inserir ──────────────────────────────────────
    registros = []
    pulados = 0

    for _, row in df.iterrows():
        obra  = NORMALIZAR_OBRAS.get(str(row[col_obra]).strip(), str(row[col_obra]).strip())
        etapa = str(row[col_etapa]).strip()
        valor = round(float(row["_valor"]), 2)
        data  = row["_data"].strftime("%Y-%m-%d")

        # Chave de deduplicacao
        chave = f"{obra}|{etapa}|{valor}|{data}"
        if chave in chaves_existentes:
            pulados += 1
            continue

        # Garante FK obrigatorias
        _garantir_obra(sb, obras_set, obra)
        _garantir_etapa(sb, etapas_set, etapa)

        # Fornecedor (opcional)
        forn = str(row[col_forn]).strip() if col_forn and pd.notna(row.get(col_forn)) else None
        if forn == "" or forn == "nan":
            forn = None
        if forn:
            _garantir_fornecedor(sb, forn_set, forn)

        # Tipo
        tipo_raw = str(row[col_tipo]).strip() if col_tipo and pd.notna(row.get(col_tipo)) else "Geral"
        tipo = NORMALIZAR_TIPOS.get(tipo_raw, tipo_raw)
        if tipo not in TIPOS_VALIDOS:
            tipo = "Geral"

        # Categoria de despesa (NULL se nao encontrada)
        desp_val = str(row[col_desp]).strip() if col_desp and pd.notna(row.get(col_desp)) else None
        if desp_val in ("", "nan", None):
            desp_val = None
        if desp_val and desp_val not in categ_set:
            desp_val = None  # nao adiciona categoria desconhecida

        # Descricao
        desc = str(row[col_desc]).strip() if col_desc and pd.notna(row.get(col_desc)) else None
        if desc in ("", "nan"):
            desc = None

        # Banco
        banco = str(row[col_banco]).strip() if col_banco and pd.notna(row.get(col_banco)) else None
        if banco in ("", "nan"):
            banco = None

        # Forma de pagamento
        forma_raw = str(row[col_forma]).strip() if col_forma and pd.notna(row.get(col_forma)) else None
        forma = forma_raw if forma_raw in FORMAS_VALIDAS else None

        # Nota fiscal
        nf = None
        if col_nf and pd.notna(row.get(col_nf)):
            val_nf = row[col_nf]
            if isinstance(val_nf, bool):
                nf = val_nf
            elif str(val_nf).strip().upper() in ("SIM", "TRUE", "1", "S", "YES"):
                nf = True
            elif str(val_nf).strip().upper() in ("NAO", "NÃO", "FALSE", "0", "N", "NO"):
                nf = False

        registros.append({
            "obra":           obra,
            "etapa":          etapa,
            "tipo":           tipo,
            "fornecedor":     forn,
            "despesa":        desp_val,
            "valor_total":    valor,
            "data":           data,
            "descricao":      desc,
            "banco":          banco,
            "forma":          forma,
            "tem_nota_fiscal": nf,
        })
        chaves_existentes.add(chave)

    print(f"\n  -> {len(registros)} novos registros para inserir ({pulados} ja existiam).")

    # ── 6. Insere em batches ──────────────────────────────────────────────────
    if registros:
        BATCH = 100
        for i in range(0, len(registros), BATCH):
            sb.table("c_despesas").insert(registros[i:i + BATCH]).execute()
            print(f"  Inseridos {min(i + BATCH, len(registros))}/{len(registros)}...")
        print(f"\nOK: {len(registros)} despesas inseridas em c_despesas!")
    else:
        print("OK: Nenhum registro novo para inserir.")

    # ── 7. Contagem final ─────────────────────────────────────────────────────
    total = sb.table("c_despesas").select("id", count="exact").execute()
    print(f"Total atual em c_despesas: {total.count} registros.")


if __name__ == "__main__":
    main()
