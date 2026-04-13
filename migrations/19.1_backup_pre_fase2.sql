-- migrations/19.1_backup_pre_fase2.sql
-- Backup completo de dados antes da Fase 2 (remoção das colunas texto).
-- Cria um schema "backup" com cópias de todas as tabelas públicas.
-- Seguro re-executar: usa IF NOT EXISTS em tudo.
--
-- Para restaurar uma tabela:
--   INSERT INTO public.obras SELECT * FROM backup.obras;
--   (ajuste conforme necessidade — pode haver conflito de PKs)

-- ── Cria o schema de backup ───────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS backup;

-- ── Tabelas de domínio (sem dependências) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.empresas            AS SELECT * FROM public.empresas;
CREATE TABLE IF NOT EXISTS backup.etapas              AS SELECT * FROM public.etapas;
CREATE TABLE IF NOT EXISTS backup.formas_pagamento    AS SELECT * FROM public.formas_pagamento;
CREATE TABLE IF NOT EXISTS backup.tipos_custo         AS SELECT * FROM public.tipos_custo;
CREATE TABLE IF NOT EXISTS backup.fornecedores        AS SELECT * FROM public.fornecedores;
CREATE TABLE IF NOT EXISTS backup.categorias_despesa  AS SELECT * FROM public.categorias_despesa;
CREATE TABLE IF NOT EXISTS backup.bancos              AS SELECT * FROM public.bancos;

-- ── Obras ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.obras               AS SELECT * FROM public.obras;

-- ── Junction tables (dependem de obras, etapas, bancos) ───────────────────────
CREATE TABLE IF NOT EXISTS backup.obra_etapas         AS SELECT * FROM public.obra_etapas;
CREATE TABLE IF NOT EXISTS backup.banco_obras         AS SELECT * FROM public.banco_obras;

-- ── Folha de pagamento ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.folhas              AS SELECT * FROM public.folhas;
CREATE TABLE IF NOT EXISTS backup.folha_regras        AS SELECT * FROM public.folha_regras;
CREATE TABLE IF NOT EXISTS backup.folha_funcionarios  AS SELECT * FROM public.folha_funcionarios;

-- ── Orçamentos e taxa de conclusão ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.orcamentos          AS SELECT * FROM public.orcamentos;
CREATE TABLE IF NOT EXISTS backup.taxa_conclusao      AS SELECT * FROM public.taxa_conclusao;

-- ── Recebimentos ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.recebimentos        AS SELECT * FROM public.recebimentos;

-- ── Contratos ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.contratos           AS SELECT * FROM public.contratos;
CREATE TABLE IF NOT EXISTS backup.contratos_etapas    AS SELECT * FROM public.contratos_etapas;
CREATE TABLE IF NOT EXISTS backup.contratos_pagamentos AS SELECT * FROM public.contratos_pagamentos;

-- ── Despesas recorrentes ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.despesas_recorrentes AS SELECT * FROM public.despesas_recorrentes;

-- ── Despesas (tabela mais crítica) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.c_despesas          AS SELECT * FROM public.c_despesas;
CREATE TABLE IF NOT EXISTS backup.comprovantes_despesa AS SELECT * FROM public.comprovantes_despesa;
CREATE TABLE IF NOT EXISTS backup.despesas_vetores    AS SELECT * FROM public.despesas_vetores;

-- ── Remessas ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backup.remessas_caixa      AS SELECT * FROM public.remessas_caixa;

-- ── Resumo do backup ──────────────────────────────────────────────────────────
SELECT
    tablename                          AS tabela,
    (xpath('/row/c/text()',
        query_to_xml('SELECT COUNT(*) AS c FROM backup.' || tablename, false, true, '')
    ))[1]::text::integer               AS linhas
FROM pg_tables
WHERE schemaname = 'backup'
ORDER BY tablename;
