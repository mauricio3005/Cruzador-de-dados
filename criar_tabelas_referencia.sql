-- =============================================================================
-- Executar no SQL Editor do Supabase
-- Cria tabelas de referência + RLS para tipos_custo e formas_pagamento
-- =============================================================================

-- ── 1. Criar tabelas ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tipos_custo (
    nome TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS formas_pagamento (
    nome TEXT PRIMARY KEY
);

-- ── 2. Habilitar RLS ─────────────────────────────────────────────────────────

ALTER TABLE tipos_custo        ENABLE ROW LEVEL SECURITY;
ALTER TABLE formas_pagamento   ENABLE ROW LEVEL SECURITY;
ALTER TABLE categorias_despesa ENABLE ROW LEVEL SECURITY;

-- ── 3. Políticas de leitura (anon + authenticated) ───────────────────────────
-- O dashboard lê essas tabelas sem autenticação de usuário (usa service key),
-- mas é boa prática liberar SELECT para autenticados e para a service role.

CREATE POLICY "Leitura pública - tipos_custo"
    ON tipos_custo FOR SELECT
    USING (true);

CREATE POLICY "Leitura pública - formas_pagamento"
    ON formas_pagamento FOR SELECT
    USING (true);

CREATE POLICY "Leitura pública - categorias_despesa"
    ON categorias_despesa FOR SELECT
    USING (true);

-- ── 4. Políticas de escrita (somente service role / authenticated) ────────────
-- INSERT / UPDATE / DELETE só pelo backend (service key) ou usuário autenticado.

CREATE POLICY "Escrita autenticada - tipos_custo"
    ON tipos_custo FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Escrita autenticada - formas_pagamento"
    ON formas_pagamento FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Escrita autenticada - categorias_despesa"
    ON categorias_despesa FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- ── 5. Seed inicial ───────────────────────────────────────────────────────────

INSERT INTO tipos_custo (nome) VALUES
    ('Mão de Obra'),
    ('Materiais'),
    ('Geral')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO formas_pagamento (nome) VALUES
    ('PIX'),
    ('Boleto'),
    ('Cartão'),
    ('Dinheiro'),
    ('Transferência'),
    ('Outro')
ON CONFLICT (nome) DO NOTHING;
