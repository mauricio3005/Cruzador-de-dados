/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Configurações (app.js)
 */

// --- SUPABASE ---
let db;
function carregarEnv() {
    if (window.ENV) {
        const { SUPABASE_URL, SUPABASE_ANON_KEY } = window.ENV;
        if (SUPABASE_URL && SUPABASE_ANON_KEY)
            db = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    }
}

// --- ESTADO ---
let obras      = [];
let etapas     = [];
let tiposCusto = [];
let formas     = [];
let categorias = [];

// --- HELPERS ---
function esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function setStatus(estado, texto) {
    const el = document.getElementById('connectionStatus');
    if (!el) return;
    el.textContent = texto;
    el.className   = `status-dot ${estado}`;
}
function formatarValor(v) {
    return Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    carregarEnv();
    if (!db) { setStatus('offline', 'Erro de conexão'); return; }

    // Tabs
    document.querySelectorAll('.sub-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.sub-tab-pane').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`pane-${btn.dataset.tab}`).classList.add('active');
        });
    });

    // Busca categoria
    document.getElementById('buscaCategoria').addEventListener('input', renderizarCategorias);

    // Botões obras
    document.getElementById('btnNovaObra').addEventListener('click', () => abrirModalObra(null));
    document.getElementById('btnSalvarObra').addEventListener('click', salvarObra);
    document.getElementById('modalObra').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModalObra();
    });

    // Botões etapas
    document.getElementById('btnNovaEtapa').addEventListener('click', () => abrirModalEtapa(null));
    document.getElementById('btnSalvarEtapa').addEventListener('click', salvarEtapa);
    document.getElementById('btnSalvarOrdemEtapas').addEventListener('click', salvarOrdemEtapas);
    document.getElementById('modalEtapa').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModalEtapa();
    });

    // Orçamentos
    document.getElementById('obraOrcamento').addEventListener('change', carregarOrcamentos);
    document.getElementById('btnSalvarOrcamentos').addEventListener('click', salvarOrcamentos);

    // Taxa
    document.getElementById('obraTaxa').addEventListener('change', carregarTaxa);
    document.getElementById('btnSalvarTaxa').addEventListener('click', salvarTaxa);

    // Formas
    document.getElementById('btnAdicionarForma').addEventListener('click', adicionarForma);
    document.getElementById('inputNovaForma').addEventListener('keydown', e => { if (e.key === 'Enter') adicionarForma(); });

    // Categorias
    document.getElementById('btnAdicionarCategoria').addEventListener('click', adicionarCategoria);
    document.getElementById('inputNovaCategoria').addEventListener('keydown', e => { if (e.key === 'Enter') adicionarCategoria(); });

    // Regras
    document.getElementById('obraRegras').addEventListener('change', carregarRegras);
    document.getElementById('btnAdicionarRegra').addEventListener('click', adicionarRegra);

    await carregarReferencias();
    setStatus('online', 'Sistema Sincronizado');
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    const safe = async (query, campo = 'nome') => {
        try {
            const { data, error } = await query;
            if (error) { console.warn(error.message); return []; }
            return (data || []);
        } catch { return []; }
    };

    const [resObras, resEtapas, resTipos, resFormas, resCats] = await Promise.all([
        safe(db.from('obras').select('*').order('nome')),
        safe(db.from('etapas').select('nome,ordem').order('ordem')),
        safe(db.from('tipos_custo').select('nome').order('nome')),
        safe(db.from('formas_pagamento').select('nome').order('nome')),
        safe(db.from('categorias_despesa').select('nome').order('nome')),
    ]);

    obras      = resObras;
    etapas     = resEtapas;
    tiposCusto = resTipos.map(r => r.nome);
    formas     = resFormas.map(r => r.nome);
    categorias = resCats.map(r => r.nome);

    renderizarObras();
    renderizarEtapas();
    popularSelectObra('obraOrcamento');
    popularSelectObra('obraTaxa');
    popularSelectObra('obraRegras');
    renderizarFormas();
    renderizarCategorias();
}

function popularSelectObra(id) {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = `<option value="">— Selecione —</option>` +
        obras.map(o => `<option value="${esc(o.nome)}">${esc(o.nome)}</option>`).join('');
}

