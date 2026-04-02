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
- **IA**: OpenAI `gpt-5.4` (extração de NF e chat principal), `gpt-4.1-mini` (análise de relatórios), Whisper (transcrição de áudio), `text-embedding-3-small` (embeddings pgvector)
- **PDF**: ReportLab + Plotly/Kaleido

### Frontend (WEB/)
- `WEB/index.html` + `WEB/app.js` — dashboard principal (KPIs, orçamento vs. realizado, fluxo de caixa, modal de PDF)
- `WEB/env.js` — credenciais Supabase para o browser (usa `SUPABASE_ANON_KEY`, chave pública); expõe `window.ENV`
- `WEB/style.css` — design system completo via CSS custom properties (não usar inline styles)
- `WEB/components/nav.js` — sidebar de navegação injetada em todas as páginas; também injeta automaticamente `ai-chat.js`
- `WEB/components/ai-chat.js` — widget global de chat IA (fixo, canto inferior direito); comunica com `POST /api/ai/chat`; suporta ação `cadastrar_despesa` que salva prefill em `sessionStorage('ai_despesa_prefill')` e navega para `/despesas/`
- Cada módulo tem sua própria pasta (`despesas/`, `historico/`, `folha/`, `recebimentos/`, `contratos/`, `configuracoes/`, `contas/`, `documentos/`, `recorrentes/`, `relatorios/`, `remessas/`)
- `WEB/contratos/` — CRUD de contratos com fornecedores por obra/etapas (seleção multi-etapa via checkboxes); cada pagamento registrado cria automaticamente uma entrada em `c_despesas`
- `WEB/relatorios/` — relatórios financeiros com IA: modo único (uma obra) ou comparativo (múltiplas obras); chama `POST /api/relatorio/analisar` e exibe saúde financeira 0-100 + alertas
- `WEB/documentos/` — galeria de comprovantes com paginação (50/página), upload drag-and-drop, múltiplos NFs por despesa, exportação CSV
- `WEB/remessas/` — módulo de controle de remessas de caixa: registra transferências do caixa principal (Maurício) para contas controladas (Kathleen, Diego etc.); calcula saldo líquido por conta (remessas recebidas − despesas de `c_despesas`); Maurício é excluído dos cálculos de saldo controlado por ser a conta-origem; suporta upload de comprovante no bucket `comprovantes`
- `WEB/historico/` — além do CRUD padrão, suporta seleção múltipla de despesas para vincular um único comprovante a várias entradas de uma vez (padrão: seleciona → modal upload → escreve N linhas em `comprovantes_despesa`)
- `WEB/components/toast.js` — sistema de notificações toast global
- `API_BASE` em todos os módulos JS: `` `http://${location.hostname}:8000` `` (não hardcode `localhost`)

### Backend (api/)
- `api/main.py` — bootstrap FastAPI, CORS aberto (`allow_origins=["*"]`), middleware HTTP de log (método + path + status + ms), registra os 5 routers: `ai`, `documentos`, `folha`, `relatorio`, `recorrentes`; expõe `/api/health` e endpoints de debug (`/api/debug/supabase`, `/api/debug/chat-context`); Swagger em `http://localhost:8000/docs`
- `api/logger.py` — configuração centralizada de logging; use `get_logger(__name__)` em qualquer módulo; grava em console (INFO+) e em `logs/api.log` com rotação (10 MB × 5 backups, DEBUG+)
- `api/supabase_client.py` — singleton Supabase com `@lru_cache`; use `get_supabase()` em novos routes (preferir sobre criar cliente local); `api/routes/relatorio.py` tem `_get_supabase()` próprio — exceção histórica, não replicar
- `api/embeddings.py` — pgvector semantic search via `text-embedding-3-small`; `sync_embeddings()` é chamado automaticamente a cada `/api/ai/chat` para embeddar despesas novas; `search_despesas(query)` retorna as N despesas semanticamente mais próximas
- `api/routes/ai.py` — múltiplos endpoints de IA: `POST /extrair` (imagem/PDF), `POST /extrair-texto` (texto livre), `POST /extrair-texto-misto` (texto+arquivos), `POST /extrair-pix` (comprovante PIX → retorna `{nome, valor}`), `POST /transcrever` (Whisper), `POST /chat-despesas` (loop de revisão iterativa de extração: recebe histórico de mensagens + array de despesas, retorna mensagem + array corrigido ou null), `POST /chat` (assistente geral com tool calling — loop de até 5 rounds; tools: `buscar_despesas`, `buscar_totais`, `listar_referencias`, `planejar_criar_despesa`, `planejar_editar_despesa`, `planejar_editar_lote_despesas`, `planejar_criar_recebimento`, `planejar_editar_recebimento`), `GET /referencias` (cache 2 min); normalização com `_normalizar()` + `_melhor_match()` para fuzzy matching de fornecedores/obras/etapas
- `api/routes/documentos.py` — `DELETE /api/documentos/nf/{nf_id}`: remove arquivo do Storage `comprovantes`, deleta registro de `comprovantes_despesa`; se não restar NFs, atualiza `tem_nota_fiscal = False` na `c_despesas`
- `api/routes/folha.py` — fechamento de folha de pagamento (operação atômica: cria despesas + faz upload de comprovantes)
- `api/routes/relatorio.py` — `GET /pdf` (StreamingResponse PDF) + `POST /analisar` (análise IA com gpt-4.1-mini, retorna JSON estruturado com saúde financeira 0-100 e alertas)
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
| `obra_etapas` | Vínculo explícito entre obras e etapas (PK composta obra+etapa) |
| `contratos` | Contratos com fornecedores; `contrato_pagamentos` registra cada pagamento |
| `contratos_etapas` | Junction table `(contrato_id, etapa)` — suporte a multi-etapa por contrato |
| `remessas_caixa` | Transferências entre contas; campos: conta destino, valor, data, obra, `comprovante_url` |
| `fornecedores`, `categorias_despesa`, `formas_pagamento` | Tabelas de referência |

