-- migrations/15_indices_complementares.sql
-- Índices complementares à migration 09.
-- Cobre: FKs sem índice, colunas de filtro frequente, pgvector HNSW.
-- Idempotente: CREATE INDEX IF NOT EXISTS é seguro re-executar.

-- ============================================================
-- c_despesas
-- ============================================================

-- Filtro por fornecedor (busca de histórico, relatórios por fornecedor)
CREATE INDEX IF NOT EXISTS idx_c_despesas_fornecedor
  ON c_despesas (fornecedor);

-- Filtro de contas a pagar: apenas despesas pendentes (subset pequeno, muito acessado)
CREATE INDEX IF NOT EXISTS idx_c_despesas_pendentes
  ON c_despesas (data, vencimento)
  WHERE paga = false;

-- Filtro por tipo de custo (Mão de Obra / Materiais / Geral)
CREATE INDEX IF NOT EXISTS idx_c_despesas_tipo
  ON c_despesas (tipo);

-- ============================================================
-- folha_funcionarios
-- ============================================================

-- Join folha → funcionários (ausente na migration 09 — scan completo a cada fechamento)
CREATE INDEX IF NOT EXISTS idx_folha_funcionarios_folha_id
  ON folha_funcionarios (folha_id);

-- ============================================================
-- contratos_etapas e contratos_pagamentos
-- ============================================================

-- Join contrato → etapas (lookup de multi-etapa por contrato)
CREATE INDEX IF NOT EXISTS idx_contratos_etapas_contrato_id
  ON contratos_etapas (contrato_id);

-- Join contrato → pagamentos
CREATE INDEX IF NOT EXISTS idx_contratos_pagamentos_contrato_id
  ON contratos_pagamentos (contrato_id);

-- ============================================================
-- recebimentos
-- ============================================================

-- Agrupamento de parcelas (grupo_id é usado para buscar todas as parcelas de um lote)
CREATE INDEX IF NOT EXISTS idx_recebimentos_grupo_id
  ON recebimentos (grupo_id)
  WHERE grupo_id IS NOT NULL;

-- Filtro de recebimentos pendentes
CREATE INDEX IF NOT EXISTS idx_recebimentos_pendentes
  ON recebimentos (obra, data)
  WHERE recebido = false;

-- ============================================================
-- remessas_caixa
-- ============================================================

-- FK para bancos (adicionada na migration 14 — sem índice próprio)
CREATE INDEX IF NOT EXISTS idx_remessas_banco_destino_id
  ON remessas_caixa (banco_destino_id);

-- Filtro por obra (relatórios de fluxo de caixa por obra)
CREATE INDEX IF NOT EXISTS idx_remessas_obra
  ON remessas_caixa (obra)
  WHERE obra IS NOT NULL;

-- ============================================================
-- banco_obras
-- ============================================================

-- Lookup reverso: quais bancos atendem uma obra (PK cobre banco_id; obra precisa de índice próprio)
CREATE INDEX IF NOT EXISTS idx_banco_obras_obra
  ON banco_obras (obra);

-- ============================================================
-- taxa_conclusao
-- ============================================================

-- Lookup por obra+etapa (sem UNIQUE ainda, mas cobre o SELECT com WHERE)
CREATE INDEX IF NOT EXISTS idx_taxa_conclusao_obra_etapa
  ON taxa_conclusao (obra, etapa);

-- ============================================================
-- despesas_vetores — pgvector HNSW
-- ============================================================
-- Substitui o seq-scan O(n) em cada chamada do chat por busca aproximada O(log n).
-- m=16 e ef_construction=64 são defaults seguros; ajustar se precisão < 95%.
-- ATENÇÃO: este índice é construído em memória — se o Supabase retornar
-- "could not write to file", aumente maintenance_work_mem na sessão antes de executar.
CREATE INDEX IF NOT EXISTS idx_despesas_vetores_hnsw
  ON despesas_vetores
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
