/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Despesas (app.js)
 */

const API_BASE = 'http://localhost:8000';

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
let loteArquivos = [];   // { file, nome, dados }

// --- INIT ---
document.addEventListener('DOMContentLoaded', async () => {
    carregarEnv();
    await carregarReferencias();

    // Hoje como padrão
    document.getElementById('fData').value = new Date().toISOString().split('T')[0];

    // Upload NF individual
    const inputNF   = document.getElementById('inputNF');
    const uploadZone = document.getElementById('uploadZone');

    uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
    uploadZone.addEventListener('drop', e => {
        e.preventDefault(); uploadZone.classList.remove('drag-over');
        if (e.dataTransfer.files[0]) { inputNF.files = e.dataTransfer.files; handleNFSelecionada(e.dataTransfer.files[0]); }
    });
    inputNF.addEventListener('change', () => { if (inputNF.files[0]) handleNFSelecionada(inputNF.files[0]); });

    // Fornecedor — toggle novo
    document.getElementById('fNovoFornecedorCheck').addEventListener('change', e => {
        const isNovo = e.target.checked;
        document.getElementById('fFornecedor').style.display   = isNovo ? 'none' : '';
        document.getElementById('fNovoFornecedor').style.display = isNovo ? '' : 'none';
    });

    // Botão extrair IA individual
    document.getElementById('btnExtrairIA').addEventListener('click', extrairIAIndividual);

    // Submit individual
    document.getElementById('btnCadastrar').addEventListener('click', cadastrarDespesa);

    // Lote — upload
    const inputLote   = document.getElementById('inputLoteNFs');
    const loteZone    = document.getElementById('loteUploadZone');
    loteZone.addEventListener('dragover', e => { e.preventDefault(); loteZone.classList.add('drag-over'); });
    loteZone.addEventListener('dragleave', () => loteZone.classList.remove('drag-over'));
    loteZone.addEventListener('drop', e => {
        e.preventDefault(); loteZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) handleLoteArquivos(e.dataTransfer.files);
    });
    inputLote.addEventListener('change', () => { if (inputLote.files.length) handleLoteArquivos(inputLote.files); });

    // Lote — botões
    document.getElementById('btnExtrairLote').addEventListener('click', extrairLoteIA);
    document.getElementById('btnLoteLimpar').addEventListener('click', limparLote);
    document.getElementById('btnLoteSalvar').addEventListener('click', salvarLote);
});

// --- REFERÊNCIAS ---
async function carregarReferencias() {
    if (!dbClient) {
        console.error('[despesas] dbClient não inicializado — verifique env.js e supabase-js CDN');
        setStatus('offline', 'Erro de conexão');
        return;
    }
    try {
        const [rObras, rEtapas, rTipos, rCat, rFormas, rForn] = await Promise.all([
            dbClient.from('obras').select('nome').order('nome'),
            dbClient.from('etapas').select('nome, ordem').order('ordem'),
            dbClient.from('tipos_custo').select('nome').order('nome'),
            dbClient.from('categorias_despesa').select('nome').order('nome'),
            dbClient.from('formas_pagamento').select('nome').order('nome'),
            dbClient.from('fornecedores').select('nome').order('nome'),
        ]);

        if (rObras.error)  console.error('[obras]', rObras.error);
        if (rEtapas.error) console.error('[etapas]', rEtapas.error);
        if (rTipos.error)  console.error('[tipos_custo]', rTipos.error);
        if (rCat.error)    console.error('[categorias_despesa]', rCat.error);
        if (rFormas.error) console.error('[formas_pagamento]', rFormas.error);
        if (rForn.error)   console.error('[fornecedores]', rForn.error);

        obras        = (rObras.data  || []).map(r => r.nome);
        etapas       = (rEtapas.data || []).map(r => r.nome);
        tipos        = (rTipos.data  || []).map(r => r.nome);
        categorias   = (rCat.data    || []).map(r => r.nome);
        formas       = (rFormas.data || []).map(r => r.nome);
        fornecedores = (rForn.data   || []).map(r => r.nome);

        console.log('[despesas] refs:', { obras: obras.length, etapas: etapas.length, tipos: tipos.length, categorias: categorias.length, formas: formas.length, fornecedores: fornecedores.length });

        popularSelect('fObra',      obras,        'Selecione a obra...',      false);
        popularSelect('fEtapa',     etapas,       'Selecione a etapa...',     false);
        popularSelect('fTipo',      tipos,        'Selecione o tipo...',      false);
        popularSelect('fDespesa',   categorias,   '—',                        true);
        popularSelect('fForma',     formas,       '—',                        true);
        popularFornecedor();

        popularSelect('lObra', obras, 'Selecione a obra...', false);

        setStatus('online', 'Sistema Sincronizado');
    } catch (e) {
        console.error('[despesas] carregarReferencias falhou:', e);
        setStatus('offline', 'Erro de conexão');
    }
}

