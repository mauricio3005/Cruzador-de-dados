-- =============================================================
-- Migração: Despesas Recorrentes
-- Executar no SQL Editor do Supabase (uma vez)
-- =============================================================

create table if not exists despesas_recorrentes (
    id              serial          primary key,
    obra            text,
    etapa           text,
    tipo            text,
    fornecedor      text,
    despesa         text,           -- categoria
    valor_total     numeric(12,2)   not null,
    descricao       text,
    banco           text,
    forma           text,
    frequencia      text            not null check (frequencia in ('mensal','trimestral','semestral','anual')),
    proxima_data    date            not null,
    data_fim        date,           -- nullable — sem fim se null
    ativa           boolean         not null default true,
    created_at      timestamptz     default now()
);

-- Índice para processar somente registros ativos com proxima_data vencida
create index if not exists despesas_recorrentes_proxima_idx
    on despesas_recorrentes (proxima_data)
    where ativa = true;
