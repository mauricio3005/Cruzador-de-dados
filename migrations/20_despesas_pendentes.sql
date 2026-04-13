-- Migration 20: Tabela de despesas enviadas por funcionários para aprovação
-- Executar no SQL Editor do Supabase (uma única vez)

CREATE TABLE IF NOT EXISTS despesas_pendentes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    funcionario         TEXT NOT NULL,
    obra                TEXT NOT NULL REFERENCES obras(nome),
    etapa               TEXT REFERENCES etapas(nome),
    tipo                TEXT NOT NULL,
    fornecedor          TEXT NOT NULL,
    valor_total         NUMERIC(12,2) NOT NULL CHECK (valor_total > 0),
    data                DATE NOT NULL,
    descricao           TEXT NOT NULL,
    despesa             TEXT,
    forma               TEXT,
    banco               TEXT,
    comprovante_url     TEXT NOT NULL,   -- obrigatório: funcionário sempre envia comprovante
    status              TEXT NOT NULL DEFAULT 'pendente'
                        CHECK (status IN ('pendente', 'aprovado', 'rejeitado')),
    observacao_admin    TEXT,            -- motivo de rejeição ou nota ao aprovar
    despesa_id_aprovada BIGINT REFERENCES c_despesas(id),  -- preenchido quando aprovado (c_despesas.id é INTEGER)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_despesas_pendentes_status      ON despesas_pendentes(status);
CREATE INDEX IF NOT EXISTS idx_despesas_pendentes_funcionario ON despesas_pendentes(funcionario);
CREATE INDEX IF NOT EXISTS idx_despesas_pendentes_created     ON despesas_pendentes(created_at DESC);

-- Trigger para manter updated_at atualizado automaticamente
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_despesas_pendentes_updated_at ON despesas_pendentes;
CREATE TRIGGER trg_despesas_pendentes_updated_at
    BEFORE UPDATE ON despesas_pendentes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- RLS: apenas service_role pode operar (Streamlit e API usam service key)
ALTER TABLE despesas_pendentes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_only" ON despesas_pendentes;
CREATE POLICY "service_role_only" ON despesas_pendentes
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
