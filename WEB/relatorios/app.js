/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Relatório Inteligente (app.js)
 */

const API_BASE = window.API_BASE || `http://${location.hostname}:8000`;

// --- SUPABASE (via nav.js → window.db) ---
let db;

// --- ESTADO ---
let obrasDisponiveis = [];   // [{nome, empresa_id, empresas: {nome, logo_url}}]
let etapasOrdem      = {};   // { nomeDaEtapa: numero_de_ordem }
let bancosFilhosRel  = [];   // [{id, nome}]

// helpers: esc, setStatus, formatarData, formatarValor — via lib/helpers.js
function fmtValor(v) {
    return 'R$ ' + Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtPct(v) {
    return Number(v || 0).toFixed(1) + '%';
}
function mostrarLoading(msg = 'Carregando dados…') {
    document.getElementById('loadingArea').style.display = 'block';
    document.getElementById('relatorioArea').style.display = 'none';
    document.getElementById('loadingMsg').textContent = msg;
    document.getElementById('btnExportar').style.display = 'none';
}
function esconderLoading() {
    document.getElementById('loadingArea').style.display = 'none';
}
// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    db = window.db;
    if (!db) { setStatus('offline', 'Erro de conexão'); return; }

    // Toggle modo
    document.querySelectorAll('input[name="modo"]').forEach(radio => {
        radio.addEventListener('change', () => {
            const v = radio.value;
            document.getElementById('grupoObraUnica').style.display      = v === 'unico'      ? '' : 'none';
            document.getElementById('grupoObraComparativo').style.display = v === 'comparativo'? '' : 'none';
            document.getElementById('grupoBanco').style.display           = v === 'unico'      ? '' : 'none';
            document.getElementById('grupoBancoRel').style.display        = v === 'banco'      ? '' : 'none';
        });
    });

    document.getElementById('selectObra').addEventListener('change', async () => {
        await carregarBancos(document.getElementById('selectObra').value);
    });

    document.getElementById('btnGerarRelatorio').addEventListener('click', gerarRelatorio);

    await Promise.all([carregarObras(), carregarOrdemEtapas(), carregarBancosFilhos()]);
    setStatus('online', 'Sistema Sincronizado');
});

// --- CARREGAR BANCOS ---
async function carregarBancos(obra) {
    const sel = document.getElementById('selectBancos');
    sel.innerHTML = '<option value="" selected>Todos</option>';
    if (!obra) return;
    const { data } = await db
        .from('c_despesas')
        .select('banco')
        .eq('obra', obra)
        .not('banco', 'is', null);
    if (!data) return;
    const bancos = [...new Set(data.map(d => d.banco).filter(Boolean))].sort();
    bancos.forEach(b => {
        const opt = document.createElement('option');
        opt.value = b;
        opt.textContent = b;
        sel.appendChild(opt);
    });
}

// --- CARREGAR BANCOS FILHOS (para modo por banco) ---
async function carregarBancosFilhos() {
    try {
        const { data } = await db.from('bancos').select('id, nome').eq('tipo', 'filho').order('nome');
        bancosFilhosRel = data || [];
        const sel = document.getElementById('selectBancosRel');
        sel.innerHTML = bancosFilhosRel.map(b =>
            `<option value="${esc(b.id)}">${esc(b.nome)}</option>`
        ).join('');
    } catch (_) {}
}

// --- CARREGAR ORDEM DE ETAPAS ---
async function carregarOrdemEtapas() {
    try {
        const { data } = await db.from('etapas').select('nome, ordem').order('ordem');
        if (data) {
            etapasOrdem = Object.fromEntries(data.map(e => [e.nome, e.ordem ?? 9999]));
        }
    } catch (_) {}
}