// ============================================================
// OBRAS
// ============================================================
function renderizarObras() {
    const tbody = document.getElementById('tabelaObras');
    if (!obras.length) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhuma obra cadastrada.</td></tr>`;
        return;
    }
    tbody.innerHTML = obras.map(o => `
        <tr>
            <td style="font-weight:600;">${esc(o.nome)}</td>
            <td>${esc(o.descricao || '—')}</td>
            <td>${esc(o.contrato || '—')}</td>
            <td>${esc(o.art || '—')}</td>
            <td style="text-align:center;white-space:nowrap;">
                <button class="btn btn-outline" onclick="abrirModalObra('${esc(o.nome)}')" style="font-size:0.72rem;padding:3px 8px;" title="Editar">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button class="btn btn-outline" onclick="removerObra('${esc(o.nome)}')" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Remover">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`).join('');
}

function abrirModalObra(nome) {
    const o = nome ? obras.find(x => x.nome === nome) : null;
    document.getElementById('modalObraTitulo').textContent = o ? 'Editar Obra' : 'Nova Obra';
    document.getElementById('oNome').value          = o ? o.nome        : '';
    document.getElementById('oNomeOriginal').value  = o ? o.nome        : '';
    document.getElementById('oDescricao').value     = o ? (o.descricao  || '') : '';
    document.getElementById('oContrato').value      = o ? (o.contrato   || '') : '';
    document.getElementById('oArt').value           = o ? (o.art        || '') : '';
    document.getElementById('oNome').disabled       = !!o; // nome é PK, não pode alterar
    document.getElementById('modalObra').style.display = 'flex';
}

function fecharModalObra() {
    document.getElementById('modalObra').style.display = 'none';
}

