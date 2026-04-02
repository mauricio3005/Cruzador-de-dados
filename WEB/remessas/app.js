/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Remessas de Caixa (app.js)
 *
 * Maurício = conta principal de origem (não aparece nos saldos controlados).
 * Kathleen, Diego (e qualquer outro que receber remessa) = contas controladas.
 */

const API_BASE = `http://${location.hostname}:8000`;

// Nome da conta principal — valores enviados DAQUI, não são rastreados como saldo
const CONTA_PRINCIPAL = 'Maurício';

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
let contasUsadas = []; // nomes únicos de banco_destino já registrados
let arquivoComprovante = null; // file pendente de upload no modal

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

    await Promise.all([carregarObras(), carregarRemessas()]);
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
    const sel = document.getElementById('rObra');
    sel.innerHTML = '<option value="">Sem obra específica</option>' +
        obras.map(o => `<option value="${o}">${o}</option>`).join('');
}

async function carregarRemessas(filtros = {}) {
    let q = dbClient.from('remessas_caixa').select('*');

    if (filtros.banco)      q = q.eq('banco_destino', filtros.banco);
    if (filtros.dataInicio) q = q.gte('data', filtros.dataInicio);
    if (filtros.dataFim)    q = q.lte('data', filtros.dataFim);

    const { data, error } = await q.order('data', { ascending: false }).limit(500);
    if (error) { console.error('Erro ao carregar remessas:', error); return; }
    remessas = data || [];

    // Atualiza lista de contas usadas para datalist e filtro
    contasUsadas = [...new Set(remessas.map(r => r.banco_destino))].sort();
    atualizarDatalist();
    atualizarFiltroBanco();
    renderTabela();
}

// --- SALDOS ---
async function renderSaldos() {
    const grid = document.getElementById('saldosGrid');

    const [{ data: remData }, { data: despData }] = await Promise.all([
        dbClient.from('remessas_caixa').select('banco_destino, valor'),
        dbClient.from('c_despesas').select('banco, valor_total').not('banco', 'is', null),
    ]);

    // Soma remessas recebidas por conta
    const recebido = {};
    for (const r of (remData || [])) {
        recebido[r.banco_destino] = (recebido[r.banco_destino] || 0) + (r.valor || 0);
    }

    // Soma despesas por conta — exclui Maurício (conta principal)
    const gasto = {};
    for (const d of (despData || [])) {
        const b = d.banco;
        if (b && b !== CONTA_PRINCIPAL) {
            gasto[b] = (gasto[b] || 0) + (d.valor_total || 0);
        }
    }

    // Contas controladas = todos os banco_destino + contas com despesas (exclui Maurício)
    const contas = new Set([...Object.keys(recebido), ...Object.keys(gasto)]);

    if (contas.size === 0) {
        grid.innerHTML = '<div class="metric-card"><div class="metric-label">Nenhuma remessa registrada ainda</div><div class="metric-value">—</div></div>';
        return;
    }

    const saldos = [...contas].sort().map(nome => ({
        nome,
        recebido: recebido[nome] || 0,
        gasto:    gasto[nome]    || 0,
        saldo:    (recebido[nome] || 0) - (gasto[nome] || 0),
    }));

    // Total geral
    const totalRecebido = saldos.reduce((s, x) => s + x.recebido, 0);
    const totalGasto    = saldos.reduce((s, x) => s + x.gasto, 0);
    const totalSaldo    = totalRecebido - totalGasto;

    grid.innerHTML = saldos.map(s => `
        <div class="metric-card" style="${s.saldo < 0 ? 'border-left:3px solid var(--danger);' : ''}">
            <div class="metric-label">${s.nome}</div>
            <div class="metric-value" style="color:${s.saldo < 0 ? 'var(--danger)' : 'var(--success)'};">${fmtMoeda(s.saldo)}</div>
            <div style="font-size:0.72rem;color:var(--on-surface-muted);margin-top:4px;">
                Recebido: ${fmtMoeda(s.recebido)} &nbsp;|&nbsp; Despesas: ${fmtMoeda(s.gasto)}
            </div>
        </div>
    `).join('') + `
        <div class="metric-card" style="border-top:2px solid var(--surface-3);">
            <div class="metric-label" style="font-weight:600;">Total Geral</div>
            <div class="metric-value" style="color:${totalSaldo < 0 ? 'var(--danger)' : 'var(--success)'};">${fmtMoeda(totalSaldo)}</div>
            <div style="font-size:0.72rem;color:var(--on-surface-muted);margin-top:4px;">
                Enviado: ${fmtMoeda(totalRecebido)} &nbsp;|&nbsp; Gasto: ${fmtMoeda(totalGasto)}
            </div>
        </div>
    `;
}