// --- CARREGAR OBRAS ---
async function carregarObras() {
    try {
        const { data, error } = await db
            .from('obras')
            .select('nome, empresa_id, empresas(nome, logo_url)')
            .order('nome');
        if (error) throw error;

        obrasDisponiveis = data || [];

        const selUnico = document.getElementById('selectObra');
        const selMulti = document.getElementById('selectObrasMulti');

        selUnico.innerHTML = `<option value="">— Selecione —</option>` +
            obrasDisponiveis.map(o => `<option value="${esc(o.nome)}">${esc(o.nome)}</option>`).join('');

        selMulti.innerHTML = obrasDisponiveis.map(o =>
            `<option value="${esc(o.nome)}">${esc(o.nome)}</option>`
        ).join('');
    } catch (e) {
        setStatus('offline', 'Erro ao carregar obras');
        console.error(e);
    }
}

// --- GERAR RELATÓRIO ---
async function gerarRelatorio() {
    const modo = document.querySelector('input[name="modo"]:checked').value;
    const dataIni = document.getElementById('filtroDataIni').value || null;
    const dataFim = document.getElementById('filtroDataFim').value || null;

    if (modo === 'banco') {
        const bancosSelIds = Array.from(document.getElementById('selectBancosRel').selectedOptions)
            .map(o => o.value).filter(Boolean);
        mostrarLoading('Buscando dados por banco…');
        try {
            const dados = await buscarDadosBancos(bancosSelIds, dataIni, dataFim);
            document.getElementById('loadingMsg').textContent = 'Renderizando…';
            renderizarRelatorioBancos(dados);
            esconderLoading();
            document.getElementById('relatorioArea').style.display = 'block';
            document.getElementById('btnExportar').style.display   = '';
        } catch (e) {
            esconderLoading();
            toast.error('Erro ao gerar relatório: ' + e.message);
            console.error(e);
        }
        return;
    }

    let obrasSelecionadas = [];
    let bancosSel = [];
    if (modo === 'unico') {
        const val = document.getElementById('selectObra').value;
        if (!val) { toast.warning('Selecione uma obra.'); return; }
        obrasSelecionadas = [val];
        bancosSel = Array.from(document.getElementById('selectBancos').selectedOptions)
            .map(o => o.value).filter(Boolean);
    } else {
        const opts = document.getElementById('selectObrasMulti').selectedOptions;
        obrasSelecionadas = Array.from(opts).map(o => o.value);
        if (obrasSelecionadas.length < 2) { toast.warning('Selecione pelo menos 2 obras para comparar.'); return; }
    }

    mostrarLoading('Buscando dados financeiros…');

    try {
        // 1. Buscar dados do Supabase (frontend direto)
        const dadosObras = await buscarDadosObras(obrasSelecionadas, dataIni, dataFim, bancosSel);

        document.getElementById('loadingMsg').textContent = 'Renderizando relatório…';

        // 2. Renderizar cabeçalhos de empresa
        renderizarEmpresaHeaders(obrasSelecionadas);

        // 3. KPIs
        renderizarKPIs(dadosObras);

        // 4. Fluxo de caixa
        renderizarFluxoCaixa(dadosObras);

        // 5. Tabela de etapas
        renderizarTabelaEtapas(dadosObras);

        // Mostrar área
        esconderLoading();
        document.getElementById('relatorioArea').style.display = 'block';
        document.getElementById('btnExportar').style.display   = '';

    } catch (e) {
        esconderLoading();
        toast.error('Erro ao gerar relatório: ' + e.message);
        console.error(e);
    }
}