function popularSelect(id, opcoes, placeholder, opcional) {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = `<option value="">${placeholder}</option>` +
        opcoes.map(o => `<option value="${o}">${o}</option>`).join('');
}

function popularFornecedor() {
    const sel = document.getElementById('fFornecedor');
    sel.innerHTML =
        `<option value="">Selecione o fornecedor...</option>` +
        fornecedores.map(f => `<option value="${f}">${f}</option>`).join('');
}

// --- MODO TABS ---
function setModo(modo) {
    const isInd = modo === 'individual';
    document.getElementById('modoIndividual').style.display = isInd ? '' : 'none';
    document.getElementById('modoLote').style.display       = isInd ? 'none' : '';
    document.getElementById('tabIndividual').classList.toggle('active', isInd);
    document.getElementById('tabLote').classList.toggle('active', !isInd);
}

// --- UPLOAD NF INDIVIDUAL ---
function handleNFSelecionada(file) {
    document.getElementById('uploadZoneText').textContent = `📎 ${file.name}`;
    document.getElementById('btnExtrairIA').disabled = false;
}

// --- EXTRAIR IA INDIVIDUAL ---
async function extrairIAIndividual() {
    const file = document.getElementById('inputNF').files[0];
    if (!file) return;

    const btn = document.getElementById('btnExtrairIA');
    btn.disabled = true;
    btn.textContent = 'Extraindo…';

    try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${API_BASE}/api/ai/extrair`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error(await res.text());
        const ia = await res.json();

        // Preencher form
        preencherCampoIA('fTipo',       ia.TIPO,       tipos);
        preencherCampoIA('fForma',      ia.FORMA,      formas);
        preencherCampoIA('fDespesa',    ia.DESPESA,    categorias);
        preencherFornecedorIA(ia.FORNECEDOR);
        if (ia.VALOR_TOTAL) document.getElementById('fValor').value = parseFloat(ia.VALOR_TOTAL).toFixed(2);
        if (ia.DATA)        document.getElementById('fData').value  = ia.DATA;
        if (ia.DESCRICAO)   document.getElementById('fDescricao').value = ia.DESCRICAO;

        document.getElementById('iaBanner').style.display = '';
        toast.success('Dados extraídos pela IA. Revise antes de salvar.');
    } catch (e) {
        toast.error(`Erro na extração: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> Extrair com IA`;
    }
}

function preencherCampoIA(selectId, valor, lista) {
    if (!valor) return;
    const sel  = document.getElementById(selectId);
    const norm = valor.trim().toLowerCase();
    const match = lista.find(o => o.toLowerCase() === norm);
    if (match) sel.value = match;
}

function preencherFornecedorIA(nome) {
    if (!nome) return;
    const norm  = nome.trim().toLowerCase();
    const match = fornecedores.find(f => f.toLowerCase() === norm);
    if (match) {
        document.getElementById('fNovoFornecedorCheck').checked   = false;
        document.getElementById('fFornecedor').style.display       = '';
        document.getElementById('fNovoFornecedor').style.display   = 'none';
        document.getElementById('fFornecedor').value               = match;
    } else {
        document.getElementById('fNovoFornecedorCheck').checked   = true;
        document.getElementById('fFornecedor').style.display       = 'none';
        document.getElementById('fNovoFornecedor').style.display   = '';
        document.getElementById('fNovoFornecedor').value           = nome;
    }
}

// --- CADASTRAR INDIVIDUAL ---
async function cadastrarDespesa() {
    const obra       = document.getElementById('fObra').value;
    const etapa      = document.getElementById('fEtapa').value;
    const tipo       = document.getElementById('fTipo').value;
    const isNovo     = document.getElementById('fNovoFornecedorCheck').checked;
    const fornecedor = isNovo
        ? document.getElementById('fNovoFornecedor').value.trim()
        : document.getElementById('fFornecedor').value;
    const valor      = parseFloat(document.getElementById('fValor').value);
    const data       = document.getElementById('fData').value;
    const descricao  = document.getElementById('fDescricao').value.trim();
    const despesa    = document.getElementById('fDespesa').value;
    const forma      = document.getElementById('fForma').value;
    const banco      = document.getElementById('fBanco').value.trim();

    // Validação
    const erros = [];
    if (!obra)          erros.push('Obra é obrigatória.');
    if (!etapa)         erros.push('Etapa é obrigatória.');
    if (!tipo)          erros.push('Tipo é obrigatório.');
    if (!fornecedor)    erros.push('Fornecedor é obrigatório.');
    if (!valor || valor <= 0) erros.push('Valor deve ser maior que zero.');
    if (!data)          erros.push('Data é obrigatória.');
    if (!descricao)     erros.push('Descrição é obrigatória.');
    if (erros.length) { erros.forEach(e => toast.error(e)); return; }

    const btn = document.getElementById('btnCadastrar');
    btn.disabled = true;

    try {
        // Upload NF (se houver arquivo)
        let comprovante_url = null;
        let tem_nota_fiscal = false;
        const fileNF = document.getElementById('inputNF').files[0];
        if (fileNF) {
            comprovante_url = await uploadComprovante(fileNF);
            tem_nota_fiscal = comprovante_url !== null;
        }

        // Upsert fornecedor
        if (fornecedor) {
            await dbClient.from('fornecedores').upsert({ nome: fornecedor }, { onConflict: 'nome' });
            if (!fornecedores.includes(fornecedor)) {
                fornecedores.push(fornecedor);
                popularFornecedor();
            }
        }

        // Insert despesa
        const { error } = await dbClient.from('c_despesas').insert({
            obra, etapa, tipo,
            fornecedor:      fornecedor || null,
            valor_total:     valor,
            data,
            descricao:       descricao || null,
            despesa:         despesa   || null,
            banco:           banco     || null,
            forma:           forma     || null,
            tem_nota_fiscal,
            comprovante_url,
        });
        if (error) throw error;

        toast.success('Despesa cadastrada com sucesso!');
        limparFormIndividual();
    } catch (e) {
        toast.error(`Erro ao cadastrar: ${e.message}`);
    } finally {
        btn.disabled = false;
    }
}

function limparFormIndividual() {
    ['fObra','fEtapa','fTipo','fFornecedor','fDespesa','fForma'].forEach(id => {
        document.getElementById(id).selectedIndex = 0;
    });
    ['fNovoFornecedor','fBanco','fDescricao'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('fValor').value = '';
    document.getElementById('fData').value  = new Date().toISOString().split('T')[0];
    document.getElementById('fNovoFornecedorCheck').checked  = false;
    document.getElementById('fFornecedor').style.display      = '';
    document.getElementById('fNovoFornecedor').style.display  = 'none';
    document.getElementById('iaBanner').style.display = 'none';
    document.getElementById('uploadZoneText').textContent = 'Arraste ou clique para anexar NF (PDF, JPG, PNG)';
    document.getElementById('btnExtrairIA').disabled = true;
    document.getElementById('inputNF').value = '';
}

// --- UPLOAD STORAGE ---
async function uploadComprovante(file) {
    try {
        const ext  = file.name.rsplit ? file.name.rsplit('.', 1)[1].toLowerCase() : file.name.split('.').pop().toLowerCase();
        const nome = `nf_${crypto.randomUUID().replace(/-/g,'').slice(0,12)}.${ext}`;
        const { error } = await dbClient.storage.from('comprovantes').upload(nome, file, { contentType: file.type });
        if (error) throw error;
        const base = window.ENV.SUPABASE_URL.replace(/\/$/, '');
        return `${base}/storage/v1/object/public/comprovantes/${nome}`;
    } catch (e) {
        toast.warning(`Nota fiscal não pôde ser salva: ${e.message}`);
        return null;
    }
}

// --- LOTE ---
function handleLoteArquivos(fileList) {
    loteArquivos = Array.from(fileList).map(f => ({ file: f, nome: f.name, dados: null }));
    const txt = loteArquivos.length === 1
        ? `📎 ${loteArquivos[0].nome}`
        : `📎 ${loteArquivos.length} arquivo(s) selecionado(s)`;
    document.getElementById('loteUploadText').textContent = txt;
    document.getElementById('btnExtrairLote').disabled = loteArquivos.length === 0;
    document.getElementById('loteRevisaoWrap').style.display = 'none';
}

async function extrairLoteIA() {
    if (!loteArquivos.length) return;

    const obra  = document.getElementById('lObra').value;
    if (!obra) { toast.warning('Selecione a obra antes de extrair.'); return; }

    document.getElementById('btnExtrairLote').disabled = true;
    document.getElementById('loteProgresso').style.display = 'flex';

    for (let i = 0; i < loteArquivos.length; i++) {
        const item = loteArquivos[i];
        document.getElementById('loteProgressoText').textContent =
            `Extraindo ${i + 1}/${loteArquivos.length}: ${item.nome}`;
        try {
            const formData = new FormData();
            formData.append('file', item.file);
            const res = await fetch(`${API_BASE}/api/ai/extrair`, { method: 'POST', body: formData });
            item.dados = res.ok ? await res.json() : {};
        } catch (_) {
            item.dados = {};
        }
        item.dados.OBRA = item.dados.OBRA || obra;
    }

    document.getElementById('loteProgresso').style.display = 'none';
    document.getElementById('btnExtrairLote').disabled = false;
    renderizarTabeLote();
}

function renderizarTabeLote() {
    const loteEtapa = '';
    const tbody = document.getElementById('loteTableBody');
    tbody.innerHTML = '';

    loteArquivos.forEach((item, idx) => {
        const d = item.dados || {};
        const tr = document.createElement('tr');
        const fornMatch = fornecedores.find(f => f.toLowerCase() === (d.FORNECEDOR || '').toLowerCase());
        const fornIsNovo = d.FORNECEDOR && !fornMatch;
        tr.innerHTML = `
            <td style="font-size:0.8125rem;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${item.nome}">${item.nome}</td>
            <td style="min-width:160px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
                    <label style="display:flex;align-items:center;gap:4px;font-size:0.75rem;cursor:pointer;color:var(--on-surface-muted);">
                        <input type="checkbox" class="forn-novo-check" data-idx="${idx}" ${fornIsNovo ? 'checked' : ''} style="cursor:pointer;"> Novo
                    </label>
                </div>
                <select class="form-select form-select-sm forn-select" data-idx="${idx}" data-field="FORNECEDOR" style="${fornIsNovo ? 'display:none;' : ''}">
                    <option value="">—</option>
                    ${fornecedores.map(f => `<option value="${f}" ${(fornMatch && fornMatch===f)?'selected':''}>${f}</option>`).join('')}
                </select>
                <input type="text" class="form-input form-input-sm forn-input" data-idx="${idx}" data-field="FORNECEDOR" placeholder="Nome do fornecedor..." value="${fornIsNovo ? d.FORNECEDOR : ''}" style="${fornIsNovo ? '' : 'display:none;'}">
            </td>
            <td><input class="form-input form-input-sm" data-idx="${idx}" data-field="DESCRICAO"  value="${d.DESCRICAO  || ''}" placeholder="Descrição"></td>
            <td>
                <select class="form-select form-select-sm" data-idx="${idx}" data-field="TIPO">
                    <option value="">—</option>
                    ${tipos.map(t => `<option value="${t}" ${d.TIPO===t?'selected':''}>${t}</option>`).join('')}
                </select>
            </td>
            <td>
                <select class="form-select form-select-sm" data-idx="${idx}" data-field="ETAPA">
                    <option value="">—</option>
                    ${etapas.map(e => `<option value="${e}" ${(d.ETAPA||loteEtapa)===e?'selected':''}>${e}</option>`).join('')}
                </select>
            </td>
            <td><input type="date" class="form-input form-input-sm" data-idx="${idx}" data-field="DATA" value="${d.DATA || ''}"></td>
            <td><input type="number" class="form-input form-input-sm text-right" data-idx="${idx}" data-field="VALOR_TOTAL" value="${d.VALOR_TOTAL || ''}" step="0.01" min="0"></td>
            <td>
                <select class="form-select form-select-sm" data-idx="${idx}" data-field="FORMA">
                    <option value="">—</option>
                    ${formas.map(f => `<option value="${f}" ${d.FORMA===f?'selected':''}>${f}</option>`).join('')}
                </select>
            </td>
            <td>
                <button class="btn-icon-sm text-error" onclick="removerItemLote(${idx})" title="Remover">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </td>`;
        tbody.appendChild(tr);
    });

    // Atualizar dados ao editar
    tbody.querySelectorAll('[data-idx]').forEach(el => {
        el.addEventListener('change', e => {
            const idx   = parseInt(e.target.dataset.idx);
            const field = e.target.dataset.field;
            loteArquivos[idx].dados[field] = e.target.value;
        });
    });

    // Fornecedor — toggle novo por linha
    tbody.querySelectorAll('.forn-novo-check').forEach(chk => {
        chk.addEventListener('change', e => {
            const i   = parseInt(e.target.dataset.idx);
            const row = tbody.querySelector(`.forn-select[data-idx="${i}"]`).closest('td');
            const sel = row.querySelector('.forn-select');
            const inp = row.querySelector('.forn-input');
            const isNovo = e.target.checked;
            sel.style.display = isNovo ? 'none' : '';
            inp.style.display = isNovo ? '' : 'none';
            loteArquivos[i].dados.FORNECEDOR = isNovo ? inp.value.trim() : sel.value;
        });
    });

    document.getElementById('loteRevisaoWrap').style.display = loteArquivos.length ? '' : 'none';
}

function removerItemLote(idx) {
    loteArquivos.splice(idx, 1);
    if (loteArquivos.length === 0) {
        limparLote();
    } else {
        renderizarTabeLote();
    }
}

function limparLote() {
    loteArquivos = [];
    document.getElementById('loteUploadText').textContent = 'Arraste ou clique para selecionar NFs';
    document.getElementById('btnExtrairLote').disabled = true;
    document.getElementById('loteRevisaoWrap').style.display = 'none';
    document.getElementById('inputLoteNFs').value = '';
}

async function salvarLote() {
    const obra = document.getElementById('lObra').value;
    if (!obra) { toast.warning('Selecione a obra.'); return; }
    if (!loteArquivos.length) return;

    const btn = document.getElementById('btnLoteSalvar');
    btn.disabled = true;

    let ok = 0, erros = 0;
    for (const item of loteArquivos) {
        const d = item.dados || {};
        const valor = parseFloat(d.VALOR_TOTAL);
        if (!valor || valor <= 0) { erros++; continue; }
        try {
            let comprovante_url = null;
            comprovante_url = await uploadComprovante(item.file);

            const fornecedor = (d.FORNECEDOR || '').trim();
            if (fornecedor) {
                await dbClient.from('fornecedores').upsert({ nome: fornecedor }, { onConflict: 'nome' });
            }

            const { error } = await dbClient.from('c_despesas').insert({
                obra:           d.OBRA  || obra,
                etapa:          d.ETAPA || etapa,
                tipo:           d.TIPO  || null,
                fornecedor:     fornecedor || null,
                valor_total:    valor,
                data:           d.DATA  || null,
                descricao:      (d.DESCRICAO  || '').trim() || null,
                despesa:        (d.DESPESA    || '') || null,
                forma:          (d.FORMA      || '') || null,
                tem_nota_fiscal: comprovante_url !== null,
                comprovante_url,
            });
            if (error) throw error;
            ok++;
        } catch (_) {
            erros++;
        }
    }

    btn.disabled = false;
    if (ok > 0)    toast.success(`${ok} despesa(s) cadastrada(s) com sucesso!`);
    if (erros > 0) toast.warning(`${erros} item(s) ignorado(s) por valor inválido ou erro.`);
    if (ok > 0) limparLote();
}

// --- HELPERS ---
function setStatus(type, text) {
    const el = document.getElementById('connectionStatus');
    if (!el) return;
    el.textContent = text;
    el.className   = `status-dot ${type}`;
}
