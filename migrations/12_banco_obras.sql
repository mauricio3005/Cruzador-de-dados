-- Migration 12: Associação banco ↔ obra + RPC de saldo agregado
-- Executar manualmente no SQL Editor do Supabase

-- Junction table: quais obras cada banco atende
-- Se um banco não tem entradas aqui → atua em todas as obras (sem restrição)
CREATE TABLE IF NOT EXISTS banco_obras (
    banco_id BIGINT NOT NULL REFERENCES bancos(id) ON DELETE CASCADE,
    obra     TEXT   NOT NULL REFERENCES obras(nome) ON DELETE CASCADE,
    PRIMARY KEY (banco_id, obra)
);

ALTER TABLE banco_obras ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon full access" ON banco_obras
  FOR ALL TO anon USING (true) WITH CHECK (true);

-- RPC: agrega saldos server-side (substitui 2 full-table scans no client)
-- Retorna apenas bancos do tipo 'filho' (contas controladas)
CREATE OR REPLACE FUNCTION saldo_bancos()
RETURNS TABLE (
    banco           TEXT,
    total_recebido  NUMERIC,
    total_gasto     NUMERIC,
    saldo           NUMERIC,
    ultima_remessa  DATE
) LANGUAGE sql AS $$
    WITH recebido AS (
        SELECT banco_destino  AS banco,
               SUM(valor)     AS total,
               MAX(data)      AS ultima
        FROM remessas_caixa
        GROUP BY banco_destino
    ),
    gasto AS (
        SELECT d.banco, SUM(d.valor_total) AS total
        FROM c_despesas d
        INNER JOIN bancos b ON b.nome = d.banco AND b.tipo = 'filho'
        GROUP BY d.banco
    )
    SELECT
        COALESCE(r.banco, g.banco)                   AS banco,
        COALESCE(r.total, 0)                         AS total_recebido,
        COALESCE(g.total, 0)                         AS total_gasto,
        COALESCE(r.total, 0) - COALESCE(g.total, 0) AS saldo,
        r.ultima::DATE                               AS ultima_remessa
    FROM recebido r
    FULL OUTER JOIN gasto g ON r.banco = g.banco
    ORDER BY banco;
$$;

GRANT EXECUTE ON FUNCTION saldo_bancos() TO anon;

NOTIFY pgrst, 'reload schema';
