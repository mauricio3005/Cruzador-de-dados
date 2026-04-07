-- migrations/10_rls_tabelas_referencia_write.sql
-- Corrige acesso de escrita às tabelas de referência.
--
-- O migration 06_rls_fix_autenticacao.sql habilitou RLS em fornecedores,
-- formas_pagamento, categorias_despesa e etapas criando apenas política
-- public_read (SELECT). Resultado: usuários autenticados não conseguem
-- INSERT/UPDATE/DELETE nessas tabelas pelo frontend (anon key).
--
-- Fix: adiciona política authenticated_write (ALL) para role authenticated.
-- A política public_read existente continua válida para leitura anônima.
--
-- Idempotente: seguro re-executar.

DO $$
DECLARE
  tbl TEXT;
  tbls TEXT[] := ARRAY['fornecedores', 'formas_pagamento', 'categorias_despesa', 'etapas'];
BEGIN
  FOREACH tbl IN ARRAY tbls LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies WHERE tablename = tbl AND policyname = 'authenticated_write'
    ) THEN
      EXECUTE format(
        'CREATE POLICY authenticated_write ON %I FOR ALL TO authenticated USING (true) WITH CHECK (true)',
        tbl
      );
    END IF;
  END LOOP;
END $$;
