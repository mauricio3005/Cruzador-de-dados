-- migrations/16_remessas_caixa_cleanup.sql
-- Remove a coluna legada banco_destino TEXT de remessas_caixa.
-- Pré-requisito: migration 14 aplicada (banco_destino_id FK já existe e está populado).
--
-- VERIFICAÇÃO ANTES DE EXECUTAR:
--   SELECT COUNT(*) FROM remessas_caixa WHERE banco_destino_id IS NULL;
--   → deve retornar 0. Se não, popule banco_destino_id antes de continuar.

-- ── 1. Remove o índice antigo que apontava para a coluna texto ────────────────
DROP INDEX IF EXISTS idx_remessas_banco_destino;

-- ── 2. Remove a coluna texto legada ──────────────────────────────────────────
ALTER TABLE remessas_caixa DROP COLUMN IF EXISTS banco_destino;

NOTIFY pgrst, 'reload schema';
