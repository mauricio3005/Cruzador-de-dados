/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Contas a Pagar (app.js)
 * Fonte de dados: c_despesas WHERE vencimento IS NOT NULL
 */

// --- SUPABASE (via nav.js → window.db) ---
let dbClient;

// --- ESTADO ---
let obras        = [];
let etapas       = [];
let tipos        = [];
let categorias   = [];
let fornecedores = [];

let todosRegistros = [];
let paginaAtual    = 1;
const PAGE_SIZE    = 50;

let editandoId = null;
let pagandoId  = null;

function addDias(d, n) {
    const dt = new Date(d + 'T00:00:00');
    dt.setDate(dt.getDate() + n);
    return dt.toISOString().split('T')[0];
}

/**
 * Status visual calculado a partir de paga (bool) + vencimento (date).
 */
function statusVisual(r) {
    if (r.paga) return 'pago';
    if (r.vencimento < hoje()) return 'vencido';
    return 'pendente';
}

function badgeStatus(sv) {
    const cfg = {
        pago:     { cor: 'var(--success)',  bg: 'rgba(46,125,50,0.1)',  label: 'Pago'     },
        vencido:  { cor: 'var(--error)',    bg: 'rgba(186,26,26,0.1)', label: 'Vencido'  },
        pendente: { cor: 'var(--warning)',  bg: 'rgba(180,83,9,0.1)',  label: 'Pendente' },
    };
    const c = cfg[sv] || cfg.pendente;
    return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:0.7rem;font-weight:700;
            color:${c.cor};background:${c.bg};">${c.label}</span>`;
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    dbClient = window.db;
    await carregarReferencias();

    document.getElementById('btnFiltrar').addEventListener('click', () => { paginaAtual = 1; carregarContas(); });
    document.getElementById('btnLimparFiltro').addEventListener('click', limparFiltros);
    document.getElementById('buscaTexto').addEventListener('input', renderizarTabela);

    document.getElementById('btnPagAnterior').addEventListener('click', () => { if (paginaAtual > 1) { paginaAtual--; renderizarTabela(); } });
    document.getElementById('btnPagProxima').addEventListener('click', () => {
        if (paginaAtual * PAGE_SIZE < filtrarRegistros().length) { paginaAtual++; renderizarTabela(); }
    });

    document.getElementById('btnNovaConta').addEventListener('click', () => abrirModalConta(null));
    document.getElementById('btnSalvarConta').addEventListener('click', salvarConta);
    document.getElementById('btnConfirmarPagar').addEventListener('click', confirmarPagamento);
    document.getElementById('btnExportarCSV').addEventListener('click', exportarCSV);

    document.getElementById('modalConta').addEventListener('click', e => { if (e.target === e.currentTarget) fecharModalConta(); });
    document.getElementById('modalPagar').addEventListener('click', e => { if (e.target === e.currentTarget) fecharModalPagar(); });

    // Upload zone no modal pagar
    const uploadZonePagar = document.getElementById('uploadZonePagar');
    const inputNFPagar    = document.getElementById('inputNFPagar');
    uploadZonePagar.addEventListener('click', () => inputNFPagar.click());
    uploadZonePagar.addEventListener('dragover', e => { e.preventDefault(); uploadZonePagar.style.borderColor = 'var(--accent)'; });
    uploadZonePagar.addEventListener('dragleave', () => { uploadZonePagar.style.borderColor = ''; });
    uploadZonePagar.addEventListener('drop', e => {
        e.preventDefault();
        uploadZonePagar.style.borderColor = '';
        if (e.dataTransfer.files[0]) definirArquivoPagamento(e.dataTransfer.files[0]);
    });
    inputNFPagar.addEventListener('change', () => { if (inputNFPagar.files[0]) definirArquivoPagamento(inputNFPagar.files[0]); });

    await carregarContas();
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    if (!dbClient) { setStatus('offline', 'Erro de conexão'); return; }

    const safe = async (query, campo = 'nome') => {
        try {
            const { data, error } = await query;
            if (error) { console.warn('[contas] ref warning:', error.message); return []; }
            return (data || []).map(r => r[campo]);
        } catch (e) { console.warn('[contas] ref error:', e.message); return []; }
    };

    [obras, etapas, tipos, categorias, fornecedores] = await Promise.all([
        safe(dbClient.from('obras').select('nome').order('nome')),
        safe(dbClient.from('etapas').select('nome').order('nome')),
        safe(dbClient.from('tipos_custo').select('nome').order('nome')),
        safe(dbClient.from('categorias_despesa').select('nome').order('nome')),
        safe(dbClient.from('fornecedores').select('nome').order('nome')),
    ]);

    // Filtros
    popularSelect('filtroObra',       obras,        'Todas as obras');
    popularSelect('filtroFornecedor', fornecedores, 'Todos');

    // Modal
    popularSelect('cObra',       obras,        '—');
    popularSelect('cEtapa',      etapas,       '—');
    popularSelect('cTipo',       tipos,        '—');
    popularSelect('cDespesa',    categorias,   '—');
    popularSelect('cFornecedor', fornecedores, 'Selecione...', false);

    setStatus('online', 'Sistema Sincronizado');
}

