"""
criar_tabelas_referencia.py
─────────────────────────────────────────────────────────────────────────────
Cria e popula as tabelas de referência que ainda não existem no Supabase:
  - tipos_custo        (nome TEXT PRIMARY KEY)
  - formas_pagamento   (nome TEXT PRIMARY KEY)
  - categorias_despesa (nome TEXT PRIMARY KEY)  ← seed se vazia

As tabelas precisam ser criadas manualmente no Supabase antes de rodar:

  CREATE TABLE tipos_custo (
      nome TEXT PRIMARY KEY
  );

  CREATE TABLE formas_pagamento (
      nome TEXT PRIMARY KEY
  );

Uso:
  python criar_tabelas_referencia.py
─────────────────────────────────────────────────────────────────────────────
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Tipos de Custo ─────────────────────────────────────────────────────────
TIPOS_CUSTO = ["Mão de Obra", "Materiais", "Geral"]

print("Populando tipos_custo...")
res = supabase.table("tipos_custo").upsert(
    [{"nome": v} for v in TIPOS_CUSTO], on_conflict="nome"
).execute()
print(f"  OK: {len(TIPOS_CUSTO)} registros inseridos/atualizados.")

# ── Formas de Pagamento ────────────────────────────────────────────────────
FORMAS_PAGAMENTO = ["PIX", "Boleto", "Cartão", "Dinheiro", "Transferência", "Outro"]

print("Populando formas_pagamento...")
res = supabase.table("formas_pagamento").upsert(
    [{"nome": v} for v in FORMAS_PAGAMENTO], on_conflict="nome"
).execute()
print(f"  OK: {len(FORMAS_PAGAMENTO)} registros inseridos/atualizados.")

# ── Categorias de Despesa (seed se vazia) ──────────────────────────────────
CATEGORIAS = [
    "AREIA COLCHÃO", "BLOCO INTERTRAVADO", "CALCETEIRO", "ESTACAS",
    "MEIO-FIO", "PARALELEPÍPEDO", "PEDRA CORTADA", "PÓ DE PEDRA", "SOLO-BRITA",
    "AÇO / VERGALHÃO", "ADITIVOS", "AREIA LAVADA", "ARGAMASSA",
    "BLOCO CERÂMICO", "BLOCO DE CIMENTO", "BRITA GRAVILHÃO", "CIMENTO",
    "COMBOGÓ", "FERRO", "MADERITE", "PREGO", "TÁBUA",
    "BLOCO CALHA", "MADEIRA P/ TELHADO", "TELHA CERÂMICA", "TELHA FIBROCIMENTO",
    "BOMBA", "CABOS", "CAIXA D'ÁGUA", "DISJUNTORES",
    "ELETRODUTO E CONEXÕES", "EMPREITEIRO ELETRICISTA", "EMPREITEIRO ENCANADOR",
    "TUBO ÁGUA E CONEXÕES", "TUBO ESGOTO E CONEXÕES",
    "ESQUADRIA DE FERRO", "ESQUADRIA DE MADEIRA", "GESSO ACARTONADO",
    "LOUÇAS", "LUMINÁRIAS", "SOLDA",
    "COMPRA EQUIPAMENTOS", "DIVERSOS", "EMPREITEIRO", "ENTULHO",
    "EQUIPAMENTOS URBANOS", "FARDAS E EPIS", "LOCAÇÃO EQUIPAMENTOS",
    "MADEIRA LOCAÇÃO OBRA", "MADEIRA TRATADA", "PAISAGISMO", "PROJETOS",
    "ÁGUA", "ALUGUEL", "CONDOMÍNIO", "CONTABILIDADE", "ENERGIA",
    "IMPRESSÃO / GRÁFICA", "INTERNET / TI", "MANUTENÇÃO",
    "MATERIAL PARA ESCRITÓRIO", "TELEFONIA FIXA", "TELEFONIA MÓVEL",
    "ALIMENTAÇÃO", "COMBUSTÍVEL", "DIÁRIA", "FERRYBOAT / BALSA",
    "HOSPEDAGEM", "PEDÁGIO", "SALÁRIO PESSOAL", "TRANSPORTE",
    "IMPOSTOS", "JUROS", "RECEITA", "REPOSIÇÃO DE CAIXA",
]

print("Populando categorias_despesa...")
res = supabase.table("categorias_despesa").upsert(
    [{"nome": v} for v in CATEGORIAS], on_conflict="nome"
).execute()
print(f"  OK: {len(CATEGORIAS)} registros inseridos/atualizados.")

print("\nConcluído!")
