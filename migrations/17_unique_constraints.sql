-- migrations/17_unique_constraints.sql
-- 1. Deduplica e adiciona UNIQUE(obra, etapa) em taxa_conclusao
-- 2. Deduplica e adiciona UNIQUE(obra, etapa, tipo_custo) em orcamentos
-- 3. Corrige created_at sem timezone em contratos e contratos_pagamentos
-- 4. Adiciona CHECK de status em folhas e obras

-- ============================================================
-- taxa_conclusao — UNIQUE(obra, etapa)
-- ============================================================
-- Remove duplicatas mantendo o registro com maior taxa (mais atual).
-- Se preferir manter o mais recente pelo id, troque MAX(taxa) por MAX(id).
DELETE FROM taxa_conclusao
WHERE id NOT IN (
    SELECT MAX(id)
    FROM taxa_conclusao
    GROUP BY obra, etapa
);

ALTER TABLE taxa_conclusao
    ADD CONSTRAINT uq_taxa_conclusao_obra_etapa UNIQUE (obra, etapa);

-- ============================================================
-- orcamentos — UNIQUE(obra, etapa, tipo_custo)
-- ============================================================
-- Remove duplicatas mantendo o registro de maior id (inserção mais recente).
DELETE FROM orcamentos
WHERE id NOT IN (
    SELECT MAX(id)
    FROM orcamentos
    GROUP BY obra, etapa, tipo_custo
);

ALTER TABLE orcamentos
    ADD CONSTRAINT uq_orcamentos_obra_etapa_tipo UNIQUE (obra, etapa, tipo_custo);

-- ============================================================
-- contratos — corrigir timestamp without time zone
-- ============================================================
-- Interpreta os valores existentes como horário de Brasília (UTC-3)
-- e converte para timestamptz. Ajuste o timezone se seu servidor usar outro fuso.
ALTER TABLE contratos
    ALTER COLUMN created_at TYPE timestamp with time zone
    USING created_at AT TIME ZONE 'America/Sao_Paulo';

ALTER TABLE contratos_pagamentos
    ALTER COLUMN created_at TYPE timestamp with time zone
    USING created_at AT TIME ZONE 'America/Sao_Paulo';

-- ============================================================
-- folhas — CHECK de status
-- ============================================================
-- VERIFICAÇÃO ANTES DE EXECUTAR:
--   SELECT DISTINCT status FROM folhas;
--   → deve conter apenas 'rascunho' e 'fechado'. Se houver outros valores,
--     normalize-os antes (UPDATE folhas SET status = '...' WHERE status = '...').
ALTER TABLE folhas
    ADD CONSTRAINT chk_folhas_status
    CHECK (status IN ('rascunho', 'fechada'));

-- ============================================================
-- obras — CHECK de status
-- ============================================================
-- VERIFICAÇÃO ANTES DE EXECUTAR:
--   SELECT DISTINCT status FROM obras;
--   → normalize valores inesperados antes de adicionar o constraint.
ALTER TABLE obras
    ADD CONSTRAINT chk_obras_status
    CHECK (status IN ('ativo', 'concluido', 'pausado', 'cancelado'));

NOTIFY pgrst, 'reload schema';
