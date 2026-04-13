/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Contratos (app.js)
 * Controle de contratos com fornecedores por obra/etapas (múltiplas).
 * Cada pagamento registrado gera uma despesa em c_despesas automaticamente.
 */

// --- SUPABASE (via nav.js → window.db) ---
let dbClient;

// --- ESTADO ---
let obras  = [];
let etapas = [];   // lista global de etapas do sistema

let todosContratos = [];   // rows enriquecidos: valor_pago, valor_restante, pct_execucao, etapas_list
let paginaAtual    = 1;
const PAGE_SIZE    = 25;

let editandoContratoId = null;
let contratoAtivoPag   = null;
let pagamentosAtivos   = [];
let arquivoPagamento   = null;
function popularSelect(id, opcoes, placeholder) {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = `<option value="">${placeholder}</option>` +
        opcoes.map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('');
}
async function filtrarEtapasPorObra(obra) {
    const el = document.getElementById('filtroEtapa');
    if (!obra) { popularSelect('filtroEtapa', etapas, 'Todas as etapas'); el.value = ''; return; }
    const { data } = await dbClient.from('obra_etapas').select('etapa').eq('obra', obra);
    const nomes = (data || []).map(r => r.etapa);
    popularSelect('filtroEtapa', nomes, 'Todas as etapas');
    if (!nomes.includes(el.value)) el.value = '';
}

function setSelectValue(id, value) {
    const sel = document.getElementById(id);
    if (!sel || !value) { if (sel) sel.value = ''; return; }
    if (!Array.from(sel.options).some(o => o.value === value)) {
        const opt = document.createElement('option');
        opt.value = opt.textContent = value;
        sel.appendChild(opt);
    }
    sel.value = value;
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    dbClient = window.db;
    await carregarReferencias();

    document.getElementById('btnFiltrar').addEventListener('click', () => { paginaAtual = 1; carregarContratos(); });
    document.getElementById('btnLimparFiltro').addEventListener('click', limparFiltros);
    document.getElementById('filtroObra').addEventListener('change', e => filtrarEtapasPorObra(e.target.value));
    document.getElementById('buscaTexto').addEventListener('input', renderizarTabela);

    document.getElementById('btnPagAnterior').addEventListener('click', () => {
        if (paginaAtual > 1) { paginaAtual--; renderizarTabela(); }
    });
    document.getElementById('btnPagProxima').addEventListener('click', () => {
        if (paginaAtual * PAGE_SIZE < filtrarContratos().length) { paginaAtual++; renderizarTabela(); }
    });

    // Modal contrato
    document.getElementById('btnNovoContrato').addEventListener('click', () => abrirModalContrato(null));
    document.getElementById('btnSalvarContrato').addEventListener('click', salvarContrato);
    document.getElementById('modalContrato').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModalContrato();
    });

    // Modal pagamentos
    document.getElementById('btnAdicionarPagamento').addEventListener('click', adicionarPagamento);
    document.getElementById('modalPagamentos').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModalPagamentos();
    });

    // Upload comprovante no modal de pagamentos
    const zone  = document.getElementById('uploadZonePag');
    const input = document.getElementById('inputComprovantePag');
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--accent)'; });
    zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
    zone.addEventListener('drop', e => {
        e.preventDefault(); zone.style.borderColor = '';
        if (e.dataTransfer.files[0]) definirArquivoPagamento(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', () => { if (input.files[0]) definirArquivoPagamento(input.files[0]); });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') { fecharModalContrato(); fecharModalPagamentos(); }
    });

    document.getElementById('btnExportarCSV').addEventListener('click', exportarCSV);

    await carregarContratos();
});