// --- BUSCAR DADOS DO SUPABASE ---
async function buscarDadosObras(obrasList, dataIni, dataFim, bancosFilter = []) {
    const resultado = [];

    for (const obraNome of obrasList) {
        const obraInfo = obrasDisponiveis.find(o => o.nome === obraNome) || { nome: obraNome };

        // Orçamentos
        const { data: orcData } = await db.from('orcamentos')
            .select('etapa, tipo_custo, valor_estimado')
            .eq('obra', obraNome);

        // Despesas
        let qDesp = db.from('c_despesas')
            .select('etapa, tipo, fornecedor, valor_total, data')
            .eq('obra', obraNome);
        if (dataIni) qDesp = qDesp.gte('data', dataIni);
        if (dataFim) qDesp = qDesp.lte('data', dataFim);
        if (bancosFilter.length > 0) qDesp = qDesp.in('banco', bancosFilter);
        const { data: despData } = await qDesp;

        // Recebimentos
        const { data: recData } = await db.from('recebimentos')
            .select('valor').eq('obra', obraNome);

        // Contas a pagar
        const { data: capData } = await db.from('contas_a_pagar')
            .select('valor').eq('obra', obraNome);

        // Taxa de conclusão
        const { data: taxaData } = await db.from('taxa_conclusao')
            .select('etapa, taxa').eq('obra', obraNome);

        // Agregações client-side
        const despesas = despData || [];
        const orcamentos = orcData || [];

        const totalOrcado    = orcamentos.reduce((s, r) => s + parseFloat(r.valor_estimado || 0), 0);
        const totalRealizado = despesas.reduce((s, r) => s + parseFloat(r.valor_total || 0), 0);
        const totalRecebido  = (recData || []).reduce((s, r) => s + parseFloat(r.valor || 0), 0);
        const totalAPagar    = (capData || []).reduce((s, r) => s + parseFloat(r.valor || 0), 0);
        const taxaMap        = Object.fromEntries((taxaData || []).map(r => [r.etapa, parseFloat(r.taxa || 0)]));

        // Por etapa
        const etapasSet = new Set([
            ...orcamentos.map(r => r.etapa),
            ...despesas.map(r => r.etapa).filter(Boolean),
        ]);
        const porEtapa = [];
        const etapasOrdenadas = [...etapasSet].sort((a, b) => {
            const oa = etapasOrdem[a] ?? 9999;
            const ob = etapasOrdem[b] ?? 9999;
            return oa !== ob ? oa - ob : a.localeCompare(b);
        });
        for (const et of etapasOrdenadas) {
            const orcEt  = orcamentos.filter(r => r.etapa === et).reduce((s, r) => s + parseFloat(r.valor_estimado || 0), 0);
            const realEt = despesas.filter(r => r.etapa === et).reduce((s, r) => s + parseFloat(r.valor_total || 0), 0);

            const tiposSet = new Set([
                ...orcamentos.filter(r => r.etapa === et).map(r => r.tipo_custo).filter(Boolean),
                ...despesas.filter(r => r.etapa === et).map(r => r.tipo).filter(Boolean),
            ]);
            const porTipoEtapa = [...tiposSet].map(tipo => {
                const orcTipo  = orcamentos.filter(r => r.etapa === et && r.tipo_custo === tipo).reduce((s, r) => s + parseFloat(r.valor_estimado || 0), 0);
                const realTipo = despesas.filter(r => r.etapa === et && r.tipo === tipo).reduce((s, r) => s + parseFloat(r.valor_total || 0), 0);
                return { tipo, orcado: orcTipo, realizado: realTipo };
            }).filter(t => t.orcado > 0 || t.realizado > 0);

            porEtapa.push({
                etapa:    et,
                orcado:   orcEt,
                realizado: realEt,
                pct:      orcEt > 0 ? (realEt / orcEt * 100) : 0,
                conclusao: taxaMap[et] || 0,
                porTipo:  porTipoEtapa,
            });
        }

        // Por tipo
        const porTipo = {};
        for (const d of despesas) {
            porTipo[d.tipo] = (porTipo[d.tipo] || 0) + parseFloat(d.valor_total || 0);
        }

        // Top 5 fornecedores
        const fornMap = {};
        for (const d of despesas) {
            if (d.fornecedor) fornMap[d.fornecedor] = (fornMap[d.fornecedor] || 0) + parseFloat(d.valor_total || 0);
        }
        const topFornecedores = Object.entries(fornMap)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([nome, total]) => ({ nome, total }));

        // Evolução mensal (últimos 6 meses)
        const mensalMap = {};
        for (const d of despesas) {
            if (!d.data) continue;
            const mes = d.data.slice(0, 7); // YYYY-MM
            mensalMap[mes] = (mensalMap[mes] || 0) + parseFloat(d.valor_total || 0);
        }
        const evolucaoMensal = Object.entries(mensalMap)
            .sort(([a], [b]) => a.localeCompare(b))
            .slice(-6)
            .map(([mes, total]) => ({ mes, total }));

        resultado.push({
            nome:              obraNome,
            empresa:           obraInfo.empresas,
            totalOrcado,
            totalRealizado,
            totalRecebido,
            totalAPagar,
            saldoCaixa:        totalRecebido - totalRealizado - totalAPagar,
            pctConsumo:        totalOrcado > 0 ? (totalRealizado / totalOrcado * 100) : 0,
            pctConclusao:      taxaMap && Object.keys(taxaMap).length > 0
                                   ? Object.values(taxaMap).reduce((s, v) => s + v, 0) / Object.keys(taxaMap).length
                                   : 0,
            porEtapa: porEtapa.filter(e => e.orcado > 0 || e.realizado > 0),
            porTipo,
            topFornecedores,
            evolucaoMensal,
        });
    }

    return resultado;
}

