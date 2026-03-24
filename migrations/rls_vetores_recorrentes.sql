-- =============================================================
-- Migração: Habilitar RLS para vector store e despesas recorrentes
-- Executar no SQL Editor do Supabase 
-- =============================================================

-- As tabelas abaixo são acessadas exclusivamente pelo backend
-- utilizando a chave SUPABASE_SERVICE_KEY (service_role),
-- que tem a permissão nativa de ignorar políticas de RLS.
-- Logo, ativar o RLS e deixar o padrão "Deny All" para anon e 
-- authenticated é o suficiente para garantir segurança e 
-- eliminar os alertas do painel do Supabase.

ALTER TABLE despesas_vetores ENABLE ROW LEVEL SECURITY;
ALTER TABLE despesas_recorrentes ENABLE ROW LEVEL SECURITY;