/** Seta o valor de um <select>. Se o valor não existir nas opções, adiciona temporariamente. */
function setSelectValue(id, value) {
    const sel = document.getElementById(id);
    if (!sel) return;
    if (!value) { sel.value = ''; return; }
    if (!Array.from(sel.options).some(o => o.value === value)) {
        const opt = document.createElement('option');
        opt.value = opt.textContent = value;
        sel.appendChild(opt);
    }
    sel.value = value;
}

function popularSelect(id, opcoes, placeholder, opcional = true) {
    const sel = document.getElementById(id);
    if (!sel) return;
    const first = opcional
        ? `<option value="">${placeholder}</option>`
        : `<option value="" disabled selected>${placeholder}</option>`;
    sel.innerHTML = first + opcoes.map(o => `<option value="${o}">${o}</option>`).join('');
}

// --- CARREGAR CONTAS ---
// Lê de c_despesas filtrando apenas registros com vencimento preenchido
async function carregarContas() {
    if (!dbClient) return;
    document.getElementById('tabelaLoading').style.display = 'flex';

    try {
        const dataIni    = document.getElementById('filtroDataIni').value;
        const dataFim    = document.getElementById('filtroDataFim').value;
        const obra       = document.getElementById('filtroObra').value;
        const fornecedor = document.getElementById('filtroFornecedor').value;
        const status     = document.getElementById('filtroStatus').value;

        // Pagas saem da view 7 dias após o pagamento
        const limiteRecente = addDias(hoje(), -7);

        let q = dbClient
            .from('c_despesas')
            .select('*')
            .not('vencimento', 'is', null)
            .or(`paga.eq.false,data_pagamento.gte.${limiteRecente}`)
            .order('vencimento', { ascending: true })
            .order('id',         { ascending: false });

        if (dataIni)    q = q.gte('vencimento', dataIni);
        if (dataFim)    q = q.lte('vencimento', dataFim);
        if (obra)       q = q.eq('obra', obra);
        if (fornecedor) q = q.eq('fornecedor', fornecedor);

        if (status === 'pago')     q = q.eq('paga', true);
        if (status === 'pendente') q = q.eq('paga', false).gte('vencimento', hoje());
        if (status === 'vencido')  q = q.eq('paga', false).lt('vencimento', hoje());

        const { data, error } = await q;
        if (error) throw error;

        todosRegistros = data || [];
        paginaAtual    = 1;
        renderizarTabela();
        atualizarKPIs();
    } catch (e) {
        console.error('[contas] carregarContas:', e);
        toast.error('Erro ao carregar contas: ' + e.message);
    } finally {
        document.getElementById('tabelaLoading').style.display = 'none';
    }
}

// --- FILTRO LOCAL (busca) ---
function filtrarRegistros() {
    const busca = document.getElementById('buscaTexto').value.trim().toLowerCase();
    if (!busca) return todosRegistros;
    return todosRegistros.filter(r =>
        (r.fornecedor || '').toLowerCase().includes(busca) ||
        (r.descricao  || '').toLowerCase().includes(busca)
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
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhuma conta encontrada.</td></tr>`;
        paginacaoWrap.style.display = 'none';
        return;
    }

    tbody.innerHTML = pagina.map(r => {
        const sv    = statusVisual(r);
        const valor = r.valor_total != null ? formatarValor(r.valor_total) : '—';
        const venc  = formatarData(r.vencimento);

        let acoes = '';
        if (!r.paga) {
            acoes += `<button class="btn btn-primary" onclick="abrirModalPagar(${r.id})"
                        style="font-size:0.72rem;padding:3px 8px;white-space:nowrap;">
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                              <polyline points="20 6 9 17 4 12"></polyline>
                          </svg>
                          Pagar
                      </button> `;
        }
        acoes += `<button class="btn btn-outline" onclick="abrirModalConta(${r.id})"
                    style="font-size:0.72rem;padding:3px 8px;" title="Editar">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                  </button> `;
        acoes += `<button class="btn btn-outline" onclick="excluirConta(${r.id})"
                    style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Excluir">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="3 6 5 6 21 6"></polyline>
                          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                      </svg>
                  </button>`;

        return `<tr>
            <td style="white-space:nowrap;font-weight:600;">${venc}</td>
            <td>${esc(r.obra || '—')}</td>
            <td>${esc(r.fornecedor || '—')}</td>
            <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(r.descricao)}">${esc(r.descricao || '—')}</td>
            <td>${esc(r.tipo || '—')}</td>
            <td>${esc(r.despesa || '—')}</td>
            <td class="text-right" style="font-weight:600;">R$ ${valor}</td>
            <td style="text-align:center;">${badgeStatus(sv)}</td>
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
    let totalProximo  = 0, countProximo = 0, totalPago = 0;

    for (const r of todosRegistros) {
        const sv = statusVisual(r);
        const v  = Number(r.valor_total || 0);
        if (sv === 'pendente') {
            totalPendente += v;
            if (r.vencimento >= hj && r.vencimento <= em7) { totalProximo += v; countProximo++; }
        }
        if (sv === 'vencido')  { totalVencido += v; countVencido++; }
        if (sv === 'pago' && (r.data_pagamento || '').startsWith(mes)) totalPago += v;
    }

    document.getElementById('kpiPendente').textContent = `R$ ${formatarValor(totalPendente)}`;
    document.getElementById('kpiVencido').textContent  = countVencido > 0 ? `${countVencido} · R$ ${formatarValor(totalVencido)}` : '—';
    document.getElementById('kpiProximo').textContent  = countProximo > 0 ? `${countProximo} · R$ ${formatarValor(totalProximo)}` : '—';
    document.getElementById('kpiPago').textContent     = totalPago > 0 ? `R$ ${formatarValor(totalPago)}` : '—';
}

