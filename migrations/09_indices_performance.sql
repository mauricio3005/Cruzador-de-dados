-- migrations/09_indices_performance.sql
-- Índices para as queries mais comuns do sistema.
-- Idempotente: CREATE INDEX IF NOT EXISTS é seguro re-executar.

-- Filtro por obra + data (dashboard, relatórios)
CREATE INDEX IF NOT EXISTS idx_c_despesas_obra_data
  ON c_despesas (obra, data DESC);

-- Filtro por obra + etapa (relatórios por etapa)
CREATE INDEX IF NOT EXISTS idx_c_despesas_obra_etapa
  ON c_despesas (obra, etapa);

-- Folha de pagamento
CREATE INDEX IF NOT EXISTS idx_c_despesas_folha_id
  ON c_despesas (folha_id)
  WHERE folha_id IS NOT NULL;

-- Recebimentos por obra e data
CREATE INDEX IF NOT EXISTS idx_recebimentos_obra_data
  ON recebimentos (obra, data DESC);

-- Folhas por obra
CREATE INDEX IF NOT EXISTS idx_folhas_obra
  ON folhas (obra);

-- Contratos por obra
CREATE INDEX IF NOT EXISTS idx_contratos_obra
  ON contratos (obra);

-- Comprovantes por despesa (join frequente)
CREATE INDEX IF NOT EXISTS idx_comprovantes_despesa_id
  ON comprovantes_despesa (despesa_id);

-- Remessas por banco destino
CREATE INDEX IF NOT EXISTS idx_remessas_banco_destino
  ON remessas_caixa (banco_destino);

-- Despesas recorrentes por próxima data (processamento)
CREATE INDEX IF NOT EXISTS idx_recorrentes_proxima_data
  ON despesas_recorrentes (proxima_data)
  WHERE ativa = true;