// --- TABELA ---
function renderTabela() {
    const tbody = document.getElementById('tabelaBody');
    const total = remessas.reduce((s, r) => s + (r.valor || 0), 0);
    document.getElementById('totalRemessas').textContent =
        `${remessas.length} remessa(s) — Total: ${fmtMoeda(total)}`;

    if (!remessas.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-6);">Nenhuma remessa encontrada.</td></tr>';
        return;
    }

    tbody.innerHTML = remessas.map(r => `
        <tr>
            <td>${fmtData(r.data)}</td>
            <td><strong>${r.banco_destino}</strong></td>
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
    document.getElementById('rDestino').value = '';
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
    document.getElementById('rDestino').value = r.banco_destino;
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
    const id      = document.getElementById('rId').value;
    const destino = document.getElementById('rDestino').value.trim();
    const valor   = parseFloat(document.getElementById('rValor').value);
    const data    = document.getElementById('rData').value;
    const obra    = document.getElementById('rObra').value || null;
    const descricao = document.getElementById('rDescricao').value.trim() || null;

    if (!destino || !valor || !data) {
        showToast('Preencha os campos obrigatórios: Conta, Valor e Data.', 'error');
        return;
    }
    if (destino === CONTA_PRINCIPAL) {
        showToast(`"${CONTA_PRINCIPAL}" é a conta principal — não pode ser o destino.`, 'error');
        return;
    }

    const btn = document.getElementById('btnSalvarRemessa');
    btn.disabled = true;
    btn.textContent = 'Salvando…';

    // Upload do comprovante (se houver arquivo novo selecionado)
    let comprovanteUrl = document.getElementById('rComprovanteUrl').value || null;
    if (arquivoComprovante) {
        const res = await uploadComprovante(arquivoComprovante);
        if (!res) { btn.disabled = false; btn.textContent = 'Salvar'; return; }
        comprovanteUrl = res.url;
        arquivoComprovante = null;
    }

    const payload = { banco_destino: destino, valor, data, obra, descricao, comprovante_url: comprovanteUrl };

    let error;
    if (id) {
        ({ error } = await dbClient.from('remessas_caixa').update(payload).eq('id', id));
    } else {
        ({ error } = await dbClient.from('remessas_caixa').insert(payload));
    }

    btn.disabled = false;
    btn.textContent = 'Salvar';

    if (error) { showToast('Erro ao salvar: ' + error.message, 'error'); return; }

    showToast(id ? 'Remessa atualizada.' : 'Remessa registrada.', 'success');
    document.getElementById('modalRemessa').style.display = 'none';
    await carregarRemessas(filtrosAtivos());
    await renderSaldos();
}

async function excluirRemessa(id) {
    if (!confirm('Excluir esta remessa?')) return;
    const { error } = await dbClient.from('remessas_caixa').delete().eq('id', id);
    if (error) { showToast('Erro ao excluir: ' + error.message, 'error'); return; }
    showToast('Remessa excluída.', 'success');
    await carregarRemessas(filtrosAtivos());
    await renderSaldos();
}

// --- FILTROS ---
function filtrosAtivos() {
    return {
        banco:      document.getElementById('filtroBanco').value || '',
        dataInicio: document.getElementById('filtroDataInicio').value || '',
        dataFim:    document.getElementById('filtroDataFim').value || '',
    };
}

async function aplicarFiltros() {
    await carregarRemessas(filtrosAtivos());
}

async function limparFiltros() {
    document.getElementById('filtroBanco').value = '';
    document.getElementById('filtroDataInicio').value = '';
    document.getElementById('filtroDataFim').value = '';
    await carregarRemessas();
}

// --- DATALIST / FILTRO CONTA ---
function atualizarDatalist() {
    document.getElementById('listaBancos').innerHTML =
        contasUsadas.map(c => `<option value="${c}">`).join('');
}

function atualizarFiltroBanco() {
    const sel = document.getElementById('filtroBanco');
    const atual = sel.value;
    sel.innerHTML = '<option value="">Todas as contas</option>' +
        contasUsadas.map(c => `<option value="${c}">${c}</option>`).join('');
    if (atual) sel.value = atual;
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
        const base = window.ENV.SUPABASE_URL.replace(/\/$/, '');
        const url  = `${base}/storage/v1/object/public/comprovantes/${nome}`;
        return { url, nome };
    } catch (e) {
        showToast('Erro no upload do comprovante: ' + e.message, 'error');
        return null;
    }
}

// --- EXPORT CSV ---
function exportarCSV() {
    if (!remessas.length) { showToast('Nenhuma remessa para exportar.', 'error'); return; }
    const header = ['data', 'conta', 'valor', 'obra', 'descricao'];
    const linhas = remessas.map(r =>
        [r.data, r.banco_destino, r.valor, r.obra || '', r.descricao || '']
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
