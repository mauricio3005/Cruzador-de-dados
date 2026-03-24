-- Adiciona a coluna etapa (caso não exista) na tabela contratos_pagamentos
ALTER TABLE public.contratos_pagamentos 
ADD COLUMN IF NOT EXISTS etapa text;

-- Recarrega o cache do PostgREST (Supabase) para evitar o erro "Could not find the 'etapa' column in the schema cache"
NOTIFY pgrst, 'reload schema';
