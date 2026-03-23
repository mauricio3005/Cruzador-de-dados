"""
importar_apuarema.py
─────────────────────────────────────────────────────────────────────────────
Lê c_despesas_apuarema.xlsx (raiz do projeto) e insere as despesas da obra
"Quadra apuarema" em c_despesas no Supabase.

Usa httpx diretamente (REST API) para evitar travamento do supabase-py 2.x
na inicialização do cliente realtime.

Seguro para re-rodar: pula registros já existentes (deduplicação por
obra+etapa+valor_total+data).
─────────────────────────────────────────────────────────────────────────────
"""

import json
import os

import httpx
import pandas as pd
from dotenv import load_dotenv

CAMINHO_EXCEL = os.path.join(os.path.dirname(__file__), "c_despesas_apuarema.xlsx")

NORMALIZAR_TIPOS = {
    "GERAL":        "Geral",
    "MATERIAL":     "Materiais",
    "MATERIAIS":    "Materiais",
    "MÃO DE OBRA":  "Mão de Obra",
    "MAO DE OBRA":  "Mão de Obra",
    "MAO-DE-OBRA":  "Mão de Obra",
    "MÃO-DE-OBRA":  "Mão de Obra",
}
TIPOS_VALIDOS  = {"Mão de Obra", "Materiais", "Geral"}
FORMAS_VALIDAS = {"PIX", "Boleto", "Cartão", "Dinheiro", "Transferência", "Outro"}


class SupabaseREST:
    """Cliente HTTP mínimo para a API REST do Supabase (sem realtime)."""

    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey":        key,
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
            "Prefer":        "return=minimal",
        }
        self._http = httpx.Client(timeout=30)

    def select(self, tabela: str, cols: str = "*", params: dict | None = None) -> list:
        p = {"select": cols}
        if params:
            p.update(params)
        r = self._http.get(f"{self.base}/{tabela}", headers=self.headers, params=p)
        r.raise_for_status()
        return r.json()

    def insert(self, tabela: str, payload: list | dict) -> None:
        data = payload if isinstance(payload, list) else [payload]
        r = self._http.post(
            f"{self.base}/{tabela}",
            headers=self.headers,
            content=json.dumps(data),
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Erro ao inserir em '{tabela}': {r.status_code} {r.text}")

    def count(self, tabela: str) -> int:
        h = {**self.headers, "Prefer": "count=exact"}
        r = self._http.get(f"{self.base}/{tabela}", headers=h, params={"select": "id"})
        r.raise_for_status()
        return int(r.headers.get("content-range", "*/0").split("/")[-1])

    def close(self):
        self._http.close()


def _carregar_credenciais():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_KEY")
           or os.getenv("SUPABASE_ANON_KEY"))
    if not url or not key:
        raise RuntimeError("Credenciais do Supabase não encontradas no .env")
    return url, key


def _set_nomes(sb: SupabaseREST, tabela: str, campo: str = "nome") -> set:
    rows = sb.select(tabela, campo)
    return {r[campo] for r in rows}


def _garantir_obra(sb, obras_set, nome):
    if nome not in obras_set:
        sb.insert("obras", {"nome": nome})
        obras_set.add(nome)
        print(f"  [novo] obra inserida: '{nome}'")


def _garantir_etapa(sb, etapas_set, nome):
    if nome not in etapas_set:
        sb.insert("etapas", {"nome": nome, "ordem": 999})
        etapas_set.add(nome)
        print(f"  [novo] etapa inserida: '{nome}' (ordem=999)")


def _garantir_fornecedor(sb, forn_set, nome):
    if nome and nome not in forn_set:
        sb.insert("fornecedores", {"nome": nome})
        forn_set.add(nome)
        print(f"  [novo] fornecedor inserido: '{nome}'")


