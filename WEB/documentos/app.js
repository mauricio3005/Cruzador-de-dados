/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Documentos (app.js)
 */

const PAGE_SIZE = 50;

// --- SUPABASE (via nav.js → window.db) ---
let dbClient;

// --- ESTADO ---
let obras           = [];
let etapas          = [];
let todosRegistros  = [];
let comprovantesMap = {};   // despesa_id → [{id, url, nome_arquivo}]
let paginaAtual     = 1;
let modalAnexarId   = null;
let arquivosAnexar  = [];   // Files selecionados no modal

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    dbClient = window.db;
    await carregarReferencias();

    const hoje = new Date();
    const ini  = new Date(hoje);
    ini.setDate(ini.getDate() - 90);
    document.getElementById('filtroDataIni').value = ini.toISOString().split('T')[0];
    document.getElementById('filtroDataFim').value = hoje.toISOString().split('T')[0];

    document.getElementById('btnFiltrar').addEventListener('click', () => { paginaAtual = 1; carregarDocs(); });
    document.getElementById('btnLimparFiltro').addEventListener('click', limparFiltros);
    document.getElementById('filtroObra').addEventListener('change', e => filtrarEtapasPorObra(e.target.value));
    document.getElementById('btnExportarCSV').addEventListener('click', exportarCSV);
    document.getElementById('buscaTexto').addEventListener('input', () => { paginaAtual = 1; renderizarTabela(); });

    document.getElementById('btnPagAnterior').addEventListener('click', () => { if (paginaAtual > 1) { paginaAtual--; renderizarTabela(); } });
    document.getElementById('btnPagProxima').addEventListener('click',  () => { if (paginaAtual * PAGE_SIZE < todosRegistros.length) { paginaAtual++; renderizarTabela(); } });

    const uploadZone = document.getElementById('uploadZoneAnexar');
    const inputFile  = document.getElementById('inputNFAnexar');

    uploadZone.addEventListener('click', () => inputFile.click());
    uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.style.borderColor = 'var(--accent)'; uploadZone.style.background = 'rgba(var(--accent-rgb,0,120,212),0.06)'; });
    uploadZone.addEventListener('dragleave', () => resetUploadZone());
    uploadZone.addEventListener('drop', e => {
        e.preventDefault();
        resetUploadZone();
        if (e.dataTransfer.files.length) selecionarArquivos(e.dataTransfer.files);
    });
    inputFile.addEventListener('change', () => { if (inputFile.files.length) selecionarArquivos(inputFile.files); });

    document.getElementById('btnConfirmarAnexar').addEventListener('click', confirmarAnexar);
    document.getElementById('modalAnexar').addEventListener('click', e => {
        if (e.target === document.getElementById('modalAnexar')) fecharModalAnexar();
    });

    carregarDocs();
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    if (!dbClient) return;
    try {
        const [rObras, rEtapas] = await Promise.all([
            dbClient.from('obras').select('nome').order('nome'),
            dbClient.from('etapas').select('nome, ordem').order('ordem'),
        ]);
        obras  = (rObras.data  || []).map(r => r.nome);
        etapas = (rEtapas.data || []).map(r => r.nome);
        popularSelect('filtroObra',  obras,  'Todas as obras');
        popularSelect('filtroEtapa', etapas, 'Todas as etapas');
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

async function filtrarEtapasPorObra(obra) {
    const el = document.getElementById('filtroEtapa');
    if (!obra) { popularSelect('filtroEtapa', etapas, 'Todas as etapas'); el.value = ''; return; }
    const { data } = await dbClient.from('obra_etapas').select('etapa').eq('obra', obra);
    const nomes = (data || []).map(r => r.etapa);
    popularSelect('filtroEtapa', nomes, 'Todas as etapas');
    if (!nomes.includes(el.value)) el.value = '';
}

// --- CARREGAR DOCS ---
async function carregarDocs() {
    if (!dbClient) return;

    const dataIni    = document.getElementById('filtroDataIni').value;
    const dataFim    = document.getElementById('filtroDataFim').value;
    const obra       = document.getElementById('filtroObra').value;
    const etapa      = document.getElementById('filtroEtapa').value;
    const nf         = document.getElementById('filtroNF').value;
    const fornecedor = document.getElementById('filtroFornecedor').value.trim();
    const descricao  = document.getElementById('filtroDescricao').value.trim();

    document.getElementById('tabelaLoading').style.display = 'flex';

    try {
        let q = dbClient
            .from('c_despesas')
            .select('id,data,obra,etapa,tipo,fornecedor,descricao,despesa,valor_total,tem_nota_fiscal,folha_id')
            .order('data', { ascending: false })
            .order('id',   { ascending: false });

        if (dataIni) q = q.gte('data', dataIni);
        if (dataFim) q = q.lte('data', dataFim);
        if (obra)    q = q.eq('obra', obra);
        if (etapa)   q = q.eq('etapa', etapa);
        if (nf === 'com')   q = q.eq('tem_nota_fiscal', true);
        if (nf === 'sem')   q = q.eq('tem_nota_fiscal', false);
        if (fornecedor)     q = q.ilike('fornecedor', `%${fornecedor}%`);
        if (descricao)      q = q.ilike('descricao',  `%${descricao}%`);

        const { data, error } = await q;
        if (error) throw error;

        todosRegistros = data || [];
        paginaAtual    = 1;

        await carregarComprovantesMap(todosRegistros.map(r => r.id));

        renderizarTabela();
        atualizarKPIs();
        setStatus('online', 'Sistema Sincronizado');
    } catch (e) {
        setStatus('offline', 'Erro ao carregar');
        toast.error(`Erro: ${e.message}`);
    } finally {
        document.getElementById('tabelaLoading').style.display = 'none';
    }
}

// --- COMPROVANTES MAP ---
async function carregarComprovantesMap(ids) {
    comprovantesMap = {};
    if (!ids.length) return;
    const { data, error } = await dbClient
        .from('comprovantes_despesa')
        .select('id, despesa_id, url, nome_arquivo')
        .in('despesa_id', ids);
    if (error) {
        console.error('[comprovantesMap] Erro ao carregar NFs:', error);
        toast.warning('Não foi possível carregar as notas fiscais vinculadas.');
        return;
    }
    for (const c of (data || [])) {
        if (!comprovantesMap[c.despesa_id]) comprovantesMap[c.despesa_id] = [];
        comprovantesMap[c.despesa_id].push(c);
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
    const tbody  = document.getElementById('tabelaBody');

    if (pagina.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhum registro encontrado.</td></tr>`;
        document.getElementById('paginacaoWrap').style.display = 'none';
        return;
    }

    const iconePaperclip = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>`;
    const iconeDoc       = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`;

    tbody.innerHTML = pagina.map(r => {
        const data  = r.data ? formatarData(r.data) : '—';
        const valor = r.valor_total != null ? formatarValor(r.valor_total) : '—';
        const comps = comprovantesMap[r.id] || [];

        // NF badge e ações
        let nfBadge, acoes;

        if (r.folha_id) {
            // Despesas de folha: comprovantes gerenciados no módulo Folha
            nfBadge = `<span style="font-size:0.75rem;color:var(--on-surface-muted);font-style:italic;">Ver na Folha</span>`;
            acoes   = `<span style="font-size:0.75rem;color:var(--on-surface-muted);">—</span>`;
        } else if (comps.length > 0) {
            const nCount = comps.length;
            nfBadge = `<span style="display:inline-flex;align-items:center;gap:4px;font-size:0.75rem;font-weight:600;color:var(--accent);">${iconeDoc} ${nCount} NF${nCount > 1 ? 's' : ''}</span>`;
            acoes = `<button class="btn btn-outline" onclick="abrirModalAnexar(${r.id})"
                             style="font-size:0.75rem;padding:3px 10px;white-space:nowrap;">
                         ${iconePaperclip} Gerenciar NFs
                     </button>`;
        } else {
            nfBadge = `<span style="font-size:0.75rem;color:var(--on-surface-muted);">—</span>`;
            acoes = `<button class="btn btn-outline" onclick="abrirModalAnexar(${r.id})"
                             style="font-size:0.75rem;padding:3px 10px;white-space:nowrap;">
                         ${iconePaperclip} Anexar NF
                     </button>`;
        }

        return `<tr>
            <td style="white-space:nowrap;">${data}</td>
            <td>${esc(r.obra)}</td>
            <td>${esc(r.etapa)}</td>
            <td>${esc(r.tipo)}</td>
            <td>${esc(r.fornecedor) || '\u2014'}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(r.descricao) || '\u2014'}">${esc(r.descricao) || '\u2014'}</td>
            <td>${esc(r.despesa) || '\u2014'}</td>
            <td class="text-right" style="font-variant-numeric:tabular-nums;">${valor}</td>
            <td style="text-align:center;">${nfBadge}</td>
            <td style="text-align:center;">${acoes}</td>
        </tr>`;
    }).join('');

    const totalPaginas  = Math.ceil(totalFiltrado / PAGE_SIZE);
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

// --- KPIs ---
function atualizarKPIs() {
    const total = todosRegistros.reduce((s, r) => s + (r.valor_total || 0), 0);
    const comNF = todosRegistros.filter(r => r.tem_nota_fiscal).length;
    const semNF = todosRegistros.filter(r => !r.tem_nota_fiscal).length;

    document.getElementById('sumRegistros').textContent = todosRegistros.length.toLocaleString('pt-BR');
    document.getElementById('sumTotal').textContent     = 'R$ ' + formatarValor(total);
    document.getElementById('sumComNF').textContent     = comNF.toLocaleString('pt-BR');
    document.getElementById('sumSemNF').textContent     = semNF.toLocaleString('pt-BR');
}

// --- FILTROS ---
function limparFiltros() {
    const hoje = new Date();
    const ini  = new Date(hoje);
    ini.setDate(ini.getDate() - 90);
    document.getElementById('filtroDataIni').value = ini.toISOString().split('T')[0];
    document.getElementById('filtroDataFim').value = hoje.toISOString().split('T')[0];
    document.getElementById('filtroObra').value    = '';
    document.getElementById('filtroEtapa').value   = '';
    document.getElementById('filtroNF').value          = '';
    document.getElementById('filtroFornecedor').value  = '';
    document.getElementById('filtroDescricao').value   = '';
    document.getElementById('buscaTexto').value        = '';
    paginaAtual = 1;
    carregarDocs();
}

// --- MODAL GERENCIAR NFs ---
function abrirModalAnexar(id) {
    const r = todosRegistros.find(x => x.id === id);
    if (!r) return;

    modalAnexarId  = id;
    arquivosAnexar = [];
    document.getElementById('inputNFAnexar').value = '';
    document.getElementById('btnConfirmarAnexar').disabled = true;
    resetUploadZone();

    const data = r.data ? formatarData(r.data) : '—';
    document.getElementById('modalAnexarInfo').innerHTML =
        `<strong>${esc(r.obra)}</strong> &nbsp;·&nbsp; ${data} &nbsp;·&nbsp; ${esc(r.fornecedor || '—')}<br>
         <span style="color:var(--on-surface-muted);">${esc(r.descricao || '—')}</span>
         &nbsp;&nbsp; <strong class="fin-num">R$ ${formatarValor(r.valor_total || 0)}</strong>`;

    renderizarNfsModal(id);

    document.getElementById('modalAnexar').style.display = 'flex';
}

function renderizarNfsModal(despesaId) {
    const comps  = comprovantesMap[despesaId] || [];
    const nfsDiv = document.getElementById('nfsExistentes');
    const lista  = document.getElementById('listaComprovantesModal');

    if (comps.length === 0) { nfsDiv.style.display = 'none'; return; }

    lista.innerHTML = comps.map(c => `
        <div style="display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-2) var(--sp-1);border-bottom:1px solid var(--outline-ghost);">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--on-surface-muted)" stroke-width="2" style="flex-shrink:0;">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <a href="${c.url}" target="_blank"
               style="flex:1;font-size:0.8125rem;color:var(--accent);text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
               title="${esc(c.nome_arquivo || 'nota_fiscal')}">
                ${esc(c.nome_arquivo || 'nota_fiscal')}
            </a>
            <button onclick="removerNFItem(${c.id}, ${despesaId})"
                    style="background:none;border:none;cursor:pointer;color:var(--error);padding:4px;border-radius:4px;flex-shrink:0;"
                    title="Remover este arquivo">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    <path d="M10 11v6M14 11v6"></path>
                </svg>
            </button>
        </div>
    `).join('');
    nfsDiv.style.display = '';
}

function fecharModalAnexar() {
    document.getElementById('modalAnexar').style.display = 'none';
    modalAnexarId  = null;
    arquivosAnexar = [];
}

function selecionarArquivos(files) {
    arquivosAnexar = Array.from(files);
    const n = arquivosAnexar.length;
    document.getElementById('uploadZoneAnexarText').textContent = n === 1 ? `📎 ${arquivosAnexar[0].name}` : `📎 ${n} arquivos selecionados`;
    document.getElementById('uploadZoneAnexar').style.borderColor = 'var(--accent)';
    document.getElementById('btnConfirmarAnexar').disabled = false;
}

function resetUploadZone() {
    document.getElementById('uploadZoneAnexar').style.borderColor = '';
    document.getElementById('uploadZoneAnexar').style.background  = '';
    if (!arquivosAnexar.length) {
        document.getElementById('uploadZoneAnexarText').textContent = 'Arraste ou clique para selecionar (PDF, JPG, PNG)';
    }
}

async function confirmarAnexar() {
    if (!arquivosAnexar.length || !modalAnexarId) return;

    const btn = document.getElementById('btnConfirmarAnexar');
    btn.disabled    = true;
    btn.textContent = 'Enviando…';

    try {
        const inseridos = [];
        for (const file of arquivosAnexar) {
            const resultado = await uploadComprovante(file);
            if (!resultado) continue;
            const { url, nome } = resultado;
            const { data: inserted, error } = await dbClient
                .from('comprovantes_despesa')
                .insert({ despesa_id: modalAnexarId, url, nome_arquivo: nome })
                .select('id, despesa_id, url, nome_arquivo')
                .single();
            if (error) throw error;
            inseridos.push(inserted);
        }

        if (inseridos.length === 0) throw new Error('Nenhum arquivo pôde ser enviado');

        await dbClient.from('c_despesas').update({ tem_nota_fiscal: true }).eq('id', modalAnexarId);

        if (!comprovantesMap[modalAnexarId]) comprovantesMap[modalAnexarId] = [];
        comprovantesMap[modalAnexarId].push(...inseridos);
        const idx = todosRegistros.findIndex(x => x.id === modalAnexarId);
        if (idx !== -1) todosRegistros[idx].tem_nota_fiscal = true;

        fecharModalAnexar();
        renderizarTabela();
        atualizarKPIs();
        toast.success(`${inseridos.length} nota(s) fiscal(is) anexada(s)!`);
    } catch (e) {
        toast.error(`Erro ao anexar: ${e.message}`);
    } finally {
        btn.disabled    = false;
        btn.textContent = 'Anexar NF';
    }
}

// --- REMOVER NF INDIVIDUAL ---
async function removerNFItem(nfId, despesaId) {
    const comps = comprovantesMap[despesaId] || [];
    const item  = comps.find(c => c.id === nfId);
    if (!item) return;
    if (!confirm(`Remover "${item.nome_arquivo || 'este arquivo'}"? A ação não pode ser desfeita.`)) return;

    try {
        // Deleta via backend (service key tem permissão no bucket)
        const token = window.getAuthToken ? await window.getAuthToken() : null;
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        const res = await fetch(`http://${location.hostname}:8000/api/documentos/nf/${nfId}`, { method: 'DELETE', headers });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const result = await res.json();

        // Atualiza estado local
        comprovantesMap[despesaId] = comps.filter(c => c.id !== nfId);
        if (result.restantes === 0) {
            const idx = todosRegistros.findIndex(x => x.id === despesaId);
            if (idx !== -1) todosRegistros[idx].tem_nota_fiscal = false;
        }

        if (modalAnexarId === despesaId) renderizarNfsModal(despesaId);
        renderizarTabela();
        atualizarKPIs();
        toast.success('Nota fiscal removida.');
    } catch (e) {
        toast.error(`Erro ao remover: ${e.message}`);
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
        toast.warning(`Nota fiscal não pôde ser salva: ${e.message}`);
        return null;
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

    const cabecalho = ['Data','Obra','Etapa','Tipo','Fornecedor','Descrição','Categoria','Valor Total','Tem NF','URLs NFs'];
    const linhas = dados.map(r => {
        const comps = comprovantesMap[r.id] || [];
        return [
            r.data || '', r.obra || '', r.etapa || '', r.tipo || '',
            r.fornecedor || '', (r.descricao || '').replace(/"/g,'""'),
            r.despesa || '',
            r.valor_total != null ? r.valor_total.toFixed(2).replace('.',',') : '',
            r.tem_nota_fiscal ? 'Sim' : 'Não',
            comps.map(c => c.url).join(' | '),
        ].map(v => `"${v}"`).join(';');
    });

    const csv  = [cabecalho.join(';'), ...linhas].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `documentos_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// helpers: esc, setStatus, formatarData, formatarValor — via lib/helpers.js
