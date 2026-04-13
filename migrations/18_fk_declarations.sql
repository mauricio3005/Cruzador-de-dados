-- migrations/18_fk_declarations.sql
-- 1. Corrige inconsistências de tipo integer ↔ bigint em FKs
-- 2. Declara FKs faltantes em contratos, folhas, folha_regras, despesas_recorrentes
-- 3. Substitui CHECK inline de c_despesas.tipo e c_despesas.forma por FKs
--    para as tabelas de domínio tipos_custo e formas_pagamento

-- ============================================================
-- Seção 1 — Fix de tipos
-- ============================================================

-- 1a. folha_funcionarios.folha_id: integer → bigint (folhas.id é bigint)
ALTER TABLE folha_funcionarios
    DROP CONSTRAINT folha_funcionarios_folha_id_fkey;

ALTER TABLE folha_funcionarios
    ALTER COLUMN folha_id TYPE bigint;

ALTER TABLE folha_funcionarios
    ADD CONSTRAINT folha_funcionarios_folha_id_fkey
    FOREIGN KEY (folha_id) REFERENCES folhas(id);

-- 1b. contratos_etapas.contrato_id: bigint → integer (contratos.id é integer)
--     Preferível mudar o lado fraco (FK) em vez de converter a PK.
ALTER TABLE contratos_etapas
    DROP CONSTRAINT contratos_etapas_contrato_id_fkey;

ALTER TABLE contratos_etapas
    ALTER COLUMN contrato_id TYPE integer;

ALTER TABLE contratos_etapas
    ADD CONSTRAINT contratos_etapas_contrato_id_fkey
    FOREIGN KEY (contrato_id) REFERENCES contratos(id);

-- ============================================================
-- Seção 2 — FKs faltantes em contratos
-- ============================================================
-- VERIFICAÇÃO ANTES DE EXECUTAR:
--   SELECT DISTINCT obra FROM contratos WHERE obra NOT IN (SELECT nome FROM obras);
--   SELECT DISTINCT fornecedor FROM contratos WHERE fornecedor NOT IN (SELECT nome FROM fornecedores);
--   → ambas devem retornar 0 linhas; limpe valores órfãos antes se necessário.

ALTER TABLE contratos
    ADD CONSTRAINT contratos_obra_fkey
    FOREIGN KEY (obra) REFERENCES obras(nome) ON UPDATE CASCADE;

ALTER TABLE contratos
    ADD CONSTRAINT contratos_fornecedor_fkey
    FOREIGN KEY (fornecedor) REFERENCES fornecedores(nome) ON UPDATE CASCADE;

-- contratos.etapa é coluna legada (substituída por contratos_etapas);
-- não adicionamos FK aqui para não bloquear dados históricos incompletos.

-- contratos_etapas.etapa sem FK
-- VERIFICAÇÃO: SELECT DISTINCT etapa FROM contratos_etapas WHERE etapa NOT IN (SELECT nome FROM etapas);
ALTER TABLE contratos_etapas
    ADD CONSTRAINT contratos_etapas_etapa_fkey
    FOREIGN KEY (etapa) REFERENCES etapas(nome) ON UPDATE CASCADE;

-- contratos_pagamentos.etapa sem FK (nullable)
-- VERIFICAÇÃO: SELECT DISTINCT etapa FROM contratos_pagamentos WHERE etapa NOT IN (SELECT nome FROM etapas);
ALTER TABLE contratos_pagamentos
    ADD CONSTRAINT contratos_pagamentos_etapa_fkey
    FOREIGN KEY (etapa) REFERENCES etapas(nome) ON UPDATE CASCADE;

-- ============================================================
-- Seção 3 — FKs faltantes em folhas e folha_regras
-- ============================================================
ALTER TABLE folhas
    ADD CONSTRAINT folhas_obra_fkey
    FOREIGN KEY (obra) REFERENCES obras(nome) ON UPDATE CASCADE;

ALTER TABLE folha_regras
    ADD CONSTRAINT folha_regras_obra_fkey
    FOREIGN KEY (obra) REFERENCES obras(nome) ON UPDATE CASCADE;

-- ============================================================
-- Seção 4 — FKs faltantes em despesas_recorrentes
-- ============================================================
-- Todas as colunas são nullable — FKs só validam valores não-nulos.
-- VERIFICAÇÃO:
--   SELECT DISTINCT obra FROM despesas_recorrentes WHERE obra IS NOT NULL AND obra NOT IN (SELECT nome FROM obras);
--   SELECT DISTINCT etapa FROM despesas_recorrentes WHERE etapa IS NOT NULL AND etapa NOT IN (SELECT nome FROM etapas);
--   SELECT DISTINCT fornecedor FROM despesas_recorrentes WHERE fornecedor IS NOT NULL AND fornecedor NOT IN (SELECT nome FROM fornecedores);
--   SELECT DISTINCT despesa FROM despesas_recorrentes WHERE despesa IS NOT NULL AND despesa NOT IN (SELECT nome FROM categorias_despesa);

ALTER TABLE despesas_recorrentes
    ADD CONSTRAINT despesas_recorrentes_obra_fkey
    FOREIGN KEY (obra) REFERENCES obras(nome) ON UPDATE CASCADE;

ALTER TABLE despesas_recorrentes
    ADD CONSTRAINT despesas_recorrentes_etapa_fkey
    FOREIGN KEY (etapa) REFERENCES etapas(nome) ON UPDATE CASCADE;

ALTER TABLE despesas_recorrentes
    ADD CONSTRAINT despesas_recorrentes_fornecedor_fkey
    FOREIGN KEY (fornecedor) REFERENCES fornecedores(nome) ON UPDATE CASCADE;

ALTER TABLE despesas_recorrentes
    ADD CONSTRAINT despesas_recorrentes_despesa_fkey
    FOREIGN KEY (despesa) REFERENCES categorias_despesa(nome) ON UPDATE CASCADE;

-- ============================================================
-- Seção 5 — Substituir CHECKs inline por FKs de domínio
-- ============================================================
-- c_despesas.tipo: CHECK → FK para tipos_custo(nome)
-- O nome do constraint auto-gerado pelo Postgres é c_despesas_tipo_check.
-- Se o comando falhar, confirme o nome com:
--   SELECT conname FROM pg_constraint WHERE conrelid = 'c_despesas'::regclass AND contype = 'c';

ALTER TABLE c_despesas DROP CONSTRAINT IF EXISTS c_despesas_tipo_check;
ALTER TABLE c_despesas
    ADD CONSTRAINT c_despesas_tipo_fkey
    FOREIGN KEY (tipo) REFERENCES tipos_custo(nome);

-- c_despesas.forma: CHECK → FK para formas_pagamento(nome)
-- Forma é nullable — FK só valida quando não é NULL.
ALTER TABLE c_despesas DROP CONSTRAINT IF EXISTS c_despesas_forma_check;
ALTER TABLE c_despesas
    ADD CONSTRAINT c_despesas_forma_fkey
    FOREIGN KEY (forma) REFERENCES formas_pagamento(nome);

-- Garante que formas_pagamento tem todos os valores usados atualmente:
INSERT INTO formas_pagamento (nome)
VALUES ('PIX'), ('Boleto'), ('Cartão'), ('Dinheiro'), ('Transferência'), ('Outro')
ON CONFLICT DO NOTHING;

-- Garante que tipos_custo tem todos os valores usados atualmente:
INSERT INTO tipos_custo (nome)
VALUES ('Mão de Obra'), ('Materiais'), ('Geral')
ON CONFLICT DO NOTHING;

NOTIFY pgrst, 'reload schema';
