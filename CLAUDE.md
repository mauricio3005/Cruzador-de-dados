# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sistema de gestão financeira para obras de construção civil. Migração ativa de Streamlit (legado) para FastAPI + vanilla JS + Supabase. **Todo desenvolvimento novo deve usar WEB/ (frontend) e api/ (backend)** — evitar modificar `dashboard.py` ou `app.py`.

## Running Locally

```bash
# Terminal 1 — API (porta 8000)
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Frontend estático (porta 8080)
cd WEB
python -m http.server 8080
```

Acesse em `http://localhost:8080`. O frontend **não funciona via file://** — precisa de servidor HTTP.

## Architecture

### Stack
- **Frontend**: HTML5 + CSS3 + vanilla JavaScript (sem framework), Supabase JS SDK diretamente no browser
- **Backend**: FastAPI (Python) com Uvicorn
- **Banco de dados**: PostgreSQL via Supabase (cliente Python `supabase-py` no backend, JS SDK no frontend)
- **IA**: OpenAI GPT-4 Vision (extração de notas fiscais/comprovantes), Whisper (transcrição de áudio)
- **PDF**: ReportLab + Plotly/Kaleido

### Frontend (WEB/)
- `WEB/index.html` + `WEB/app.js` — dashboard principal (KPIs, orçamento vs. realizado, fluxo de caixa, modal de PDF)
- `WEB/env.js` — credenciais Supabase para o browser (usa `SUPABASE_ANON_KEY`, chave pública); expõe `window.ENV`
- `WEB/style.css` — design system completo via CSS custom properties (não usar inline styles)
- `WEB/components/nav.js` — sidebar de navegação injetada em todas as páginas; também injeta automaticamente `ai-chat.js`
- `WEB/components/ai-chat.js` — widget global de chat IA (fixo, canto inferior direito); comunica com `POST /api/ai/chat`; suporta ação `cadastrar_despesa` que salva prefill em `sessionStorage('ai_despesa_prefill')` e navega para `/despesas/`
- Cada módulo tem sua própria pasta (`despesas/`, `historico/`, `folha/`, `recebimentos/`, `contratos/`, `configuracoes/`, `contas/`, `documentos/`, `recorrentes/`, `relatorios/`)
- `WEB/components/toast.js` — sistema de notificações toast global
- `API_BASE` em todos os módulos JS: `` `http://${location.hostname}:8000` `` (não hardcode `localhost`)

### Backend (api/)
- `api/main.py` — bootstrap FastAPI, CORS aberto (`allow_origins=["*"]`), registra os 5 routers: `ai`, `documentos`, `folha`, `relatorio`, `recorrentes`; expõe `/api/health` e endpoints de debug (`/api/debug/supabase`, `/api/debug/chat-context`); Swagger em `http://localhost:8000/docs`
- `api/supabase_client.py` — singleton Supabase com `@lru_cache`; use `get_supabase()` em novos routes (preferir sobre criar cliente local)
- `api/embeddings.py` — pgvector semantic search via `text-embedding-3-small`; `sync_embeddings()` é chamado automaticamente a cada `/api/ai/chat` para embeddar despesas novas; `search_despesas(query)` retorna as N despesas semanticamente mais próximas
- `api/routes/ai.py` — múltiplos endpoints de IA: `POST /extrair` (imagem/PDF), `POST /extrair-texto` (texto livre), `POST /extrair-texto-misto` (texto+arquivos), `POST /transcrever` (Whisper), `POST /chat-despesas` (revisão), `POST /chat` (assistente geral com acesso ao banco), `GET /referencias`
- `api/routes/folha.py` — fechamento de folha de pagamento (operação atômica: cria despesas + faz upload de comprovantes)
- `api/routes/relatorio.py` — geração de PDF via `relatorio.py` raiz
- `api/routes/recorrentes.py` — CRUD de templates de despesas recorrentes + `POST /api/recorrentes/processar` (gera `c_despesas` para templates vencidos, avança `proxima_data`, desativa quando `data_fim` é atingida)
- Backend usa `SUPABASE_SERVICE_KEY` (admin) — nunca expor no frontend

