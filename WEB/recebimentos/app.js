/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Recebimentos (app.js)
 * Fonte de dados: tabela `recebimentos`
 */

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
let obras  = [];
let etapas = [];
let formas = [];

let todosRegistros = [];
let paginaAtual    = 1;
const PAGE_SIZE    = 50;

let editandoId  = null;
let recebendoId = null;

// --- HELPERS ---
function esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatarData(d) {
    if (!d) return '—';
    const [y, m, dia] = d.split('-');
    return `${dia}/${m}/${y}`;
}

function formatarValor(v) {
    return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function hoje() {
    return new Date().toISOString().split('T')[0];
}

function addDias(d, n) {
    const dt = new Date(d + 'T00:00:00');
    dt.setDate(dt.getDate() + n);
    return dt.toISOString().split('T')[0];
}

function statusVisual(r) {
    if (r.recebido) return 'recebido';
    if (r.vencimento && r.vencimento < hoje()) return 'vencido';
    return 'pendente';
}

function badgeStatus(sv) {
    const cfg = {
        recebido: { cor: 'var(--success)', bg: 'rgba(46,125,50,0.1)',   label: 'Recebido' },
        vencido:  { cor: 'var(--error)',   bg: 'rgba(186,26,26,0.1)',   label: 'Vencido'  },
        pendente: { cor: 'var(--warning)', bg: 'rgba(180,83,9,0.1)',    label: 'Pendente' },
    };
    const c = cfg[sv] || cfg.pendente;
    return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:0.7rem;font-weight:700;
            color:${c.cor};background:${c.bg};">${c.label}</span>`;
}

function setStatus(estado, texto) {
    const el = document.getElementById('connectionStatus');
    if (!el) return;
    el.textContent = texto;
    el.className   = `status-dot ${estado}`;
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    carregarEnv();
    await carregarReferencias();

    document.getElementById('btnFiltrar').addEventListener('click', () => { paginaAtual = 1; carregarRecebimentos(); });
    document.getElementById('btnLimparFiltro').addEventListener('click', limparFiltros);
    document.getElementById('buscaTexto').addEventListener('input', renderizarTabela);

    document.getElementById('btnPagAnterior').addEventListener('click', () => { if (paginaAtual > 1) { paginaAtual--; renderizarTabela(); } });
    document.getElementById('btnPagProxima').addEventListener('click', () => {
        if (paginaAtual * PAGE_SIZE < filtrarRegistros().length) { paginaAtual++; renderizarTabela(); }
    });

    document.getElementById('btnNovoRecebimento').addEventListener('click', () => abrirModalRec(null));
    document.getElementById('btnSalvarRec').addEventListener('click', salvarRecebimento);
    document.getElementById('btnConfirmarReceber').addEventListener('click', confirmarRecebimento);
    document.getElementById('btnExportarCSV').addEventListener('click', exportarCSV);

    document.getElementById('modalRecebimento').addEventListener('click', e => { if (e.target === e.currentTarget) fecharModalRec(); });
    document.getElementById('modalReceberPag').addEventListener('click',  e => { if (e.target === e.currentTarget) fecharModalReceber(); });

    // Upload zone
    const zone  = document.getElementById('uploadZoneReceber');
    const input = document.getElementById('inputNFReceber');
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--accent)'; });
    zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
    zone.addEventListener('drop', e => {
        e.preventDefault(); zone.style.borderColor = '';
        if (e.dataTransfer.files[0]) definirArquivo(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', () => { if (input.files[0]) definirArquivo(input.files[0]); });

    await carregarRecebimentos();
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    if (!dbClient) { setStatus('offline', 'Erro de conexão'); return; }

    const safe = async (query, campo = 'nome') => {
        try {
            const { data, error } = await query;
            if (error) { console.warn('[recebimentos] ref warning:', error.message); return []; }
            return (data || []).map(r => r[campo]);
        } catch (e) { console.warn('[recebimentos] ref error:', e.message); return []; }
    };

    [obras, etapas, formas] = await Promise.all([
        safe(dbClient.from('obras').select('nome').order('nome')),
        safe(dbClient.from('etapas').select('nome').order('nome')),
        safe(dbClient.from('formas_pagamento').select('nome').order('nome')),
    ]);

    popularSelect('filtroObra', obras, 'Todas as obras');
    popularSelect('rObra',  obras,  '—');
    popularSelect('rEtapa', etapas, '—');
    popularSelect('rForma', formas, '—');

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
        const opt = document.createElement('option');
        opt.value = opt.textContent = value;
        sel.appendChild(opt);
    }
    sel.value = value;
}

// --- CARREGAR ---
async function carregarRecebimentos() {
    if (!dbClient) return;
    document.getElementById('tabelaLoading').style.display = 'flex';

    try {
        const dataIni = document.getElementById('filtroDataIni').value;
        const dataFim = document.getElementById('filtroDataFim').value;
        const obra    = document.getElementById('filtroObra').value;
        const cliente = document.getElementById('filtroCliente').value.trim();
        const status  = document.getElementById('filtroStatus').value;

        // Recebidos saem da view 7 dias após o recebimento
        const limiteRecente = addDias(hoje(), -7);

        let q = dbClient
            .from('recebimentos')
            .select('*')
            .or(`recebido.eq.false,data_recebimento.gte.${limiteRecente}`)
            .order('vencimento', { ascending: true })
            .order('id',         { ascending: false });

        if (dataIni) q = q.gte('vencimento', dataIni);
        if (dataFim) q = q.lte('vencimento', dataFim);
        if (obra)    q = q.eq('obra', obra);
        if (cliente) q = q.ilike('cliente', `%${cliente}%`);

        if (status === 'recebido') q = q.eq('recebido', true);
        if (status === 'pendente') q = q.eq('recebido', false).gte('vencimento', hoje());
        if (status === 'vencido')  q = q.eq('recebido', false).lt('vencimento', hoje());

        const { data, error } = await q;
        if (error) throw error;

        todosRegistros = data || [];
        paginaAtual    = 1;
        renderizarTabela();
        atualizarKPIs();
    } catch (e) {
        console.error('[recebimentos] carregar:', e);
        toast.error('Erro ao carregar recebimentos: ' + e.message);
    } finally {
        document.getElementById('tabelaLoading').style.display = 'none';
    }
}

// --- FILTRO LOCAL ---
function filtrarRegistros() {
    const busca = document.getElementById('buscaTexto').value.trim().toLowerCase();
    if (!busca) return todosRegistros;
    return todosRegistros.filter(r =>
        (r.cliente   || '').toLowerCase().includes(busca) ||
        (r.descricao || '').toLowerCase().includes(busca)
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
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhum recebimento encontrado.</td></tr>`;
        paginacaoWrap.style.display = 'none';
        return;
    }

    tbody.innerHTML = pagina.map(r => {
        const sv    = statusVisual(r);
        const valor = r.valor != null ? formatarValor(r.valor) : '—';
        const venc  = formatarData(r.vencimento);

        const nfIcon = r.tem_comprovante && r.comprovante_url
            ? `<a href="${r.comprovante_url}" target="_blank" title="Ver comprovante" style="color:var(--secondary);">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
               </a>`
            : '—';

        let acoes = '';
        if (!r.recebido) {
            acoes += `<button class="btn btn-primary" onclick="abrirModalReceber(${r.id})"
                        style="font-size:0.72rem;padding:3px 8px;white-space:nowrap;background:var(--success);border-color:var(--success);">
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                              <polyline points="20 6 9 17 4 12"></polyline>
                          </svg>
                          Receber
                      </button> `;
        }
        acoes += `<button class="btn btn-outline" onclick="abrirModalRec(${r.id})"
                    style="font-size:0.72rem;padding:3px 8px;" title="Editar">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                  </button> `;
        acoes += `<button class="btn btn-outline" onclick="excluirRecebimento(${r.id})"
                    style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Excluir">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="3 6 5 6 21 6"></polyline>
                          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                      </svg>
                  </button>`;

        return `<tr>
            <td style="white-space:nowrap;font-weight:600;">${venc}</td>
            <td>${esc(r.obra || '—')}</td>
            <td>${esc(r.cliente || '—')}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(r.descricao)}">${esc(r.descricao || '—')}</td>
            <td>${esc(r.etapa || '—')}</td>
            <td class="text-right" style="font-weight:600;">R$ ${valor}</td>
            <td style="text-align:center;">${badgeStatus(sv)}</td>
            <td style="text-align:center;">${nfIcon}</td>
            <td style="text-align:center;white-space:nowrap;">${acoes}</td>
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
    const hj  = hoje();
    const em7 = addDias(hj, 7);
    const mes = hj.substring(0, 7);

    let totalPendente = 0, totalVencido = 0, countVencido = 0;
    let totalProximo  = 0, countProximo = 0, totalRecebido = 0;

    for (const r of todosRegistros) {
        const sv = statusVisual(r);
        const v  = Number(r.valor || 0);
        if (sv === 'pendente') {
            totalPendente += v;
            if (r.vencimento >= hj && r.vencimento <= em7) { totalProximo += v; countProximo++; }
        }
        if (sv === 'vencido') { totalVencido += v; countVencido++; }
        if (sv === 'recebido' && (r.data_recebimento || '').startsWith(mes)) totalRecebido += v;
    }

    document.getElementById('kpiPendente').textContent  = `R$ ${formatarValor(totalPendente)}`;
    document.getElementById('kpiVencido').textContent   = countVencido > 0 ? `${countVencido} · R$ ${formatarValor(totalVencido)}` : '—';
    document.getElementById('kpiProximo').textContent   = countProximo > 0 ? `${countProximo} · R$ ${formatarValor(totalProximo)}` : '—';
    document.getElementById('kpiRecebido').textContent  = totalRecebido > 0 ? `R$ ${formatarValor(totalRecebido)}` : '—';
}

// --- LIMPAR FILTROS ---
function limparFiltros() {
    ['filtroDataIni','filtroDataFim','filtroObra','filtroStatus'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('filtroCliente').value = '';
    document.getElementById('buscaTexto').value    = '';
    paginaAtual = 1;
    carregarRecebimentos();
}

// --- MODAL NOVO/EDITAR ---
function abrirModalRec(id) {
    editandoId = id;
    document.getElementById('modalRecTitulo').textContent = id ? 'Editar Recebimento' : 'Novo Recebimento';

    document.getElementById('rCliente').value    = '';
    document.getElementById('rValor').value      = '';
    document.getElementById('rVencimento').value = '';
    document.getElementById('rDescricao').value  = '';
    document.getElementById('rBanco').value      = '';
    document.getElementById('rRecebido').checked = false;
    ['rObra','rEtapa','rForma'].forEach(id => { document.getElementById(id).value = ''; });

    if (id) {
        const r = todosRegistros.find(x => x.id === id);
        if (r) {
            document.getElementById('rCliente').value    = r.cliente    || '';
            document.getElementById('rValor').value      = r.valor      || '';
            document.getElementById('rVencimento').value = r.vencimento || '';
            document.getElementById('rDescricao').value  = r.descricao  || '';
            document.getElementById('rBanco').value      = r.banco      || '';
            document.getElementById('rRecebido').checked = !!r.recebido;
            setSelectValue('rObra',  r.obra);
            setSelectValue('rEtapa', r.etapa);
            setSelectValue('rForma', r.forma);
        }
    }

    document.getElementById('modalRecebimento').style.display = 'flex';
}

function fecharModalRec() {
    document.getElementById('modalRecebimento').style.display = 'none';
    editandoId = null;
}

async function salvarRecebimento() {
    const cliente    = document.getElementById('rCliente').value.trim();
    const valor      = parseFloat(document.getElementById('rValor').value);
    const vencimento = document.getElementById('rVencimento').value;

    if (!cliente)               { toast.warning('Informe o cliente.'); return; }
    if (isNaN(valor) || valor <= 0) { toast.warning('Informe um valor válido.'); return; }
    if (!vencimento)            { toast.warning('Informe a data de vencimento.'); return; }

    const recebido = document.getElementById('rRecebido').checked;

    const payload = {
        cliente,
        valor:      Math.round(valor * 100) / 100,
        vencimento,
        obra:       document.getElementById('rObra').value    || null,
        etapa:      document.getElementById('rEtapa').value   || null,
        forma:      document.getElementById('rForma').value   || null,
        banco:      document.getElementById('rBanco').value.trim() || null,
        descricao:  document.getElementById('rDescricao').value.trim() || null,
        recebido,
    };

    if (recebido) {
        const r = editandoId ? todosRegistros.find(x => x.id === editandoId) : null;
        if (!r || !r.data_recebimento) payload.data_recebimento = hoje();
    }

    const btn = document.getElementById('btnSalvarRec');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        let result;
        if (editandoId) {
            result = await dbClient.from('recebimentos').update(payload).eq('id', editandoId).select().single();
        } else {
            result = await dbClient.from('recebimentos').insert(payload).select().single();
        }
        if (result.error) throw result.error;

        fecharModalRec();
        await carregarRecebimentos();
        toast.success(editandoId ? 'Recebimento atualizado.' : 'Recebimento cadastrado.');
    } catch (e) {
        toast.error('Erro ao salvar: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

// --- UPLOAD HELPER ---
async function uploadComprovante(file) {
    try {
        const ext  = file.name.split('.').pop().toLowerCase();
        const nome = `rec_${crypto.randomUUID().replace(/-/g,'').slice(0,12)}.${ext}`;
        const { error } = await dbClient.storage.from('comprovantes').upload(nome, file, { contentType: file.type });
        if (error) throw error;
        const base = window.ENV.SUPABASE_URL.replace(/\/$/, '');
        const url  = `${base}/storage/v1/object/public/comprovantes/${nome}`;
        return { url, nome };
    } catch (e) {
        toast.warning(`Comprovante não pôde ser salvo: ${e.message}`);
        return null;
    }
}

function definirArquivo(file) {
    document.getElementById('inputNFReceber')._file = file;
    document.getElementById('uploadZoneReceberText').textContent = `📎 ${file.name}`;
    document.getElementById('uploadZoneReceber').style.borderColor = 'var(--accent)';
}

// --- MODAL CONFIRMAR RECEBIMENTO ---
function abrirModalReceber(id) {
    recebendoId = id;
    const r = todosRegistros.find(x => x.id === id);
    if (!r) return;

    document.getElementById('modalReceberInfo').innerHTML =
        `<strong>${esc(r.cliente)}</strong><br>
         Vencimento: ${formatarData(r.vencimento)}<br>
         Valor: <strong>R$ ${formatarValor(r.valor)}</strong>
         ${r.descricao ? `<br>Descrição: ${esc(r.descricao)}` : ''}`;

    document.getElementById('rDataRecebimento').value = hoje();
    document.getElementById('uploadZoneReceberText').textContent = 'Clique ou arraste (PDF, JPG, PNG)';
    document.getElementById('uploadZoneReceber').style.borderColor = '';
    document.getElementById('inputNFReceber').value = '';
    document.getElementById('inputNFReceber')._file = null;

    document.getElementById('modalReceberPag').style.display = 'flex';
}

function fecharModalReceber() {
    document.getElementById('modalReceberPag').style.display = 'none';
    recebendoId = null;
}

async function confirmarRecebimento() {
    const dataRec = document.getElementById('rDataRecebimento').value;
    if (!dataRec) { toast.warning('Informe a data do recebimento.'); return; }

    const btn = document.getElementById('btnConfirmarReceber');
    btn.disabled = true; btn.textContent = 'Registrando…';

    try {
        const { error } = await dbClient
            .from('recebimentos')
            .update({ recebido: true, data_recebimento: dataRec })
            .eq('id', recebendoId);
        if (error) throw error;

        const file = document.getElementById('inputNFReceber')._file;
        if (file) {
            const resultado = await uploadComprovante(file);
            if (resultado) {
                await dbClient.from('recebimentos').update({
                    comprovante_url: resultado.url,
                    tem_comprovante: true,
                }).eq('id', recebendoId);
            }
        }

        fecharModalReceber();
        await carregarRecebimentos();
        toast.success('Recebimento confirmado.' + (file ? ' Comprovante anexado.' : ''));
    } catch (e) {
        toast.error('Erro ao registrar: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Confirmar Recebimento';
    }
}

// --- EXCLUIR ---
async function excluirRecebimento(id) {
    const r = todosRegistros.find(x => x.id === id);
    if (!r) return;
    const desc = r.cliente + (r.descricao ? ` — ${r.descricao}` : '');
    if (!confirm(`Excluir "${desc}"? Esta ação não pode ser desfeita.`)) return;

    try {
        const { error } = await dbClient.from('recebimentos').delete().eq('id', id);
        if (error) throw error;
        todosRegistros = todosRegistros.filter(x => x.id !== id);
        renderizarTabela();
        atualizarKPIs();
        toast.success('Recebimento excluído.');
    } catch (e) {
        toast.error('Erro ao excluir: ' + e.message);
    }
}

// --- EXPORT CSV ---
function exportarCSV() {
    const dados = filtrarRegistros();
    if (!dados.length) { toast.warning('Nenhum dado para exportar.'); return; }

    const cab  = ['Vencimento','Recebimento','Obra','Etapa','Cliente','Descrição','Valor','Forma','Status'];
    const rows = dados.map(r => [
        r.vencimento        || '',
        r.data_recebimento  || '',
        r.obra              || '',
        r.etapa             || '',
        r.cliente           || '',
        r.descricao         || '',
        r.valor             || 0,
        r.forma             || '',
        statusVisual(r),
    ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','));

    const csv  = [cab.join(','), ...rows].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `recebimentos_${hoje()}.csv`; a.click();
    URL.revokeObjectURL(url);
}