window.addEventListener('jarvis:data-changed', (e) => {
    if (e.detail?.tabela === 'contas_a_pagar') {
        paginaAtual = 1;
        carregarContratos();
    }
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    if (!dbClient) { setStatus('offline', 'Erro de conexão'); return; }

    const safe = async (query, campo = 'nome') => {
        try {
            const { data, error } = await query;
            if (error) { console.warn('[contratos]', error.message); return []; }
            return (data || []).map(r => r[campo]);
        } catch (e) { return []; }
    };

    [obras, etapas] = await Promise.all([
        safe(dbClient.from('obras').select('nome').order('nome')),
        safe(dbClient.from('etapas').select('nome').order('ordem').order('nome')),
    ]);

    popularSelect('filtroObra',  obras,  'Todas as obras');
    popularSelect('filtroEtapa', etapas, 'Todas as etapas');
    popularSelect('cObra', obras, '— Selecione —');

    // Renderiza checkboxes de etapas no modal (sem seleção inicial)
    renderizarEtapasCheckboxes([]);

    setStatus('online', 'Sistema Sincronizado');
}

// --- CHIPS DE ETAPAS ---
function renderizarEtapasCheckboxes(selecionadas = []) {
    const container = document.getElementById('cEtapasContainer');
    if (!etapas.length) {
        container.innerHTML = '<span style="color:var(--on-surface-muted);font-size:0.8rem;">Nenhuma etapa cadastrada.</span>';
        return;
    }
    container.innerHTML = etapas.map(e => {
        const checked = selecionadas.includes(e);
        return `<label style="${_chipStyle(checked)}">
            <input type="checkbox" value="${esc(e)}" ${checked ? 'checked' : ''} onchange="_atualizarChip(this)" style="position:absolute;opacity:0;width:1px;height:1px;pointer-events:none;">
            ${esc(e)}
        </label>`;
    }).join('');
    _atualizarBotaoTodos();
}

function _chipStyle(checked) {
    return checked
        ? 'display:inline-flex;align-items:center;cursor:pointer;font-size:0.78rem;padding:4px 12px;border-radius:20px;border:1px solid var(--primary);background:var(--primary);color:#fff;font-weight:600;user-select:none;transition:all 0.15s;white-space:nowrap;'
        : 'display:inline-flex;align-items:center;cursor:pointer;font-size:0.78rem;padding:4px 12px;border-radius:20px;border:1px solid var(--outline-ghost);background:var(--surface-container);color:var(--on-surface-muted);font-weight:500;user-select:none;transition:all 0.15s;white-space:nowrap;';
}

function _atualizarChip(cb) {
    const label = cb.closest('label');
    label.style.cssText = _chipStyle(cb.checked);
    _atualizarBotaoTodos();
}

function _atualizarBotaoTodos() {
    const container  = document.getElementById('cEtapasContainer');
    const cbs        = Array.from(container.querySelectorAll('input[type="checkbox"]'));
    const todasMarcadas = cbs.length > 0 && cbs.every(cb => cb.checked);
    const btn = document.getElementById('btnTodasEtapas');
    if (!btn) return;
    if (todasMarcadas) {
        btn.style.background    = 'var(--primary)';
        btn.style.color         = '#fff';
        btn.style.borderColor   = 'var(--primary)';
    } else {
        btn.style.background    = 'var(--surface-low)';
        btn.style.color         = 'var(--on-surface-muted)';
        btn.style.borderColor   = 'var(--outline-ghost)';
    }
}

function selecionarTodasEtapas() {
    const container     = document.getElementById('cEtapasContainer');
    const cbs           = Array.from(container.querySelectorAll('input[type="checkbox"]'));
    const todasMarcadas = cbs.every(cb => cb.checked);
    cbs.forEach(cb => {
        cb.checked = !todasMarcadas;
        _atualizarChip(cb);
    });
}

function getEtapasSelecionadas() {
    const container = document.getElementById('cEtapasContainer');
    return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
}

// --- CARREGAR CONTRATOS ---
async function carregarContratos() {
    if (!dbClient) return;
    document.getElementById('tabelaLoading').style.display = 'flex';

    try {
        const obra       = document.getElementById('filtroObra').value;
        const etapaFiltro = document.getElementById('filtroEtapa').value;
        const fornecedor = document.getElementById('filtroFornecedor').value.trim();

        let q = dbClient
            .from('contratos')
            .select('*')
            .order('created_at', { ascending: false });

        if (obra)       q = q.eq('obra', obra);
        if (fornecedor) q = q.ilike('fornecedor', `%${fornecedor}%`);

        const [
            { data: contratosData, error: contratosErr },
            { data: etapasData,    error: etapasErr    },
            { data: pagData,       error: pagErr        },
        ] = await Promise.all([
            q,
            dbClient.from('contratos_etapas').select('contrato_id, etapa'),
            dbClient.from('contratos_pagamentos').select('contrato_id, valor'),
        ]);

        if (contratosErr) throw contratosErr;
        if (etapasErr)    console.warn('contratos_etapas:', etapasErr.message);
        if (pagErr)       console.warn('contratos_pagamentos:', pagErr.message);

        // Agrupar etapas por contrato_id
        const etapasPorContrato = {};
        (etapasData || []).forEach(e => {
            if (!etapasPorContrato[e.contrato_id]) etapasPorContrato[e.contrato_id] = [];
            etapasPorContrato[e.contrato_id].push(e.etapa);
        });

        // Agrupar pagamentos por contrato_id
        const pagPorContrato = {};
        (pagData || []).forEach(p => {
            pagPorContrato[p.contrato_id] = (pagPorContrato[p.contrato_id] || 0) + Number(p.valor || 0);
        });

        // Enriquecer cada contrato
        let contratos = (contratosData || []).map(c => {
            const pago      = pagPorContrato[c.id] || 0;
            const restante  = Number(c.valor_total || 0) - pago;
            const pct       = Number(c.valor_total || 0) > 0 ? (pago / Number(c.valor_total)) * 100 : 0;
            return {
                ...c,
                etapas_list:    etapasPorContrato[c.id] || [],
                valor_pago:     pago,
                valor_restante: restante,
                pct_execucao:   pct,
                status_calc:    pct >= 100 ? 'concluido' : 'em_andamento',
            };
        });

        // Filtro por etapa (client-side, pois é sobre o array etapas_list)
        if (etapaFiltro) {
            contratos = contratos.filter(c => c.etapas_list.includes(etapaFiltro));
        }

        todosContratos = contratos;
        paginaAtual = 1;
        renderizarTabela();
        atualizarKPIs();
    } catch (e) {
        toast.error('Erro ao carregar contratos: ' + e.message);
    } finally {
        document.getElementById('tabelaLoading').style.display = 'none';
    }
}

// --- FILTRO LOCAL ---
function filtrarContratos() {
    const busca  = document.getElementById('buscaTexto').value.trim().toLowerCase();
    const status = document.getElementById('filtroStatus').value;

    return todosContratos.filter(c => {
        if (status && c.status_calc !== status) return false;
        if (busca) {
            return (c.fornecedor || '').toLowerCase().includes(busca) ||
                   (c.descricao  || '').toLowerCase().includes(busca) ||
                   (c.obra       || '').toLowerCase().includes(busca) ||
                   c.etapas_list.some(e => e.toLowerCase().includes(busca));
        }
        return true;
    });
}

// --- RENDERIZAR TABELA ---
function renderizarTabela() {
    const tbody    = document.getElementById('tabelaBody');
    const filtrado = filtrarContratos();
    const total    = filtrado.length;
    const inicio   = (paginaAtual - 1) * PAGE_SIZE;
    const pagina   = filtrado.slice(inicio, inicio + PAGE_SIZE);
    const paginacaoWrap = document.getElementById('paginacaoWrap');

    if (!pagina.length) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhum contrato encontrado.</td></tr>`;
        paginacaoWrap.style.display = 'none';
        return;
    }

    tbody.innerHTML = pagina.map(c => {
        const pct        = c.pct_execucao || 0;
        const barColor   = pct >= 100 ? 'var(--success)' : 'var(--primary)';
        const statusBadge = c.status_calc === 'concluido'
            ? `<span style="font-size:0.7rem;padding:2px 7px;background:rgba(34,197,94,0.15);color:var(--success);border-radius:4px;font-weight:600;">Concluído</span>`
            : `<span style="font-size:0.7rem;padding:2px 7px;background:var(--surface-low);color:var(--on-surface-muted);border-radius:4px;font-weight:600;">Em Andamento</span>`;

        // Etapas como badges ou texto
        const etapasBadges = c.etapas_list.length
            ? c.etapas_list.map(e =>
                `<span style="font-size:0.68rem;padding:2px 6px;background:var(--surface-low);border:1px solid var(--outline-ghost);border-radius:4px;white-space:nowrap;">${esc(e)}</span>`
              ).join('')
            : '<span style="color:var(--on-surface-muted);">—</span>';

        return `<tr>
            <td style="white-space:nowrap;">${formatarData(c.data_assinatura)}</td>
            <td>${esc(c.obra || '—')}</td>
            <td style="max-width:260px;">
                <div style="display:flex; flex-wrap:wrap; gap:4px; max-height:60px; overflow-y:auto; align-content:flex-start; scrollbar-width:thin; padding-right:4px;">
                    ${etapasBadges}
                </div>
            </td>
            <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(c.fornecedor)}">${esc(c.fornecedor || '—')}</td>
            <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(c.descricao)}">${esc(c.descricao || '—')}</td>
            <td class="text-right fin-num">R$ ${formatarValor(c.valor_total)}</td>
            <td class="text-right fin-num" style="color:var(--success);">R$ ${formatarValor(c.valor_pago)}</td>
            <td class="text-right fin-num" style="color:${c.valor_restante > 0 ? 'var(--warning)' : 'var(--success)'};">R$ ${formatarValor(c.valor_restante)}</td>
            <td>
                <div style="display:flex;align-items:center;gap:6px;">
                    <div style="flex:1;height:4px;background:var(--surface-low);border-radius:2px;overflow:hidden;">
                        <div style="width:${Math.min(pct, 100)}%;height:100%;background:${barColor};border-radius:2px;"></div>
                    </div>
                    <span style="font-size:0.78rem;font-weight:600;min-width:42px;text-align:right;">${pct.toFixed(1)}%</span>
                </div>
                <div style="margin-top:3px;">${statusBadge}</div>
            </td>
            <td style="text-align:center;white-space:nowrap;">
                <button class="btn btn-primary" onclick="abrirModalPagamentos(${c.id})" style="font-size:0.72rem;padding:3px 8px;margin-right:3px;" title="Pagamentos">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="1" x2="12" y2="23"></line>
                        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
                    </svg>
                    Pgtos
                </button>
                <button class="btn btn-outline" onclick="abrirModalContrato(${c.id})" style="font-size:0.72rem;padding:3px 8px;" title="Editar">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button class="btn btn-outline" onclick="excluirContrato(${c.id})" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Excluir">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`;
    }).join('');

    if (total > PAGE_SIZE) {
        paginacaoWrap.style.display = 'flex';
        document.getElementById('paginacaoInfo').textContent =
            `Exibindo ${inicio + 1}–${Math.min(inicio + PAGE_SIZE, total)} de ${total}`;
        document.getElementById('btnPagAnterior').disabled = paginaAtual === 1;
        document.getElementById('btnPagProxima').disabled  = (paginaAtual * PAGE_SIZE) >= total;
    } else {
        paginacaoWrap.style.display = 'none';
    }
}

