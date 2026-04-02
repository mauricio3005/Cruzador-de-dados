/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Histórico de Despesas (app.js)
 */

const API_BASE = `http://${location.hostname}:8000`;
const PAGE_SIZE = 50;

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
let etapas       = [];
let tipos        = [];
let categorias   = [];
let formas       = [];
let fornecedores = [];

let todosRegistros = [];   // resultado completo do filtro atual
let paginaAtual    = 1;
let selecionados   = new Set(); // IDs selecionados para vincular comprovante

// --- REALTIME ---
let _realtimeDebounce = null;

function iniciarRealtime() {
    if (!dbClient) return;
    dbClient
        .channel('historico-despesas')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'c_despesas' }, () => {
            // Não recarrega enquanto o modal de edição estiver aberto
            const modalAberto = document.getElementById('modalEditar').style.display === 'flex';
            if (modalAberto) return;

            clearTimeout(_realtimeDebounce);
            _realtimeDebounce = setTimeout(() => {
                carregarHistorico();
                setStatus('online', 'Atualizado agora');
                setTimeout(() => setStatus('online', 'Sistema Sincronizado'), 3000);
            }, 800);
        })
        .subscribe();
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    carregarEnv();
    await carregarReferencias();

    // Datas padrão: início de 2025 até hoje
    const hoje = new Date();
    const ini  = new Date('2025-01-01');
    document.getElementById('filtroDataIni').value = ini.toISOString().split('T')[0];
    document.getElementById('filtroDataFim').value = hoje.toISOString().split('T')[0];

    document.getElementById('btnFiltrar').addEventListener('click', () => { paginaAtual = 1; carregarHistorico(); });
    document.getElementById('btnLimparFiltro').addEventListener('click', limparFiltros);
    document.getElementById('filtroObra').addEventListener('change', e => filtrarEtapasPorObra(e.target.value));
    document.getElementById('btnAtualizar').addEventListener('click', () => { paginaAtual = 1; carregarHistorico(); });
    document.getElementById('btnExportarCSV').addEventListener('click', exportarCSV);
    document.getElementById('buscaTexto').addEventListener('input', () => { paginaAtual = 1; renderizarTabela(); });

    document.getElementById('btnPagAnterior').addEventListener('click', () => { if (paginaAtual > 1) { paginaAtual--; renderizarTabela(); } });
    document.getElementById('btnPagProxima').addEventListener('click',  () => { if (paginaAtual * PAGE_SIZE < todosRegistros.length) { paginaAtual++; renderizarTabela(); } });

    // Modal: fornecedor toggle
    document.getElementById('editNovoFornecedorCheck').addEventListener('change', e => {
        const isNovo = e.target.checked;
        document.getElementById('editFornecedor').style.display    = isNovo ? 'none' : '';
        document.getElementById('editNovoFornecedor').style.display = isNovo ? '' : 'none';
    });

    document.getElementById('btnSalvarEdicao').addEventListener('click', salvarEdicao);
    document.getElementById('btnDeletarModal').addEventListener('click', deletarDespesa);

    // Filtrar ao carregar e iniciar escuta em tempo real
    carregarHistorico();
    iniciarRealtime();
});