// --- EMPRESA HEADERS ---
function renderizarEmpresaHeaders(obrasList) {
    _garantirSecaoObras();
    const container = document.getElementById('empresaHeaders');
    const headers = obrasList.map(nome => {
        const info = obrasDisponiveis.find(o => o.nome === nome);
        const empresa = info?.empresas;
        if (!empresa) return '';
        return `
            <div class="rel-empresa-header">
                ${empresa.logo_url ? `<img src="${esc(empresa.logo_url)}" alt="${esc(empresa.nome)}">` : ''}
                <div>
                    <div class="rel-empresa-nome">${esc(empresa.nome)}</div>
                    <div class="rel-obra-nome">${esc(nome)}</div>
                </div>
            </div>`;
    }).join('');
    container.innerHTML = headers;
}

// --- KPIs ---
function renderizarKPIs(dadosObras) {
    const grid = document.getElementById('kpisGrid');

    // Agregar totais (soma de todas as obras selecionadas)
    const totalOrcado    = dadosObras.reduce((s, o) => s + o.totalOrcado, 0);
    const totalRealizado = dadosObras.reduce((s, o) => s + o.totalRealizado, 0);
    const saldoOrc       = totalOrcado - totalRealizado;
    const pctConclusao   = dadosObras.reduce((s, o) => s + o.pctConclusao, 0) / dadosObras.length;

    const kpis = [
        { label: 'Orçamento Total',   value: fmtValor(totalOrcado),    sub: null },
        { label: 'Realizado',         value: fmtValor(totalRealizado), sub: fmtPct(totalOrcado > 0 ? totalRealizado / totalOrcado * 100 : 0) + ' do orçamento' },
        { label: 'Saldo Orçamentário',value: fmtValor(saldoOrc),       sub: saldoOrc < 0 ? 'Acima do orçamento' : 'Disponível', color: saldoOrc < 0 ? 'var(--error)' : 'inherit' },
        { label: 'Conclusão Média',   value: fmtPct(pctConclusao),     sub: null },
    ];

    grid.innerHTML = kpis.map(k => `
        <div class="kpi-card">
            <div class="kpi-label">${esc(k.label)}</div>
            <div class="kpi-value fin-num" style="${k.color ? `color:${k.color}` : ''}">${esc(k.value)}</div>
            ${k.sub ? `<div style="font-size:0.75rem;color:var(--on-surface-muted);margin-top:2px;">${esc(k.sub)}</div>` : ''}
        </div>`).join('');
}