// --- KPIs ---
function atualizarKPIs() {
    const totalContratado = todosContratos.reduce((s, c) => s + Number(c.valor_total || 0), 0);
    const totalPago       = todosContratos.reduce((s, c) => s + (c.valor_pago || 0), 0);
    const totalRestante   = totalContratado - totalPago;
    const execMedia       = totalContratado > 0 ? (totalPago / totalContratado) * 100 : 0;

    document.getElementById('kpiTotalContratos').textContent = `R$ ${formatarValor(totalContratado)}`;
    document.getElementById('kpiTotalPago').textContent      = `R$ ${formatarValor(totalPago)}`;
    document.getElementById('kpiTotalRestante').textContent  = `R$ ${formatarValor(totalRestante)}`;
    document.getElementById('kpiExecucaoMedia').textContent  = totalContratado > 0 ? `${execMedia.toFixed(1)}%` : '—';
}

// --- LIMPAR FILTROS ---
function limparFiltros() {
    ['filtroObra', 'filtroEtapa', 'filtroStatus'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('filtroFornecedor').value = '';
    document.getElementById('buscaTexto').value = '';
    paginaAtual = 1;
    carregarContratos();
}

// ===================== MODAL CONTRATO =====================

function abrirModalContrato(id) {
    editandoContratoId = id;
    document.getElementById('modalContratoTitulo').textContent = id ? 'Editar Contrato' : 'Novo Contrato';

    // Resetar campos
    document.getElementById('cFornecedor').value     = '';
    document.getElementById('cValorTotal').value     = '';
    document.getElementById('cDataAssinatura').value = hoje();
    document.getElementById('cDescricao').value      = '';
    document.getElementById('cObservacao').value     = '';
    document.getElementById('cObra').value           = '';
    renderizarEtapasCheckboxes([]);

    if (id) {
        const c = todosContratos.find(x => x.id === id);
        if (c) {
            document.getElementById('cFornecedor').value     = c.fornecedor      || '';
            document.getElementById('cValorTotal').value     = c.valor_total     || '';
            document.getElementById('cDataAssinatura').value = c.data_assinatura || '';
            document.getElementById('cDescricao').value      = c.descricao       || '';
            document.getElementById('cObservacao').value     = c.observacao      || '';
            setSelectValue('cObra', c.obra);
            renderizarEtapasCheckboxes(c.etapas_list || []);
        }
    }

    document.getElementById('modalContrato').style.display = 'flex';
}

function fecharModalContrato() {
    document.getElementById('modalContrato').style.display = 'none';
    editandoContratoId = null;
}

async function salvarContrato() {
    const fornecedor = document.getElementById('cFornecedor').value.trim();
    const valor      = parseFloat(document.getElementById('cValorTotal').value);
    const obra       = document.getElementById('cObra').value;
    const descricao  = document.getElementById('cDescricao').value.trim();
    const etapasSel  = getEtapasSelecionadas();

    if (!fornecedor)                { toast.warning('Informe o fornecedor.'); return; }
    if (isNaN(valor) || valor <= 0) { toast.warning('Informe um valor total válido.'); return; }
    if (!obra)                      { toast.warning('Selecione a obra.'); return; }
    if (!etapasSel.length)          { toast.warning('Selecione ao menos uma etapa.'); return; }
    if (!descricao)                 { toast.warning('Informe a descrição do contrato.'); return; }

    const payload = {
        fornecedor,
        valor_total:     Math.round(valor * 100) / 100,
        obra,
        etapa:           etapasSel[0],   // coluna legada NOT NULL; etapas completas em contratos_etapas
        descricao,
        data_assinatura: document.getElementById('cDataAssinatura').value || null,
        observacao:      document.getElementById('cObservacao').value.trim() || null,
    };

    const btn = document.getElementById('btnSalvarContrato');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        if (fornecedor) {
            const { error: fErr } = await dbClient.from('fornecedores').upsert({ nome: fornecedor }, { onConflict: 'nome' });
            if (fErr) throw fErr;
        }
        let contratoId = editandoContratoId;

        if (editandoContratoId) {
            const { error } = await dbClient.from('contratos').update(payload).eq('id', editandoContratoId);
            if (error) throw error;
        } else {
            const { data, error } = await dbClient.from('contratos').insert(payload).select('id').single();
            if (error) throw error;
            contratoId = data.id;
        }

        // Gerenciar contratos_etapas: apaga as existentes e reinsere
        await dbClient.from('contratos_etapas').delete().eq('contrato_id', contratoId);
        const etapasRows = etapasSel.map(e => ({ contrato_id: contratoId, etapa: e }));
        const { error: etapasErr } = await dbClient.from('contratos_etapas').insert(etapasRows);
        if (etapasErr) throw etapasErr;

        toast.success(editandoContratoId ? 'Contrato atualizado.' : 'Contrato cadastrado.');
        fecharModalContrato();
        await carregarContratos();
    } catch (e) {
        toast.error('Erro ao salvar: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

async function excluirContrato(id) {
    const c = todosContratos.find(x => x.id === id);
    if (!c) return;
    const label = `${c.fornecedor} — ${c.descricao}`;
    if (!confirm(`Excluir o contrato "${label}"?\n\nOs pagamentos vinculados e as despesas geradas também serão excluídos.`)) return;

    try {
        // Buscar despesas vinculadas para remover
        const { data: pags } = await dbClient
            .from('contratos_pagamentos')
            .select('despesa_id')
            .eq('contrato_id', id);

        for (const p of (pags || [])) {
            if (p.despesa_id) {
                await dbClient.from('comprovantes_despesa').delete().eq('despesa_id', p.despesa_id);
                await dbClient.from('c_despesas').delete().eq('id', p.despesa_id);
            }
        }

        // Excluir contrato (CASCADE remove contratos_etapas e contratos_pagamentos)
        const { error } = await dbClient.from('contratos').delete().eq('id', id);
        if (error) throw error;

        todosContratos = todosContratos.filter(x => x.id !== id);
        renderizarTabela();
        atualizarKPIs();
        toast.success('Contrato excluído.');
    } catch (e) {
        toast.error('Erro ao excluir: ' + e.message);
    }
}

// ===================== MODAL PAGAMENTOS =====================

async function abrirModalPagamentos(contratoId) {
    const c = todosContratos.find(x => x.id === contratoId);
    if (!c) return;

    contratoAtivoPag = contratoId;

    document.getElementById('modalPagTitulo').textContent    = `Pagamentos — ${c.fornecedor}`;
    document.getElementById('modalPagSubtitulo').textContent = `${c.obra} › ${c.descricao}`;

    // Resetar formulário
    document.getElementById('pData').value      = hoje();
    document.getElementById('pValor').value      = '';
    document.getElementById('pDescricao').value  = '';
    document.getElementById('uploadZonePagText').textContent = 'Arquivo';
    document.getElementById('uploadZonePag').style.borderColor = '';
    document.getElementById('inputComprovantePag').value = '';
    arquivoPagamento = null;

    // Preencher select de etapa do pagamento
    const pEtapa = document.getElementById('pEtapa');
    pEtapa.innerHTML = '<option value="">— Sem etapa específica —</option>' +
        (c.etapas_list || []).map(e => `<option value="${esc(e)}">${esc(e)}</option>`).join('');
    // Auto-selecionar se só tiver uma etapa
    if (c.etapas_list && c.etapas_list.length === 1) {
        pEtapa.value = c.etapas_list[0];
    }

    // Buscar pagamentos do contrato
    try {
        const { data, error } = await dbClient
            .from('contratos_pagamentos')
            .select('*')
            .eq('contrato_id', contratoId)
            .order('data', { ascending: true });
        if (error) throw error;
        pagamentosAtivos = data || [];
    } catch (e) {
        pagamentosAtivos = [];
        toast.warning('Erro ao carregar pagamentos: ' + e.message);
    }

    atualizarResumoPagamentos(c);
    renderizarPagamentos();

    document.getElementById('modalPagamentos').style.display = 'flex';
}

function fecharModalPagamentos() {
    document.getElementById('modalPagamentos').style.display = 'none';
    contratoAtivoPag = null;
    pagamentosAtivos = [];
    arquivoPagamento = null;
}

function atualizarResumoPagamentos(contrato) {
    const c         = contrato || todosContratos.find(x => x.id === contratoAtivoPag);
    if (!c) return;
    const totalPago = pagamentosAtivos.reduce((s, p) => s + Number(p.valor || 0), 0);
    const restante  = Number(c.valor_total || 0) - totalPago;
    const pct       = Number(c.valor_total || 0) > 0 ? (totalPago / Number(c.valor_total)) * 100 : 0;

    document.getElementById('pagSumTotal').textContent    = `R$ ${formatarValor(c.valor_total)}`;
    document.getElementById('pagSumPago').textContent     = `R$ ${formatarValor(totalPago)}`;
    document.getElementById('pagSumRestante').textContent = `R$ ${formatarValor(restante)}`;
    document.getElementById('pagSumExec').textContent     = `${pct.toFixed(1)}%`;
    document.getElementById('pagExecBar').style.width     = `${Math.min(pct, 100)}%`;
    document.getElementById('pagExecBar').style.background = pct >= 100 ? 'var(--success)' : 'var(--primary)';

    // Atualizar row em memória
    const idx = todosContratos.findIndex(x => x.id === contratoAtivoPag);
    if (idx >= 0) {
        todosContratos[idx].valor_pago     = totalPago;
        todosContratos[idx].valor_restante = restante;
        todosContratos[idx].pct_execucao   = pct;
        todosContratos[idx].status_calc    = pct >= 100 ? 'concluido' : 'em_andamento';
        renderizarTabela();
        atualizarKPIs();
    }
}

function renderizarPagamentos() {
    const tbody = document.getElementById('pagamentosBody');

    if (!pagamentosAtivos.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-5);">Nenhum pagamento registrado.</td></tr>`;
        return;
    }

    tbody.innerHTML = pagamentosAtivos.map(p => {
        const nfIcon = p.comprovante_url
            ? `<a href="${p.comprovante_url}" target="_blank" title="Ver comprovante" style="color:var(--secondary);">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg></a>`
            : '—';
        const etapaLabel = p.etapa
            ? `<span style="font-size:0.7rem;padding:1px 5px;background:var(--surface-low);border:1px solid var(--outline-ghost);border-radius:4px;">${esc(p.etapa)}</span>`
            : '';

        return `<tr>
            <td style="white-space:nowrap;">${formatarData(p.data)}</td>
            <td>${esc(p.descricao || '—')} ${etapaLabel}</td>
            <td class="text-right fin-num" style="font-weight:600;">R$ ${formatarValor(p.valor)}</td>
            <td style="text-align:center;">${nfIcon}</td>
            <td style="text-align:center;">
                <button class="btn btn-outline" onclick="excluirPagamento(${p.id})" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Excluir">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`;
    }).join('');
}

// --- ADICIONAR PAGAMENTO ---
async function adicionarPagamento() {
    const data      = document.getElementById('pData').value;
    const valor     = parseFloat(document.getElementById('pValor').value);
    const etapa     = document.getElementById('pEtapa').value || null;
    const descricao = document.getElementById('pDescricao').value.trim();

    if (!data)                      { toast.warning('Informe a data do pagamento.'); return; }
    if (isNaN(valor) || valor <= 0) { toast.warning('Informe um valor válido.'); return; }

    const c = todosContratos.find(x => x.id === contratoAtivoPag);
    if (!c) return;

    const btn = document.getElementById('btnAdicionarPagamento');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        // 1. Upload comprovante (opcional)
        let comprovanteUrl = null;
        if (arquivoPagamento) {
            comprovanteUrl = await uploadComprovante(arquivoPagamento);
        }

        // 2. Criar despesa em c_despesas
        // Etapa: usa a selecionada no pagamento, senão a primeira do contrato, senão null
        const etapaDespesa = etapa || (c.etapas_list && c.etapas_list[0]) || null;
        const descDespesa  = descricao ? `${descricao} — ${c.descricao}` : c.descricao;

        if (c.fornecedor) {
            await dbClient.from('fornecedores').upsert({ nome: c.fornecedor }, { onConflict: 'nome' });
        }

        const despesaPayload = {
            obra:            c.obra,
            etapa:           etapaDespesa,
            fornecedor:      c.fornecedor,
            tipo:            'Mão de Obra',
            despesa:         'SALÁRIO PESSOAL',
            valor_total:     Math.round(valor * 100) / 100,
            data:            data,
            descricao:       descDespesa,
            tem_nota_fiscal: comprovanteUrl ? true : false,
        };

        const { data: despesaData, error: despesaErr } = await dbClient
            .from('c_despesas')
            .insert(despesaPayload)
            .select('id')
            .single();
        if (despesaErr) throw despesaErr;

        const despesaId = despesaData.id;

        // 3. Vincular comprovante à despesa
        if (comprovanteUrl && despesaId) {
            const ext  = arquivoPagamento.name.split('.').pop().toLowerCase();
            const nome = `ctr_${despesaId}_${Date.now()}.${ext}`;
            await dbClient.from('comprovantes_despesa').insert({
                despesa_id:   despesaId,
                url:          comprovanteUrl,
                nome_arquivo: nome,
            });
        }

        // 4. Inserir em contratos_pagamentos
        const { data: pagData, error: pagErr } = await dbClient
            .from('contratos_pagamentos')
            .insert({
                contrato_id:     contratoAtivoPag,
                despesa_id:      despesaId,
                etapa:           etapa || null,
                data:            data,
                valor:           Math.round(valor * 100) / 100,
                descricao:       descricao || null,
                comprovante_url: comprovanteUrl || null,
            })
            .select('*')
            .single();
        if (pagErr) throw pagErr;

        // 5. Atualizar estado
        pagamentosAtivos.push(pagData);
        atualizarResumoPagamentos();
        renderizarPagamentos();

        // 6. Resetar formulário
        document.getElementById('pValor').value     = '';
        document.getElementById('pDescricao').value  = '';
        document.getElementById('pData').value       = hoje();
        document.getElementById('pEtapa').value      = c.etapas_list && c.etapas_list.length === 1 ? c.etapas_list[0] : '';
        document.getElementById('uploadZonePagText').textContent = 'Arquivo';
        document.getElementById('uploadZonePag').style.borderColor = '';
        document.getElementById('inputComprovantePag').value = '';
        arquivoPagamento = null;

        toast.success('Pagamento registrado e despesa criada.');
    } catch (e) {
        toast.error('Erro ao registrar pagamento: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Adicionar';
    }
}

// --- EXCLUIR PAGAMENTO ---
async function excluirPagamento(pagId) {
    const p = pagamentosAtivos.find(x => x.id === pagId);
    if (!p) return;
    if (!confirm('Excluir este pagamento? A despesa correspondente também será removida.')) return;

    try {
        if (p.despesa_id) {
            await dbClient.from('comprovantes_despesa').delete().eq('despesa_id', p.despesa_id);
            await dbClient.from('c_despesas').delete().eq('id', p.despesa_id);
        }
        const { error } = await dbClient.from('contratos_pagamentos').delete().eq('id', pagId);
        if (error) throw error;

        pagamentosAtivos = pagamentosAtivos.filter(x => x.id !== pagId);
        atualizarResumoPagamentos();
        renderizarPagamentos();
        toast.success('Pagamento excluído.');
    } catch (e) {
        toast.error('Erro ao excluir: ' + e.message);
    }
}

// --- UPLOAD COMPROVANTE ---
function definirArquivoPagamento(file) {
    arquivoPagamento = file;
    document.getElementById('uploadZonePagText').textContent = `📎 ${file.name}`;
    document.getElementById('uploadZonePag').style.borderColor = 'var(--primary)';
}

async function uploadComprovante(file) {
    try {
        const ext  = file.name.split('.').pop().toLowerCase();
        const nome = `ctr_${crypto.randomUUID().replace(/-/g,'').slice(0,12)}.${ext}`;
        const { error } = await dbClient.storage.from('comprovantes').upload(nome, file, { contentType: file.type });
        if (error) throw error;
        return `${window.ENV.SUPABASE_URL.replace(/\/$/, '')}/storage/v1/object/public/comprovantes/${nome}`;
    } catch (e) {
        toast.warning(`Comprovante não pôde ser salvo: ${e.message}`);
        return null;
    }
}

// --- EXPORT CSV ---
function exportarCSV() {
    const dados = filtrarContratos();
    if (!dados.length) { toast.warning('Nenhum dado para exportar.'); return; }

    const cab  = ['Data Assinatura','Obra','Etapas','Fornecedor','Descrição','Valor Total','Pago','Restante','% Execução','Status'];
    const rows = dados.map(c => [
        c.data_assinatura || '',
        c.obra        || '',
        (c.etapas_list || []).join('; '),
        c.fornecedor  || '',
        c.descricao   || '',
        c.valor_total || 0,
        c.valor_pago  || 0,
        c.valor_restante || 0,
        (c.pct_execucao || 0).toFixed(1) + '%',
        c.status_calc === 'concluido' ? 'Concluído' : 'Em Andamento',
    ].map(v => `"${String(v).replace(/"/g,'""')}"`).join(','));

    const csv  = [cab.join(','), ...rows].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `contratos_${hoje()}.csv`; a.click();
    URL.revokeObjectURL(url);
}
