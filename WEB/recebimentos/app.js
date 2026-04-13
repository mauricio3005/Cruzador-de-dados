/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Recebimentos (app.js)
 * Lógica: entrada direta vinculada à obra. Sem controle de vencimento.
 */

// --- SUPABASE (via nav.js → window.db) ---
let dbClient;

// --- ESTADO ---
let obras  = [];
let formas = [];

let todosRegistros = [];
let paginaAtual    = 1;
const PAGE_SIZE    = 50;

let editandoId   = null;
let confirmarId  = null;

function statusBadge(r) {
    if (r.recebido) {
        return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:0.7rem;font-weight:700;color:var(--success);background:rgba(46,125,50,0.1);">Confirmado</span>`;
    }
    return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:0.7rem;font-weight:700;color:var(--warning);background:rgba(180,83,9,0.1);">Pendente</span>`;
}

// helpers: esc, setStatus, formatarData, formatarValor, hoje — via lib/helpers.js
function addMeses(d, n) {
    const dt = new Date(d + 'T00:00:00');
    dt.setMonth(dt.getMonth() + n);
    return dt.toISOString().split('T')[0];
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    dbClient = window.db;
    await carregarReferencias();

    document.getElementById('btnFiltrar').addEventListener('click', () => { paginaAtual = 1; carregarRecebimentos(); });
    document.getElementById('btnLimparFiltro').addEventListener('click', limparFiltros);
    document.getElementById('buscaTexto').addEventListener('input', renderizarTabela);

    document.getElementById('btnPagAnterior').addEventListener('click', () => { if (paginaAtual > 1) { paginaAtual--; renderizarTabela(); } });
    document.getElementById('btnPagProxima').addEventListener('click', () => {
        if (paginaAtual * PAGE_SIZE < filtrarRegistros().length) { paginaAtual++; renderizarTabela(); }
    });

    document.getElementById('btnNovoRecebimento').addEventListener('click', () => abrirModal(null));
    document.getElementById('btnSalvarRec').addEventListener('click', salvarRecebimento);
    document.getElementById('btnExportarCSV').addEventListener('click', exportarCSV);

    document.getElementById('modalRecebimento').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModal();
    });
    document.getElementById('modalConfirmar').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModalConfirmar();
    });
    document.getElementById('btnConfirmarRecebimento').addEventListener('click', confirmarRecebimento);

    document.getElementById('rUsarParcelas').addEventListener('change', e => {
        document.getElementById('parcelasConfig').style.display = e.target.checked ? 'grid' : 'none';
    });

    // Upload comprovante
    const zone  = document.getElementById('uploadZoneRec');
    const input = document.getElementById('inputComprovanteRec');
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--accent)'; });
    zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
    zone.addEventListener('drop', e => {
        e.preventDefault(); zone.style.borderColor = '';
        if (e.dataTransfer.files[0]) definirComprovante(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', () => { if (input.files[0]) definirComprovante(input.files[0]); });

    await carregarRecebimentos();
});

window.addEventListener('jarvis:data-changed', (e) => {
    if (e.detail?.tabela === 'recebimentos') {
        paginaAtual = 1;
        carregarRecebimentos();
    }
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    if (!dbClient) { setStatus('offline', 'Erro de conexão'); return; }

    const safe = async (query, campo = 'nome') => {
        try {
            const { data, error } = await query;
            if (error) { console.warn('[recebimentos]', error.message); return []; }
            return (data || []).map(r => r[campo]);
        } catch (e) { return []; }
    };

    let bancos;
    [obras, formas, bancos] = await Promise.all([
        safe(dbClient.from('obras').select('nome').order('nome')),
        safe(dbClient.from('formas_pagamento').select('nome').order('nome')),
        safe(dbClient.from('bancos').select('nome').order('nome')),
    ]);

    popularSelect('filtroObra',  obras,  'Todas as obras');
    popularSelect('filtroBanco', bancos, 'Todos');
    popularSelect('rObra',  obras,  '—');
    popularSelect('rForma', formas, '—');
    popularSelect('rBanco', bancos, '— Sem banco —');

    setStatus('online', 'Sistema Sincronizado');
}

function popularSelect(id, opcoes, placeholder) {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = `<option value="">${placeholder}</option>` +
        opcoes.map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('');
}
function setSelectValue(id, value) {
    const sel = document.getElementById(id);
    if (!sel || !value) { if (sel) sel.value = ''; return; }
    if (!Array.from(sel.options).some(o => o.value === value)) {
        const opt = document.createElement('option'); opt.value = opt.textContent = value; sel.appendChild(opt);
    }
    sel.value = value;
}

// --- CARREGAR ---
async function carregarRecebimentos() {
    if (!dbClient) return;
    document.getElementById('tabelaLoading').style.display = 'flex';

    try {
        const dataIni    = document.getElementById('filtroDataIni').value;
        const dataFim    = document.getElementById('filtroDataFim').value;
        const obra       = document.getElementById('filtroObra').value;
        const fornecedor = document.getElementById('filtroFornecedor').value.trim();
        const banco      = document.getElementById('filtroBanco').value;
        const status     = document.getElementById('filtroStatus').value;

        let q = dbClient
            .from('recebimentos')
            .select('*')
            .order('data', { ascending: false })
            .order('id',   { ascending: false });

        if (dataIni)              q = q.gte('data', dataIni);
        if (dataFim)              q = q.lte('data', dataFim);
        if (obra)                 q = q.eq('obra', obra);
        if (fornecedor)           q = q.ilike('fornecedor', `%${fornecedor}%`);
        if (banco)                q = q.eq('banco', banco);
        if (status === 'pendente')   q = q.eq('recebido', false);
        if (status === 'confirmado') q = q.eq('recebido', true);

        const { data, error } = await q;
        if (error) throw error;

        todosRegistros = data || [];
        paginaAtual    = 1;
        renderizarTabela();
        atualizarKPIs();
    } catch (e) {
        toast.error('Erro ao carregar: ' + e.message);
    } finally {
        document.getElementById('tabelaLoading').style.display = 'none';
    }
}

// --- FILTRO LOCAL ---
function filtrarRegistros() {
    const busca = document.getElementById('buscaTexto').value.trim().toLowerCase();
    if (!busca) return todosRegistros;
    return todosRegistros.filter(r =>
        (r.fornecedor || '').toLowerCase().includes(busca) ||
        (r.descricao  || '').toLowerCase().includes(busca) ||
        (r.observacao || '').toLowerCase().includes(busca)
    );
}

// --- RENDERIZAR TABELA ---
function renderizarTabela() {
    const tbody    = document.getElementById('tabelaBody');
    const filtrado = filtrarRegistros();
    const total    = filtrado.length;
    const inicio   = (paginaAtual - 1) * PAGE_SIZE;
    const pagina   = filtrado.slice(inicio, inicio + PAGE_SIZE);
    const paginacaoWrap = document.getElementById('paginacaoWrap');

    if (!pagina.length) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhum recebimento encontrado.</td></tr>`;
        paginacaoWrap.style.display = 'none';
        return;
    }

    tbody.innerHTML = pagina.map(r => {
        const valor = r.valor != null ? formatarValor(r.valor) : '—';

        const parcelaBadge = r.total_parcelas > 1
            ? `<span style="font-size:0.7rem;background:var(--surface-low);border:1px solid var(--outline-ghost);border-radius:4px;padding:1px 5px;margin-left:4px;color:var(--on-surface-muted);">${r.parcela_num}/${r.total_parcelas}</span>`
            : '';

        const nfIcon = r.comprovante_url
            ? `<a href="${r.comprovante_url}" target="_blank" title="Ver comprovante" style="color:var(--secondary);">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg></a>`
            : '—';

        const confirmarCol = r.recebido
            ? `<span style="font-size:0.72rem;color:var(--on-surface-muted);">${formatarData(r.data_recebimento)}</span>`
            : `<button class="btn btn-outline" onclick="abrirModalConfirmar(${r.id})" style="font-size:0.72rem;padding:3px 10px;color:var(--success);border-color:var(--success);" title="Confirmar recebimento">Confirmar</button>`;

        return `<tr>
            <td style="white-space:nowrap;">${formatarData(r.data)}</td>
            <td>${esc(r.obra || '—')}</td>
            <td>${esc(r.fornecedor || '—')}</td>
            <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(r.descricao)}">
                ${esc(r.descricao || '—')}${parcelaBadge}
            </td>
            <td>${esc(r.forma || '—')}</td>
            <td>${esc(r.banco || '—')}</td>
            <td class="text-right" style="font-weight:600;">R$ ${valor}</td>
            <td style="text-align:center;">${nfIcon}</td>
            <td style="text-align:center;">${statusBadge(r)}</td>
            <td style="text-align:center;white-space:nowrap;">
                ${confirmarCol}
                <button class="btn btn-outline" onclick="abrirModal(${r.id})" style="font-size:0.72rem;padding:3px 8px;margin-left:4px;" title="Editar">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button class="btn btn-outline" onclick="excluir(${r.id})" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Excluir">
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
    const confirmado  = todosRegistros.filter(r => r.recebido).reduce((s, r) => s + Number(r.valor || 0), 0);
    const aConfirmar  = todosRegistros.filter(r => !r.recebido).reduce((s, r) => s + Number(r.valor || 0), 0);

    const porObra = {};
    for (const r of todosRegistros) {
        const o = r.obra || '(sem obra)';
        porObra[o] = (porObra[o] || 0) + Number(r.valor || 0);
    }
    const obraTop  = Object.entries(porObra).sort((a, b) => b[1] - a[1])[0];
    const qtdObras = Object.keys(porObra).length;

    document.getElementById('kpiTotal').textContent   = confirmado > 0 ? `R$ ${formatarValor(confirmado)}` : '—';
    document.getElementById('kpiMes').textContent     = aConfirmar > 0 ? `R$ ${formatarValor(aConfirmar)}` : '—';
    document.getElementById('kpiObraTop').textContent = obraTop ? `${obraTop[0]}: R$ ${formatarValor(obraTop[1])}` : '—';
    document.getElementById('kpiObras').textContent   = qtdObras > 0 ? `${qtdObras} obra${qtdObras > 1 ? 's' : ''}` : '—';
}

// --- LIMPAR FILTROS ---
function limparFiltros() {
    ['filtroDataIni','filtroDataFim','filtroObra'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('filtroFornecedor').value = '';
    document.getElementById('filtroBanco').value      = '';
    document.getElementById('filtroStatus').value     = '';
    document.getElementById('buscaTexto').value = '';
    paginaAtual = 1;
    carregarRecebimentos();
}

// --- MODAL ---
function abrirModal(id) {
    editandoId = id;
    document.getElementById('modalRecTitulo').textContent = id ? 'Editar Recebimento' : 'Novo Recebimento';

    ['rFornecedor','rDescricao','rBanco'].forEach(i => document.getElementById(i).value = '');
    document.getElementById('rValor').value = '';
    document.getElementById('rData').value  = hoje();
    document.getElementById('rUsarParcelas').checked = false;
    document.getElementById('parcelasConfig').style.display = 'none';
    document.getElementById('rTotalParcelas').value  = '2';
    document.getElementById('rIntervaloMeses').value = '1';
    document.getElementById('uploadZoneRecText').textContent = 'Clique ou arraste (PDF, JPG, PNG)';
    document.getElementById('uploadZoneRec').style.borderColor = '';
    document.getElementById('inputComprovanteRec').value = '';
    document.getElementById('inputComprovanteRec')._file = null;
    ['rObra','rForma'].forEach(i => document.getElementById(i).value = '');

    if (id) {
        const r = todosRegistros.find(x => x.id === id);
        if (r) {
            document.getElementById('rFornecedor').value = r.fornecedor || '';
            document.getElementById('rDescricao').value  = r.descricao  || '';
            document.getElementById('rBanco').value      = r.banco      || '';
            document.getElementById('rValor').value      = r.valor      || '';
            document.getElementById('rData').value       = r.data       || '';
            setSelectValue('rObra',  r.obra);
            setSelectValue('rForma', r.forma);
            // Esconde parcelas na edição
            document.getElementById('parcelasToggleWrap').style.display = 'none';
        }
    } else {
        document.getElementById('parcelasToggleWrap').style.display = '';
    }

    document.getElementById('modalRecebimento').style.display = 'flex';
}

function fecharModal() {
    document.getElementById('modalRecebimento').style.display = 'none';
    editandoId = null;
}

// --- UPLOAD ---
async function uploadComprovante(file) {
    try {
        const ext  = file.name.split('.').pop().toLowerCase();
        const nome = `rec_${crypto.randomUUID().replace(/-/g,'').slice(0,12)}.${ext}`;
        const { error } = await dbClient.storage.from('comprovantes').upload(nome, file, { contentType: file.type });
        if (error) throw error;
        return `${window.ENV.SUPABASE_URL.replace(/\/$/, '')}/storage/v1/object/public/comprovantes/${nome}`;
    } catch (e) {
        toast.warning(`Comprovante não pôde ser salvo: ${e.message}`);
        return null;
    }
}

function definirComprovante(file) {
    document.getElementById('inputComprovanteRec')._file = file;
    document.getElementById('uploadZoneRecText').textContent = `📎 ${file.name}`;
    document.getElementById('uploadZoneRec').style.borderColor = 'var(--accent)';
}

// --- SALVAR ---
async function salvarRecebimento() {
    const fornecedor = document.getElementById('rFornecedor').value.trim();
    const valor      = parseFloat(document.getElementById('rValor').value);
    const data       = document.getElementById('rData').value;

    if (!fornecedor)                { toast.warning('Informe o fornecedor/cliente.'); return; }
    if (isNaN(valor) || valor <= 0) { toast.warning('Informe um valor válido.'); return; }
    if (!data)                      { toast.warning('Informe a data.'); return; }

    const usarParcelas = document.getElementById('rUsarParcelas').checked && !editandoId;
    const totalParc    = usarParcelas ? parseInt(document.getElementById('rTotalParcelas').value) || 1 : 1;
    const intervalo    = usarParcelas ? parseInt(document.getElementById('rIntervaloMeses').value) || 1 : 1;

    const base = {
        fornecedor,
        valor:      Math.round(valor * 100) / 100,
        obra:       document.getElementById('rObra').value    || null,
        forma:      document.getElementById('rForma').value   || null,
        banco:      document.getElementById('rBanco').value              || null,
        descricao:  document.getElementById('rDescricao').value.trim()  || null,
    };

    const btn = document.getElementById('btnSalvarRec');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        // Upload comprovante (só na criação única ou edição)
        let comprovanteUrl = null;
        const file = document.getElementById('inputComprovanteRec')._file;
        if (file && (!usarParcelas || totalParc === 1)) {
            comprovanteUrl = await uploadComprovante(file);
        }

        if (editandoId) {
            const payload = { ...base, data };
            if (comprovanteUrl) { payload.comprovante_url = comprovanteUrl; payload.tem_comprovante = true; }
            const { error } = await dbClient.from('recebimentos').update(payload).eq('id', editandoId);
            if (error) throw error;
            toast.success('Recebimento atualizado.');
        } else if (totalParc > 1) {
            const grupoId = Date.now();
            const rows = Array.from({ length: totalParc }, (_, i) => ({
                ...base,
                data:           addMeses(data, i * intervalo),
                parcela_num:    i + 1,
                total_parcelas: totalParc,
                grupo_id:       grupoId,
            }));
            const { error } = await dbClient.from('recebimentos').insert(rows);
            if (error) throw error;
            toast.success(`${totalParc} parcelas criadas!`);
        } else {
            const payload = { ...base, data, parcela_num: 1, total_parcelas: 1 };
            if (comprovanteUrl) { payload.comprovante_url = comprovanteUrl; payload.tem_comprovante = true; }
            const { error } = await dbClient.from('recebimentos').insert(payload);
            if (error) throw error;
            toast.success('Recebimento cadastrado.');
        }

        fecharModal();
        await carregarRecebimentos();
    } catch (e) {
        toast.error('Erro ao salvar: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

// --- EXCLUIR ---
async function excluir(id) {
    const r = todosRegistros.find(x => x.id === id);
    if (!r) return;
    const desc = r.fornecedor + (r.descricao ? ` — ${r.descricao}` : '');
    if (!confirm(`Excluir "${desc}"?`)) return;

    try {
        const { error } = await dbClient.from('recebimentos').delete().eq('id', id);
        if (error) throw error;
        todosRegistros = todosRegistros.filter(x => x.id !== id);
        renderizarTabela();
        atualizarKPIs();
        toast.success('Excluído.');
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

// --- CONFIRMAR RECEBIMENTO ---
function abrirModalConfirmar(id) {
    const r = todosRegistros.find(x => x.id === id);
    if (!r) return;
    confirmarId = id;
    const desc = [r.fornecedor, r.descricao, r.obra].filter(Boolean).join(' — ');
    document.getElementById('modalConfirmarDesc').textContent =
        `${desc} · R$ ${formatarValor(r.valor)} · ${formatarData(r.data)}`;
    document.getElementById('confirmarData').value = hoje();
    document.getElementById('modalConfirmar').style.display = 'flex';
}

function fecharModalConfirmar() {
    document.getElementById('modalConfirmar').style.display = 'none';
    confirmarId = null;
}

async function confirmarRecebimento() {
    if (!confirmarId) return;
    const dataRec = document.getElementById('confirmarData').value;
    if (!dataRec) { toast.warning('Informe a data do recebimento.'); return; }

    const btn = document.getElementById('btnConfirmarRecebimento');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        const { error } = await dbClient.from('recebimentos').update({
            recebido: true,
            data_recebimento: dataRec,
        }).eq('id', confirmarId);
        if (error) throw error;

        const idx = todosRegistros.findIndex(x => x.id === confirmarId);
        if (idx !== -1) {
            todosRegistros[idx].recebido        = true;
            todosRegistros[idx].data_recebimento = dataRec;
        }

        fecharModalConfirmar();
        renderizarTabela();
        atualizarKPIs();
        toast.success('Recebimento confirmado.');
    } catch (e) {
        toast.error('Erro ao confirmar: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Confirmar';
    }
}

// --- EXPORT CSV ---
function exportarCSV() {
    const dados = filtrarRegistros();
    if (!dados.length) { toast.warning('Nenhum dado para exportar.'); return; }

    const cab  = ['Data','Obra','Fornecedor','Descrição','Forma','Valor','Parcela','Status','Data Recebimento'];
    const rows = dados.map(r => [
        r.data        || '',
        r.obra        || '',
        r.fornecedor  || '',
        r.descricao   || '',
        r.forma       || '',
        r.valor       || 0,
        r.total_parcelas > 1 ? `${r.parcela_num}/${r.total_parcelas}` : '',
        r.recebido ? 'Confirmado' : 'Pendente',
        r.data_recebimento || '',
    ].map(v => `"${String(v).replace(/"/g,'""')}"`).join(','));

    const csv  = [cab.join(','), ...rows].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `recebimentos_${hoje()}.csv`; a.click();
    URL.revokeObjectURL(url);
}
