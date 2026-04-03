-- Migration 06: adiciona forma_pagamento e banco em folha_funcionarios
ALTER TABLE folha_funcionarios
    ADD COLUMN IF NOT EXISTS forma_pagamento TEXT,
    ADD COLUMN IF NOT EXISTS banco TEXT;
