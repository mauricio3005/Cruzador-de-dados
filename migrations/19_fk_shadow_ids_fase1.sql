-- migrations/19_fk_shadow_ids_fase1.sql
-- FASE 1 de 2 — Adiciona colunas ID numéricas paralelas às FKs em texto.
--
-- OBJETIVO:
--   Substituir gradualmente as FKs em texto (obra TEXT, etapa TEXT, etc.)
--   por FKs numéricas (obra_id INTEGER, etapa_id INTEGER, etc.).
--   Esta fase é NÃO-DESTRUTIVA: as colunas texto continuam existindo,
--   o app continua funcionando normalmente enquanto o código é migrado.
--
-- FASE 2 (executar após atualizar frontend e backend):
--   - Adicionar NOT NULL nas colunas _id onde aplicável
--   - Remover as colunas texto antigas
--   - Atualizar queries no backend para usar _id em vez de texto
--
-- TABELAS COBERTAS:
--   c_despesas, orcamentos, recebimentos, folhas, folha_regras,
--   contratos, despesas_recorrentes

-- ============================================================
-- c_despesas
-- ============================================================
ALTER TABLE c_despesas
    ADD COLUMN IF NOT EXISTS obra_id integer REFERENCES obras(id),
    ADD COLUMN IF NOT EXISTS etapa_id integer REFERENCES etapas(id),
    ADD COLUMN IF NOT EXISTS fornecedor_id integer REFERENCES fornecedores(id),
    ADD COLUMN IF NOT EXISTS categoria_id integer REFERENCES categorias_despesa(id),
    ADD COLUMN IF NOT EXISTS banco_id bigint REFERENCES bancos(id);

-- Backfill — opera apenas nas linhas ainda não preenchidas
UPDATE c_despesas d SET
    obra_id      = o.id  FROM obras o             WHERE o.nome = d.obra      AND d.obra_id      IS NULL;
UPDATE c_despesas d SET
    etapa_id     = e.id  FROM etapas e            WHERE e.nome = d.etapa     AND d.etapa_id     IS NULL;
UPDATE c_despesas d SET
    fornecedor_id = f.id FROM fornecedores f      WHERE f.nome = d.fornecedor AND d.fornecedor_id IS NULL AND d.fornecedor IS NOT NULL;
UPDATE c_despesas d SET
    categoria_id = c.id  FROM categorias_despesa c WHERE c.nome = d.despesa  AND d.categoria_id IS NULL AND d.despesa IS NOT NULL;
UPDATE c_despesas d SET
    banco_id     = b.id  FROM bancos b            WHERE b.nome = d.banco     AND d.banco_id     IS NULL AND d.banco IS NOT NULL;

-- Índices nas novas colunas
CREATE INDEX IF NOT EXISTS idx_c_despesas_obra_id       ON c_despesas (obra_id);
CREATE INDEX IF NOT EXISTS idx_c_despesas_etapa_id      ON c_despesas (etapa_id);
CREATE INDEX IF NOT EXISTS idx_c_despesas_fornecedor_id ON c_despesas (fornecedor_id);
CREATE INDEX IF NOT EXISTS idx_c_despesas_banco_id      ON c_despesas (banco_id) WHERE banco_id IS NOT NULL;

-- ============================================================
-- orcamentos
-- ============================================================
ALTER TABLE orcamentos
    ADD COLUMN IF NOT EXISTS obra_id integer REFERENCES obras(id),
    ADD COLUMN IF NOT EXISTS etapa_id integer REFERENCES etapas(id);

UPDATE orcamentos r SET obra_id  = o.id FROM obras o   WHERE o.nome = r.obra  AND r.obra_id  IS NULL;
UPDATE orcamentos r SET etapa_id = e.id FROM etapas e  WHERE e.nome = r.etapa AND r.etapa_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_orcamentos_obra_id  ON orcamentos (obra_id);
CREATE INDEX IF NOT EXISTS idx_orcamentos_etapa_id ON orcamentos (etapa_id);

-- ============================================================
-- recebimentos
-- ============================================================
ALTER TABLE recebimentos
    ADD COLUMN IF NOT EXISTS obra_id integer REFERENCES obras(id),
    ADD COLUMN IF NOT EXISTS fornecedor_id integer REFERENCES fornecedores(id),
    ADD COLUMN IF NOT EXISTS banco_id bigint REFERENCES bancos(id);

UPDATE recebimentos r SET obra_id       = o.id FROM obras o         WHERE o.nome = r.obra       AND r.obra_id       IS NULL;
UPDATE recebimentos r SET fornecedor_id = f.id FROM fornecedores f  WHERE f.nome = r.fornecedor AND r.fornecedor_id IS NULL AND r.fornecedor IS NOT NULL;
UPDATE recebimentos r SET banco_id      = b.id FROM bancos b        WHERE b.nome = r.banco      AND r.banco_id      IS NULL AND r.banco IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_recebimentos_obra_id  ON recebimentos (obra_id);
CREATE INDEX IF NOT EXISTS idx_recebimentos_banco_id ON recebimentos (banco_id) WHERE banco_id IS NOT NULL;

