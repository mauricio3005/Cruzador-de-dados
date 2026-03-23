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
- `WEB/env.js` — credenciais Supabase para o browser (usa `SUPABASE_ANON_KEY`, chave pública)
- `WEB/style.css` — design system completo via CSS custom properties (não usar inline styles)
- `WEB/components/nav.js` — sidebar de navegação injetada em todas as páginas
- Cada módulo tem sua própria pasta (`despesas/`, `historico/`, `folha/`, `recebimentos/`, `contratos/`, `configuracoes/`, `contas/`, `documentos/`)

### Backend (api/)
- `api/main.py` — bootstrap FastAPI, registra os 4 routers: `ai`, `documentos`, `folha`, `relatorio`
- `api/routes/ai.py` — extração de documentos via GPT-4 Vision e Whisper
- `api/routes/folha.py` — fechamento de folha de pagamento (operação atômica: cria despesas + faz upload de comprovantes)
- `api/routes/relatorio.py` — geração de PDF via `relatorio.py` raiz
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
| `fornecedores`, `categorias_despesa`, `formas_pagamento` | Tabelas de referência |

A tabela `c_despesas` é a versão atual (substitui esquema legado). Campo `folha_id` é nullable — preenchido somente para despesas de mão de obra geradas pelo fechamento de folha.

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

**Navegação:** `nav.js` é injetado via `document.getElementById('nav-placeholder')` — todo `index.html` novo deve incluir esse placeholder e importar o script.
