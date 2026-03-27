-- Migration 03: Tabela de vínculo explícito entre obras e etapas
-- Executar no SQL Editor do Supabase

CREATE TABLE IF NOT EXISTS obra_etapas (
  obra  TEXT NOT NULL REFERENCES obras(nome)   ON DELETE CASCADE,
  etapa TEXT NOT NULL REFERENCES etapas(nome)  ON DELETE CASCADE,
  PRIMARY KEY (obra, etapa)
);

ALTER TABLE obra_etapas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon full access" ON obra_etapas
  FOR ALL TO anon
  USING (true)
  WITH CHECK (true);