// --- LIMPAR FILTROS ---
function limparFiltros() {
    ['filtroDataIni','filtroDataFim','filtroObra','filtroFornecedor','filtroStatus'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('buscaTexto').value = '';
    paginaAtual = 1;
    carregarContas();
}

// --- MODAL NOVA/EDITAR CONTA ---
function abrirModalConta(id) {
    editandoId = id;
    document.getElementById('modalContaTitulo').textContent = id ? 'Editar Conta' : 'Nova Conta a Pagar';

    // Limpa selects
    ['cFornecedor','cObra','cEtapa','cTipo','cDespesa'].forEach(sel => {
        document.getElementById(sel).value = '';
    });
    document.getElementById('cValor').value      = '';
    document.getElementById('cVencimento').value = '';
    document.getElementById('cDescricao').value  = '';
    document.getElementById('cPaga').checked     = false;

    if (id) {
        const r = todosRegistros.find(x => x.id === id);
        if (r) {
            setSelectValue('cFornecedor', r.fornecedor);
            setSelectValue('cObra',       r.obra);
            setSelectValue('cEtapa',      r.etapa);
            setSelectValue('cTipo',       r.tipo);
            setSelectValue('cDespesa',    r.despesa);
            document.getElementById('cValor').value      = r.valor_total  || '';
            document.getElementById('cVencimento').value = r.vencimento   || '';
            document.getElementById('cDescricao').value  = r.descricao    || '';
            document.getElementById('cPaga').checked     = !!r.paga;
        }
    }

    document.getElementById('modalConta').style.display = 'flex';
}

function fecharModalConta() {
    document.getElementById('modalConta').style.display = 'none';
    editandoId = null;
}

async function salvarConta() {
    const fornecedor = document.getElementById('cFornecedor').value;
    const valor      = parseFloat(document.getElementById('cValor').value);
    const vencimento = document.getElementById('cVencimento').value;

    if (!fornecedor)                { toast.warning('Selecione um fornecedor.'); return; }
    if (isNaN(valor) || valor <= 0) { toast.warning('Informe um valor válido.'); return; }
    if (!vencimento)                { toast.warning('Informe a data de vencimento.'); return; }

    const paga = document.getElementById('cPaga').checked;

    const payload = {
        fornecedor,
        valor_total: Math.round(valor * 100) / 100,
        vencimento,
        data:        vencimento,                                      // c_despesas exige data
        obra:        document.getElementById('cObra').value    || null,
        etapa:       document.getElementById('cEtapa').value   || null,
        tipo:        document.getElementById('cTipo').value    || null,
        despesa:     document.getElementById('cDespesa').value || null,
        descricao:   document.getElementById('cDescricao').value.trim() || null,
        paga,
    };

    if (paga) {
        const r = editandoId ? todosRegistros.find(x => x.id === editandoId) : null;
        if (!r || !r.data_pagamento) payload.data_pagamento = hoje();
    }

    const btn = document.getElementById('btnSalvarConta');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        let result;
        if (editandoId) {
            result = await dbClient.from('c_despesas').update(payload).eq('id', editandoId).select().single();
        } else {
            result = await dbClient.from('c_despesas').insert(payload).select().single();
        }
        if (result.error) throw result.error;

        fecharModalConta();
        await carregarContas();
        toast.success(editandoId ? 'Conta atualizada.' : 'Conta cadastrada.');
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
        const nome = `nf_${crypto.randomUUID().replace(/-/g,'').slice(0,12)}.${ext}`;
        const { error } = await dbClient.storage.from('comprovantes').upload(nome, file, { contentType: file.type });
        if (error) throw error;
        const base = window.ENV.SUPABASE_URL.replace(/\/$/, '');
        const url  = `${base}/storage/v1/object/public/comprovantes/${nome}`;
        return { url, nome };
    } catch (e) {
        toast.warning(`NF não pôde ser salva: ${e.message}`);
        return null;
    }
}