def _str_or_none(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return None if s in ("", "nan", "None") else s


def main():
    if not os.path.exists(CAMINHO_EXCEL):
        print(f"ERRO: arquivo não encontrado:\n  {CAMINHO_EXCEL}")
        return

    print("Conectando ao Supabase...")
    url, key = _carregar_credenciais()
    sb = SupabaseREST(url, key)

    # Teste rápido de conectividade
    sb.select("obras", "nome", {"limit": "1"})
    print("Conectado.\n")

    # ── 1. Carrega tabelas de referência ──────────────────────────────────────
    print("Carregando tabelas de referência...")
    obras_set  = _set_nomes(sb, "obras")
    etapas_set = _set_nomes(sb, "etapas")
    forn_set   = _set_nomes(sb, "fornecedores")
    categ_set  = _set_nomes(sb, "categorias_despesa")
    print(f"  obras={len(obras_set)}, etapas={len(etapas_set)}, "
          f"fornecedores={len(forn_set)}, categorias={len(categ_set)}")

    # ── 2. Lê Excel ───────────────────────────────────────────────────────────
    print(f"\nLendo {CAMINHO_EXCEL}...")
    df = pd.read_excel(CAMINHO_EXCEL)
    df.columns = df.columns.str.strip()
    print(f"  -> {len(df)} linhas lidas. Colunas: {df.columns.tolist()}")

    df["_data"]  = pd.to_datetime(df["DATA"], errors="coerce")
    df["_valor"] = pd.to_numeric(df["VALOR TOTAL"], errors="coerce").fillna(0)

    antes = len(df)
    df = df.dropna(subset=["_data"])
    df = df[df["OBRA"].notna() & (df["OBRA"].astype(str).str.strip() != "")]
    df = df[df["ETAPA"].notna() & (df["ETAPA"].astype(str).str.strip() != "")]
    print(f"  -> {len(df)} linhas válidas (descartadas {antes - len(df)} sem data/obra/etapa).")

    # ── 3. Verifica duplicatas já existentes ──────────────────────────────────
    print("\nVerificando duplicatas em c_despesas...")
    existentes = sb.select("c_despesas", "obra,etapa,valor_total,data")
    chaves_existentes: set[str] = set()
    for r in existentes:
        dt = str(r["data"])[:10] if r["data"] else ""
        chaves_existentes.add(
            f"{r['obra']}|{r['etapa']}|{round(float(r['valor_total']),2)}|{dt}"
        )
    print(f"  -> {len(chaves_existentes)} registros já existem em c_despesas.")

    # ── 4. Monta registros para inserir ───────────────────────────────────────
    col_desc = next((c for c in df.columns if "descri" in c.lower()), None)
    registros: list[dict] = []
    pulados = 0

    for _, row in df.iterrows():
        obra  = str(row["OBRA"]).strip()
        etapa = str(row["ETAPA"]).strip()
        valor = round(float(row["_valor"]), 2)
        data  = row["_data"].strftime("%Y-%m-%d")

        chave = f"{obra}|{etapa}|{valor}|{data}"
        if chave in chaves_existentes:
            pulados += 1
            continue

        _garantir_obra(sb, obras_set, obra)
        _garantir_etapa(sb, etapas_set, etapa)

        tipo_raw = _str_or_none(row.get("TIPO")) or "Geral"
        tipo = NORMALIZAR_TIPOS.get(tipo_raw.upper(), NORMALIZAR_TIPOS.get(tipo_raw, tipo_raw))
        if tipo not in TIPOS_VALIDOS:
            tipo = "Geral"

        forn = _str_or_none(row.get("FORNECEDOR"))
        if forn:
            _garantir_fornecedor(sb, forn_set, forn)

        desp_val = _str_or_none(row.get("DESPESA"))
        if desp_val and desp_val not in categ_set:
            print(f"  [aviso] categoria '{desp_val}' não encontrada — NULL")
            desp_val = None

        desc      = _str_or_none(row.get(col_desc)) if col_desc else None
        banco     = _str_or_none(row.get("BANCO"))
        forma_raw = _str_or_none(row.get("FORMA"))
        forma     = forma_raw if forma_raw in FORMAS_VALIDAS else None

        registros.append({
            "obra":            obra,
            "etapa":           etapa,
            "tipo":            tipo,
            "fornecedor":      forn,
            "despesa":         desp_val,
            "valor_total":     valor,
            "data":            data,
            "descricao":       desc,
            "banco":           banco,
            "forma":           forma,
            "tem_nota_fiscal": False,
        })
        chaves_existentes.add(chave)

    print(f"\n  -> {len(registros)} novos registros para inserir ({pulados} já existiam).")

    # ── 5. Insere em batches ──────────────────────────────────────────────────
    if registros:
        BATCH = 100
        for i in range(0, len(registros), BATCH):
            sb.insert("c_despesas", registros[i:i + BATCH])
            print(f"  Inseridos {min(i + BATCH, len(registros))}/{len(registros)}...")
        print(f"\nOK: {len(registros)} despesas inseridas em c_despesas!")
    else:
        print("OK: Nenhum registro novo para inserir (todos já existiam).")

    total = sb.count("c_despesas")
    print(f"Total atual em c_despesas: {total} registros.")
    sb.close()


if __name__ == "__main__":
    main()