// --- FLUXO DE CAIXA ---
function renderizarFluxoCaixa(dadosObras) {
    const recebido   = dadosObras.reduce((s, o) => s + o.totalRecebido,  0);
    const gasto      = dadosObras.reduce((s, o) => s + o.totalRealizado, 0);
    const saldoAtual = recebido - gasto;
    const corSaldo   = saldoAtual >= 0 ? 'var(--success)' : 'var(--error)';

    const item = (label, valor, cor) => `
        <div>
            <div style="font-size:0.75rem;font-weight:600;color:var(--on-surface-muted);margin-bottom:6px;">${label}</div>
            <div class="fin-num" style="font-family:var(--font-display);font-size:1.25rem;font-weight:800;color:${cor};">${fmtValor(valor)}</div>
        </div>`;

    document.getElementById('fluxoGrid').innerHTML =
        item('Recebido',    recebido,   'var(--success)') +
        item('Gasto',       gasto,      'var(--error)')   +
        item('Saldo Atual', saldoAtual, corSaldo);
}

// --- TABELA DE ETAPAS ---
function renderizarTabelaEtapas(dadosObras) {
    const tbody = document.getElementById('tabelaEtapas');
    const linhas = [];
    let uid = 0;

    for (const obra of dadosObras) {
        for (const et of obra.porEtapa) {
            const id        = `et-${uid++}`;
            const saldo     = et.orcado - et.realizado;
            const isAcima   = et.pct > 100;
            const isCritico = et.pct > 90 && et.pct <= 100;
            const cor       = isAcima ? 'var(--error)' : isCritico ? 'var(--warning)' : 'var(--success)';
            const temTipos  = et.porTipo && et.porTipo.length > 0;

            linhas.push(`
                <tr class="etapa-row${temTipos ? ' etapa-expandivel' : ''}" ${temTipos ? `onclick="toggleEtapa('${id}')" id="row-${id}"` : ''}>
                    <td>
                        ${temTipos
                            ? `<span class="etapa-chevron" id="chev-${id}">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
                               </span>`
                            : `<span class="status-bar" style="background:${cor};"></span>`}
                    </td>
                    <td style="font-weight:500;">${esc(obra.nome)}</td>
                    <td style="font-weight:600;">${esc(et.etapa)}</td>
                    <td class="text-right fin-num">${fmtValor(et.orcado)}</td>
                    <td class="text-right fin-num">${fmtValor(et.realizado)}</td>
                    <td class="text-right fin-num" style="color:${saldo < 0 ? 'var(--error)' : 'inherit'}">${fmtValor(saldo)}</td>
                    <td class="text-right fin-num" style="color:${cor}">${fmtPct(et.pct)}</td>
                    <td class="text-right fin-num">${fmtPct(et.conclusao)}</td>
                </tr>`);

            if (temTipos) {
                for (const t of et.porTipo) {
                    const saldoT = t.orcado - t.realizado;
                    const pctT   = t.orcado > 0 ? (t.realizado / t.orcado * 100) : 0;
                    const corT   = pctT > 100 ? 'var(--error)' : pctT > 90 ? 'var(--warning)' : 'var(--success)';
                    linhas.push(`
                        <tr class="tipo-row tipo-${id}" style="display:none;">
                            <td></td>
                            <td></td>
                            <td class="tipo-nome">↳ ${esc(t.tipo)}</td>
                            <td class="text-right fin-num tipo-num">${fmtValor(t.orcado)}</td>
                            <td class="text-right fin-num tipo-num">${fmtValor(t.realizado)}</td>
                            <td class="text-right fin-num tipo-num" style="color:${saldoT < 0 ? 'var(--error)' : 'inherit'}">${fmtValor(saldoT)}</td>
                            <td class="text-right fin-num tipo-num" style="color:${corT}">${fmtPct(pctT)}</td>
                            <td></td>
                        </tr>`);
                }
            }
        }
    }

    tbody.innerHTML = linhas.join('') || `<tr><td colspan="8" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-6);">Sem dados de etapas.</td></tr>`;
}

function toggleEtapa(id) {
    const rows   = document.querySelectorAll(`.tipo-${id}`);
    const chev   = document.getElementById(`chev-${id}`);
    const isOpen = rows.length > 0 && rows[0].style.display !== 'none';
    rows.forEach(r => r.style.display = isOpen ? 'none' : '');
    if (chev) chev.style.transform = isOpen ? '' : 'rotate(90deg)';
}