window.addEventListener('jarvis:data-changed', (e) => {
    if (e.detail?.tabela === 'c_despesas') {
        paginaAtual = 1;
        carregarHistorico();
    }
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    if (!dbClient) return;
    try {
        const [rObras, rEtapas, rTipos, rCat, rFormas, rForn] = await Promise.all([
            dbClient.from('obras').select('nome').order('nome'),
            dbClient.from('etapas').select('nome, ordem').order('ordem'),
            dbClient.from('tipos_custo').select('nome').order('nome'),
            dbClient.from('categorias_despesa').select('nome').order('nome'),
            dbClient.from('formas_pagamento').select('nome').order('nome'),
            dbClient.from('fornecedores').select('nome').order('nome'),
        ]);

        obras        = (rObras.data  || []).map(r => r.nome);
        etapas       = (rEtapas.data || []).map(r => r.nome);
        tipos        = (rTipos.data  || []).map(r => r.nome);
        categorias   = (rCat.data    || []).map(r => r.nome);
        formas       = (rFormas.data || []).map(r => r.nome);
        fornecedores = (rForn.data   || []).map(r => r.nome);

        popularSelect('filtroObra',       obras,      'Todas as obras');
        popularSelect('filtroEtapa',      etapas,     'Todas as etapas');
        popularSelect('filtroTipo',       tipos,      'Todos os tipos');
        popularSelect('filtroCategoria',  categorias, 'Todas as categorias');

        popularSelectModal('editObra',    obras,      'Selecione...');
        popularSelectModal('editEtapa',   etapas,     'Selecione...');
        popularSelectModal('editTipo',    tipos,      'Selecione...');
        popularSelectModal('editDespesa', categorias, '—');
        popularSelectModal('editForma',   formas,     '—');
        popularFornecedorModal();

        setStatus('online', 'Sistema Sincronizado');
    } catch (e) {
        setStatus('offline', 'Erro de conexão');
    }
}

function popularSelect(id, opcoes, placeholder) {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = `<option value="">${placeholder}</option>` +
        opcoes.map(o => `<option value="${o}">${o}</option>`).join('');
}

function popularSelectModal(id, opcoes, placeholder) {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = `<option value="">${placeholder}</option>` +
        opcoes.map(o => `<option value="${o}">${o}</option>`).join('');
}

async function filtrarEtapasPorObra(obra) {
    const el = document.getElementById('filtroEtapa');
    if (!obra) { popularSelect('filtroEtapa', etapas, 'Todas as etapas'); el.value = ''; return; }
    const { data } = await dbClient.from('obra_etapas').select('etapa').eq('obra', obra);
    const nomes = (data || []).map(r => r.etapa);
    popularSelect('filtroEtapa', nomes, 'Todas as etapas');
    if (!nomes.includes(el.value)) el.value = '';
}

function popularFornecedorModal() {
    const sel = document.getElementById('editFornecedor');
    if (!sel) return;
    sel.innerHTML = `<option value="">Selecione...</option>` +
        fornecedores.map(f => `<option value="${f}">${f}</option>`).join('');
}

// --- CARREGAR HISTÓRICO ---
async function carregarHistorico() {
    if (!dbClient) return;

    const dataIni    = document.getElementById('filtroDataIni').value;
    const dataFim    = document.getElementById('filtroDataFim').value;
    const obra       = document.getElementById('filtroObra').value;
    const etapa      = document.getElementById('filtroEtapa').value;
    const tipo       = document.getElementById('filtroTipo').value;
    const categoria  = document.getElementById('filtroCategoria').value;
    const fornecedor = document.getElementById('filtroFornecedor').value.trim();
    const descricao  = document.getElementById('filtroDescricao').value.trim();
    const banco      = document.getElementById('filtroBanco').value.trim();

    document.getElementById('tabelaLoading').style.display = 'flex';

    try {
        let q = dbClient
            .from('c_despesas')
            .select('id,data,obra,etapa,tipo,fornecedor,descricao,despesa,forma,banco,valor_total,tem_nota_fiscal,comprovante_url')
            .or('vencimento.is.null,paga.eq.true')   // exclui contas a pagar não pagas
            .order('data', { ascending: false })
            .order('id',   { ascending: false });

        if (dataIni)   q = q.gte('data', dataIni);
        if (dataFim)   q = q.lte('data', dataFim);
        if (obra)      q = q.eq('obra', obra);
        if (etapa)     q = q.eq('etapa', etapa);
        if (tipo)       q = q.eq('tipo', tipo);
        if (categoria)  q = q.eq('despesa', categoria);
        if (fornecedor) q = q.ilike('fornecedor', `%${fornecedor}%`);
        if (descricao)  q = q.ilike('descricao',  `%${descricao}%`);
        if (banco)      q = q.ilike('banco',      `%${banco}%`);

        const { data, error } = await q;
        if (error) throw error;

        todosRegistros = data || [];
        paginaAtual    = 1;
        renderizarTabela();
        atualizarSumario();
        setStatus('online', 'Sistema Sincronizado');
    } catch (e) {
        setStatus('offline', 'Erro ao carregar');
        toast.error(`Erro: ${e.message}`);
    } finally {
        document.getElementById('tabelaLoading').style.display = 'none';
    }
}

// --- RENDERIZAR TABELA ---
function renderizarTabela() {
    const busca = document.getElementById('buscaTexto').value.trim().toLowerCase();

    const filtrado = busca
        ? todosRegistros.filter(r =>
            (r.fornecedor || '').toLowerCase().includes(busca) ||
            (r.descricao  || '').toLowerCase().includes(busca)
          )
        : todosRegistros;

    const totalFiltrado = filtrado.length;
    const inicio = (paginaAtual - 1) * PAGE_SIZE;
    const pagina = filtrado.slice(inicio, inicio + PAGE_SIZE);

    const tbody = document.getElementById('tabelaBody');

    if (pagina.length === 0) {
        tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhum registro encontrado.</td></tr>`;
        document.getElementById('paginacaoWrap').style.display = 'none';
        atualizarBarraSelecao();
        return;
    }

    tbody.innerHTML = pagina.map(r => {
        const data       = r.data ? formatarData(r.data) : '—';
        const valor      = r.valor_total != null ? formatarValor(r.valor_total) : '—';
        const sel        = selecionados.has(r.id);
        const nfIcon     = r.tem_nota_fiscal && r.comprovante_url
            ? `<a href="${r.comprovante_url}" target="_blank" title="Ver comprovante" style="color:var(--secondary);">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
               </a>`
            : r.tem_nota_fiscal
                ? `<span title="NF sem link direto" style="color:var(--on-surface-muted);">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                   </span>`
                : '—';

        return `<tr class="${sel ? 'row-selecionada' : ''}">
            <td style="text-align:center;width:36px;">
                <input type="checkbox" class="chk-selecao" data-id="${r.id}" ${sel ? 'checked' : ''}
                    onchange="toggleSelecao(${r.id})" style="cursor:pointer;width:14px;height:14px;">
            </td>
            <td style="white-space:nowrap;">${data}</td>
            <td>${esc(r.obra)}</td>
            <td>${esc(r.etapa)}</td>
            <td>${esc(r.tipo)}</td>
            <td>${esc(r.fornecedor)}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(r.descricao)}">${esc(r.descricao)}</td>
            <td>${esc(r.despesa)}</td>
            <td>${esc(r.forma)}</td>
            <td>${esc(r.banco || '—')}</td>
            <td class="text-right" style="font-variant-numeric:tabular-nums;">${valor}</td>
            <td style="text-align:center;">${nfIcon}</td>
            <td>
                <button class="btn-icon-sm" onclick="abrirModalEditar(${r.id})" title="Editar">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
            </td>
        </tr>`;
    }).join('');

    atualizarBarraSelecao();

    // Paginação
    const totalPaginas = Math.ceil(totalFiltrado / PAGE_SIZE);
    const paginacaoWrap = document.getElementById('paginacaoWrap');
    if (totalPaginas > 1) {
        paginacaoWrap.style.display = 'flex';
        document.getElementById('paginacaoInfo').textContent =
            `Página ${paginaAtual} de ${totalPaginas} — ${totalFiltrado} registros`;
        document.getElementById('btnPagAnterior').disabled = paginaAtual === 1;
        document.getElementById('btnPagProxima').disabled  = paginaAtual === totalPaginas;
    } else {
        paginacaoWrap.style.display = 'none';
    }
}

// --- SUMÁRIO ---
function atualizarSumario() {
    const total       = todosRegistros.reduce((s, r) => s + (r.valor_total || 0), 0);
    const comNF       = todosRegistros.filter(r => r.tem_nota_fiscal).length;
    const fornUnicos  = new Set(todosRegistros.map(r => r.fornecedor).filter(Boolean)).size;

    document.getElementById('sumRegistros').textContent   = todosRegistros.length.toLocaleString('pt-BR');
    document.getElementById('sumTotal').textContent       = formatarValor(total);
    document.getElementById('sumComNF').textContent       = comNF.toLocaleString('pt-BR');
    document.getElementById('sumFornecedores').textContent = fornUnicos.toLocaleString('pt-BR');
}

// --- FILTROS ---
function limparFiltros() {
    const hoje = new Date();
    const ini  = new Date(hoje);
    ini.setDate(ini.getDate() - 90);
    document.getElementById('filtroDataIni').value = ini.toISOString().split('T')[0];
    document.getElementById('filtroDataFim').value = hoje.toISOString().split('T')[0];
    document.getElementById('filtroObra').value       = '';
    document.getElementById('filtroEtapa').value      = '';
    document.getElementById('filtroTipo').value       = '';
    document.getElementById('filtroCategoria').value  = '';
    document.getElementById('filtroFornecedor').value = '';
    document.getElementById('filtroDescricao').value  = '';
    document.getElementById('filtroBanco').value      = '';
    document.getElementById('buscaTexto').value       = '';
    paginaAtual = 1;
    carregarHistorico();
}

// --- MODAL EDITAR ---
function abrirModalEditar(id) {
    const r = todosRegistros.find(x => x.id === id);
    if (!r) return;

    document.getElementById('editId').value          = id;
    document.getElementById('editObra').value         = r.obra    || '';
    document.getElementById('editEtapa').value        = r.etapa   || '';
    document.getElementById('editTipo').value         = r.tipo    || '';
    document.getElementById('editValor').value        = r.valor_total != null ? r.valor_total : '';
    document.getElementById('editData').value         = r.data    || '';
    document.getElementById('editDescricao').value    = r.descricao || '';
    document.getElementById('editDespesa').value      = r.despesa  || '';
    document.getElementById('editForma').value        = r.forma   || '';
    document.getElementById('editBanco').value        = r.banco   || '';

    // Fornecedor
    const match = fornecedores.find(f => f === r.fornecedor);
    const isNovo = r.fornecedor && !match;
    document.getElementById('editNovoFornecedorCheck').checked    = isNovo;
    document.getElementById('editFornecedor').style.display        = isNovo ? 'none' : '';
    document.getElementById('editNovoFornecedor').style.display    = isNovo ? '' : 'none';
    document.getElementById('editFornecedor').value                = match || '';
    document.getElementById('editNovoFornecedor').value            = isNovo ? r.fornecedor : '';

    document.getElementById('modalEditar').style.display = 'flex';
}

function fecharModal() {
    document.getElementById('modalEditar').style.display = 'none';
}

// Fecha modal ao clicar fora
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('modalEditar').addEventListener('click', e => {
        if (e.target === document.getElementById('modalEditar')) fecharModal();
    });
});

async function salvarEdicao() {
    const id         = parseInt(document.getElementById('editId').value);
    const obra       = document.getElementById('editObra').value;
    const etapa      = document.getElementById('editEtapa').value;
    const tipo       = document.getElementById('editTipo').value;
    const isNovo     = document.getElementById('editNovoFornecedorCheck').checked;
    const fornecedor = isNovo
        ? document.getElementById('editNovoFornecedor').value.trim()
        : document.getElementById('editFornecedor').value;
    const valor      = parseFloat(document.getElementById('editValor').value);
    const data       = document.getElementById('editData').value;
    const descricao  = document.getElementById('editDescricao').value.trim();
    const despesa    = document.getElementById('editDespesa').value;
    const forma      = document.getElementById('editForma').value;
    const banco      = document.getElementById('editBanco').value.trim();

    const erros = [];
    if (!obra)              erros.push('Obra é obrigatória.');
    if (!etapa)             erros.push('Etapa é obrigatória.');
    if (!tipo)              erros.push('Tipo é obrigatório.');
    if (!fornecedor)        erros.push('Fornecedor é obrigatório.');
    if (!valor || valor<=0) erros.push('Valor deve ser maior que zero.');
    if (!data)              erros.push('Data é obrigatória.');
    if (!descricao)         erros.push('Descrição é obrigatória.');
    if (erros.length) { erros.forEach(e => toast.error(e)); return; }

    const btn = document.getElementById('btnSalvarEdicao');
    btn.disabled = true;

    try {
        // Upsert fornecedor se novo
        if (isNovo && fornecedor) {
            await dbClient.from('fornecedores').upsert({ nome: fornecedor }, { onConflict: 'nome' });
            if (!fornecedores.includes(fornecedor)) {
                fornecedores.push(fornecedor);
                popularFornecedorModal();
            }
        }

        const { error } = await dbClient.from('c_despesas').update({
            obra, etapa, tipo, fornecedor: fornecedor || null,
            valor_total: valor, data, descricao: descricao || null,
            despesa: despesa || null, forma: forma || null, banco: banco || null,
        }).eq('id', id);

        if (error) throw error;

        // Atualiza registro local
        const idx = todosRegistros.findIndex(x => x.id === id);
        if (idx !== -1) {
            todosRegistros[idx] = { ...todosRegistros[idx], obra, etapa, tipo, fornecedor, valor_total: valor, data, descricao, despesa, forma, banco };
        }

        fecharModal();
        renderizarTabela();
        atualizarSumario();
        toast.success('Despesa atualizada com sucesso!');
    } catch (e) {
        toast.error(`Erro ao salvar: ${e.message}`);
    } finally {
        btn.disabled = false;
    }
}

async function deletarDespesa() {
    const id = parseInt(document.getElementById('editId').value);
    if (!confirm('Excluir esta despesa permanentemente?')) return;

    try {
        const { error } = await dbClient.from('c_despesas').delete().eq('id', id);
        if (error) throw error;

        todosRegistros = todosRegistros.filter(x => x.id !== id);
        fecharModal();
        renderizarTabela();
        atualizarSumario();
        toast.success('Despesa excluída.');
    } catch (e) {
        toast.error(`Erro ao excluir: ${e.message}`);
    }
}

// --- EXPORT CSV ---
function exportarCSV() {
    if (!todosRegistros.length) { toast.warning('Nenhum dado para exportar.'); return; }

    const busca = document.getElementById('buscaTexto').value.trim().toLowerCase();
    const dados = busca
        ? todosRegistros.filter(r =>
            (r.fornecedor || '').toLowerCase().includes(busca) ||
            (r.descricao  || '').toLowerCase().includes(busca)
          )
        : todosRegistros;

    const cabecalho = ['Data','Obra','Etapa','Tipo','Fornecedor','Descrição','Categoria','Forma','Banco','Valor Total','Tem NF'];
    const linhas = dados.map(r => [
        r.data || '', r.obra || '', r.etapa || '', r.tipo || '',
        r.fornecedor || '', (r.descricao || '').replace(/"/g,'""'),
        r.despesa || '', r.forma || '', r.banco || '',
        r.valor_total != null ? r.valor_total.toFixed(2).replace('.',',') : '',
        r.tem_nota_fiscal ? 'Sim' : 'Não',
    ].map(v => `"${v}"`).join(';'));

    const csv  = [cabecalho.join(';'), ...linhas].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `historico_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// --- HELPERS ---
function formatarData(iso) {
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
}

function formatarValor(v) {
    return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function esc(v) {
    if (v == null) return '—';
    return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function setStatus(type, text) {
    const el = document.getElementById('connectionStatus');
    if (!el) return;
    el.textContent = text;
    el.className   = `status-dot ${type}`;
}

// ── EXCLUSÃO EM LOTE ────────────────────────────────────────────────────────

async function deletarSelecionadas() {
    const ids = [...selecionados];
    if (ids.length === 0) return;
    const n = ids.length;
    if (!confirm(`Excluir permanentemente ${n} despesa${n > 1 ? 's' : ''} selecionada${n > 1 ? 's' : ''}?`)) return;

    try {
        const { error } = await dbClient.from('c_despesas').delete().in('id', ids);
        if (error) throw error;

        todosRegistros = todosRegistros.filter(r => !selecionados.has(r.id));
        limparSelecao();
        renderizarTabela();
        atualizarSumario();
        toast.success(`${n} despesa${n > 1 ? 's' : ''} excluída${n > 1 ? 's' : ''}.`);
    } catch (e) {
        toast.error(`Erro ao excluir: ${e.message}`);
    }
}

// ── SELEÇÃO E VINCULAR COMPROVANTE ──────────────────────────────────────────

function toggleSelecao(id) {
    if (selecionados.has(id)) selecionados.delete(id);
    else selecionados.add(id);
    // atualiza visual da linha sem re-renderizar toda a tabela
    const chk = document.querySelector(`.chk-selecao[data-id="${id}"]`);
    if (chk) chk.closest('tr').classList.toggle('row-selecionada', selecionados.has(id));
    atualizarBarraSelecao();
}

function atualizarBarraSelecao() {
    const barra = document.getElementById('barraSelecao');
    const n = selecionados.size;
    if (n === 0) { barra.style.display = 'none'; return; }
    barra.style.display = 'flex';
    document.getElementById('barraSelecaoInfo').textContent =
        `${n} despesa${n > 1 ? 's' : ''} selecionada${n > 1 ? 's' : ''}`;
}

function limparSelecao() {
    selecionados.clear();
    document.querySelectorAll('.chk-selecao').forEach(c => c.checked = false);
    document.querySelectorAll('.row-selecionada').forEach(r => r.classList.remove('row-selecionada'));
    atualizarBarraSelecao();
}

function abrirVincularComprovante() {
    if (selecionados.size === 0) return;
    const lista = document.getElementById('vincularLista');
    lista.innerHTML = [...selecionados].map(id => {
        const r = todosRegistros.find(x => x.id === id);
        if (!r) return '';
        return `<div class="file-chip" style="max-width:100%;border-radius:var(--r-md);">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <span>${esc(r.fornecedor)} — ${esc(r.descricao)} (${r.data ? formatarData(r.data) : '—'})</span>
        </div>`;
    }).join('');
    document.getElementById('vincularFileInput').value = '';
    document.getElementById('vincularFileChip').style.display = 'none';
    document.getElementById('modalVincular').style.display = 'flex';
}

function fecharModalVincular() {
    document.getElementById('modalVincular').style.display = 'none';
}

async function confirmarVincularComprovante() {
    const input = document.getElementById('vincularFileInput');
    const file  = input.files[0];
    if (!file) { toast.warning('Selecione um arquivo.'); return; }

    const btn = document.getElementById('btnConfirmarVincular');
    btn.disabled = true; btn.textContent = 'Vinculando…';

    try {
        // Upload único
        const ext  = file.name.split('.').pop().toLowerCase();
        const nome = `nf_${crypto.randomUUID().replace(/-/g,'').slice(0,12)}.${ext}`;
        const { error: upErr } = await dbClient.storage.from('comprovantes').upload(nome, file, { contentType: file.type });
        if (upErr) throw upErr;
        const base = window.ENV.SUPABASE_URL.replace(/\/$/, '');
        const url  = `${base}/storage/v1/object/public/comprovantes/${nome}`;

        // Vincula a todas as despesas selecionadas
        const ids = [...selecionados];
        for (const id of ids) {
            await dbClient.from('comprovantes_despesa').insert({ despesa_id: id, url, nome_arquivo: nome });
            await dbClient.from('c_despesas').update({ tem_nota_fiscal: true, comprovante_url: url }).eq('id', id);
            const idx = todosRegistros.findIndex(x => x.id === id);
            if (idx !== -1) { todosRegistros[idx].tem_nota_fiscal = true; todosRegistros[idx].comprovante_url = url; }
        }

        fecharModalVincular();
        limparSelecao();
        renderizarTabela();
        toast.success(`Comprovante vinculado a ${ids.length} despesa(s)!`);
    } catch (e) {
        toast.error(`Erro: ${e.message}`);
    } finally {
        btn.disabled = false; btn.textContent = 'Vincular';
    }
}
