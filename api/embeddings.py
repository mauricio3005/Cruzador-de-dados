"""
Gerenciamento de embeddings de despesas via pgvector (Supabase).

Fluxo:
  - sync_embeddings(): embeds apenas despesas novas (sem embedding) — chamado
    automaticamente no início de cada /api/ai/chat.
  - search_despesas(query): embeds a pergunta do usuário e retorna as N
    despesas mais semanticamente similares via pgvector.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

_EMBED_MODEL = "text-embedding-3-small"
_EMBED_DIMS  = 1536
_BATCH_SIZE  = 100   # limite seguro da API de embeddings


@lru_cache(maxsize=1)
def _get_openai():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada")
    return OpenAI(api_key=api_key)


def build_texto(row: dict) -> str:
    """Serializa uma linha de c_despesas como texto para embedding."""
    parts = []
    if row.get("obra"):                parts.append(f"obra={row['obra']}")
    if row.get("etapa"):               parts.append(f"etapa={row['etapa']}")
    if row.get("fornecedor"):          parts.append(f"fornecedor={row['fornecedor']}")
    if row.get("despesa"):             parts.append(f"categoria={row['despesa']}")
    if row.get("tipo"):                parts.append(f"tipo={row['tipo']}")
    if row.get("data"):                parts.append(f"data={row['data']}")
    if row.get("valor_total") is not None:
        parts.append(f"valor=R${row['valor_total']:,.2f}")
    if row.get("descricao"):           parts.append(f"descricao={row['descricao']}")
    return " | ".join(parts)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Gera embeddings em batch via OpenAI (text-embedding-3-small)."""
    client = _get_openai()
    resp = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    return [item.embedding for item in resp.data]


MAX_SYNC_PER_RUN = int(os.getenv("EMBEDDING_SYNC_LIMIT", "200"))


def sync_embeddings(db=None) -> int:
    """
    Detecta despesas sem embedding e as processa.
    Operação idempotente — seguro chamar a cada request.
    Retorna a quantidade de registros recém-embedados.
    """
    from api.supabase_client import get_supabase
    if db is None:
        db = get_supabase()

    # IDs já embedados
    existing = db.table("despesas_vetores").select("despesa_id").execute().data or []
    existing_ids = {r["despesa_id"] for r in existing}  # integers

    # Todas as despesas
    rows = (
        db.table("c_despesas")
        .select("id, obra, etapa, fornecedor, despesa, tipo, data, valor_total, descricao")
        .execute()
        .data or []
    )

    pending = [r for r in rows if r["id"] not in existing_ids]
    pending = pending[:MAX_SYNC_PER_RUN]
    if not pending:
        return 0

    total = 0
    for i in range(0, len(pending), _BATCH_SIZE):
        batch   = pending[i : i + _BATCH_SIZE]
        textos  = [build_texto(r) for r in batch]
        embeds  = _embed_texts(textos)
        upserts = [
            {"despesa_id": r["id"], "texto": t, "embedding": e}
            for r, t, e in zip(batch, textos, embeds)
        ]
        db.table("despesas_vetores").upsert(upserts).execute()
        total += len(batch)

    return total


def search_despesas(query: str, k: int = 40, db=None) -> list[dict]:
    """
    Retorna as k despesas mais semanticamente próximas da query.
    Embeds a query, chama a RPC buscar_despesas_similares e devolve
    os dados completos das despesas encontradas.
    """
    from api.supabase_client import get_supabase
    if db is None:
        db = get_supabase()

    [query_emb] = _embed_texts([query])

    result = db.rpc(
        "buscar_despesas_similares",
        {"query_embedding": query_emb, "match_count": k},
    ).execute()

    similares = result.data or []
    if not similares:
        return []

    ids = [r["despesa_id"] for r in similares]
    despesas = (
        db.table("c_despesas")
        .select("id, obra, etapa, fornecedor, despesa, tipo, data, valor_total, descricao")
        .in_("id", ids)
        .execute()
        .data or []
    )
    return despesas