// --- RELATÓRIO POR BANCO ---

async function buscarDadosBancos(bancosSelIds, dataIni, dataFim) {
    // Determina quais bancos mostrar
    const bancos = bancosSelIds.length > 0
        ? bancosFilhosRel.filter(b => bancosSelIds.includes(b.id))
        : bancosFilhosRel;

    const resultado = [];

    for (const banco of bancos) {
        // Remessas recebidas por este banco
        let qRem = db.from('remessas_caixa')
            .select('valor, data, obra')
            .eq('banco_destino_id', banco.id);
        if (dataIni) qRem = qRem.gte('data', dataIni);
        if (dataFim) qRem = qRem.lte('data', dataFim);
        const { data: remData } = await qRem;

        // Despesas pagas por este banco (campo texto "banco" = nome do banco)
        let qDesp = db.from('c_despesas')
            .select('valor_total, data, obra, etapa, fornecedor')
            .eq('banco', banco.nome);
        if (dataIni) qDesp = qDesp.gte('data', dataIni);
        if (dataFim) qDesp = qDesp.lte('data', dataFim);
        const { data: despData } = await qDesp;

        const remessas  = remData  || [];
        const despesas  = despData || [];

        const totalRemessas  = remessas.reduce((s, r) => s + parseFloat(r.valor || 0), 0);
        const totalDespesas  = despesas.reduce((s, r) => s + parseFloat(r.valor_total || 0), 0);
        const saldo          = totalRemessas - totalDespesas;

        // Agrupamento por obra
        const obraSet = new Set([
            ...remessas.map(r => r.obra).filter(Boolean),
            ...despesas.map(d => d.obra).filter(Boolean),
        ]);
        const porObra = [...obraSet].sort().map(obraNome => {
            const remObra  = remessas.filter(r => r.obra === obraNome).reduce((s, r) => s + parseFloat(r.valor || 0), 0);
            const despObra = despesas.filter(d => d.obra === obraNome).reduce((s, d) => s + parseFloat(d.valor_total || 0), 0);
            return { obra: obraNome, remessas: remObra, despesas: despObra, saldo: remObra - despObra };
        }).filter(o => o.remessas > 0 || o.despesas > 0);

        // Top 5 fornecedores
        const fornMap = {};
        for (const d of despesas) {
            if (d.fornecedor) fornMap[d.fornecedor] = (fornMap[d.fornecedor] || 0) + parseFloat(d.valor_total || 0);
        }
        const topFornecedores = Object.entries(fornMap)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([nome, total]) => ({ nome, total }));

        resultado.push({ banco, totalRemessas, totalDespesas, saldo, porObra, topFornecedores });
    }

    return resultado;
}