-- ============================================================
-- folhas
-- ============================================================
ALTER TABLE folhas
    ADD COLUMN IF NOT EXISTS obra_id integer REFERENCES obras(id);

UPDATE folhas f SET obra_id = o.id FROM obras o WHERE o.nome = f.obra AND f.obra_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_folhas_obra_id ON folhas (obra_id);

-- ============================================================
-- folha_regras
-- ============================================================
ALTER TABLE folha_regras
    ADD COLUMN IF NOT EXISTS obra_id integer REFERENCES obras(id);

UPDATE folha_regras r SET obra_id = o.id FROM obras o WHERE o.nome = r.obra AND r.obra_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_folha_regras_obra_id ON folha_regras (obra_id);

-- ============================================================
-- contratos
-- ============================================================
ALTER TABLE contratos
    ADD COLUMN IF NOT EXISTS obra_id integer REFERENCES obras(id),
    ADD COLUMN IF NOT EXISTS fornecedor_id integer REFERENCES fornecedores(id);

UPDATE contratos c SET obra_id       = o.id FROM obras o        WHERE o.nome = c.obra       AND c.obra_id       IS NULL;
UPDATE contratos c SET fornecedor_id = f.id FROM fornecedores f WHERE f.nome = c.fornecedor AND c.fornecedor_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_contratos_obra_id       ON contratos (obra_id);
CREATE INDEX IF NOT EXISTS idx_contratos_fornecedor_id ON contratos (fornecedor_id);

-- ============================================================
-- despesas_recorrentes
-- ============================================================
ALTER TABLE despesas_recorrentes
    ADD COLUMN IF NOT EXISTS obra_id integer REFERENCES obras(id),
    ADD COLUMN IF NOT EXISTS etapa_id integer REFERENCES etapas(id),
    ADD COLUMN IF NOT EXISTS fornecedor_id integer REFERENCES fornecedores(id),
    ADD COLUMN IF NOT EXISTS categoria_id integer REFERENCES categorias_despesa(id),
    ADD COLUMN IF NOT EXISTS banco_id bigint REFERENCES bancos(id);

UPDATE despesas_recorrentes r SET obra_id       = o.id FROM obras o             WHERE o.nome = r.obra       AND r.obra_id       IS NULL AND r.obra IS NOT NULL;
UPDATE despesas_recorrentes r SET etapa_id      = e.id FROM etapas e            WHERE e.nome = r.etapa      AND r.etapa_id      IS NULL AND r.etapa IS NOT NULL;
UPDATE despesas_recorrentes r SET fornecedor_id = f.id FROM fornecedores f      WHERE f.nome = r.fornecedor AND r.fornecedor_id IS NULL AND r.fornecedor IS NOT NULL;
UPDATE despesas_recorrentes r SET categoria_id  = c.id FROM categorias_despesa c WHERE c.nome = r.despesa   AND r.categoria_id  IS NULL AND r.despesa IS NOT NULL;
UPDATE despesas_recorrentes r SET banco_id      = b.id FROM bancos b            WHERE b.nome = r.banco      AND r.banco_id      IS NULL AND r.banco IS NOT NULL;

-- ============================================================
-- FASE 2 — Checklist (não execute aqui, fazer em migration 20_)
-- ============================================================
-- Após atualizar o backend e frontend para usar as colunas _id:
--
-- Para cada tabela coberta acima:
--   1. ALTER TABLE <tabela> ALTER COLUMN <col>_id SET NOT NULL;   ← onde aplicável
--   2. ALTER TABLE <tabela> DROP COLUMN <col_texto>;
--   3. DROP INDEX IF EXISTS <idx antigo na coluna texto>;
--
-- Exemplo para c_despesas:
--   ALTER TABLE c_despesas ALTER COLUMN obra_id SET NOT NULL;
--   ALTER TABLE c_despesas ALTER COLUMN etapa_id SET NOT NULL;
--   ALTER TABLE c_despesas DROP COLUMN obra;
--   ALTER TABLE c_despesas DROP COLUMN etapa;
--   ALTER TABLE c_despesas DROP COLUMN fornecedor;
--   ALTER TABLE c_despesas DROP COLUMN despesa;
--   ALTER TABLE c_despesas DROP COLUMN banco;
--   DROP INDEX IF EXISTS idx_c_despesas_obra_data;   -- recriar com obra_id
--   DROP INDEX IF EXISTS idx_c_despesas_obra_etapa;  -- recriar com obra_id, etapa_id

NOTIFY pgrst, 'reload schema';
