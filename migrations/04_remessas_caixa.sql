-- Migration 04: Remessas de Caixa — ajustes
-- Executar manualmente no SQL Editor do Supabase

-- Remove tabela de contas bancárias (não necessária no modelo simplificado)
DROP TABLE IF EXISTS contas_bancarias;

-- Adiciona coluna de comprovante (se a tabela já existir sem ela)
ALTER TABLE remessas_caixa ADD COLUMN IF NOT EXISTS comprovante_url TEXT;

-- RLS: frontend usa anon key diretamente
ALTER TABLE remessas_caixa ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon full access" ON remessas_caixa
  FOR ALL TO anon
  USING (true)
  WITH CHECK (true);

-- Recarrega o schema do PostgREST
NOTIFY pgrst, 'reload schema';