function renderizarRelatorioBancos(dados) {
    // Esconder seções de obra, mostrar seção de bancos
    document.getElementById('empresaHeaders').innerHTML = '';
    document.getElementById('secaoEtapas').style.display  = 'none';
    document.getElementById('secaoBancos').style.display  = '';

    // KPIs globais
    const totalRem  = dados.reduce((s, b) => s + b.totalRemessas, 0);
    const totalDesp = dados.reduce((s, b) => s + b.totalDespesas, 0);
    const saldoGlob = totalRem - totalDesp;

    const grid = document.getElementById('kpisGrid');
    const kpis = [
        { label: 'Total Remessas',  value: fmtValor(totalRem),  sub: null },
        { label: 'Total Despesas',  value: fmtValor(totalDesp), sub: null },
        { label: 'Saldo Líquido',   value: fmtValor(saldoGlob), sub: saldoGlob < 0 ? 'Déficit' : 'Disponível', color: saldoGlob < 0 ? 'var(--error)' : 'inherit' },
        { label: 'Contas analisadas', value: String(dados.length), sub: null },
    ];
    grid.innerHTML = kpis.map(k => `
        <div class="kpi-card">
            <div class="kpi-label">${esc(k.label)}</div>
            <div class="kpi-value fin-num" style="${k.color ? `color:${k.color}` : ''}">${esc(k.value)}</div>
            ${k.sub ? `<div style="font-size:0.75rem;color:var(--on-surface-muted);margin-top:2px;">${esc(k.sub)}</div>` : ''}
        </div>`).join('');

    // Fluxo de caixa
    const corSaldo = saldoGlob >= 0 ? 'var(--success)' : 'var(--error)';
    const item = (label, valor, cor) => `
        <div>
            <div style="font-size:0.75rem;font-weight:600;color:var(--on-surface-muted);margin-bottom:6px;">${label}</div>
            <div class="fin-num" style="font-family:var(--font-display);font-size:1.25rem;font-weight:800;color:${cor};">${fmtValor(valor)}</div>
        </div>`;
    document.getElementById('fluxoGrid').innerHTML =
        item('Remessas Recebidas', totalRem,  'var(--success)') +
        item('Despesas Pagas',     totalDesp, 'var(--error)')   +
        item('Saldo Líquido',      saldoGlob, corSaldo);

    // Tabela de bancos com detalhamento por obra
    const tbody = document.getElementById('tabelaBancos');
    let uid = 0;
    const linhas = [];

    for (const b of dados) {
        const id     = `banco-${uid++}`;
        const temObras = b.porObra.length > 0;
        const cor    = b.saldo < 0 ? 'var(--error)' : b.saldo === 0 ? 'var(--on-surface-muted)' : 'inherit';

        linhas.push(`
            <tr class="${temObras ? 'etapa-expandivel' : ''}" ${temObras ? `onclick="toggleEtapa('${id}')" id="row-${id}"` : ''}>
                <td>
                    ${temObras
                        ? `<span class="etapa-chevron" id="chev-${id}">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
                           </span>`
                        : `<span class="status-bar" style="background:${cor};"></span>`}
                </td>
                <td style="font-weight:600;">${esc(b.banco.nome)}</td>
                <td class="text-right fin-num" style="color:var(--success);">${fmtValor(b.totalRemessas)}</td>
                <td class="text-right fin-num" style="color:var(--error);">${fmtValor(b.totalDespesas)}</td>
                <td class="text-right fin-num" style="color:${cor};font-weight:700;">${fmtValor(b.saldo)}</td>
            </tr>`);

        for (const o of b.porObra) {
            const corO = o.saldo < 0 ? 'var(--error)' : 'inherit';
            linhas.push(`
                <tr class="tipo-row tipo-${id}" style="display:none;">
                    <td></td>
                    <td class="tipo-nome" style="padding-left:2rem;">↳ ${esc(o.obra)}</td>
                    <td class="text-right fin-num tipo-num" style="color:var(--success);">${fmtValor(o.remessas)}</td>
                    <td class="text-right fin-num tipo-num" style="color:var(--error);">${fmtValor(o.despesas)}</td>
                    <td class="text-right fin-num tipo-num" style="color:${corO};">${fmtValor(o.saldo)}</td>
                </tr>`);
        }

        if (b.topFornecedores.length > 0) {
            linhas.push(`
                <tr class="tipo-row tipo-${id}" style="display:none;">
                    <td></td>
                    <td colspan="4" style="padding-left:2rem;padding-top:6px;padding-bottom:2px;">
                        <span style="font-size:0.75rem;font-weight:600;color:var(--on-surface-muted);">Top fornecedores: </span>
                        ${b.topFornecedores.map(f => `<span style="font-size:0.75rem;margin-right:12px;">${esc(f.nome)} <strong>${fmtValor(f.total)}</strong></span>`).join('')}
                    </td>
                </tr>`);
        }
    }

    tbody.innerHTML = linhas.join('') || `<tr><td colspan="5" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-6);">Nenhum banco encontrado.</td></tr>`;
}

function _garantirSecaoObras() {
    document.getElementById('secaoEtapas').style.display = '';
    document.getElementById('secaoBancos').style.display = 'none';
}