### Database Schema (Supabase/PostgreSQL)
Tabelas principais:
| Tabela | Papel |
|--------|-------|
| `obras` | Projetos (PK: `nome`) |
| `etapas` | Fases da obra (PK: `nome`) |
| `tipos_custo` | 'Mão de Obra' / 'Materiais' / 'Geral' |
| `orcamentos` | Orçamento por obra+etapa+tipo |
| `c_despesas` | Despesas (schema atual, UUID PK) |
| `folhas` + `folha_funcionarios` | Folha de pagamento |
| `recebimentos` | Receitas/entradas |
| `contas_a_pagar` | Contas a pagar |
| `comprovantes_despesa` | Links de comprovantes (Supabase Storage) |
| `despesas_recorrentes` | Templates de despesas recorrentes (mensal/trimestral/semestral/anual) |
| `empresas` | Empresas proprietárias; `obras.empresa_id` FK nullable |
| `taxa_conclusao` | % de conclusão por obra+etapa (`taxa` NUMERIC 0-100) |
| `fornecedores`, `categorias_despesa`, `formas_pagamento` | Tabelas de referência |

A tabela `c_despesas` é a versão atual (substitui esquema legado). Campo `folha_id` é nullable — preenchido somente para despesas de mão de obra geradas pelo fechamento de folha.

**Migrations:** arquivos em `migrations/` são executados manualmente no SQL Editor do Supabase (não há runner automático). O último arquivo é `02_empresas.sql` — nomear novos arquivos a partir de `03_`.

## Design System

Descrito em `DESIGN.md`. Princípios-chave:
- **Tonal layering** — profundidade via tons de cor, sem bordas `1px solid`
- Fontes: Manrope (display/títulos), Inter (corpo)
- Paleta de superfícies hierárquica via CSS tokens em `style.css`
- Componentes: usar classes existentes em `style.css` antes de criar novos estilos

## Environment Variables

| Variável | Usado em | Propósito |
|----------|----------|-----------|
| `SUPABASE_URL` | backend + frontend | URL do projeto Supabase |
| `SUPABASE_SERVICE_KEY` | backend (`.env`) | Chave admin — nunca no frontend |
| `SUPABASE_ANON_KEY` | frontend (`WEB/env.js`) | Chave pública |
| `OPENAI_API_KEY` | backend (`.env`) | GPT-4 Vision + Whisper |

## Key Patterns

**Extração de IA (despesas):** O fluxo passa por `/api/ai/extrair` (arquivo único) → retorna JSON estruturado → frontend exibe tabela editável para revisão → usuário confirma → salva em `c_despesas` direto via Supabase JS SDK.

**Folha de pagamento:** Operação atômica em `api/routes/folha.py` — o frontend envia payload completo e o backend executa tudo: inserir despesas, upload de comprovantes em Supabase Storage, atualizar status da folha.

**Relatórios PDF:** Frontend chama `GET /api/relatorio/pdf?obra=X&tipo=Y&...` → backend busca dados no Supabase com `service_key`, processa com Pandas, renderiza PDF com ReportLab, retorna como `application/pdf`.

**Navegação:** `nav.js` popula `document.getElementById('main-nav')` — todo `index.html` novo deve incluir `<div id="main-nav"></div>` na sidebar e importar o script. O chat widget é injetado automaticamente via `nav.js`.

**Prefill IA → Despesas:** O chat widget pode navegar para `/despesas/` com dados pré-preenchidos. O `despesas/app.js` lê `sessionStorage('ai_despesa_prefill')` no `DOMContentLoaded` e preenche o formulário.

**Supabase no frontend:** Cada módulo chama `window.supabase.createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY)` após verificar `window.ENV`. Não usar service key no browser.
