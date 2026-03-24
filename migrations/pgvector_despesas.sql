-- =============================================================
-- Migração: pgvector para busca semântica de despesas
-- Executar no SQL Editor do Supabase (uma vez)
-- =============================================================

-- 1. Habilitar extensão pgvector
create extension if not exists vector;

-- 2. Tabela de embeddings (separada de c_despesas para não inflar a tabela principal)
create table if not exists despesas_vetores (
    despesa_id  integer     primary key references c_despesas(id) on delete cascade,
    texto       text        not null,
    embedding   vector(1536) not null,
    updated_at  timestamptz default now()
);

-- 3. Índice HNSW (melhor custo-benefício para < 1M registros)
create index if not exists despesas_vetores_embedding_idx
    on despesas_vetores
    using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

-- 4. Função de busca por similaridade semântica
create or replace function buscar_despesas_similares(
    query_embedding vector(1536),
    match_count     int default 40
)
returns table (
    despesa_id integer,
    texto      text,
    similarity float
)
language sql stable
as $$
    select
        dv.despesa_id,
        dv.texto,
        1 - (dv.embedding <=> query_embedding) as similarity
    from despesas_vetores dv
    order by dv.embedding <=> query_embedding
    limit match_count;
$$;
