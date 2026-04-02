-- Migration 05: adicionar valor_fixo em folha_funcionarios
-- Quando preenchido, sobrepõe o cálculo por diárias (usado para CLT e salários fixos)

ALTER TABLE folha_funcionarios
  ADD COLUMN IF NOT EXISTS valor_fixo NUMERIC;
