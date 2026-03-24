-- ============================================================
-- 1. contratos_etapas (relação N:1 com contratos)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.contratos_etapas (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contrato_id bigint NOT NULL REFERENCES public.contratos(id) ON DELETE CASCADE,
    etapa text NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Índice para melhorar as buscas onde filtramos pelo contrato
CREATE INDEX IF NOT EXISTS idx_contratos_etapas_contrato ON public.contratos_etapas (contrato_id);


-- ============================================================
-- 2. contratos_pagamentos (relação N:1 com contratos)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.contratos_pagamentos (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contrato_id bigint NOT NULL REFERENCES public.contratos(id) ON DELETE CASCADE,
    despesa_id bigint REFERENCES public.c_despesas(id) ON DELETE SET NULL,
    etapa text,
    data date NOT NULL DEFAULT CURRENT_DATE,
    valor numeric(15,2) NOT NULL,
    descricao text,
    comprovante_url text,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_contratos_pagamentos_contrato ON public.contratos_pagamentos (contrato_id);


-- ============================================================
-- 3. Migrar dados existentes (etapa legada → contratos_etapas)
-- ============================================================
INSERT INTO public.contratos_etapas (contrato_id, etapa)
SELECT id, etapa FROM public.contratos
WHERE etapa IS NOT NULL AND etapa <> ''
ON CONFLICT DO NOTHING;


-- ============================================================
-- 4. RLS — Habilitar Row Level Security e criar Políticas
-- ============================================================
ALTER TABLE public.contratos_etapas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contratos_pagamentos ENABLE ROW LEVEL SECURITY;

-- Para contratos_etapas
CREATE POLICY "Allow all authenticated (etapas)" ON public.contratos_etapas
FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role' OR auth.role() = 'anon')
WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role' OR auth.role() = 'anon');

-- Para contratos_pagamentos
CREATE POLICY "Allow all authenticated (pagamentos)" ON public.contratos_pagamentos
FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role' OR auth.role() = 'anon')
WITH CHECK (auth.role() = 'authenticated' OR auth.role() = 'service_role' OR auth.role() = 'anon');