function definirArquivoPagamento(file) {
    document.getElementById('inputNFPagar')._file = file;
    document.getElementById('uploadZonePagarText').textContent = `📎 ${file.name}`;
    document.getElementById('uploadZonePagar').style.borderColor = 'var(--accent)';
}

// --- MODAL REGISTRAR PAGAMENTO ---
function abrirModalPagar(id) {
    pagandoId = id;
    const r   = todosRegistros.find(x => x.id === id);
    if (!r) return;

    document.getElementById('modalPagarInfo').innerHTML =
        `<strong>${esc(r.fornecedor)}</strong><br>
         Vencimento: ${formatarData(r.vencimento)}<br>
         Valor: <strong>R$ ${formatarValor(r.valor_total)}</strong>
         ${r.descricao ? `<br>Descrição: ${esc(r.descricao)}` : ''}`;

    document.getElementById('pDataPagamento').value = hoje();
    // Resetar upload
    document.getElementById('uploadZonePagarText').textContent = 'Clique ou arraste (PDF, JPG, PNG)';
    document.getElementById('uploadZonePagar').style.borderColor = '';
    document.getElementById('inputNFPagar').value = '';
    document.getElementById('inputNFPagar')._file = null;

    document.getElementById('modalPagar').style.display = 'flex';
}

function fecharModalPagar() {
    document.getElementById('modalPagar').style.display = 'none';
    pagandoId = null;
}

async function confirmarPagamento() {
    const dataPag = document.getElementById('pDataPagamento').value;
    if (!dataPag) { toast.warning('Informe a data do pagamento.'); return; }

    const btn = document.getElementById('btnConfirmarPagar');
    btn.disabled = true; btn.textContent = 'Registrando…';

    try {
        // 1. Registrar pagamento — atualiza data para data_pagamento
        //    para que o registro apareça no histórico pelo dia correto
        const { error } = await dbClient
            .from('c_despesas')
            .update({ paga: true, data_pagamento: dataPag, data: dataPag })
            .eq('id', pagandoId);
        if (error) throw error;

        // 2. Upload NF (opcional)
        const file = document.getElementById('inputNFPagar')._file;
        if (file) {
            const resultado = await uploadComprovante(file);
            if (resultado) {
                const { url, nome } = resultado;
                await dbClient.from('comprovantes_despesa').insert({ despesa_id: pagandoId, url, nome_arquivo: nome });
                await dbClient.from('c_despesas').update({ tem_nota_fiscal: true }).eq('id', pagandoId);
            }
        }

        fecharModalPagar();
        await carregarContas();
        toast.success('Pagamento registrado.' + (file ? ' NF anexada.' : ''));
    } catch (e) {
        toast.error('Erro ao registrar: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Confirmar Pagamento';
    }
}

// --- EXCLUIR ---
async function excluirConta(id) {
    const r = todosRegistros.find(x => x.id === id);
    if (!r) return;
    const desc = r.fornecedor + (r.descricao ? ` — ${r.descricao}` : '');
    if (!confirm(`Excluir conta "${desc}"? Esta ação não pode ser desfeita.`)) return;

    try {
        const { error } = await dbClient.from('c_despesas').delete().eq('id', id);
        if (error) throw error;
        todosRegistros = todosRegistros.filter(x => x.id !== id);
        renderizarTabela();
        atualizarKPIs();
        toast.success('Conta excluída.');
    } catch (e) {
        toast.error('Erro ao excluir: ' + e.message);
    }
}

// --- EXPORT CSV ---
function exportarCSV() {
    const dados = filtrarRegistros();
    if (!dados.length) { toast.warning('Nenhum dado para exportar.'); return; }

    const cab  = ['Vencimento','Pagamento','Obra','Etapa','Fornecedor','Descrição','Tipo','Categoria','Valor','Status'];
    const rows = dados.map(r => [
        r.vencimento       || '',
        r.data_pagamento   || '',
        r.obra             || '',
        r.etapa            || '',
        r.fornecedor       || '',
        r.descricao        || '',
        r.tipo             || '',
        r.despesa          || '',
        r.valor_total      || 0,
        statusVisual(r),
    ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','));

    const csv  = [cab.join(','), ...rows].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `contas_pagar_${hoje()}.csv`; a.click();
    URL.revokeObjectURL(url);
}
