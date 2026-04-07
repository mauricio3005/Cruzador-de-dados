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
let empresas   = [];
let etapas     = [];
let tiposCusto = [];
let formas     = [];
let categorias = [];
let fornecedores = [];
let bancos     = []; // { id, nome, tipo, descricao }
let bancosObras = {}; // banco_id → string[] (nomes das obras)

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
    document.getElementById('btnNovaObra').addEventListener('click', abrirWizard);
    document.getElementById('btnSalvarObra').addEventListener('click', salvarObra);
    document.getElementById('modalObra').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModalObra();
    });
    document.getElementById('modalWizardObra').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharWizard();
    });

    // Botões empresas
    document.getElementById('btnNovaEmpresa').addEventListener('click', () => abrirModalEmpresa(null));
    document.getElementById('btnSalvarEmpresa').addEventListener('click', salvarEmpresa);
    document.getElementById('modalEmpresa').addEventListener('click', e => {
        if (e.target === e.currentTarget) fecharModalEmpresa();
    });
    document.getElementById('btnEscolherLogo').addEventListener('click', () => {
        document.getElementById('eLogoFile').click();
    });
    document.getElementById('eLogoFile').addEventListener('change', e => {
        const file = e.target.files[0];
        if (!file) return;
        document.getElementById('eLogoNome').textContent = file.name;
        const reader = new FileReader();
        reader.onload = ev => {
            const prev = document.getElementById('eLogoPreview');
            prev.src = ev.target.result;
            prev.style.display = 'block';
        };
        reader.readAsDataURL(file);
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

    // Fornecedores
    document.getElementById('btnAdicionarFornecedor').addEventListener('click', adicionarFornecedor);
    document.getElementById('inputNovoFornecedor').addEventListener('keydown', e => { if (e.key === 'Enter') adicionarFornecedor(); });
    document.getElementById('buscaFornecedor').addEventListener('input', renderizarFornecedores);

    // Regras
    document.getElementById('obraRegras').addEventListener('change', carregarRegras);
    document.getElementById('btnAdicionarRegra').addEventListener('click', adicionarRegra);

    // Bancos
    document.getElementById('btnAdicionarBanco').addEventListener('click', adicionarBanco);
    document.getElementById('inputNovoBanco').addEventListener('keydown', e => { if (e.key === 'Enter') adicionarBanco(); });

    await carregarReferencias();
    setStatus('online', 'Sistema Sincronizado');
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    const safe = async (query) => {
        try {
            const { data, error } = await query;
            if (error) { console.warn(error.message); return []; }
            return (data || []);
        } catch { return []; }
    };

    const [resObras, resEmpresas, resEtapas, resTipos, resFormas, resCats, resForn, resBancos] = await Promise.all([
        safe(db.from('obras').select('*').order('nome')),
        safe(db.from('empresas').select('*').order('nome')),
        safe(db.from('etapas').select('nome,ordem').order('ordem')),
        safe(db.from('tipos_custo').select('nome').order('nome')),
        safe(db.from('formas_pagamento').select('nome').order('nome')),
        safe(db.from('categorias_despesa').select('nome').order('nome')),
        safe(db.from('fornecedores').select('nome').order('nome')),
        safe(db.from('bancos').select('id,nome,tipo,descricao').order('tipo').order('nome')),
    ]);

    obras        = resObras;
    empresas     = resEmpresas;
    etapas       = resEtapas;
    tiposCusto   = resTipos.map(r => r.nome);
    formas       = resFormas.map(r => r.nome);
    categorias   = resCats.map(r => r.nome);
    fornecedores = resForn.map(r => r.nome);
    bancos       = resBancos;

    // banco_obras em query separada: tabela pode não existir (migration pendente)
    bancosObras = {};
    try {
        const resBancoObras = await safe(db.from('banco_obras').select('banco_id,obra'));
        for (const bo of resBancoObras) {
            if (!bancosObras[bo.banco_id]) bancosObras[bo.banco_id] = [];
            bancosObras[bo.banco_id].push(bo.obra);
        }
    } catch (_) { /* tabela ainda não existe — segue sem restrições */ }

    renderizarObras();
    renderizarEmpresas();
    renderizarEtapas();
    popularSelectObra('obraOrcamento');
    popularSelectObra('obraTaxa');
    popularSelectObra('obraRegras');
    renderizarFormas();
    renderizarCategorias();
    renderizarFornecedores();
    renderizarBancos();
    popularCheckboxesNovoBanco();
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
    tbody.innerHTML = obras.map(o => {
        const empresa = empresas.find(e => e.id === o.empresa_id);
        return `
        <tr>
            <td style="font-weight:600;">${esc(o.nome)}</td>
            <td>${esc(o.descricao || '—')}</td>
            <td>${empresa ? `<span style="font-size:0.8125rem;background:var(--surface-low);padding:2px 8px;border-radius:4px;">${esc(empresa.nome)}</span>` : '—'}</td>
            <td>${esc(o.contrato || '—')}</td>
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
        </tr>`;
    }).join('');
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

    // Popula select de empresas
    const sel = document.getElementById('oEmpresaId');
    sel.innerHTML = `<option value="">— Sem empresa —</option>` +
        empresas.map(e => `<option value="${e.id}"${o && o.empresa_id === e.id ? ' selected' : ''}>${esc(e.nome)}</option>`).join('');

    document.getElementById('btnEditarEtapasObra').style.display = o ? '' : 'none';
    document.getElementById('modalObra').style.display = 'flex';
}

function fecharModalObra() {
    document.getElementById('modalObra').style.display = 'none';
}

// --- EDITAR ETAPAS DA OBRA ---
let _etapasObraOriginal = []; // etapas já associadas antes de abrir

async function abrirModalEtapasObra() {
    const nome = document.getElementById('oNomeOriginal').value;
    if (!nome) return;

    document.getElementById('modalEtapasObraSubtitulo').textContent = nome;
    document.getElementById('modalEtapasObraChips').innerHTML = '<span style="color:var(--on-surface-muted);font-size:0.8rem;">Carregando…</span>';
    document.getElementById('modalEtapasObra').style.display = 'flex';
    document.getElementById('btnSalvarEtapasObra').onclick = salvarEtapasObra;

    const { data } = await db.from('obra_etapas').select('etapa').eq('obra', nome);
    _etapasObraOriginal = (data || []).map(r => r.etapa);
    renderizarChipsEtapasObra(_etapasObraOriginal);
}

function fecharModalEtapasObra() {
    document.getElementById('modalEtapasObra').style.display = 'none';
}

function renderizarChipsEtapasObra(selecionadas) {
    const container = document.getElementById('modalEtapasObraChips');
    if (!etapas.length) {
        container.innerHTML = '<span style="color:var(--on-surface-muted);font-size:0.8rem;">Nenhuma etapa cadastrada.</span>';
        return;
    }
    container.innerHTML = etapas.map(et => {
        const sel = selecionadas.includes(et.nome) ? ' selected' : '';
        return `<div class="etapa-chip${sel}" onclick="this.classList.toggle('selected');atualizarContadorEtapas()" data-etapa="${esc(et.nome)}"><span class="chip-check"></span>${esc(et.nome)}</div>`;
    }).join('');
    atualizarContadorEtapas();
}

function atualizarContadorEtapas() {
    const total = document.querySelectorAll('#modalEtapasObraChips .etapa-chip').length;
    const sel   = document.querySelectorAll('#modalEtapasObraChips .etapa-chip.selected').length;
    document.getElementById('modalEtapasObraContador').textContent = `${sel} de ${total} selecionadas`;
}

function modalEtapasObraToggleAll() {
    const chips = Array.from(document.querySelectorAll('#modalEtapasObraChips .etapa-chip'));
    const todaSelecionada = chips.every(c => c.classList.contains('selected'));
    chips.forEach(c => c.classList.toggle('selected', !todaSelecionada));
    atualizarContadorEtapas();
}

async function salvarEtapasObra() {
    const nome = document.getElementById('oNomeOriginal').value;
    const chips = Array.from(document.querySelectorAll('#modalEtapasObraChips .etapa-chip.selected'));
    const novas = chips.map(c => c.dataset.etapa);

    const adicionadas = novas.filter(e => !_etapasObraOriginal.includes(e));
    const removidas   = _etapasObraOriginal.filter(e => !novas.includes(e));

    const btn = document.getElementById('btnSalvarEtapasObra');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        if (removidas.length) {
            const { error } = await db.from('obra_etapas').delete().eq('obra', nome).in('etapa', removidas);
            if (error) throw error;
        }
        if (adicionadas.length) {
            const { error } = await db.from('obra_etapas').insert(adicionadas.map(e => ({ obra: nome, etapa: e })));
            if (error) throw error;
        }
        toast.success('Etapas atualizadas.');
        fecharModalEtapasObra();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

async function salvarObra() {
    const nome     = document.getElementById('oNome').value.trim();
    const original = document.getElementById('oNomeOriginal').value;
    const empresaIdVal = document.getElementById('oEmpresaId').value;
    const payload  = {
        descricao:  document.getElementById('oDescricao').value.trim() || null,
        contrato:   document.getElementById('oContrato').value.trim()  || null,
        art:        document.getElementById('oArt').value.trim()       || null,
        empresa_id: empresaIdVal ? parseInt(empresaIdVal) : null,
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
// EMPRESAS
// ============================================================
function renderizarEmpresas() {
    const tbody = document.getElementById('tabelaEmpresas');
    if (!tbody) return;
    if (!empresas.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhuma empresa cadastrada.</td></tr>`;
        return;
    }
    tbody.innerHTML = empresas.map(e => `
        <tr>
            <td>
                ${e.logo_url
                    ? `<img src="${esc(e.logo_url)}" alt="${esc(e.nome)}" style="width:48px;height:32px;object-fit:contain;border-radius:4px;background:var(--surface-low);padding:2px;">`
                    : `<span style="font-size:0.75rem;color:var(--on-surface-muted);">Sem logo</span>`}
            </td>
            <td style="font-weight:600;">${esc(e.nome)}</td>
            <td>${esc(e.cnpj || '—')}</td>
            <td>${esc(e.telefone || '—')}</td>
            <td>${esc(e.endereco || '—')}</td>
            <td style="text-align:center;white-space:nowrap;">
                <button class="btn btn-outline" onclick="abrirModalEmpresa(${e.id})" style="font-size:0.72rem;padding:3px 8px;" title="Editar">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button class="btn btn-outline" onclick="removerEmpresa(${e.id},'${esc(e.nome)}')" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Remover">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`).join('');
}

function abrirModalEmpresa(id) {
    const e = id ? empresas.find(x => x.id === id) : null;
    document.getElementById('modalEmpresaTitulo').textContent = e ? 'Editar Empresa' : 'Nova Empresa';
    document.getElementById('eId').value        = e ? e.id           : '';
    document.getElementById('eNome').value      = e ? e.nome         : '';
    document.getElementById('eCnpj').value      = e ? (e.cnpj        || '') : '';
    document.getElementById('eTelefone').value  = e ? (e.telefone    || '') : '';
    document.getElementById('eEndereco').value  = e ? (e.endereco    || '') : '';
    document.getElementById('eLogoUrlAtual').value = e ? (e.logo_url || '') : '';
    document.getElementById('eLogoNome').textContent = '';
    document.getElementById('eLogoFile').value = '';

    const prev = document.getElementById('eLogoPreview');
    if (e && e.logo_url) {
        prev.src = e.logo_url;
        prev.style.display = 'block';
    } else {
        prev.src = '';
        prev.style.display = 'none';
    }

    document.getElementById('modalEmpresa').style.display = 'flex';
}

function fecharModalEmpresa() {
    document.getElementById('modalEmpresa').style.display = 'none';
    document.getElementById('modalEmpresa').style.zIndex = '';
    if (wizardAberto) wizEmpresaFechada();
}

async function salvarEmpresa() {
    const nome = document.getElementById('eNome').value.trim();
    if (!nome) { toast.warning('Nome é obrigatório.'); return; }

    const btn = document.getElementById('btnSalvarEmpresa');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        let logo_url = document.getElementById('eLogoUrlAtual').value || null;

        // Upload de logo se um novo arquivo foi selecionado
        const fileInput = document.getElementById('eLogoFile');
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const ext  = file.name.split('.').pop().toLowerCase();
            const path = `empresa_${nome.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${Date.now()}.${ext}`;

            const { error: upErr } = await db.storage.from('logos').upload(path, file, {
                contentType: file.type,
                upsert: true,
            });
            if (upErr) throw upErr;

            const base = window.ENV.SUPABASE_URL.replace(/\/$/, '');
            logo_url = `${base}/storage/v1/object/public/logos/${path}`;
        }

        const payload = {
            nome,
            cnpj:     document.getElementById('eCnpj').value.trim()     || null,
            telefone: document.getElementById('eTelefone').value.trim()  || null,
            endereco: document.getElementById('eEndereco').value.trim()  || null,
            logo_url,
        };

        const id = document.getElementById('eId').value;
        if (id) {
            const { error } = await db.from('empresas').update(payload).eq('id', parseInt(id));
            if (error) throw error;
            toast.success('Empresa atualizada.');
        } else {
            const { error } = await db.from('empresas').insert(payload);
            if (error) throw error;
            toast.success(`Empresa "${nome}" adicionada.`);
        }

        fecharModalEmpresa();
        const { data } = await db.from('empresas').select('*').order('nome');
        empresas = data || [];
        renderizarEmpresas();
        renderizarObras(); // atualiza coluna empresa nas obras
    } catch (e) {
        toast.error('Erro: ' + e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

async function removerEmpresa(id, nome) {
    if (!confirm(`Remover a empresa "${nome}"? As obras vinculadas ficarão sem empresa.`)) return;
    try {
        const { error } = await db.from('empresas').delete().eq('id', id);
        if (error) throw error;
        toast.success(`Empresa "${nome}" removida.`);
        const { data } = await db.from('empresas').select('*').order('nome');
        empresas = data || [];
        renderizarEmpresas();
        // Recarregar obras para refletir remoção da empresa
        const { data: obrasData } = await db.from('obras').select('*').order('nome');
        obras = obrasData || [];
        renderizarObras();
    } catch (e) {
        toast.error('Erro: ' + e.message);
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
        const [{ data, error }, { data: oeData }] = await Promise.all([
            db.from('orcamentos').select('obra,etapa,tipo_custo,valor_estimado').eq('obra', obra),
            db.from('obra_etapas').select('etapa').eq('obra', obra),
        ]);
        if (error) throw error;

        orcamentosData = {};
        for (const r of (data || [])) {
            if (!orcamentosData[r.etapa]) orcamentosData[r.etapa] = {};
            orcamentosData[r.etapa][r.tipo_custo] = r.valor_estimado;
        }

        const etapasObra = (oeData || []).map(r => r.etapa);
        renderizarGridOrcamentos(wrap, etapasObra.length ? etapasObra : null);
    } catch (e) {
        wrap.innerHTML = `<p style="padding:var(--sp-6);color:var(--error);">Erro: ${esc(e.message)}</p>`;
    }
}

function renderizarGridOrcamentos(wrap, etapasObra = null) {
    const etapasParaRenderizar = etapasObra
        ? etapas.filter(et => etapasObra.includes(et.nome))
        : etapas;
    if (!etapasParaRenderizar.length || !tiposCusto.length) {
        wrap.innerHTML = '<p style="padding:var(--sp-6);color:var(--on-surface-muted);">Configure etapas e tipos de custo primeiro.</p>';
        return;
    }

    const cols = tiposCusto;
    const header = `<tr><th>Etapa</th>${cols.map(c => `<th class="text-right">${esc(c)}</th>`).join('')}</tr>`;
    const rows = etapasParaRenderizar.map(et => {
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
// FORNECEDORES
// ============================================================
function renderizarFornecedores() {
    const tbody = document.getElementById('tabelaFornecedores');
    const busca = document.getElementById('buscaFornecedor').value.trim().toLowerCase();
    const lista = busca ? fornecedores.filter(f => f.toLowerCase().includes(busca)) : fornecedores;

    document.getElementById('totalFornecedores').textContent =
        `${lista.length} de ${fornecedores.length}`;

    if (!lista.length) {
        tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhum fornecedor encontrado.</td></tr>`;
        return;
    }
    tbody.innerHTML = lista.map(f => `
        <tr>
            <td style="font-size:0.8125rem;">${esc(f)}</td>
            <td style="text-align:center;">
                <button class="btn btn-outline" onclick="removerFornecedor('${esc(f)}')" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Remover">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`).join('');
}

async function adicionarFornecedor() {
    const nome = document.getElementById('inputNovoFornecedor').value.trim();
    if (!nome) { toast.warning('Informe um nome.'); return; }
    try {
        const { error } = await db.from('fornecedores').insert({ nome });
        if (error) throw error;
        toast.success(`"${nome}" adicionado.`);
        document.getElementById('inputNovoFornecedor').value = '';
        await recarregarFornecedores();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function removerFornecedor(nome) {
    if (!confirm(`Remover o fornecedor "${nome}"?`)) return;
    try {
        const { error } = await db.from('fornecedores').delete().eq('nome', nome);
        if (error) throw error;
        toast.success(`"${nome}" removido.`);
        await recarregarFornecedores();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function recarregarFornecedores() {
    const { data } = await db.from('fornecedores').select('nome').order('nome');
    fornecedores = (data || []).map(r => r.nome);
    renderizarFornecedores();
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

// ============================================================
// BANCOS
// ============================================================
function renderizarBancos() {
    const tbody = document.getElementById('tabelaBancos');
    if (!bancos.length) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-8);">Nenhum banco cadastrado.</td></tr>`;
        return;
    }
    const badgePrincipal = `<span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:0.7rem;font-weight:700;background:color-mix(in srgb,var(--warning,#f59e0b) 20%,transparent);color:var(--warning,#b45309);">Principal</span>`;
    const badgeFilho     = `<span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:0.7rem;font-weight:700;background:color-mix(in srgb,var(--primary) 15%,transparent);color:var(--primary);">Filho</span>`;
    const badgeTodas     = `<span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:0.7rem;font-weight:600;background:var(--surface-low);color:var(--on-surface-muted);">Todas</span>`;
    tbody.innerHTML = bancos.map(b => {
        const obras = bancosObras[b.id] || [];
        const obrasHtml = obras.length
            ? obras.map(o => `<span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:0.7rem;font-weight:600;background:color-mix(in srgb,var(--success,#16a34a) 12%,transparent);color:var(--success,#16a34a);margin:1px;">${esc(o)}</span>`).join('')
            : badgeTodas;
        return `
        <tr>
            <td style="font-weight:500;">${esc(b.nome)}</td>
            <td style="text-align:center;">${b.tipo === 'principal' ? badgePrincipal : badgeFilho}</td>
            <td>
                <div style="display:flex;align-items:center;gap:var(--sp-2);flex-wrap:wrap;">
                    ${obrasHtml}
                    <button class="btn btn-outline" onclick="abrirModalObras(${b.id}, '${esc(b.nome)}')" style="font-size:0.7rem;padding:2px 8px;" title="Configurar obras">⚙</button>
                </div>
            </td>
            <td style="text-align:center;">
                <button class="btn btn-outline" onclick="removerBanco(${b.id}, '${esc(b.nome)}')" style="font-size:0.72rem;padding:3px 8px;color:var(--error);border-color:var(--error);" title="Remover">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                    </svg>
                </button>
            </td>
        </tr>`;
    }).join('');
}

function popularCheckboxesNovoBanco() {
    const container = document.getElementById('novoBancoObrasCheckboxes');
    if (!container) return;
    if (!obras.length) {
        container.innerHTML = '<span style="color:var(--on-surface-muted);font-size:0.8rem;">Nenhuma obra cadastrada.</span>';
        return;
    }
    container.innerHTML = obras.map(o => `
        <label style="display:flex;align-items:center;gap:var(--sp-2);cursor:pointer;font-size:0.875rem;">
            <input type="checkbox" value="${esc(o.nome)}" style="accent-color:var(--primary);">
            ${esc(o.nome)}
        </label>`).join('');
}

async function adicionarBanco() {
    const nome      = document.getElementById('inputNovoBanco').value.trim();
    const tipo      = document.getElementById('selectTipoBanco').value;
    const descricao = document.getElementById('inputDescricaoBanco').value.trim() || null;
    if (!nome) { toast.warning('Informe um nome.'); return; }

    const obrasChecked = [...document.querySelectorAll('#novoBancoObrasCheckboxes input[type=checkbox]:checked')]
        .map(el => el.value);

    try {
        const { data, error } = await db.from('bancos').insert({ nome, tipo, descricao }).select('id').single();
        if (error) throw error;

        if (obrasChecked.length) {
            const { error: errOb } = await db.from('banco_obras')
                .insert(obrasChecked.map(o => ({ banco_id: data.id, obra: o })));
            if (errOb && errOb.code !== '42P01') throw errOb;
        }

        toast.success(`Banco "${nome}" adicionado.`);
        document.getElementById('inputNovoBanco').value      = '';
        document.getElementById('inputDescricaoBanco').value = '';
        // Desmarca todos os checkboxes
        document.querySelectorAll('#novoBancoObrasCheckboxes input[type=checkbox]')
            .forEach(el => { el.checked = false; });
        await recarregarBancos();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function removerBanco(id, nome) {
    if (!confirm(`Remover o banco "${nome}"?`)) return;
    try {
        const { error } = await db.from('bancos').delete().eq('id', id);
        if (error) throw error;
        toast.success(`"${nome}" removido.`);
        await recarregarBancos();
    } catch (e) {
        toast.error('Erro: ' + e.message);
    }
}

async function recarregarBancos() {
    const { data: dataBancos } = await db.from('bancos').select('id,nome,tipo,descricao').order('tipo').order('nome');
    bancos = dataBancos || [];

    bancosObras = {};
    try {
        const { data: dataObrasBanco } = await db.from('banco_obras').select('banco_id,obra');
        for (const bo of (dataObrasBanco || [])) {
            if (!bancosObras[bo.banco_id]) bancosObras[bo.banco_id] = [];
            bancosObras[bo.banco_id].push(bo.obra);
        }
    } catch (_) { /* tabela ainda não existe */ }

    renderizarBancos();
}

// --- Modal obras por banco ---
async function abrirModalObras(bancoId, bancoNome) {
    document.getElementById('modalObrasBancoId').value = bancoId;
    document.getElementById('modalObrasBancoTitulo').textContent = `Obras — ${bancoNome}`;

    const associadas = new Set(bancosObras[bancoId] || []);
    const container  = document.getElementById('modalObrasCheckboxes');
    container.innerHTML = obras.length
        ? obras.map(o => `
            <label style="display:flex;align-items:center;gap:var(--sp-2);cursor:pointer;padding:var(--sp-2);border-radius:var(--radius-sm);transition:background .12s;" onmouseover="this.style.background='var(--surface-low)'" onmouseout="this.style.background='transparent'">
                <input type="checkbox" value="${esc(o.nome)}" ${associadas.has(o.nome) ? 'checked' : ''} style="accent-color:var(--primary);width:16px;height:16px;">
                <span style="font-size:0.875rem;">${esc(o.nome)}</span>
            </label>`).join('')
        : '<p style="color:var(--on-surface-muted);font-size:0.875rem;">Nenhuma obra cadastrada.</p>';

    document.getElementById('modalObrasBanco').style.display = 'flex';
}

function fecharModalObras() {
    document.getElementById('modalObrasBanco').style.display = 'none';
}

async function salvarObrasDoBanco() {
    const bancoId = parseInt(document.getElementById('modalObrasBancoId').value);
    const checked = [...document.querySelectorAll('#modalObrasCheckboxes input[type=checkbox]:checked')]
        .map(el => el.value);

    try {
        const { error: errDel } = await db.from('banco_obras').delete().eq('banco_id', bancoId);
        if (errDel) {
            if (errDel.code === '42P01') {
                toast.error('Execute a migration 12_banco_obras.sql no Supabase antes de usar esta função.');
                return;
            }
            throw errDel;
        }
        if (checked.length) {
            const { error } = await db.from('banco_obras').insert(checked.map(o => ({ banco_id: bancoId, obra: o })));
            if (error) throw error;
        }
        toast.success('Obras atualizadas.');
        fecharModalObras();
        await recarregarBancos();
    } catch (e) {
        toast.error('Erro ao salvar obras: ' + e.message);
    }
}

// ============================================================
// WIZARD: NOVA OBRA
// ============================================================
let wizardAberto = false;
let _wizPreviousEmpresaIds = [];
let wiz = { step: 1, nome: '', empresa_id: null, descricao: null, contrato: null, art: null, etapas: [], orcamentos: {} };

function abrirWizard() {
    wizardAberto = true;
    wiz = { step: 1, nome: '', empresa_id: null, descricao: null, contrato: null, art: null, etapas: [], orcamentos: {} };
    document.getElementById('wNome').value     = '';
    document.getElementById('wDescricao').value = '';
    document.getElementById('wContrato').value  = '';
    document.getElementById('wArt').value       = '';
    wizPopularEmpresaSelect();
    wizSetStep(1);
    document.getElementById('modalWizardObra').style.display = 'flex';
}

function fecharWizard() {
    wizardAberto = false;
    document.getElementById('modalWizardObra').style.display = 'none';
}

function wizPopularEmpresaSelect(autoSelecionarId = null) {
    const sel = document.getElementById('wEmpresaId');
    sel.innerHTML = `<option value="">— Sem empresa —</option>` +
        empresas.map(e => `<option value="${e.id}">${esc(e.nome)}</option>`).join('');
    if (autoSelecionarId) sel.value = autoSelecionarId;
}

function wizSetStep(n) {
    wiz.step = n;

    for (let i = 1; i <= 4; i++) {
        document.getElementById(`wizStep${i}`).style.display = i === n ? 'block' : 'none';
    }

    for (let i = 1; i <= 4; i++) {
        const ind = document.getElementById(`wizInd${i}`);
        const dot = ind.querySelector('.wiz-dot');
        ind.className = 'wiz-ind' + (i === n ? ' active' : i < n ? ' done' : '');
        if (i < n) {
            dot.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        } else {
            dot.textContent = i;
        }
    }

    document.getElementById('wizBtnAnterior').style.display = n > 1 ? 'inline-flex' : 'none';
    document.getElementById('wizBtnProximo').textContent = n === 4 ? 'Criar Obra' : 'Próximo →';

    if (n === 2) wizRenderizarChips();
    if (n === 3) wizRenderizarGridOrcamentos();
    if (n === 4) wizRenderizarRevisao();
}

async function wizNext() {
    if (wiz.step === 1) {
        const nome = document.getElementById('wNome').value.trim();
        if (!nome) { toast.warning('Nome da obra é obrigatório.'); return; }
        if (obras.find(o => o.nome === nome)) { toast.warning(`Já existe uma obra com o nome "${nome}".`); return; }
        wiz.nome      = nome;
        const empVal  = document.getElementById('wEmpresaId').value;
        wiz.empresa_id = empVal ? parseInt(empVal) : null;
        wiz.descricao = document.getElementById('wDescricao').value.trim() || null;
        wiz.contrato  = document.getElementById('wContrato').value.trim()  || null;
        wiz.art       = document.getElementById('wArt').value.trim()       || null;
        wizSetStep(2);

    } else if (wiz.step === 2) {
        const selected = wizGetEtapasSelecionadas();
        if (!selected.length) { toast.warning('Selecione ao menos uma etapa.'); return; }
        wiz.etapas = selected;
        wiz.orcamentos = {};
        for (const et of wiz.etapas) {
            wiz.orcamentos[et] = {};
            for (const tipo of tiposCusto) wiz.orcamentos[et][tipo] = 0;
        }
        wizSetStep(3);

    } else if (wiz.step === 3) {
        wizColetarOrcamentos();
        wizSetStep(4);

    } else if (wiz.step === 4) {
        await criarObraCompleta();
    }
}

function wizPrev() {
    if (wiz.step > 1) wizSetStep(wiz.step - 1);
}

// ── Step 2: Etapas ──────────────────────────────────────────

function wizGetEtapasSelecionadas() {
    return Array.from(document.querySelectorAll('#wizChipsEtapas .wiz-chip.selected'))
        .map(chip => chip.dataset.etapa);
}

function wizRenderizarChips() {
    const container = document.getElementById('wizChipsEtapas');
    if (!etapas.length) {
        container.innerHTML = `<p style="color:var(--on-surface-muted);font-size:0.875rem;">Nenhuma etapa cadastrada. Adicione uma abaixo.</p>`;
    } else {
        container.innerHTML = etapas.map(et => {
            const sel = wiz.etapas.includes(et.nome);
            return `<div class="wiz-chip${sel ? ' selected' : ''}" data-etapa="${esc(et.nome)}" onclick="this.classList.toggle('selected')">${esc(et.nome)}</div>`;
        }).join('');
    }
    // Reset inline form
    document.getElementById('wNovaEtapaNome').style.display    = 'none';
    document.getElementById('wizBtnConfirmarEtapa').style.display = 'none';
    document.getElementById('wizBtnCancelarEtapa').style.display  = 'none';
    document.getElementById('wizBtnNovaEtapa').style.display      = 'inline-flex';
}

function wizToggleNovaEtapa() {
    const input      = document.getElementById('wNovaEtapaNome');
    const btnNovaEt  = document.getElementById('wizBtnNovaEtapa');
    const btnConfirm = document.getElementById('wizBtnConfirmarEtapa');
    const btnCancel  = document.getElementById('wizBtnCancelarEtapa');
    const showing = input.style.display !== 'none';
    if (showing) {
        input.style.display = 'none';
        btnConfirm.style.display = 'none';
        btnCancel.style.display  = 'none';
        btnNovaEt.style.display  = 'inline-flex';
        input.value = '';
    } else {
        input.style.display = 'block';
        btnConfirm.style.display = 'inline-flex';
        btnCancel.style.display  = 'inline-flex';
        btnNovaEt.style.display  = 'none';
        input.focus();
    }
}

async function wizAdicionarEtapa() {
    const nome = document.getElementById('wNovaEtapaNome').value.trim();
    if (!nome) { toast.warning('Informe o nome da etapa.'); return; }

    const btn = document.getElementById('wizBtnConfirmarEtapa');
    btn.disabled = true; btn.textContent = 'Adicionando…';

    try {
        const { error } = await db.from('etapas').insert({ nome, ordem: 999 });
        if (error) throw error;

        // Preserve current chip selection + add new
        const currentSelected = wizGetEtapasSelecionadas();
        wiz.etapas = [...new Set([...currentSelected, nome])];

        // Reload global etapas
        const { data } = await db.from('etapas').select('nome,ordem').order('ordem');
        etapas = data || [];

        wizRenderizarChips(); // re-renders with wiz.etapas for selection
        toast.success(`Etapa "${nome}" adicionada.`);
    } catch (e) {
        toast.error('Erro: ' + e.message);
        btn.disabled = false; btn.textContent = 'Adicionar';
    }
}

// ── Step 3: Orçamentos ───────────────────────────────────────

function wizRenderizarGridOrcamentos() {
    const wrap = document.getElementById('wizGridOrcamentos');
    if (!wiz.etapas.length || !tiposCusto.length) {
        wrap.innerHTML = '<p style="color:var(--on-surface-muted);">Sem etapas ou tipos de custo configurados.</p>';
        return;
    }

    const cols   = tiposCusto;
    const header = `<tr><th>Etapa</th>${cols.map(c => `<th class="text-right">${esc(c)}</th>`).join('')}<th class="text-right">Total</th></tr>`;

    const bodyRows = wiz.etapas.map(et => {
        const inputs = cols.map(c => {
            const val = (wiz.orcamentos[et] || {})[c] || 0;
            return `<td><input type="number" class="form-input" data-et="${esc(et)}" data-tipo="${esc(c)}"
                value="${val}" min="0" step="0.01"
                style="width:100%;padding:4px 8px;font-size:0.875rem;text-align:right;font-variant-numeric:tabular-nums;"
                oninput="wizAtualizarTotais()"></td>`;
        }).join('');
        const rowTotal = cols.reduce((s, c) => s + ((wiz.orcamentos[et] || {})[c] || 0), 0);
        return `<tr>
            <td style="font-weight:500;">${esc(et)}</td>
            ${inputs}
            <td class="text-right" data-row-total="${esc(et)}" style="font-variant-numeric:tabular-nums;color:var(--on-surface-muted);">R$ ${formatarValor(rowTotal)}</td>
        </tr>`;
    }).join('');

    const colTotals = cols.map(c => {
        const total = wiz.etapas.reduce((s, et) => s + ((wiz.orcamentos[et] || {})[c] || 0), 0);
        return `<td class="text-right" data-col-total="${esc(c)}" style="font-weight:600;font-variant-numeric:tabular-nums;">R$ ${formatarValor(total)}</td>`;
    }).join('');
    const grand = wiz.etapas.reduce((s, et) => s + cols.reduce((ss, c) => ss + ((wiz.orcamentos[et] || {})[c] || 0), 0), 0);
    const totaisRow = `<tr style="background:var(--surface-low);">
        <td style="font-weight:600;">Total</td>
        ${colTotals}
        <td class="text-right" id="wizGrandTotal" style="font-weight:700;font-variant-numeric:tabular-nums;">R$ ${formatarValor(grand)}</td>
    </tr>`;

    wrap.innerHTML = `<div class="table-wrapper"><table class="styled-table">
        <thead>${header}</thead>
        <tbody>${bodyRows}${totaisRow}</tbody>
    </table></div>`;
}

function wizAtualizarTotais() {
    const cols      = tiposCusto;
    const etapasArr = wiz.etapas;

    // Collect current values from DOM
    const vals = {};
    for (const inp of document.querySelectorAll('#wizGridOrcamentos input[data-et]')) {
        const et = inp.dataset.et, tipo = inp.dataset.tipo;
        if (!vals[et]) vals[et] = {};
        vals[et][tipo] = parseFloat(inp.value) || 0;
    }

    // Row totals
    for (const el of document.querySelectorAll('#wizGridOrcamentos [data-row-total]')) {
        const et = el.dataset.rowTotal;
        el.textContent = `R$ ${formatarValor(cols.reduce((s, c) => s + ((vals[et] || {})[c] || 0), 0))}`;
    }

    // Col totals
    let grand = 0;
    for (const el of document.querySelectorAll('#wizGridOrcamentos [data-col-total]')) {
        const tipo  = el.dataset.colTotal;
        const total = etapasArr.reduce((s, et) => s + ((vals[et] || {})[tipo] || 0), 0);
        grand += total;
        el.textContent = `R$ ${formatarValor(total)}`;
    }

    const grandEl = document.getElementById('wizGrandTotal');
    if (grandEl) grandEl.textContent = `R$ ${formatarValor(grand)}`;
}

function wizColetarOrcamentos() {
    wiz.orcamentos = {};
    for (const inp of document.querySelectorAll('#wizGridOrcamentos input[data-et]')) {
        const et = inp.dataset.et, tipo = inp.dataset.tipo;
        if (!wiz.orcamentos[et]) wiz.orcamentos[et] = {};
        wiz.orcamentos[et][tipo] = parseFloat(inp.value) || 0;
    }
}

// ── Step 4: Revisão ──────────────────────────────────────────

function wizRenderizarRevisao() {
    const empresa = wiz.empresa_id ? empresas.find(e => e.id === wiz.empresa_id) : null;

    const orcRows = [];
    for (const [et, tipos] of Object.entries(wiz.orcamentos)) {
        for (const [tipo, val] of Object.entries(tipos)) {
            if (val > 0) orcRows.push({ et, tipo, val });
        }
    }

    const orcHtml = orcRows.length
        ? `<div class="table-wrapper" style="margin-top:var(--sp-2);">
            <table class="styled-table">
                <thead><tr><th>Etapa</th><th>Tipo de Custo</th><th class="text-right">Valor Est.</th></tr></thead>
                <tbody>${orcRows.map(r => `<tr>
                    <td>${esc(r.et)}</td>
                    <td>${esc(r.tipo)}</td>
                    <td class="text-right">R$ ${formatarValor(r.val)}</td>
                </tr>`).join('')}</tbody>
            </table></div>`
        : `<p style="font-size:0.875rem;color:var(--on-surface-muted);margin-top:var(--sp-2);">Nenhum orçamento preenchido — configure depois pela aba Orçamentos.</p>`;

    document.getElementById('wizResumo').innerHTML = `
        <div style="display:grid;gap:var(--sp-4);">
            <div style="background:var(--surface-low);border-radius:var(--radius-md);padding:var(--sp-4);">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-3);">
                    <div>
                        <p style="font-size:0.75rem;color:var(--on-surface-muted);margin-bottom:2px;">Nome</p>
                        <p style="font-weight:600;">${esc(wiz.nome)}</p>
                    </div>
                    <div>
                        <p style="font-size:0.75rem;color:var(--on-surface-muted);margin-bottom:2px;">Empresa</p>
                        <p style="font-weight:600;">${empresa ? esc(empresa.nome) : '—'}</p>
                    </div>
                    ${wiz.descricao ? `<div>
                        <p style="font-size:0.75rem;color:var(--on-surface-muted);margin-bottom:2px;">Descrição</p>
                        <p>${esc(wiz.descricao)}</p></div>` : ''}
                    ${wiz.contrato ? `<div>
                        <p style="font-size:0.75rem;color:var(--on-surface-muted);margin-bottom:2px;">Contrato</p>
                        <p>${esc(wiz.contrato)}</p></div>` : ''}
                    ${wiz.art ? `<div style="grid-column:1/-1;">
                        <p style="font-size:0.75rem;color:var(--on-surface-muted);margin-bottom:2px;">ART</p>
                        <p>${esc(wiz.art)}</p></div>` : ''}
                </div>
            </div>
            <div>
                <p style="font-size:0.8125rem;font-weight:600;margin-bottom:var(--sp-2);">Etapas (${wiz.etapas.length})</p>
                <div style="display:flex;flex-wrap:wrap;gap:var(--sp-2);">
                    ${wiz.etapas.map(et => `<span style="background:color-mix(in srgb,var(--primary) 15%,transparent);color:var(--primary);border:1px solid var(--primary);padding:3px 12px;border-radius:20px;font-size:0.8125rem;font-weight:500;">${esc(et)}</span>`).join('')}
                </div>
            </div>
            <div>
                <p style="font-size:0.8125rem;font-weight:600;margin-bottom:var(--sp-2);">Orçamentos</p>
                ${orcHtml}
            </div>
        </div>`;
}

// ── Sub-popup: Empresa ────────────────────────────────────────

function wizAbrirNovaEmpresa() {
    _wizPreviousEmpresaIds = empresas.map(e => e.id);
    document.getElementById('modalEmpresa').style.zIndex = '1100';
    abrirModalEmpresa(null);
}

async function wizEmpresaFechada() {
    const { data } = await db.from('empresas').select('*').order('nome');
    empresas = data || [];
    renderizarEmpresas();
    const novaEmpresa = empresas.find(e => !_wizPreviousEmpresaIds.includes(e.id));
    wizPopularEmpresaSelect(novaEmpresa ? novaEmpresa.id : null);
}

// ── Salvar ───────────────────────────────────────────────────

async function criarObraCompleta() {
    const btn = document.getElementById('wizBtnProximo');
    btn.disabled = true; btn.textContent = 'Criando…';

    try {
        // 1. obras
        const { error: obraErr } = await db.from('obras').insert({
            nome:       wiz.nome,
            empresa_id: wiz.empresa_id,
            descricao:  wiz.descricao,
            contrato:   wiz.contrato,
            art:        wiz.art,
        });
        if (obraErr) throw obraErr;

        // 2. obra_etapas
        const { error: etErr } = await db.from('obra_etapas')
            .insert(wiz.etapas.map(e => ({ obra: wiz.nome, etapa: e })));
        if (etErr) throw etErr;

        // 3. orcamentos (apenas não-zeros)
        const orcRows = [];
        for (const [et, tipos] of Object.entries(wiz.orcamentos)) {
            for (const [tipo_custo, valor_estimado] of Object.entries(tipos)) {
                if (valor_estimado > 0) orcRows.push({ obra: wiz.nome, etapa: et, tipo_custo, valor_estimado });
            }
        }
        if (orcRows.length) {
            const { error: orcErr } = await db.from('orcamentos')
                .upsert(orcRows, { onConflict: 'obra,etapa,tipo_custo' });
            if (orcErr) throw orcErr;
        }

        fecharWizard();
        await carregarReferencias();
        toast.success(`Obra "${wiz.nome}" criada com sucesso!`);
    } catch (e) {
        toast.error('Erro ao criar obra: ' + e.message);
        btn.disabled = false; btn.textContent = 'Criar Obra';
    }
}
