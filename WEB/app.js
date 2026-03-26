/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Dashboard principal (app.js)
 */

// --- SUPABASE ---
let SUPABASE_URL = '';
let SUPABASE_ANON_KEY = '';
let dbClient;

function carregarEnv() {
    if (window.ENV) {
        SUPABASE_URL = window.ENV.SUPABASE_URL;
        SUPABASE_ANON_KEY = window.ENV.SUPABASE_ANON_KEY;
        if (SUPABASE_URL && SUPABASE_ANON_KEY) {
            dbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        } else {
            console.error("Chaves não encontradas em env.js");
        }
    } else {
        console.error("window.ENV não encontrado. Verifique env.js.");
    }
}

// --- ESTADO ---
let rawData = [];
let filteredData = [];
let currentObraFilters  = [];   // vazio = nenhuma obra selecionada
let currentEtapaFilters = [];
let currentTipoFilters  = [];

// --- INICIALIZAÇÃO ---
document.addEventListener('DOMContentLoaded', async () => {
    carregarEnv();
    await carregarDados();

    // Move dropdown lists to body so position:fixed works correctly
    ['obraCheckboxes', 'etapaCheckboxes', 'tipoCheckboxes'].forEach(id => {
        const el = document.getElementById(id);
        if (el) document.body.appendChild(el);
    });

    configurarFiltrosMultiplos('obraCheckboxes',  'obraDropdownText',  'obra');
    configurarFiltrosMultiplos('etapaCheckboxes', 'etapaDropdownText', 'etapa');
    configurarFiltrosMultiplos('tipoCheckboxes',  'tipoDropdownText',  'tipo');

    setupDropdown('obraDropdownHeader',  'obraCheckboxes');
    setupDropdown('etapaDropdownHeader', 'etapaCheckboxes');
    setupDropdown('tipoDropdownHeader',  'tipoCheckboxes');

    document.getElementById('refreshBtn').addEventListener('click', async () => {
        const btn = document.getElementById('refreshBtn');
        btn.textContent = 'Atualizando…';
        btn.disabled = true;
        await carregarDados();
        btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg> Atualizar`;
        btn.disabled = false;
    });

    // Botão "Relatório Inteligente" agora é um <a href>, sem listener necessário.

    document.getElementById('applyFiltersBtn').addEventListener('click', atualizarDashboard);
});

// --- DROPDOWN SETUP ---
function positionDropdown(header, list) {
    const rect = header.getBoundingClientRect();
    list.style.top   = (rect.bottom + 4) + 'px';
    list.style.left  = rect.left + 'px';
    list.style.width = rect.width + 'px';
}

function setupDropdown(headerId, listId) {
    const header = document.getElementById(headerId);
    const list   = document.getElementById(listId);

    header.addEventListener('click', (e) => {
        e.stopPropagation();
        document.querySelectorAll('.dropdown-list.show').forEach(el => {
            if (el.id !== listId) {
                el.classList.remove('show');
                const h = document.getElementById(el.id.replace('Checkboxes', 'DropdownHeader'));
                if (h) h.classList.remove('active');
            }
        });
        const opening = !list.classList.contains('show');
        list.classList.toggle('show');
        header.classList.toggle('active');
        if (opening) positionDropdown(header, list);
    });

    document.addEventListener('click', (e) => {
        if (!header.contains(e.target) && !list.contains(e.target)) {
            list.classList.remove('show');
            header.classList.remove('active');
        }
    });
}

// --- FILTROS MÚLTIPLOS ---
function configurarFiltrosMultiplos(containerId, textId, filterType) {
    const container   = document.getElementById(containerId);
    const textElement = document.getElementById(textId);

    container.addEventListener('change', (e) => {
        if (e.target.tagName !== 'INPUT' || e.target.type !== 'checkbox') return;

        const checkboxes   = Array.from(container.querySelectorAll('input[type="checkbox"]'));
        const checkedBoxes = checkboxes.filter(cb => cb.checked);
        const values       = checkedBoxes.map(cb => cb.value);

        if (filterType === 'obra') {
            currentObraFilters = values;
            povoarFiltroEtapas();
            povoarFiltroTipos();
        } else if (filterType === 'etapa') {
            currentEtapaFilters = values;
        } else if (filterType === 'tipo') {
            currentTipoFilters = values;
        }

        const defaults = { obra: 'Selecionar Obras', etapa: 'Todas as Etapas', tipo: 'Todos os Tipos' };
        const todos    = { obra: 'Todas as Obras',   etapa: 'Todas as Etapas', tipo: 'Todos os Tipos' };
        const plurals  = { obra: 'obras', etapa: 'etapas', tipo: 'tipos' };

        if (values.length === 0) {
            textElement.textContent = defaults[filterType];
        } else if (values.length === checkboxes.length) {
            textElement.textContent = todos[filterType];
        } else if (values.length === 1) {
            textElement.textContent = checkedBoxes[0].parentElement.textContent.trim();
        } else {
            textElement.textContent = `${values.length} ${plurals[filterType]} selecionados`;
        }

        atualizarDashboard();
    });
}

// --- CARREGAR DADOS ---
async function carregarDados() {
    try {
        if (!dbClient) throw new Error("Cliente Supabase não inicializado.");

        const [resOrc, resDesp] = await Promise.all([
            dbClient.from('orcamentos').select('obra, etapa, tipo_custo, valor_estimado'),
            dbClient.from('c_despesas').select('obra, etapa, tipo, valor_total'),
        ]);

        if (resOrc.error)  throw resOrc.error;
        if (resDesp.error) throw resDesp.error;

        const gastos = {};
        (resDesp.data || []).forEach(d => {
            const key = `${d.obra}||${d.etapa}||${d.tipo || 'Geral'}`;
            gastos[key] = (gastos[key] || 0) + Number(d.valor_total || 0);
        });

        const visto = new Set();
        rawData = (resOrc.data || []).map(o => {
            const tipo = o.tipo_custo || 'Geral';
            const key  = `${o.obra}||${o.etapa}||${tipo}`;
            visto.add(key);
            const gasto = gastos[key] || 0;
            const orc   = Number(o.valor_estimado || 0);
            return { OBRA: o.obra, ETAPA: o.etapa, TIPO_CUSTO: tipo,
                     ORÇAMENTO_ESTIMADO: orc, GASTO_REALIZADO: gasto, SALDO_ETAPA: orc - gasto };
        });

        Object.entries(gastos).forEach(([key, gasto]) => {
            if (!visto.has(key)) {
                const [obra, etapa, tipo] = key.split('||');
                rawData.push({ OBRA: obra, ETAPA: etapa, TIPO_CUSTO: tipo,
                               ORÇAMENTO_ESTIMADO: 0, GASTO_REALIZADO: gasto, SALDO_ETAPA: -gasto });
            }
        });

        setStatus('online', 'Sistema Sincronizado');

        if (document.getElementById('obraCheckboxes').children.length === 0) {
            currentObraFilters  = [];
            currentEtapaFilters = [];
            currentTipoFilters  = [];
            povoarFiltroObras();
        }
        povoarFiltroTipos();

        atualizarDashboard();

    } catch (error) {
        console.error("Erro ao carregar dados:", error);
        setStatus('offline', 'Erro de conexão');
    }
}

// --- POPULAR FILTROS ---
function povoarFiltroObras() {
    const container = document.getElementById('obraCheckboxes');
    container.innerHTML = '';
    const obras = [...new Set(rawData.map(i => i.OBRA))].filter(Boolean).sort();
    obras.forEach(obra => {
        container.innerHTML += `<label class="checkbox-item"><input type="checkbox" value="${obra}"> ${obra}</label>`;
    });
}

function povoarFiltroEtapas() {
    const container = document.getElementById('etapaCheckboxes');
    container.innerHTML = '';

    if (currentObraFilters.length === 0) {
        currentEtapaFilters = [];
        document.getElementById('etapaDropdownText').textContent = 'Todas as Etapas';
        return;
    }

    const filtradas  = rawData.filter(i => currentObraFilters.includes(i.OBRA));
    const etapas     = [...new Set(filtradas.map(i => i.ETAPA))].filter(Boolean).sort();
    const stillValid = currentEtapaFilters.filter(e => etapas.includes(e));
    currentEtapaFilters = stillValid.length === 0 ? [...etapas] : stillValid;

    etapas.forEach(etapa => {
        const chk = currentEtapaFilters.includes(etapa) ? 'checked' : '';
        container.innerHTML += `<label class="checkbox-item"><input type="checkbox" value="${etapa}" ${chk}> ${etapa}</label>`;
    });

    const el = document.getElementById('etapaDropdownText');
    el.textContent = currentEtapaFilters.length === etapas.length ? 'Todas as Etapas'
        : currentEtapaFilters.length === 1 ? currentEtapaFilters[0]
        : `${currentEtapaFilters.length} etapas selecionadas`;
}

function povoarFiltroTipos() {
    const container = document.getElementById('tipoCheckboxes');
    container.innerHTML = '';

    const fonte  = currentObraFilters.length > 0
        ? rawData.filter(i => currentObraFilters.includes(i.OBRA))
        : rawData;
    const tipos      = [...new Set(fonte.map(i => i.TIPO_CUSTO))].filter(Boolean).sort();
    const stillValid = currentTipoFilters.filter(e => tipos.includes(e));
    currentTipoFilters = stillValid.length === 0 ? [...tipos] : stillValid;

    tipos.forEach(tipo => {
        const chk = currentTipoFilters.includes(tipo) ? 'checked' : '';
        container.innerHTML += `<label class="checkbox-item"><input type="checkbox" value="${tipo}" ${chk}> ${tipo}</label>`;
    });

    const el = document.getElementById('tipoDropdownText');
    el.textContent = currentTipoFilters.length === tipos.length ? 'Todos os Tipos'
        : currentTipoFilters.length === 1 ? currentTipoFilters[0]
        : `${currentTipoFilters.length} tipos selecionados`;
}

// --- ATUALIZAR DASHBOARD ---
async function atualizarDashboard() {
    // Sem obra selecionada → estado vazio
    if (currentObraFilters.length === 0) {
        resetarKPIs();
        renderizarTabelaVazia();
        ocultarFluxo();
        document.getElementById('dashboardTitle').textContent = 'Visão Geral';
        return;
    }

    filteredData = rawData.filter(i =>
        currentObraFilters.includes(i.OBRA) &&
        (currentEtapaFilters.length === 0 || currentEtapaFilters.includes(i.ETAPA)) &&
        (currentTipoFilters.length === 0   || currentTipoFilters.includes(i.TIPO_CUSTO))
    );

    const todasObrasQtd  = [...new Set(rawData.map(i => i.OBRA))].filter(Boolean).length;
    const todasEtapasQtd = [...new Set(rawData.filter(i => currentObraFilters.includes(i.OBRA)).map(i => i.ETAPA))].filter(Boolean).length;
    const filtroGlobal   = currentObraFilters.length === todasObrasQtd && currentEtapaFilters.length === todasEtapasQtd;

    document.getElementById('dashboardTitle').textContent = filtroGlobal
        ? 'Visão Geral'
        : currentObraFilters.length === 1
            ? currentObraFilters[0]
            : `${currentObraFilters.length} Obras Selecionadas`;

    // KPIs — Orçamento, Custo Realizado, % Consumo
    const orcTotal   = filteredData.reduce((s, i) => s + Number(i.ORÇAMENTO_ESTIMADO || 0), 0);
    const gastoTotal = filteredData.reduce((s, i) => s + Number(i.GASTO_REALIZADO    || 0), 0);
    const pctConsumo = orcTotal > 0 ? (gastoTotal / orcTotal) * 100 : 0;

    document.getElementById('kpiOrcamento').textContent  = formatCurrency(orcTotal);
    document.getElementById('kpiRealizado').textContent  = formatCurrency(gastoTotal);
    document.getElementById('kpiConsumo').textContent    = `${pctConsumo.toFixed(1)}%`;
    document.getElementById('kpiConsumoMin').textContent = `${pctConsumo.toFixed(1)}%`;

    const fill = document.getElementById('kpiConsumoBar');
    fill.style.width = `${Math.min(pctConsumo, 100)}%`;
    fill.className   = pctConsumo > 100 ? 'progress-fill over-budget' : 'progress-fill';

    // % Realização — busca taxa_conclusao das obras selecionadas
    await atualizarRealizacao(orcTotal);

    renderizarTabela();

    // Fluxo de Caixa — busca dados financeiros das obras selecionadas
    await atualizarFluxoCaixa(gastoTotal);
}

// --- % REALIZAÇÃO ---
async function atualizarRealizacao(orcTotal) {
    const realizacaoEl  = document.getElementById('kpiRealizacao');
    const realizacaoBar = document.getElementById('kpiRealizacaoBar');
    const realizacaoMin = document.getElementById('kpiRealizacaoMin');

    if (!dbClient) return;

    try {
        const { data, error } = await dbClient
            .from('taxa_conclusao')
            .select('obra, etapa, taxa')
            .in('obra', currentObraFilters);

        if (error) throw error;

        let pctReal = 0;

        if (data && data.length > 0) {
            if (orcTotal > 0) {
                // Média ponderada por orçamento de cada etapa
                let numPonderado = 0;
                data.forEach(t => {
                    const etapaOrc = rawData
                        .filter(r => r.OBRA === t.obra && r.ETAPA === t.etapa)
                        .reduce((s, r) => s + Number(r.ORÇAMENTO_ESTIMADO || 0), 0);
                    numPonderado += Number(t.taxa || 0) * etapaOrc;
                });
                pctReal = numPonderado / orcTotal;
            } else {
                const soma = data.reduce((s, t) => s + Number(t.taxa || 0), 0);
                pctReal = soma / data.length;
            }
        }

        realizacaoEl.textContent  = `${pctReal.toFixed(1)}%`;
        realizacaoMin.textContent = `${pctReal.toFixed(1)}%`;
        realizacaoBar.style.width = `${Math.min(pctReal, 100)}%`;
        realizacaoBar.className   = pctReal > 100 ? 'progress-fill over-budget' : 'progress-fill';

    } catch (err) {
        console.warn("Erro ao carregar % Realização:", err);
        realizacaoEl.textContent = '—%';
    }
}

// --- FLUXO DE CAIXA ---
async function atualizarFluxoCaixa(gastoTotal) {
    const section = document.getElementById('fluxoSection');
    if (!dbClient) { section.style.display = 'none'; return; }

    try {
        const [resRec, resCap, resCtr] = await Promise.all([
            dbClient.from('recebimentos')
                .select('valor')
                .in('obra', currentObraFilters),
            dbClient.from('c_despesas')
                .select('valor_total')
                .in('obra', currentObraFilters)
                .not('vencimento', 'is', null)
                .eq('paga', false),
            dbClient.from('contratos')
                .select('id, valor_total')
                .in('obra', currentObraFilters),
        ]);

        const recebido    = (resRec.data  || []).reduce((s, r) => s + Number(r.valor || 0), 0);
        const aPagar      = (resCap.data  || []).reduce((s, r) => s + Number(r.valor_total || 0), 0);

        // Contratos — busca pagamentos dos contratos encontrados
        const ctrTotal = (resCtr.data || []).reduce((s, c) => s + Number(c.valor_total || 0), 0);
        let ctrPago = 0;
        const ctrIds = (resCtr.data || []).map(c => c.id);
        if (ctrIds.length > 0) {
            const { data: pagData } = await dbClient
                .from('contratos_pagamentos')
                .select('valor')
                .in('contrato_id', ctrIds);
            ctrPago = (pagData || []).reduce((s, p) => s + Number(p.valor || 0), 0);
        }

        document.getElementById('fluxoContratosTotal').textContent     = formatCurrency(ctrTotal);
        document.getElementById('fluxoContratosPago').textContent      = formatCurrency(ctrPago);
        document.getElementById('fluxoContratosRestante').textContent  = formatCurrency(ctrTotal - ctrPago);
        const saldoAtual  = recebido - gastoTotal;
        const saldoProj   = recebido - gastoTotal - aPagar;

        const kpiSaldo    = document.getElementById('kpiSaldoCaixa');
        const kpiSaldoSub = document.getElementById('kpiSaldoCaixaSub');
        if (kpiSaldo) {
            kpiSaldo.textContent = formatCurrency(recebido);
            kpiSaldo.style.color = 'var(--success)';
        }
        if (kpiSaldoSub) {
            const saldo = recebido - gastoTotal;
            kpiSaldoSub.textContent = `Saldo: ${formatCurrency(saldo)}`;
            kpiSaldoSub.style.color = saldo >= 0 ? 'var(--success)' : 'var(--error)';
        }

        const colorSaldoAtual = saldoAtual >= 0 ? 'var(--success)' : 'var(--error)';
        const colorSaldoProj  = saldoProj  >= 0 ? 'var(--success)' : 'var(--error)';

        document.getElementById('fluxoRecebido').textContent      = formatCurrency(recebido);
        document.getElementById('fluxoGasto').textContent         = formatCurrency(gastoTotal);
        document.getElementById('fluxoAPagar').textContent        = formatCurrency(aPagar);
        document.getElementById('fluxoSaldoAtual').textContent    = formatCurrency(saldoAtual);
        document.getElementById('fluxoSaldoProjetado').textContent = formatCurrency(saldoProj);

        document.getElementById('fluxoSaldoAtual').style.color    = colorSaldoAtual;
        document.getElementById('fluxoSaldoProjetado').style.color = colorSaldoProj;

        section.style.display = '';

    } catch (err) {
        console.error("Erro ao carregar fluxo de caixa:", err.message, err);
        section.style.display = 'none';
    }
}

// --- HELPERS ---
function ocultarFluxo() {
    const section = document.getElementById('fluxoSection');
    if (section) section.style.display = 'none';
}

function resetarKPIs() {
    document.getElementById('kpiOrcamento').textContent   = 'R$ —';
    document.getElementById('kpiRealizado').textContent   = 'R$ —';
    document.getElementById('kpiConsumo').textContent     = '—%';
    document.getElementById('kpiConsumoMin').textContent  = '0%';
    document.getElementById('kpiConsumoBar').style.width  = '0%';
    document.getElementById('kpiRealizacao').textContent  = '—%';
    document.getElementById('kpiRealizacaoMin').textContent = '0%';
    document.getElementById('kpiRealizacaoBar').style.width = '0%';
    const ctrTotalEl    = document.getElementById('fluxoContratosTotal');
    const ctrPagoEl     = document.getElementById('fluxoContratosPago');
    const ctrRestanteEl = document.getElementById('fluxoContratosRestante');
    if (ctrTotalEl)    ctrTotalEl.textContent    = 'R$ —';
    if (ctrPagoEl)     ctrPagoEl.textContent     = 'R$ —';
    if (ctrRestanteEl) ctrRestanteEl.textContent = 'R$ —';
    const kpiSaldo    = document.getElementById('kpiSaldoCaixa');
    const kpiSaldoSub = document.getElementById('kpiSaldoCaixaSub');
    if (kpiSaldo)    { kpiSaldo.textContent = 'R$ —'; kpiSaldo.style.color = ''; }
    if (kpiSaldoSub) { kpiSaldoSub.textContent = 'Total recebido nas obras'; kpiSaldoSub.style.color = ''; }
}

function setStatus(type, text) {
    const el = document.getElementById('connectionStatus');
    if (!el) return;
    el.textContent = text;
    el.className   = `status-dot ${type}`;
}

const formatCurrency = (value) =>
    new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);

// --- DOWNLOAD PDF ---
async function baixarPdf(url, nomeArquivo) {
    try {
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
            toast.error(`Erro ao gerar PDF: ${err.detail || res.statusText}`);
            return;
        }
        const blob = await res.blob();
        const link = document.createElement('a');
        link.href  = URL.createObjectURL(blob);
        link.download = nomeArquivo;
        link.click();
        URL.revokeObjectURL(link.href);
    } catch (e) {
        toast.error('Não foi possível conectar à API. Verifique se o servidor está rodando.');
    }
}

// --- MODAL RELATÓRIO PDF ---
function abrirModalRelatorio(obraNome) {
    // Remove modal anterior se existir
    const prev = document.getElementById('modalRelatorio');
    if (prev) prev.remove();

    const hoje  = new Date().toISOString().split('T')[0];
    const umMesAtras = new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString().split('T')[0];

    const modal = document.createElement('div');
    modal.id = 'modalRelatorio';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal" style="max-width:420px;">
            <div class="modal-header">
                <h3>Exportar Relatório PDF</h3>
                <button class="modal-close" id="modalRelatorioClose">&times;</button>
            </div>
            <div class="modal-body">
                <p style="font-size:0.875rem;color:var(--on-surface-muted);margin-bottom:var(--sp-5);">
                    Obra: <strong>${obraNome}</strong>
                </p>

                <div style="font-size:0.75rem;font-weight:600;color:var(--on-surface-variant);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:var(--sp-3);">Tipo de Relatório</div>
                <div style="display:flex;gap:var(--sp-3);margin-bottom:var(--sp-5);flex-wrap:wrap;">
                    <label class="radio-pill active">
                        <input type="radio" name="tipoRel" value="simples" checked style="display:none;">
                        Simples
                    </label>
                    <label class="radio-pill">
                        <input type="radio" name="tipoRel" value="detalhado" style="display:none;">
                        Detalhado
                    </label>
                    <label class="radio-pill">
                        <input type="radio" name="tipoRel" value="administrativo" style="display:none;">
                        Administrativo
                    </label>
                </div>

                <div id="porEtapaWrap" style="display:none;margin-bottom:var(--sp-5);">
                    <label style="display:flex;align-items:center;gap:var(--sp-3);cursor:pointer;font-size:0.875rem;color:var(--on-surface);">
                        <input type="checkbox" id="relPorEtapa" style="width:16px;height:16px;cursor:pointer;accent-color:var(--primary);">
                        Detalhar por etapa
                    </label>
                </div>

                <div id="admDateRange" style="display:none;">
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-4);margin-bottom:var(--sp-5);">
                        <div>
                            <div style="font-size:0.75rem;font-weight:600;color:var(--on-surface-variant);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:var(--sp-2);">Data Inicial</div>
                            <input type="date" id="relDataIni" style="width:100%;padding:8px 10px;border:none;border-bottom:2px solid var(--surface-container);border-radius:var(--r-md);background:var(--surface-low);font-family:var(--font-body);font-size:0.875rem;color:var(--on-surface);outline:none;" value="${umMesAtras}">
                        </div>
                        <div>
                            <div style="font-size:0.75rem;font-weight:600;color:var(--on-surface-variant);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:var(--sp-2);">Data Final</div>
                            <input type="date" id="relDataFim" style="width:100%;padding:8px 10px;border:none;border-bottom:2px solid var(--surface-container);border-radius:var(--r-md);background:var(--surface-low);font-family:var(--font-body);font-size:0.875rem;color:var(--on-surface);outline:none;" value="${hoje}">
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-outline" id="modalRelatorioCancelar">Cancelar</button>
                <button class="btn btn-primary" id="modalRelatorioGerar">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                    Gerar PDF
                </button>
            </div>
        </div>`;

    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.classList.add('active'));

    // Fechar modal
    const fechar = () => {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 200);
    };
    document.getElementById('modalRelatorioClose').addEventListener('click', fechar);
    document.getElementById('modalRelatorioCancelar').addEventListener('click', fechar);
    modal.addEventListener('click', (e) => { if (e.target === modal) fechar(); });

    // Toggle pills
    modal.querySelectorAll('input[name="tipoRel"]').forEach(radio => {
        radio.addEventListener('change', () => {
            modal.querySelectorAll('.radio-pill').forEach(p => p.classList.remove('active'));
            radio.parentElement.classList.add('active');
            const isAdm = radio.value === 'administrativo';
            const isDetalhado = radio.value === 'detalhado';
            document.getElementById('admDateRange').style.display = isAdm ? 'block' : 'none';
            document.getElementById('porEtapaWrap').style.display = (isAdm || isDetalhado) ? 'block' : 'none';
            // detalhado: por etapa marcado por padrão; administrativo: desmarcado
            document.getElementById('relPorEtapa').checked = isDetalhado;
        });
    });

    // Gerar
    document.getElementById('modalRelatorioGerar').addEventListener('click', () => {
        const tipo = modal.querySelector('input[name="tipoRel"]:checked').value;
        const porEtapa = document.getElementById('relPorEtapa').checked;
        let url = `http://${location.hostname}:8000/api/relatorio/pdf?obra=${encodeURIComponent(obraNome)}&tipo=${tipo}`;

        if (tipo === 'administrativo') {
            const ini = document.getElementById('relDataIni').value;
            const fim = document.getElementById('relDataFim').value;
            if (!ini || !fim) { toast.warning('Informe o período para o relatório administrativo.'); return; }
            url += `&data_ini=${ini}&data_fim=${fim}`;
        }

        if (tipo === 'detalhado' || tipo === 'administrativo') {
            url += `&por_etapa=${porEtapa}`;
        }

        fechar();
        toast.info('Gerando PDF…');
        baixarPdf(url, `relatorio_${obraNome.replace(/\s+/g,'_')}_${tipo}.pdf`);
    });
}

// --- TABELA ---
function renderizarTabelaVazia() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="5" style="text-align:center;padding:48px 20px;color:var(--on-surface-muted);font-size:0.875rem;">
                Selecione uma ou mais obras no filtro acima para visualizar os dados.
            </td>
        </tr>`;
}

function renderizarTabela() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    if (filteredData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align:center;padding:40px 20px;color:var(--on-surface-muted);font-size:0.875rem;">
                    Nenhum dado encontrado para a seleção atual.
                </td>
            </tr>`;
        return;
    }

    // Agrupar por obra → etapa → tipos
    const obrasAgrupadas = {};
    filteredData.forEach(item => {
        if (!obrasAgrupadas[item.OBRA]) {
            obrasAgrupadas[item.OBRA] = { previsto_total: 0, realizado_total: 0, etapas: {} };
        }
        const et = item.ETAPA || '—';
        if (!obrasAgrupadas[item.OBRA].etapas[et]) {
            obrasAgrupadas[item.OBRA].etapas[et] = { previsto: 0, realizado: 0, tipos: [] };
        }
        obrasAgrupadas[item.OBRA].etapas[et].previsto  += Number(item.ORÇAMENTO_ESTIMADO);
        obrasAgrupadas[item.OBRA].etapas[et].realizado += Number(item.GASTO_REALIZADO);
        obrasAgrupadas[item.OBRA].etapas[et].tipos.push(item);
        obrasAgrupadas[item.OBRA].previsto_total  += Number(item.ORÇAMENTO_ESTIMADO);
        obrasAgrupadas[item.OBRA].realizado_total += Number(item.GASTO_REALIZADO);
    });

    Object.keys(obrasAgrupadas).forEach((obraName, obraIdx) => {
        const obra    = obrasAgrupadas[obraName];
        const saldo   = obra.previsto_total - obra.realizado_total;
        const pct     = obra.previsto_total > 0 ? (obra.realizado_total / obra.previsto_total) * 100 : 0;

        const statusClass = saldo >= 0 ? 'status-ok' : 'status-over';
        const saldoClass  = saldo  < 0 ? 'text-error' : 'text-success';
        const pctClass    = pct   > 100 ? 'text-error' : '';

        const totalEtapasDaObra = [...new Set(rawData.filter(i => i.OBRA === obraName).map(i => i.ETAPA))].filter(Boolean).length;
        const autoExpand = currentEtapaFilters.length < totalEtapasDaObra || currentObraFilters.length === 1;

        const trObra = document.createElement('tr');
        trObra.className = `row-obra ${statusClass} ${autoExpand ? 'expanded' : ''}`;
        trObra.dataset.obraId = obraIdx;
        trObra.innerHTML = `
            <td><span class="expand-icon">▶</span>${obraName}</td>
            <td class="text-right fin-num"><strong>${formatCurrency(obra.previsto_total)}</strong></td>
            <td class="text-right fin-num"><strong>${formatCurrency(obra.realizado_total)}</strong></td>
            <td class="text-right fin-num ${saldoClass}"><strong>${formatCurrency(saldo)}</strong></td>
            <td class="text-center">
                <div class="mini-bar-wrap">
                    <span class="${pctClass} fin-num">${pct.toFixed(1)}%</span>
                    <div class="mini-bar">
                        <div class="mini-bar-fill ${pct > 100 ? 'over' : ''}" style="width:${Math.min(pct, 100)}%"></div>
                    </div>
                </div>
            </td>`;

        trObra.addEventListener('click', function () {
            this.classList.toggle('expanded');
            const isExp = this.classList.contains('expanded');
            document.querySelectorAll(`.etapa-of-${obraIdx}`).forEach(el => {
                el.style.display = isExp ? 'table-row' : 'none';
            });
            // Colapsar tipos ao fechar obra
            if (!isExp) {
                document.querySelectorAll(`[class*="tipo-of-${obraIdx}-"]`).forEach(el => {
                    el.style.display = 'none';
                });
                document.querySelectorAll(`.etapa-of-${obraIdx}`).forEach(el => {
                    el.classList.remove('expanded');
                    const icon = el.querySelector('.expand-icon-etapa');
                    if (icon) icon.style.transform = '';
                });
            }
        });

        tbody.appendChild(trObra);

        // Etapas da obra
        Object.entries(obra.etapas).forEach(([etapaNome, etapaData], etapaIdx) => {
            // Apenas etapas com orçamento ou gasto
            if (etapaData.previsto === 0 && etapaData.realizado === 0) return;

            const etId       = `${obraIdx}-${etapaIdx}`;
            const saldoEt    = etapaData.previsto - etapaData.realizado;
            const pctEt      = etapaData.previsto > 0 ? (etapaData.realizado / etapaData.previsto) * 100 : 0;
            const saldoEtCls = saldoEt < 0 ? 'text-error' : 'text-success';
            const pctEtCls   = pctEt  > 100 ? 'text-error' : '';

            // Tipos com orçamento ou gasto
            const tiposFiltrados = etapaData.tipos.filter(t =>
                Number(t.ORÇAMENTO_ESTIMADO) > 0 || Number(t.GASTO_REALIZADO) > 0
            );

            const trEtapa = document.createElement('tr');
            trEtapa.className = `row-etapa etapa-of-${obraIdx}`;
            if (autoExpand) trEtapa.style.display = 'table-row';
            if (tiposFiltrados.length > 0) trEtapa.style.cursor = 'pointer';

            trEtapa.innerHTML = `
                <td style="padding-left:1.5rem;">
                    ${tiposFiltrados.length > 0
                        ? `<span class="expand-icon-etapa" style="margin-right:6px;display:inline-block;transition:transform .18s;font-size:0.7em;opacity:0.55;">▶</span>`
                        : `<span style="display:inline-block;width:18px;"></span>`}
                    ${etapaNome}
                </td>
                <td class="text-right fin-num">${formatCurrency(etapaData.previsto)}</td>
                <td class="text-right fin-num">${formatCurrency(etapaData.realizado)}</td>
                <td class="text-right fin-num ${saldoEtCls}">${formatCurrency(saldoEt)}</td>
                <td class="text-center fin-num ${pctEtCls}">${pctEt.toFixed(1)}%</td>`;

            if (tiposFiltrados.length > 0) {
                trEtapa.addEventListener('click', function () {
                    this.classList.toggle('expanded');
                    const isExp = this.classList.contains('expanded');
                    document.querySelectorAll(`.tipo-of-${etId}`).forEach(el => {
                        el.style.display = isExp ? 'table-row' : 'none';
                    });
                    const icon = this.querySelector('.expand-icon-etapa');
                    if (icon) icon.style.transform = isExp ? 'rotate(90deg)' : '';
                });
            }

            tbody.appendChild(trEtapa);

            // Sub-linhas de tipo (ocultas por padrão)
            tiposFiltrados.forEach(t => {
                const saldoT    = Number(t.SALDO_ETAPA);
                const pctT      = Number(t.ORÇAMENTO_ESTIMADO) > 0
                    ? (Number(t.GASTO_REALIZADO) / Number(t.ORÇAMENTO_ESTIMADO)) * 100 : 0;
                const saldoTCls = saldoT < 0 ? 'text-error' : 'text-success';
                const pctTCls   = pctT  > 100 ? 'text-error' : '';

                const trTipo = document.createElement('tr');
                trTipo.className = `row-tipo tipo-of-${etId}`;
                trTipo.style.display = 'none';
                trTipo.innerHTML = `
                    <td style="padding-left:3rem;color:var(--on-surface-muted);font-size:0.8125rem;">↳ ${t.TIPO_CUSTO || 'Geral'}</td>
                    <td class="text-right fin-num" style="font-size:0.8125rem;opacity:0.85;">${formatCurrency(t.ORÇAMENTO_ESTIMADO)}</td>
                    <td class="text-right fin-num" style="font-size:0.8125rem;opacity:0.85;">${formatCurrency(t.GASTO_REALIZADO)}</td>
                    <td class="text-right fin-num ${saldoTCls}" style="font-size:0.8125rem;opacity:0.85;">${formatCurrency(saldoT)}</td>
                    <td class="text-center fin-num ${pctTCls}" style="font-size:0.8125rem;opacity:0.85;">${pctT.toFixed(1)}%</td>`;
                tbody.appendChild(trTipo);
            });
        });
    });
}
