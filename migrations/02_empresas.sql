-- Migration: 02_empresas.sql
-- Criação da tabela empresas e vínculo com obras
-- Executar manualmente no SQL Editor do Supabase

-- Tabela de empresas (cada obra pertence a uma empresa)
CREATE TABLE IF NOT EXISTS empresas (
  id          SERIAL PRIMARY KEY,
  nome        TEXT UNIQUE NOT NULL,
  cnpj        TEXT,
  logo_url    TEXT,          -- URL pública no Supabase Storage (bucket: logos)
  endereco    TEXT,
  telefone    TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Vincular obras a uma empresa (nullable para compatibilidade com dados existentes)
ALTER TABLE obras
  ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL;

-- RLS permissivo (anon pode ler; service_role faz tudo)
ALTER TABLE empresas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_empresas"
  ON empresas
  FOR ALL
  USING (true)
  WITH CHECK (true);

-- Criar bucket para logos (executar separadamente se necessário via Storage API)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('logos', 'logos', true)
-- ON CONFLICT (id) DO NOTHING;

-- Política de storage para o bucket logos
-- CREATE POLICY "logos_public_read" ON storage.objects FOR SELECT USING (bucket_id = 'logos');
-- CREATE POLICY "logos_auth_write" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'logos');
-- CREATE POLICY "logos_auth_delete" ON storage.objects FOR DELETE USING (bucket_id = 'logos');

-- Notificar PostgREST para recarregar o schema
NOTIFY pgrst, 'reload schema';
