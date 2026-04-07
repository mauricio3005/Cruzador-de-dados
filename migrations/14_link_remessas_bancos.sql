-- Migration 14: Vincula remessas_caixa → bancos (destino) e → obras via FK
-- Executar manualmente no SQL Editor do Supabase.

-- ── 1. FK para o banco destino ────────────────────────────────────────────────
-- banco_destino (texto) já foi removido manualmente; apenas adiciona a FK tipada.
ALTER TABLE remessas_caixa
    ADD COLUMN IF NOT EXISTS banco_destino_id BIGINT NOT NULL REFERENCES bancos(id);

CREATE INDEX IF NOT EXISTS idx_remessas_banco_destino_id ON remessas_caixa(banco_destino_id);

-- ── 2. FK para obra ───────────────────────────────────────────────────────────
-- obra continua TEXT nullable; apenas adicionamos a constraint referencial.
-- Se houver valores órfãos, este comando falhará — limpe antes com:
--   UPDATE remessas_caixa SET obra = NULL WHERE obra NOT IN (SELECT nome FROM obras);
ALTER TABLE remessas_caixa
    ADD CONSTRAINT fk_remessas_obra FOREIGN KEY (obra) REFERENCES obras(nome) ON UPDATE CASCADE;

CREATE INDEX IF NOT EXISTS idx_remessas_obra ON remessas_caixa(obra);

-- ── 3. Recria saldo_bancos() com join por FK (sem text-matching) ──────────────
DROP FUNCTION IF EXISTS saldo_bancos();
CREATE OR REPLACE FUNCTION saldo_bancos()
RETURNS TABLE (
    banco_id        BIGINT,
    banco           TEXT,
    total_recebido  NUMERIC,
    total_gasto     NUMERIC,
    saldo           NUMERIC,
    ultima_remessa  DATE
) LANGUAGE sql AS $$
    WITH recebido AS (
        SELECT
            r.banco_destino_id  AS banco_id,
            b.nome              AS banco,
            SUM(r.valor)        AS total,
            MAX(r.data)         AS ultima
        FROM remessas_caixa r
        INNER JOIN bancos b ON b.id = r.banco_destino_id
        GROUP BY r.banco_destino_id, b.nome
    ),
    gasto AS (
        -- c_despesas ainda usa banco TEXT; join por nome enquanto não migrar
        SELECT
            b.id   AS banco_id,
            b.nome AS banco,
            SUM(d.valor_total) AS total
        FROM c_despesas d
        INNER JOIN bancos b ON b.nome = d.banco AND b.tipo = 'filho'
        GROUP BY b.id, b.nome
    )
    SELECT
        COALESCE(r.banco_id, g.banco_id)             AS banco_id,
        COALESCE(r.banco,    g.banco)                AS banco,
        COALESCE(r.total, 0)                         AS total_recebido,
        COALESCE(g.total, 0)                         AS total_gasto,
        COALESCE(r.total, 0) - COALESCE(g.total, 0) AS saldo,
        r.ultima::DATE                               AS ultima_remessa
    FROM recebido r
    FULL OUTER JOIN gasto g ON r.banco_id = g.banco_id
    ORDER BY banco;
$$;

GRANT EXECUTE ON FUNCTION saldo_bancos() TO anon;

NOTIFY pgrst, 'reload schema';
