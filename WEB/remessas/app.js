/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Remessas de Caixa (app.js)
 *
 * banco_destino_id → FK para bancos(id)  [tipo='filho']
 * obra             → FK para obras(nome) [nullable]
 */

const API_BASE = window.API_BASE || `http://${location.hostname}:8000`;

// --- SUPABASE ---
let dbClient;
function carregarEnv() {
    if (window.ENV) {
        const { SUPABASE_URL, SUPABASE_ANON_KEY } = window.ENV;
        if (SUPABASE_URL && SUPABASE_ANON_KEY) {
            dbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        }
    }
}

// --- ESTADO ---
let obras        = [];
let remessas     = [];
let bancosFilhos = []; // { id, nome } — contas controladas (tipo='filho')
let bancosObras  = {}; // banco_id → string[] (obras associadas; vazio = todas)
let arquivoComprovante = null;

// --- FORMATAÇÃO ---
function fmtMoeda(v) {
    return (v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
function fmtData(d) {
    if (!d) return '—';
    const [y, m, dd] = d.split('-');
    return `${dd}/${m}/${y}`;
}
function hoje() {
    return new Date().toISOString().slice(0, 10);
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    carregarEnv();
    if (!dbClient) {
        document.getElementById('tabelaBody').innerHTML =
            '<tr><td colspan="6" style="text-align:center;color:var(--danger);padding:var(--sp-6);">Erro: credenciais Supabase não carregadas.</td></tr>';
        return;
    }

    document.getElementById('rData').value = hoje();

    await Promise.all([carregarObras(), carregarBancos(), carregarRemessas()]);
    await renderSaldos();

    document.getElementById('btnNovaRemessa').addEventListener('click', abrirModalNovaRemessa);
    document.getElementById('btnSalvarRemessa').addEventListener('click', salvarRemessa);
    document.getElementById('btnFiltrar').addEventListener('click', aplicarFiltros);
    document.getElementById('btnLimparFiltros').addEventListener('click', limparFiltros);
    document.getElementById('btnExportarCSV').addEventListener('click', exportarCSV);
});

// --- CARREGAMENTO ---
async function carregarObras() {
    const { data } = await dbClient.from('obras').select('nome').order('nome');
    obras = (data || []).map(o => o.nome);
    popularSelectObra(obras);
}

function popularSelectObra(lista) {
    const sel = document.getElementById('rObra');
    const atual = sel.value;
    sel.innerHTML = '<option value="">Sem obra específica</option>' +
        lista.map(o => `<option value="${o}">${o}</option>`).join('');
    if (lista.includes(atual)) sel.value = atual;
}

async function carregarBancos() {
    const [{ data: dataBancos }, { data: dataObrasBanco }] = await Promise.all([
        dbClient.from('bancos').select('id, nome, tipo').eq('tipo', 'filho').order('nome'),
        dbClient.from('banco_obras').select('banco_id, obra'),
    ]);

    bancosFilhos = dataBancos || [];

    bancosObras = {};
    for (const bo of (dataObrasBanco || [])) {
        if (!bancosObras[bo.banco_id]) bancosObras[bo.banco_id] = [];
        bancosObras[bo.banco_id].push(bo.obra);
    }

    // Modal: value = id numérico
    const selDestino = document.getElementById('rDestino');
    selDestino.innerHTML = bancosFilhos.map(b => `<option value="${b.id}">${b.nome}</option>`).join('');
    selDestino.addEventListener('change', () => filtrarObrasPorDestino(selDestino.value));

    // Filtro de banco
    atualizarFiltroBanco();
}

// bancoId: ID numérico do banco destino — filtra obras disponíveis no modal
function filtrarObrasPorDestino(bancoId) {
    const id = parseInt(bancoId, 10);
    const permitidas = bancosObras[id] || [];
    // sem restrição configurada → mostra todas
    const lista = permitidas.length ? obras.filter(o => permitidas.includes(o)) : obras;
    popularSelectObra(lista);
}

async function carregarRemessas(filtros = {}) {
    // Join embutido: banco_destino retorna { id, nome }
    let q = dbClient.from('remessas_caixa').select(
        '*, banco_destino:bancos!banco_destino_id(id,nome)'
    );

    if (filtros.banco)      q = q.eq('banco_destino_id', filtros.banco);
    if (filtros.obra)       q = q.eq('obra', filtros.obra);
    if (filtros.dataInicio) q = q.gte('data', filtros.dataInicio);
    if (filtros.dataFim)    q = q.lte('data', filtros.dataFim);

    const { data, error } = await q.order('data', { ascending: false }).limit(500);
    if (error) { console.error('Erro ao carregar remessas:', error); return; }
    remessas = data || [];
    renderTabela();
}

// --- SALDOS ---
let _cardAtivo = null; // banco_id selecionado via card interativo

async function renderSaldos() {
    const grid = document.getElementById('saldosGrid');
    grid.innerHTML = '<div class="metric-card"><div class="metric-label">Carregando saldos…</div><div class="metric-value">—</div></div>';

    const { data, error } = await dbClient.rpc('saldo_bancos');
    if (error) {
        grid.innerHTML = `<div class="metric-card"><div class="metric-label" style="color:var(--danger);">Erro ao carregar saldos</div><div class="metric-value">—</div></div>`;
        console.error('saldo_bancos RPC error:', error);
        return;
    }

    const saldos = data || [];
    if (!saldos.length) {
        grid.innerHTML = '<div class="metric-card"><div class="metric-label">Nenhuma remessa registrada ainda</div><div class="metric-value">—</div></div>';
        return;
    }

    const totalRecebido = saldos.reduce((s, x) => s + (x.total_recebido || 0), 0);
    const totalGasto    = saldos.reduce((s, x) => s + (x.total_gasto    || 0), 0);
    const totalSaldo    = totalRecebido - totalGasto;

    grid.innerHTML = saldos.map(s => {
        const isAtivo = _cardAtivo === s.banco_id;
        const ultimaStr = s.ultima_remessa ? `Última: ${fmtData(s.ultima_remessa)}` : '';
        return `
        <div class="metric-card" onclick="filtrarPorCard(${s.banco_id})" style="cursor:pointer;transition:border .15s;${s.saldo < 0 ? 'border-left:3px solid var(--danger);' : ''}${isAtivo ? 'border-left:3px solid var(--primary);' : ''}">
            <div class="metric-label">${s.banco}</div>
            <div class="metric-value" style="color:${s.saldo < 0 ? 'var(--danger)' : 'var(--success)'};">${fmtMoeda(s.saldo)}</div>
            <div style="font-size:0.72rem;color:var(--on-surface-muted);margin-top:4px;">
                Recebido: ${fmtMoeda(s.total_recebido)} &nbsp;|&nbsp; Despesas: ${fmtMoeda(s.total_gasto)}
                ${ultimaStr ? `<br>${ultimaStr}` : ''}
            </div>
        </div>`;
    }).join('') + `
        <div class="metric-card">
            <div class="metric-label" style="font-weight:600;">Total Geral</div>
            <div class="metric-value" style="color:${totalSaldo < 0 ? 'var(--danger)' : 'var(--success)'};">${fmtMoeda(totalSaldo)}</div>
            <div style="font-size:0.72rem;color:var(--on-surface-muted);margin-top:4px;">
                Enviado: ${fmtMoeda(totalRecebido)} &nbsp;|&nbsp; Gasto: ${fmtMoeda(totalGasto)}
            </div>
        </div>`;
}

function filtrarPorCard(bancoId) {
    const sel = document.getElementById('filtroBanco');
    if (_cardAtivo === bancoId) {
        _cardAtivo = null;
        sel.value = '';
    } else {
        _cardAtivo = bancoId;
        sel.value = bancoId;
    }
    aplicarFiltros();
    renderSaldos();
}

// --- TABELA ---
function renderTabela() {
    const tbody = document.getElementById('tabelaBody');
    const total = remessas.reduce((s, r) => s + (r.valor || 0), 0);
    const limiteBadge = remessas.length >= 500
        ? ' &nbsp;<span style="font-size:0.72rem;background:color-mix(in srgb,var(--warning,#f59e0b) 20%,transparent);color:var(--warning,#b45309);padding:2px 8px;border-radius:12px;">⚠ limite 500 — use filtros</span>'
        : '';
    document.getElementById('totalRemessas').innerHTML =
        `${remessas.length} remessa(s) — Total: ${fmtMoeda(total)}${limiteBadge}`;

    if (!remessas.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-6);">Nenhuma remessa encontrada.</td></tr>';
        return;
    }

    tbody.innerHTML = remessas.map(r => `
        <tr>
            <td>${fmtData(r.data)}</td>
            <td><strong>${r.banco_destino?.nome || '—'}</strong></td>
            <td style="color:var(--on-surface-muted);">${r.obra || '—'}</td>
            <td style="color:var(--on-surface-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${r.descricao || '—'}</td>
            <td class="text-right"><strong>${fmtMoeda(r.valor)}</strong></td>
            <td style="text-align:center;">
                ${r.comprovante_url
                    ? `<a href="${r.comprovante_url}" target="_blank" title="Ver comprovante"
                          style="color:var(--primary);font-size:0.8rem;text-decoration:none;">📎 Ver</a>`
                    : '<span style="color:var(--on-surface-muted);font-size:0.75rem;">—</span>'}
            </td>
            <td>
                <div style="display:flex;gap:var(--sp-1);justify-content:flex-end;">
                    <button class="btn btn-outline btn-sm" onclick="editarRemessa('${r.id}')" style="font-size:0.75rem;padding:3px 10px;">Editar</button>
                    <button class="btn btn-outline btn-sm" onclick="excluirRemessa('${r.id}')" style="font-size:0.75rem;padding:3px 10px;color:var(--danger);">Excluir</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// --- MODAL REMESSA ---
function abrirModalNovaRemessa() {
    document.getElementById('rId').value = '';
    if (bancosFilhos.length) {
        document.getElementById('rDestino').value = bancosFilhos[0].id;
        filtrarObrasPorDestino(bancosFilhos[0].id);
    }
    document.getElementById('rValor').value = '';
    document.getElementById('rData').value = hoje();
    document.getElementById('rObra').value = '';
    document.getElementById('rDescricao').value = '';
    document.getElementById('rComprovanteUrl').value = '';
    limparUploadZone();
    document.getElementById('modalRemessaTitulo').textContent = 'Nova Remessa';
    document.getElementById('modalRemessa').style.display = 'flex';
    document.getElementById('rDestino').focus();
}

function fecharModalRemessa(e) {
    if (e && e.target !== document.getElementById('modalRemessa')) return;
    document.getElementById('modalRemessa').style.display = 'none';
}

function editarRemessa(id) {
    const r = remessas.find(x => x.id === id);
    if (!r) return;
    document.getElementById('rId').value = id;
    document.getElementById('rDestino').value = r.banco_destino_id || '';
    filtrarObrasPorDestino(r.banco_destino_id || '');
    document.getElementById('rValor').value = r.valor;
    document.getElementById('rData').value = r.data;
    document.getElementById('rObra').value = r.obra || '';
    document.getElementById('rDescricao').value = r.descricao || '';
    document.getElementById('rComprovanteUrl').value = r.comprovante_url || '';
    limparUploadZone();
    if (r.comprovante_url) {
        const div = document.getElementById('comprovanteAtual');
        div.style.display = 'block';
        div.innerHTML = `Comprovante atual: <a href="${r.comprovante_url}" target="_blank" style="color:var(--primary);">ver arquivo</a>
            <button onclick="removerComprovanteAtual()" style="margin-left:8px;background:none;border:none;color:var(--danger);cursor:pointer;font-size:0.8rem;">Remover</button>`;
    }
    document.getElementById('modalRemessaTitulo').textContent = 'Editar Remessa';
    document.getElementById('modalRemessa').style.display = 'flex';
}

async function salvarRemessa() {
    const id        = document.getElementById('rId').value;
    const destinoId = parseInt(document.getElementById('rDestino').value, 10) || null;
    const valor     = parseFloat(document.getElementById('rValor').value);
    const data      = document.getElementById('rData').value;
    const obra      = document.getElementById('rObra').value || null;
    const descricao = document.getElementById('rDescricao').value.trim() || null;

    if (!destinoId || !valor || !data) {
        toast.error('Preencha os campos obrigatórios: Destino, Valor e Data.');
        return;
    }

    const btn = document.getElementById('btnSalvarRemessa');
    btn.disabled = true;
    btn.textContent = 'Salvando…';

    let comprovanteUrl = document.getElementById('rComprovanteUrl').value || null;
    if (arquivoComprovante) {
        const res = await uploadComprovante(arquivoComprovante);
        if (!res) { btn.disabled = false; btn.textContent = 'Salvar'; return; }
        comprovanteUrl = res.url;
        arquivoComprovante = null;
    }

    const payload = {
        banco_destino_id: destinoId,
        valor,
        data,
        obra,
        descricao,
        comprovante_url: comprovanteUrl,
    };

    let error;
    if (id) {
        ({ error } = await dbClient.from('remessas_caixa').update(payload).eq('id', id));
    } else {
        ({ error } = await dbClient.from('remessas_caixa').insert(payload));
    }

    btn.disabled = false;
    btn.textContent = 'Salvar';

    if (error) { toast.error('Erro ao salvar: ' + error.message); return; }

    toast.success(id ? 'Remessa atualizada.' : 'Remessa registrada.');
    document.getElementById('modalRemessa').style.display = 'none';
    await carregarRemessas(filtrosAtivos());
    await renderSaldos();
}

async function excluirRemessa(id) {
    if (!confirm('Excluir esta remessa?')) return;
    const { error } = await dbClient.from('remessas_caixa').delete().eq('id', id);
    if (error) { toast.error('Erro ao excluir: ' + error.message); return; }
    toast.success('Remessa excluída.');
    await carregarRemessas(filtrosAtivos());
    await renderSaldos();
}

// --- FILTROS ---
function filtrosAtivos() {
    return {
        banco:      document.getElementById('filtroBanco').value || '',
        obra:       document.getElementById('filtroObra').value  || '',
        dataInicio: document.getElementById('filtroDataInicio').value || '',
        dataFim:    document.getElementById('filtroDataFim').value || '',
    };
}

async function aplicarFiltros() {
    await carregarRemessas(filtrosAtivos());
}

async function limparFiltros() {
    document.getElementById('filtroBanco').value = '';
    document.getElementById('filtroObra').value  = '';
    document.getElementById('filtroDataInicio').value = '';
    document.getElementById('filtroDataFim').value = '';
    _cardAtivo = null;
    await carregarRemessas();
    await renderSaldos();
}

// --- FILTRO CONTA ---
function atualizarFiltroBanco() {
    const sel = document.getElementById('filtroBanco');
    const atual = sel.value;
    sel.innerHTML = '<option value="">Todas as contas</option>' +
        bancosFilhos.map(b => `<option value="${b.id}">${b.nome}</option>`).join('');
    if (atual) sel.value = atual;

    // Filtro de obra (estático, todas as obras)
    const selObra = document.getElementById('filtroObra');
    if (selObra) {
        selObra.innerHTML = '<option value="">Todas as obras</option>' +
            obras.map(o => `<option value="${o}">${o}</option>`).join('');
    }
}

// --- COMPROVANTE UPLOAD ---
function handleFileComprovante(file) {
    if (!file) return;
    arquivoComprovante = file;
    document.getElementById('uploadZoneRem_label').textContent = `📎 ${file.name}`;
    document.getElementById('uploadZoneRem').style.borderColor = 'var(--primary)';
}

function handleDropComprovante(e) {
    e.preventDefault();
    document.getElementById('uploadZoneRem').style.borderColor = 'var(--surface-3)';
    const file = e.dataTransfer.files[0];
    if (file) handleFileComprovante(file);
}

function limparUploadZone() {
    arquivoComprovante = null;
    document.getElementById('uploadZoneRem_label').textContent = 'Clique ou arraste o comprovante (JPG, PNG, PDF)';
    document.getElementById('uploadZoneRem').style.borderColor = 'var(--surface-3)';
    document.getElementById('comprovanteAtual').style.display = 'none';
    document.getElementById('comprovanteAtual').innerHTML = '';
    document.getElementById('inputComprovante').value = '';
}

function removerComprovanteAtual() {
    document.getElementById('rComprovanteUrl').value = '';
    document.getElementById('comprovanteAtual').style.display = 'none';
}

async function uploadComprovante(file) {
    try {
        const ext  = file.name.split('.').pop().toLowerCase();
        const nome = `rem_${crypto.randomUUID().replace(/-/g,'').slice(0,12)}.${ext}`;
        const { error } = await dbClient.storage.from('comprovantes').upload(nome, file, { contentType: file.type });
        if (error) throw error;
        const { data: { publicUrl } } = dbClient.storage.from('comprovantes').getPublicUrl(nome);
        return { url: publicUrl, nome };
    } catch (e) {
        toast.error('Erro no upload do comprovante: ' + e.message);
        return null;
    }
}

// --- EXPORT CSV ---
function exportarCSV() {
    if (!remessas.length) { toast.error('Nenhuma remessa para exportar.'); return; }
    const header = ['data', 'destino', 'valor', 'obra', 'descricao'];
    const linhas = remessas.map(r =>
        [r.data, r.banco_destino?.nome || '', r.valor, r.obra || '', r.descricao || '']
        .map(v => `"${String(v).replace(/"/g, '""')}"`)
        .join(',')
    );
    const csv  = [header.join(','), ...linhas].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `remessas_${hoje()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
