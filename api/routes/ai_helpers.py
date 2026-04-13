"""Helpers compartilhados entre os módulos de IA (normalização, OpenAI, cache de referências)."""

import datetime
import json
import os
import time
import unicodedata
from functools import lru_cache

from fastapi import HTTPException

from api.logger import get_logger
from api.supabase_client import get_supabase as _get_supabase

logger = get_logger(__name__)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


# ---------------------------------------------------------------------------
# Helpers de normalização (usados em tool calling e busca híbrida)
# ---------------------------------------------------------------------------

def _normalizar(s: str) -> str:
    """Remove acentos e converte para minúsculas."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def _melhor_match(candidatos: list, query: str) -> str | None:
    """Retorna o candidato com mais palavras (>3 letras) presentes na query."""
    best, best_score = None, 0
    for c in candidatos:
        palavras = [p for p in _normalizar(c).split() if len(p) > 3]
        score = sum(1 for p in palavras if p in query)
        if score > best_score:
            best_score, best = score, c
    return best if best_score > 0 else None


def _normalizar_fornecedor(nome: str | None, lista: list[str]) -> str | None:
    """Retorna o fornecedor da lista mais próximo, ou None se não houver match."""
    if not nome or not lista:
        return nome
    return _melhor_match(lista, _normalizar(nome))


# ---------------------------------------------------------------------------
# OpenAI client + JSON parser
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_openai():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não configurada")
    return OpenAI(api_key=api_key)


def _parse_json_response(text: str):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


# ---------------------------------------------------------------------------
# Cache de referências (obras, etapas, fornecedores, categorias)
# ---------------------------------------------------------------------------

_refs_cache: dict = {}
_refs_cache_ts: float = 0.0
_REFS_TTL = 120  # segundos


def _get_referencias() -> dict:
    """Busca obras, etapas, fornecedores e categorias do Supabase (cache de 2 min)."""
    global _refs_cache, _refs_cache_ts
    if _refs_cache and (time.monotonic() - _refs_cache_ts) < _REFS_TTL:
        return _refs_cache
    db = _get_supabase()
    obras      = [r["nome"] for r in (db.table("obras").select("nome").order("nome").execute().data or [])]
    etapas     = [r["nome"] for r in (db.table("etapas").select("nome").order("nome").execute().data or [])]
    fornecs    = [r["nome"] for r in (db.table("fornecedores").select("nome").order("nome").execute().data or [])]
    categorias = [r["nome"] for r in (db.table("categorias_despesa").select("nome").order("nome").execute().data or [])]
    _refs_cache = {"obras": obras, "etapas": etapas, "fornecedores": fornecs, "categorias": categorias}
    _refs_cache_ts = time.monotonic()
    logger.debug("_get_referencias: cache atualizado (%d fornecs, %d obras)", len(fornecs), len(obras))
    return _refs_cache


# ---------------------------------------------------------------------------
# System prompt base (extração) — gerado dinamicamente com data atual
# ---------------------------------------------------------------------------

def _get_system_extracao() -> str:
    hoje = datetime.date.today()
    return (
        f"Data de hoje: {hoje.isoformat()} (ano {hoje.year}). "
        "Toda DATA extraída deve ser deste ano, salvo indicação explícita em contrário no documento.\n\n"
        "Você é um assistente especializado em gestão de obras e despesas da construção civil brasileira. "
        "Sua única função é extrair dados estruturados de documentos fiscais, comprovantes e textos, "
        "retornando SEMPRE JSON válido — nunca texto livre, nunca markdown, nunca explicações.\n\n"
        "REGRAS INVIOLÁVEIS:\n"
        "1. Retorne SOMENTE o JSON solicitado. Nenhum texto antes ou depois. Nenhum bloco ```json```.\n"
        "2. OBRA, ETAPA, FORNECEDOR são campos próprios — JAMAIS os coloque em DESCRICAO.\n"
        "3. FORNECEDOR: use APENAS nomes da lista fornecida. Correspondência flexível (ignore acentos, "
        "   maiúsculas, abreviações). Se nenhum nome da lista for claramente compatível, retorne null — "
        "   NUNCA invente um fornecedor novo.\n"
        "4. DESCRICAO: descreva o material/serviço em 2 a 6 palavras, em Title Case "
        "   (primeira letra maiúscula em cada palavra relevante). Inclua especificações quando disponíveis "
        "   (marca, medida, local). Exemplos corretos: 'Cimento CP-II 50kg', 'Café da Manhã', "
        "   'Sapatas de Concreto', 'Pedágio BA-093', 'Reboco Externo Fachada', 'Locação de Andaime'. "
        "   Nunca use só uma palavra. Nunca repita obra, etapa ou fornecedor na descrição.\n"
        "5. DESPESA deve ser exatamente um dos valores da lista de categorias, ou null. "
        "   Nunca use sinônimos nem variações.\n"
        "6. TIPO deve ser exatamente 'Mão de Obra', 'Materiais' ou 'Geral'. "
        "   Use 'Mão de Obra' para serviços/empreiteiros; 'Materiais' para insumos físicos; "
        "   'Geral' para despesas administrativas/operacionais.\n"
        "7. FORMA deve ser exatamente 'PIX', 'Boleto', 'Cartão', 'Dinheiro' ou 'Transferência', ou null.\n"
        "8. DATA deve estar no formato YYYY-MM-DD, ou null se não encontrada.\n"
        "9. VALOR_TOTAL deve ser um número float, sem símbolo de moeda, ou null.\n"
        "10. Quando houver múltiplas despesas no mesmo conteúdo, retorne um array com todas elas. "
        "    Nunca agrupe despesas distintas em uma só entrada.\n"
        "11. Campos não encontrados devem ser null — nunca string vazia, nunca 'N/A'.\n"
        "12. Quando um único comprovante ou documento cobrir mais de uma despesa (ex: uma NF com itens "
        "    de categorias ou etapas diferentes, ou um PIX que paga duas notas distintas), gere uma "
        "    entrada separada para cada despesa E atribua a todas elas o mesmo valor no campo _grupo "
        "    (string curta, ex: 'A', 'B'). Despesas de documentos distintos que não compartilham "
        "    comprovante NÃO devem ter _grupo. Nunca coloque nada sobre comprovante na DESCRICAO.\n"
    )
