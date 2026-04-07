-- Migration 11: Tabela de Bancos com classificação Principal/Filho
-- Executar manualmente no SQL Editor do Supabase

-- Tabela de bancos/contas com classificação de tipo
CREATE TABLE IF NOT EXISTS bancos (
    id         BIGSERIAL PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE,
    tipo       TEXT NOT NULL CHECK (tipo IN ('principal', 'filho')),
    descricao  TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS: frontend usa anon key diretamente
ALTER TABLE bancos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon full access" ON bancos
  FOR ALL TO anon
  USING (true)
  WITH CHECK (true);

-- ── Popular com dados conhecidos ─────────────────────────────────────────────

-- Bancos principais (fontes de recursos, não recebem remessas)
INSERT INTO bancos (nome, tipo, descricao) VALUES
    ('Maurício',         'principal', NULL),
    ('Marcos Cabelinho', 'principal', 'Somente obra de Teofilândia')
ON CONFLICT (nome) DO NOTHING;

-- Bancos filhos conhecidos (contas controladas)
INSERT INTO bancos (nome, tipo) VALUES
    ('Kathleen Thais',   'filho'),
    ('Diego estagiário', 'filho')
ON CONFLICT (nome) DO NOTHING;

-- Captura qualquer outro banco_destino já registrado em remessas
INSERT INTO bancos (nome, tipo)
    SELECT DISTINCT banco_destino, 'filho'
    FROM remessas_caixa
    WHERE banco_destino IS NOT NULL
    AND banco_destino NOT IN ('Maurício', 'Marcos Cabelinho', 'Kathleen Thais', 'Diego estagiário')
ON CONFLICT (nome) DO NOTHING;

-- Captura qualquer outro banco em c_despesas ainda não classificado
INSERT INTO bancos (nome, tipo)
    SELECT DISTINCT banco, 'filho'
    FROM c_despesas
    WHERE banco IS NOT NULL
    AND banco NOT IN ('Maurício', 'Marcos Cabelinho', 'Kathleen Thais', 'Diego estagiário')
ON CONFLICT (nome) DO NOTHING;

-- Recarrega o schema do PostgREST
NOTIFY pgrst, 'reload schema';
