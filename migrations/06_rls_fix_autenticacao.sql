-- migrations/06_rls_fix_autenticacao.sql
-- Corrige políticas RLS permissivas e habilita RLS nas tabelas principais.
-- ATENÇÃO: executar manualmente no SQL Editor do Supabase.
-- Idempotente: seguro re-executar.

-- ── 1. Remove políticas permissivas de migrações anteriores ────────────────

-- migrations/00_contratos_etapas_pagamentos.sql
DROP POLICY IF EXISTS "Allow all authenticated (etapas)" ON contratos_etapas;
DROP POLICY IF EXISTS "Allow all authenticated (pagamentos)" ON contratos_pagamentos;

-- migrations/02_empresas.sql
DROP POLICY IF EXISTS "allow_all_empresas" ON empresas;

-- migrations/03_obra_etapas.sql
DROP POLICY IF EXISTS "anon full access" ON obra_etapas;

-- migrations/04_remessas_caixa.sql
DROP POLICY IF EXISTS "anon full access" ON remessas_caixa;

-- ── 2. Habilita RLS nas tabelas principais ─────────────────────────────────

ALTER TABLE c_despesas          ENABLE ROW LEVEL SECURITY;
ALTER TABLE recebimentos         ENABLE ROW LEVEL SECURITY;
ALTER TABLE folhas               ENABLE ROW LEVEL SECURITY;
ALTER TABLE folha_funcionarios   ENABLE ROW LEVEL SECURITY;
ALTER TABLE contratos            ENABLE ROW LEVEL SECURITY;
ALTER TABLE contratos_etapas     ENABLE ROW LEVEL SECURITY;
ALTER TABLE contratos_pagamentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE orcamentos           ENABLE ROW LEVEL SECURITY;
ALTER TABLE obras                ENABLE ROW LEVEL SECURITY;
ALTER TABLE obra_etapas          ENABLE ROW LEVEL SECURITY;
ALTER TABLE remessas_caixa       ENABLE ROW LEVEL SECURITY;
ALTER TABLE empresas             ENABLE ROW LEVEL SECURITY;
ALTER TABLE despesas_recorrentes ENABLE ROW LEVEL SECURITY;
ALTER TABLE comprovantes_despesa ENABLE ROW LEVEL SECURITY;

-- ── 3. Cria políticas: apenas usuários autenticados têm acesso ─────────────
-- (service_role bypassa RLS automaticamente — backend continua funcionando)

DO $$
DECLARE
  tbl TEXT;
  tbls TEXT[] := ARRAY[
    'c_despesas', 'recebimentos', 'folhas', 'folha_funcionarios',
    'contratos', 'contratos_etapas', 'contratos_pagamentos',
    'orcamentos', 'obras', 'obra_etapas', 'remessas_caixa',
    'empresas', 'despesas_recorrentes', 'comprovantes_despesa'
  ];
BEGIN
  FOREACH tbl IN ARRAY tbls LOOP
    -- Evita duplicar policies
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies WHERE tablename = tbl AND policyname = 'authenticated_only'
    ) THEN
      EXECUTE format(
        'CREATE POLICY authenticated_only ON %I FOR ALL TO authenticated USING (true) WITH CHECK (true)',
        tbl
      );
    END IF;
  END LOOP;
END $$;

-- ── 4. Tabelas de referência mantêm leitura pública ───────────────────────

ALTER TABLE tipos_custo          ENABLE ROW LEVEL SECURITY;
ALTER TABLE formas_pagamento     ENABLE ROW LEVEL SECURITY;
ALTER TABLE fornecedores         ENABLE ROW LEVEL SECURITY;
ALTER TABLE categorias_despesa   ENABLE ROW LEVEL SECURITY;
ALTER TABLE etapas               ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
  tbl TEXT;
  tbls TEXT[] := ARRAY['tipos_custo', 'formas_pagamento', 'fornecedores', 'categorias_despesa', 'etapas'];
BEGIN
  FOREACH tbl IN ARRAY tbls LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies WHERE tablename = tbl AND policyname = 'public_read'
    ) THEN
      EXECUTE format(
        'CREATE POLICY public_read ON %I FOR SELECT TO anon, authenticated USING (true)',
        tbl
      );
    END IF;
  END LOOP;
END $$;