async function salvarObra() {
    const nome     = document.getElementById('oNome').value.trim();
    const original = document.getElementById('oNomeOriginal').value;
    const payload  = {
        descricao: document.getElementById('oDescricao').value.trim() || null,
        contrato:  document.getElementById('oContrato').value.trim()  || null,
        art:       document.getElementById('oArt').value.trim()       || null,
    };

    if (!nome) { toast.warning('Nome é obrigatório.'); return; }

    const btn = document.getElementById('btnSalvarObra');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        if (original) {
            // Editar
            const { error } = await db.from('obras').update(payload).eq('nome', original);
            if (error) throw error;
            toast.success('Obra atualizada.');
        } else {
            // Criar
            const { error } = await db.from('obras').insert({ nome, ...payload });
            if (error) throw error;
            toast.success(`Obra "${nome}" adicionada.`);
        }
        fecharModalObra();
        await carregarReferencias();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

async function removerObra(nome) {
    if (!confirm(`Remover a obra "${nome}"? Esta ação não pode ser desfeita.`)) return;
    try {
        const { error } = await db.from('obras').delete().eq('nome', nome);
        if (error) throw error;
        toast.success(`Obra "${nome}" removida.`);
        await carregarReferencias();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

// ============================================================
// ETAPAS
// ============================================================
function renderizarEtapas() {
    const tbody = document.getElementById('tabelaEtapas');
    if (!etapas.length) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhuma etapa cadastrada.</td></tr>`;
        return;
    }
    tbody.innerHTML = etapas.map(e => `
        <tr>
            <td style="font-weight:500;">${esc(e.nome)}</td>
            <td><input type="number" class="form-input" data-etapa="${esc(e.nome)}" value="${e.ordem ?? 999}" min="0" step="1" style="width:80px;padding:4px 8px;font-size:0.875rem;"></td>
            <td style="text-align:center;">
                <button class="btn btn-outline" onclick="abrirModalEtapa('${esc(e.nome)}')" style="font-size:0.72rem;padding:3px 8px;" title="Editar">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
            </td>
        </tr>`).join('');
}

function abrirModalEtapa(nome) {
    const e = nome ? etapas.find(x => x.nome === nome) : null;
    document.getElementById('modalEtapaTitulo').textContent = e ? 'Editar Etapa' : 'Nova Etapa';
    document.getElementById('etNome').value         = e ? e.nome  : '';
    document.getElementById('etNomeOriginal').value = e ? e.nome  : '';
    document.getElementById('etOrdem').value        = e ? (e.ordem ?? 999) : 999;
    document.getElementById('etNome').disabled      = !!e;
    document.getElementById('modalEtapa').style.display = 'flex';
}

function fecharModalEtapa() {
    document.getElementById('modalEtapa').style.display = 'none';
}

async function salvarEtapa() {
    const nome     = document.getElementById('etNome').value.trim();
    const original = document.getElementById('etNomeOriginal').value;
    const ordem    = parseInt(document.getElementById('etOrdem').value) || 999;

    if (!nome) { toast.warning('Nome é obrigatório.'); return; }

    const btn = document.getElementById('btnSalvarEtapa');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        if (original) {
            const { error } = await db.from('etapas').update({ ordem }).eq('nome', original);
            if (error) throw error;
            toast.success('Etapa atualizada.');
        } else {
            const { error } = await db.from('etapas').insert({ nome, ordem });
            if (error) throw error;
            toast.success(`Etapa "${nome}" adicionada.`);
        }
        fecharModalEtapa();
        await carregarReferencias();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

async function salvarOrdemEtapas() {
    const inputs = document.querySelectorAll('#tabelaEtapas input[data-etapa]');
    const rows = Array.from(inputs).map(inp => ({
        nome:  inp.dataset.etapa,
        ordem: parseInt(inp.value) || 999,
    }));

    const btn = document.getElementById('btnSalvarOrdemEtapas');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        const { error } = await db.from('etapas').upsert(rows, { onConflict: 'nome' });
        if (error) throw error;
        toast.success('Ordem salva.');
        await carregarReferencias();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar Ordem';
    }
}

// ============================================================
// ORÇAMENTOS
// ============================================================
let orcamentosData = {};

async function carregarOrcamentos() {
    const obra = document.getElementById('obraOrcamento').value;
    const wrap = document.getElementById('tabelaOrcamentosWrap');
    if (!obra) {
        wrap.innerHTML = '<p style="padding:var(--sp-6);color:var(--on-surface-muted);">Selecione uma obra para editar os orçamentos.</p>';
        return;
    }

    wrap.innerHTML = '<p style="padding:var(--sp-6);color:var(--on-surface-muted);">Carregando…</p>';

    try {
        const { data, error } = await db.from('orcamentos')
            .select('obra,etapa,tipo_custo,valor_estimado')
            .eq('obra', obra);
        if (error) throw error;

        orcamentosData = {};
        for (const r of (data || [])) {
            if (!orcamentosData[r.etapa]) orcamentosData[r.etapa] = {};
            orcamentosData[r.etapa][r.tipo_custo] = r.valor_estimado;
        }

        renderizarGridOrcamentos(wrap);
    } catch (e) {
        wrap.innerHTML = `<p style="padding:var(--sp-6);color:var(--error);">Erro: ${esc(e.message)}</p>`;
    }
}

function renderizarGridOrcamentos(wrap) {
    if (!etapas.length || !tiposCusto.length) {
        wrap.innerHTML = '<p style="padding:var(--sp-6);color:var(--on-surface-muted);">Configure etapas e tipos de custo primeiro.</p>';
        return;
    }

    const cols = tiposCusto;
    const header = `<tr><th>Etapa</th>${cols.map(c => `<th class="text-right">${esc(c)}</th>`).join('')}</tr>`;
    const rows = etapas.map(et => {
        const inputs = cols.map(c => {
            const val = (orcamentosData[et.nome] || {})[c] || 0;
            return `<td><input type="number" class="form-input" data-etapa="${esc(et.nome)}" data-tipo="${esc(c)}" value="${val}" min="0" step="0.01" style="width:100%;padding:4px 8px;font-size:0.875rem;text-align:right;font-variant-numeric:tabular-nums;"></td>`;
        }).join('');
        return `<tr><td style="font-weight:500;">${esc(et.nome)}</td>${inputs}</tr>`;
    }).join('');

    wrap.innerHTML = `<table class="styled-table"><thead>${header}</thead><tbody>${rows}</tbody></table>`;
}

async function salvarOrcamentos() {
    const obra = document.getElementById('obraOrcamento').value;
    if (!obra) { toast.warning('Selecione uma obra.'); return; }

    const inputs = document.querySelectorAll('#tabelaOrcamentosWrap input[data-etapa]');
    const rows = Array.from(inputs).map(inp => ({
        obra,
        etapa:           inp.dataset.etapa,
        tipo_custo:      inp.dataset.tipo,
        valor_estimado:  parseFloat(inp.value) || 0,
    }));

    const btn = document.getElementById('btnSalvarOrcamentos');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        const { error } = await db.from('orcamentos').upsert(rows, { onConflict: 'obra,etapa,tipo_custo' });
        if (error) throw error;
        toast.success('Orçamentos salvos.');
    } catch (e) {
        toast.error('Erro: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar Orçamentos';
    }
}

// ============================================================
// TAXA DE CONCLUSÃO
// ============================================================
let taxaData = {};

async function carregarTaxa() {
    const obra = document.getElementById('obraTaxa').value;
    const wrap = document.getElementById('tabelaTaxaWrap');
    if (!obra) {
        wrap.innerHTML = '<p style="padding:var(--sp-6);color:var(--on-surface-muted);">Selecione uma obra para editar as taxas.</p>';
        return;
    }

    wrap.innerHTML = '<p style="padding:var(--sp-6);color:var(--on-surface-muted);">Carregando…</p>';

    try {
        const { data, error } = await db.from('taxa_conclusao')
            .select('obra,etapa,taxa')
            .eq('obra', obra);
        if (error) throw error;

        taxaData = {};
        for (const r of (data || [])) {
            taxaData[r.etapa] = r.taxa;
        }

        renderizarGridTaxa(wrap);
    } catch (e) {
        wrap.innerHTML = `<p style="padding:var(--sp-6);color:var(--error);">Erro: ${esc(e.message)}</p>`;
    }
}

function renderizarGridTaxa(wrap) {
    if (!etapas.length) {
        wrap.innerHTML = '<p style="padding:var(--sp-6);color:var(--on-surface-muted);">Configure etapas primeiro.</p>';
        return;
    }

    const rows = etapas.map(et => {
        const val = taxaData[et.nome] ?? 0;
        return `<tr>
            <td style="font-weight:500;">${esc(et.nome)}</td>
            <td style="width:160px;">
                <div style="display:flex;align-items:center;gap:var(--sp-2);">
                    <input type="number" class="form-input" data-etapa="${esc(et.nome)}" value="${val}" min="0" max="100" step="0.1" style="width:100px;padding:4px 8px;font-size:0.875rem;text-align:right;font-variant-numeric:tabular-nums;">
                    <span style="color:var(--on-surface-muted);font-size:0.875rem;">%</span>
                </div>
            </td>
        </tr>`;
    }).join('');

    wrap.innerHTML = `<table class="styled-table">
        <thead><tr><th>Etapa</th><th>Taxa de Conclusão</th></tr></thead>
        <tbody>${rows}</tbody>
    </table>`;
}

async function salvarTaxa() {
    const obra = document.getElementById('obraTaxa').value;
    if (!obra) { toast.warning('Selecione uma obra.'); return; }

    const inputs = document.querySelectorAll('#tabelaTaxaWrap input[data-etapa]');
    const rows = Array.from(inputs).map(inp => ({
        obra,
        etapa: inp.dataset.etapa,
        taxa:  parseFloat(inp.value) || 0,
    }));

    const btn = document.getElementById('btnSalvarTaxa');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        const { error } = await db.from('taxa_conclusao').upsert(rows, { onConflict: 'obra,etapa' });
        if (error) throw error;
        toast.success('Taxas salvas.');
    } catch (e) {
        toast.error('Erro: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar Taxas';
    }
}

// ============================================================
// FORMAS DE PAGAMENTO
// ============================================================
function renderizarFormas() {
    const tbody = document.getElementById('tabelaFormas');
    if (!formas.length) {
        tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhuma forma cadastrada.</td></tr>`;
        return;
    }
    tbody.innerHTML = formas.map(f => `
        <tr>
            <td>${esc(f)}</td>
            <td style="text-align:center;">
                <button class="btn btn-outline" onclick="removerForma('${esc(f)}')" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Remover">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`).join('');
}

async function adicionarForma() {
    const nome = document.getElementById('inputNovaForma').value.trim();
    if (!nome) { toast.warning('Informe um nome.'); return; }
    try {
        const { error } = await db.from('formas_pagamento').insert({ nome });
        if (error) throw error;
        toast.success(`"${nome}" adicionada.`);
        document.getElementById('inputNovaForma').value = '';
        await recarregarFormas();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function removerForma(nome) {
    if (!confirm(`Remover "${nome}"?`)) return;
    try {
        const { error } = await db.from('formas_pagamento').delete().eq('nome', nome);
        if (error) throw error;
        toast.success(`"${nome}" removida.`);
        await recarregarFormas();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function recarregarFormas() {
    const { data } = await db.from('formas_pagamento').select('nome').order('nome');
    formas = (data || []).map(r => r.nome);
    renderizarFormas();
}

// ============================================================
// CATEGORIAS DE DESPESA
// ============================================================
function renderizarCategorias() {
    const tbody = document.getElementById('tabelaCategorias');
    const busca = document.getElementById('buscaCategoria').value.trim().toLowerCase();
    const lista = busca ? categorias.filter(c => c.toLowerCase().includes(busca)) : categorias;

    document.getElementById('totalCategorias').textContent =
        `${lista.length} de ${categorias.length}`;

    if (!lista.length) {
        tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhuma categoria encontrada.</td></tr>`;
        return;
    }
    tbody.innerHTML = lista.map(c => `
        <tr>
            <td style="font-size:0.8125rem;">${esc(c)}</td>
            <td style="text-align:center;">
                <button class="btn btn-outline" onclick="removerCategoria('${esc(c)}')" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Remover">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`).join('');
}

async function adicionarCategoria() {
    const nome = document.getElementById('inputNovaCategoria').value.trim().toUpperCase();
    if (!nome) { toast.warning('Informe um nome.'); return; }
    try {
        const { error } = await db.from('categorias_despesa').insert({ nome });
        if (error) throw error;
        toast.success(`"${nome}" adicionada.`);
        document.getElementById('inputNovaCategoria').value = '';
        await recarregarCategorias();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function removerCategoria(nome) {
    if (!confirm(`Remover a categoria "${nome}"?`)) return;
    try {
        const { error } = await db.from('categorias_despesa').delete().eq('nome', nome);
        if (error) throw error;
        toast.success(`"${nome}" removida.`);
        await recarregarCategorias();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function recarregarCategorias() {
    const { data } = await db.from('categorias_despesa').select('nome').order('nome');
    categorias = (data || []).map(r => r.nome);
    renderizarCategorias();
}

// ============================================================
// REGRAS DE SERVIÇO
// ============================================================
let regrasData = [];

async function carregarRegras() {
    const obra = document.getElementById('obraRegras').value;
    const tbody = document.getElementById('tabelaRegras');
    if (!obra) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Selecione uma obra.</td></tr>`;
        return;
    }

    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Carregando…</td></tr>`;

    try {
        const { data, error } = await db.from('folha_regras')
            .select('servico,tipo,valor')
            .eq('obra', obra)
            .order('servico');
        if (error) throw error;

        regrasData = data || [];
        renderizarRegras();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

function renderizarRegras() {
    const tbody = document.getElementById('tabelaRegras');
    const obra  = document.getElementById('obraRegras').value;
    if (!regrasData.length) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhuma regra para esta obra.</td></tr>`;
        return;
    }
    const tipoLabel = { diaria: 'Diária', m2: 'M²', fixo: 'Fixo' };
    tbody.innerHTML = regrasData.map(r => `
        <tr>
            <td style="font-weight:500;">${esc(r.servico)}</td>
            <td><span style="font-size:0.8rem;background:var(--surface-low);padding:2px 8px;border-radius:4px;">${esc(tipoLabel[r.tipo] || r.tipo)}</span></td>
            <td class="text-right">R$ ${formatarValor(r.valor)}</td>
            <td style="text-align:center;">
                <button class="btn btn-outline" onclick="removerRegra('${esc(obra)}','${esc(r.servico)}')" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Remover">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`).join('');
}

async function adicionarRegra() {
    const obra    = document.getElementById('obraRegras').value;
    const servico = document.getElementById('inputNovoServico').value.trim();
    const tipo    = document.getElementById('selectNovoTipoRegra').value;
    const valor   = parseFloat(document.getElementById('inputNovoValorRegra').value) || 0;

    if (!obra)    { toast.warning('Selecione uma obra.'); return; }
    if (!servico) { toast.warning('Informe o serviço.'); return; }

    try {
        const { error } = await db.from('folha_regras').upsert(
            { obra, servico, tipo, valor },
            { onConflict: 'obra,servico' }
        );
        if (error) throw error;
        toast.success(`Regra "${servico}" salva.`);
        document.getElementById('inputNovoServico').value   = '';
        document.getElementById('inputNovoValorRegra').value = '';
        await carregarRegras();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function removerRegra(obra, servico) {
    if (!confirm(`Remover regra "${servico}" de "${obra}"?`)) return;
    try {
        const { error } = await db.from('folha_regras').delete().eq('obra', obra).eq('servico', servico);
        if (error) throw error;
        toast.success(`Regra "${servico}" removida.`);
        await carregarRegras();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}
