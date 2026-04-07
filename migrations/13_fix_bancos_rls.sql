-- migrations/13_fix_bancos_rls.sql
-- Habilita RLS e garante acesso completo (anon + authenticated) nas tabelas
-- bancos e banco_obras. Seguro re-executar (DROP IF EXISTS antes de CREATE).

-- ── bancos ────────────────────────────────────────────────────────────────────
ALTER TABLE bancos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon full access"          ON bancos;
DROP POLICY IF EXISTS "authenticated full access" ON bancos;

CREATE POLICY "anon full access"
  ON bancos FOR ALL TO anon
  USING (true) WITH CHECK (true);

CREATE POLICY "authenticated full access"
  ON bancos FOR ALL TO authenticated
  USING (true) WITH CHECK (true);

-- ── banco_obras ───────────────────────────────────────────────────────────────
ALTER TABLE banco_obras ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon full access"          ON banco_obras;
DROP POLICY IF EXISTS "authenticated full access" ON banco_obras;

CREATE POLICY "anon full access"
  ON banco_obras FOR ALL TO anon
  USING (true) WITH CHECK (true);

CREATE POLICY "authenticated full access"
  ON banco_obras FOR ALL TO authenticated
  USING (true) WITH CHECK (true);

-- Força o PostgREST a recarregar o schema
NOTIFY pgrst, 'reload schema';