A tabela `c_despesas` é a versão atual (substitui esquema legado). Campo `folha_id` é nullable — preenchido somente para despesas de mão de obra geradas pelo fechamento de folha.

`folha_funcionarios` tem coluna `valor_fixo` (NUMERIC, nullable): quando preenchida, substitui o cálculo baseado em diárias/regras; o módulo `folha/` mostra o campo destacado e botão "reverter" para limpar o valor fixo.

`recebimentos` suporta parcelamento: campos `parcela_num`, `total_parcelas`, `grupo_id` (timestamp de agrupamento) permitem dividir um recebimento em N parcelas com intervalo em meses.

**Migrations:** arquivos em `migrations/` são executados manualmente no SQL Editor do Supabase (não há runner automático). O último arquivo aplicado é `05_folha_valor_fixo.sql` — nomear novos arquivos a partir de `06_`.

**Logs:** em `logs/api.log` (gitignore). Para acompanhar em tempo real: `tail -f logs/api.log`. Para filtrar por rota: `grep "POST /api/ai" logs/api.log`.

**Utilitários Windows:** `diagnostico.bat` (status da API + últimas 30 linhas de log), `restart_api.bat` (mata processo na porta 8000 e reinicia), `watchdog_api.bat` (loop de auto-restart em caso de crash).

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

**Extração de IA (despesas):** O fluxo passa por `/api/ai/extrair` (arquivo único) → retorna JSON estruturado → frontend exibe tabela editável para revisão → usuário pode corrigir via `POST /chat-despesas` (loop iterativo com histórico de mensagens) → confirma → salva em `c_despesas` direto via Supabase JS SDK.

**Folha de pagamento:** Operação atômica em `api/routes/folha.py` — o frontend envia payload completo e o backend executa tudo: inserir despesas, upload de comprovantes em Supabase Storage, atualizar status da folha.

**Relatórios PDF:** Frontend chama `GET /api/relatorio/pdf?obra=X&tipo=Y&...` → backend busca dados no Supabase com `service_key`, processa com Pandas, renderiza PDF com ReportLab, retorna como `application/pdf`.

**Navegação:** `nav.js` popula `document.getElementById('main-nav')` — todo `index.html` novo deve incluir `<div id="main-nav"></div>` na sidebar e importar o script. O chat widget é injetado automaticamente via `nav.js`.

**Prefill IA → Despesas:** O chat widget pode navegar para `/despesas/` com dados pré-preenchidos. O `despesas/app.js` lê `sessionStorage('ai_despesa_prefill')` no `DOMContentLoaded` e preenche o formulário.

**Supabase no frontend:** Cada módulo chama `window.supabase.createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY)` após verificar `window.ENV`. Não usar service key no browser.

## Testing

Não há suite de testes automatizados. Teste manual via Swagger UI (`http://localhost:8000/docs`) para endpoints backend.

Para verificar conexão com o banco:
```bash
python test_db.py
```

Para debug de contexto do chat IA: `GET /api/debug/chat-context` (requer API rodando).

## Known Caveats

- **Sem transações reais** — o fechamento de folha executa operações sequenciais sem rollback; falha parcial deixa estado inconsistente
- **Duas tabelas de despesas** — `c_despesas` (atual) e schema legado coexistem; sempre usar `c_despesas` em código novo
- **CORS aberto** — `allow_origins=["*"]` em `api/main.py`; adequado apenas para desenvolvimento local
- **Migrations não são idempotentes** — executar novamente pode duplicar dados históricos; nunca re-executar arquivos já aplicados
- **`relatorio.py` usa `_get_supabase()` próprio** — exceção histórica; novos routes devem usar `get_supabase()` de `api/supabase_client.py`
