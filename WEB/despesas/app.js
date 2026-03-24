/**
 * INDUSTRIAL ARCHITECT — Finance Suite
 * Despesas (app.js)
 */

const API_BASE = `http://${location.hostname}:8000`;

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
    initUploadZoneTexto();

    // Hoje como padrão
    document.getElementById('fData').value = new Date().toISOString().split('T')[0];

    // Prefill enviado pelo chat de IA (via sessionStorage)
    const prefillRaw = sessionStorage.getItem('ai_despesa_prefill');
    if (prefillRaw) {
        try {
            const ia = JSON.parse(prefillRaw);
            sessionStorage.removeItem('ai_despesa_prefill');
            preencherCampoIA('fTipo',    ia.TIPO,    tipos);
            preencherCampoIA('fForma',   ia.FORMA,   formas);
            preencherCampoIA('fDespesa', ia.DESPESA, categorias);
            preencherCampoIA('fObra',    ia.OBRA,    obras);
            preencherCampoIA('fEtapa',   ia.ETAPA,   etapas);
            preencherFornecedorIA(ia.FORNECEDOR);
            if (ia.VALOR_TOTAL) document.getElementById('fValor').value = parseFloat(ia.VALOR_TOTAL).toFixed(2);
            if (ia.DATA)        document.getElementById('fData').value  = ia.DATA;
            if (ia.DESCRICAO)   document.getElementById('fDescricao').value = ia.DESCRICAO;
            document.getElementById('iaBanner').style.display = '';
        } catch (_) {}
    }

    // Upload NF individual
    const inputNF   = document.getElementById('inputNF');
    const uploadZone = document.getElementById('uploadZone');

    uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
    uploadZone.addEventListener('drop', e => {
        e.preventDefault(); uploadZone.classList.remove('drag-over');
        if (e.dataTransfer.files[0]) { inputNF.files = e.dataTransfer.files; handleNFSelecionada(e.dataTransfer.files); }
    });
    inputNF.addEventListener('change', () => { if (inputNF.files[0]) handleNFSelecionada(inputNF.files); });

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
    document.getElementById('modoIndividual').style.display = modo === 'individual' ? '' : 'none';
    document.getElementById('modoLote').style.display       = modo === 'lote'       ? '' : 'none';
    document.getElementById('modoTexto').style.display      = modo === 'texto'      ? '' : 'none';
    document.getElementById('tabIndividual').classList.toggle('active', modo === 'individual');
    document.getElementById('tabLote').classList.toggle('active',       modo === 'lote');
    document.getElementById('tabTexto').classList.toggle('active',      modo === 'texto');
}

// --- VOZ (Whisper) ---
let mediaRecorder = null;
let audioChunks   = [];
let vozAtiva      = false;

async function toggleVoz() {
    if (vozAtiva) {
        mediaRecorder?.stop();
        return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
        toast.error('Microfone não suportado neste navegador.');
        return;
    }

    try {
        const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
        audioChunks    = [];
        mediaRecorder  = new MediaRecorder(stream, { mimeType });

        mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };

        mediaRecorder.onstart = () => {
            vozAtiva = true;
            document.getElementById('btnVoz').style.color        = 'var(--error)';
            document.getElementById('btnVoz').style.borderColor  = 'var(--error)';
            document.getElementById('btnVozLabel').textContent   = 'Parar';
            document.getElementById('textoIAStatus').textContent = '🎙 Gravando…';
        };

        mediaRecorder.onstop = async () => {
            vozAtiva = false;
            stream.getTracks().forEach(t => t.stop());
            document.getElementById('btnVoz').style.color        = '';
            document.getElementById('btnVoz').style.borderColor  = '';
            document.getElementById('btnVozLabel').textContent   = 'Falar';
            document.getElementById('textoIAStatus').textContent = 'Transcrevendo…';

            try {
                const ext  = mimeType.includes('webm') ? 'webm' : 'ogg';
                const blob = new Blob(audioChunks, { type: mimeType });
                const fd   = new FormData();
                fd.append('file', blob, `audio.${ext}`);

                const res = await fetch(`${API_BASE}/api/ai/transcrever`, { method: 'POST', body: fd });
                if (!res.ok) throw new Error(await res.text());
                const { texto } = await res.json();

                if (texto) {
                    const ta = document.getElementById('textoIA');
                    ta.value = ta.value ? ta.value.trimEnd() + ' ' + texto : texto;
                }
            } catch (e) {
                toast.error('Erro na transcrição: ' + e.message);
            } finally {
                document.getElementById('textoIAStatus').textContent = '';
            }
        };

        mediaRecorder.start();
    } catch (e) {
        toast.error('Microfone bloqueado: ' + e.message);
    }
}

// --- NFs DA ABA TEXTO ---
let nfsTexto = [];   // Files selecionados na aba texto

function initUploadZoneTexto() {
    const zone  = document.getElementById('uploadZoneTexto');
    const input = document.getElementById('inputNFTexto');
    if (!zone || !input) return;

    zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--accent)'; });
    zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
    zone.addEventListener('drop', e => {
        e.preventDefault(); zone.style.borderColor = '';
        if (e.dataTransfer.files.length) definirNFsTexto(e.dataTransfer.files);
    });
    input.addEventListener('change', () => { if (input.files.length) definirNFsTexto(input.files); });
}

function definirNFsTexto(files) {
    nfsTexto = [...nfsTexto, ...Array.from(files)];
    renderizarChipsNFsTexto();
}

function removerNFTexto(idx) {
    nfsTexto.splice(idx, 1);
    renderizarChipsNFsTexto();
}

function renderizarChipsNFsTexto() {
    const el    = document.getElementById('uploadZoneTextoText');
    const chips = document.getElementById('nfsTextoChips');
    const zone  = document.getElementById('uploadZoneTexto');

    if (!nfsTexto.length) {
        el.textContent = 'Clique ou arraste as NFs aqui (PDF, JPG, PNG)';
        zone.style.borderColor = '';
        chips.style.display = 'none';
        chips.innerHTML = '';
        return;
    }

    el.textContent = `${nfsTexto.length} arquivo(s) selecionado(s)`;
    zone.style.borderColor = 'var(--secondary)';
    chips.style.display = 'flex';
    chips.innerHTML = nfsTexto.map((f, i) => `
        <div class="file-chip">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <span title="${esc(f.name)}">${esc(f.name)}</span>
            <button class="file-chip-remove" onclick="removerNFTexto(${i})" title="Remover">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>
    `).join('');
}

// --- EXTRAIR IA POR TEXTO ---
let despesasTexto = [];  // resultado da extração (array)
let chatHistorico     = [];  // [{role, content}] histórico do chat de revisão (Por Texto)
let chatContexto      = '';  // texto original enviado para extração
let chatLoteHistorico = [];  // histórico do chat do lote
let chatLoteContexto  = '';  // contexto do lote (nomes dos arquivos)

async function extrairIATexto() {
    const texto = document.getElementById('textoIA').value.trim();
    if (!texto && !nfsTexto.length) { toast.warning('Digite algum texto ou anexe uma NF.'); return; }

    const btn    = document.getElementById('btnExtrairTexto');
    const status = document.getElementById('textoIAStatus');
    btn.disabled = true;
    status.textContent = 'Extraindo…';

    try {
        let lista;
        if (nfsTexto.length > 0) {
            // Texto + arquivos → endpoint multimodal
            const fd = new FormData();
            fd.append('texto', texto);
            fd.append('fornecedores', JSON.stringify(fornecedores));
            fd.append('categorias',   JSON.stringify(categorias));
            fd.append('obras',        JSON.stringify(obras));
            fd.append('etapas',       JSON.stringify(etapas));
            nfsTexto.forEach(f => fd.append('files', f));
            const res = await fetch(`${API_BASE}/api/ai/extrair-texto-misto`, { method: 'POST', body: fd });
            if (!res.ok) throw new Error(await res.text());
            lista = await res.json();
        } else {
            // Só texto → endpoint original
            const res = await fetch(`${API_BASE}/api/ai/extrair-texto`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ texto, fornecedores, categorias, obras, etapas }),
            });
            if (!res.ok) throw new Error(await res.text());
            lista = await res.json();
        }
        despesasTexto = Array.isArray(lista) ? lista : [lista];

        if (despesasTexto.length === 1) {
            // Apenas uma → preenche form individual
            const ia = despesasTexto[0];
            setModo('individual');
            preencherCampoIA('fTipo',    ia.TIPO,    tipos);
            preencherCampoIA('fForma',   ia.FORMA,   formas);
            preencherCampoIA('fDespesa', ia.DESPESA, categorias);
            preencherCampoIA('fObra',    ia.OBRA,    obras);
            preencherCampoIA('fEtapa',   ia.ETAPA,   etapas);
            preencherFornecedorIA(ia.FORNECEDOR);
            if (ia.VALOR_TOTAL) document.getElementById('fValor').value = parseFloat(ia.VALOR_TOTAL).toFixed(2);
            if (ia.DATA)        document.getElementById('fData').value  = ia.DATA;
            if (ia.DESCRICAO)   document.getElementById('fDescricao').value = ia.DESCRICAO;
            document.getElementById('iaBanner').style.display = '';
            if (nfsTexto.length === 1) handleNFSelecionada(nfsTexto);
            document.getElementById('textoIA').value = '';
            toast.success('Dados extraídos. Revise e salve na aba Individual.');
        } else {
            // Múltiplas → mostra tabela de revisão + chat
            chatContexto  = texto || `[${nfsTexto.map(f => f.name).join(', ')}]`;
            chatHistorico = [];
            renderizarRevisaoTexto(despesasTexto, nfsTexto);
            document.getElementById('textoRevisaoWrap').style.display = '';
            iniciarChat();
            document.getElementById('textoIA').value = '';
            popularSelect('textoObra', obras, 'Obra *', false);
            toast.success(`${despesasTexto.length} despesas detectadas. Revise e cadastre.`);
        }
    } catch (e) {
        toast.error('Erro na extração: ' + e.message);
    } finally {
        btn.disabled = false;
        status.textContent = '';
    }
}

function renderizarRevisaoTexto(lista, arquivos) {
    const tbody = document.getElementById('textoRevisaoBody');
    const titulo = document.getElementById('textoRevisaoTitulo');
    titulo.textContent = `${lista.length} despesa(s) detectada(s) — revise antes de cadastrar`;

    const opcoesObra = obras.map(o => `<option value="${esc(o)}"${''}>  ${esc(o)}</option>`).join('');

    tbody.innerHTML = lista.map((d, i) => {
        const nf = arquivos[i] ? `📎 ${arquivos[i].name}` : '—';
        const obraVal = d.OBRA || '';
        return `<tr>
            <td style="font-weight:600;color:var(--accent);">${i + 1}</td>
            <td>
                <select class="form-select obra-linha" data-idx="${i}" style="min-width:140px;font-size:0.8rem;padding:2px 6px;">
                    <option value="">— Obra —</option>
                    ${obras.map(o => `<option value="${esc(o)}"${o === obraVal ? ' selected' : ''}>${esc(o)}</option>`).join('')}
                </select>
            </td>
            <td>${esc(d.FORNECEDOR || '—')}</td>
            <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(d.DESCRICAO || '—')}</td>
            <td>${esc(d.TIPO || '—')}</td>
            <td>
                <select class="form-select form-select-sm etapa-linha" data-idx="${i}" style="min-width:120px;font-size:0.8rem;padding:2px 6px;">
                    <option value="">—</option>
                    ${etapas.map(e => `<option value="${esc(e)}"${e === (d.ETAPA || '') ? ' selected' : ''}>${esc(e)}</option>`).join('')}
                </select>
            </td>
            <td>${esc(d.DESPESA || '—')}</td>
            <td style="font-weight:600;">R$ ${d.VALOR_TOTAL ? Number(d.VALOR_TOTAL).toLocaleString('pt-BR',{minimumFractionDigits:2}) : '—'}</td>
            <td>${d.DATA ? d.DATA.split('-').reverse().join('/') : '—'}</td>
            <td style="font-size:0.75rem;color:var(--on-surface-muted);">${nf}</td>
        </tr>`;
    }).join('');

    popularSelect('textoObraGlobal', obras, 'Aplicar obra a todas…');
}

function aplicarObraGlobal(valor) {
    if (!valor) return;
    document.querySelectorAll('.obra-linha').forEach(sel => { sel.value = valor; });
}

async function salvarTodasDoTexto() {
    if (!despesasTexto.length) return;

    // Valida que todas as linhas têm obra
    const selects = Array.from(document.querySelectorAll('.obra-linha'));
    const etapaSelects = Array.from(document.querySelectorAll('.etapa-linha'));
    const semObra = selects.filter(s => !s.value);
    if (semObra.length) { toast.warning(`Selecione a obra em ${semObra.length} linha(s).`); return; }

    const btn = document.getElementById('btnSalvarTodasTexto');
    btn.disabled = true; btn.textContent = 'Cadastrando…';

    // Pré-upload: para despesas com _grupo, faz upload do arquivo uma única vez por grupo
    const uploadCache = {}; // grupo -> { url, nome } ou índice -> { url, nome }
    for (let i = 0; i < despesasTexto.length; i++) {
        const d    = despesasTexto[i];
        const file = nfsTexto[i];
        if (!file) continue;
        const grupo = d._grupo || null;
        if (grupo) {
            if (!uploadCache[`g:${grupo}`]) {
                const res = await uploadComprovante(file);
                if (res) uploadCache[`g:${grupo}`] = res;
            }
        } else {
            const res = await uploadComprovante(file);
            if (res) uploadCache[`i:${i}`] = res;
        }
    }

    let ok = 0, erros = 0;
    for (let i = 0; i < despesasTexto.length; i++) {
        const d     = despesasTexto[i];
        const obra  = selects[i]?.value || '';
        const etapa = etapaSelects[i]?.value || d.ETAPA || null;
        const valor = parseFloat(d.VALOR_TOTAL);
        if (!valor || valor <= 0) { erros++; continue; }
        try {
            const fornecedor = (d.FORNECEDOR || '').trim();
            if (fornecedor) await dbClient.from('fornecedores').upsert({ nome: fornecedor }, { onConflict: 'nome' });

            const { data: inserted, error } = await dbClient.from('c_despesas').insert({
                obra,
                etapa:       etapa,
                tipo:        d.TIPO      || null,
                fornecedor:  fornecedor  || null,
                valor_total: valor,
                data:        d.DATA      || new Date().toISOString().split('T')[0],
                descricao:   d.DESCRICAO || null,
                despesa:     d.DESPESA   || null,
                forma:       d.FORMA     || null,
            }).select('id').single();
            if (error) throw error;

            // Vincula comprovante — usa cache para grupos (mesmo arquivo, múltiplas despesas)
            const grupo = d._grupo || null;
            const comp  = grupo ? uploadCache[`g:${grupo}`] : uploadCache[`i:${i}`];
            if (comp) {
                await dbClient.from('comprovantes_despesa').insert({
                    despesa_id: inserted.id, url: comp.url, nome_arquivo: comp.nome,
                });
                await dbClient.from('c_despesas').update({ tem_nota_fiscal: true }).eq('id', inserted.id);
            }
            ok++;
        } catch (_) { erros++; }
    }

    btn.disabled = false; btn.textContent = 'Cadastrar todas';
    if (ok)    toast.success(`${ok} despesa(s) cadastrada(s)!`);
    if (erros) toast.warning(`${erros} item(s) com erro.`);
    if (ok) {
        despesasTexto = [];
        nfsTexto      = [];
        chatHistorico = [];
        chatContexto  = '';
        document.getElementById('textoIA').value              = '';
        document.getElementById('inputNFTexto').value         = '';
        document.getElementById('textoRevisaoWrap').style.display  = 'none';
        document.getElementById('chatRevisaoWrap').style.display   = 'none';
        renderizarChipsNFsTexto();
    }
}

// --- UPLOAD NF INDIVIDUAL ---
function handleNFSelecionada(files) {
    if (!files || !files.length) return;
    const texto = files.length === 1
        ? `📎 ${files[0].name}`
        : `📎 ${files.length} arquivos — a IA usará o primeiro para identificar a despesa`;
    document.getElementById('uploadZoneText').textContent = texto;
    document.getElementById('btnExtrairIA').disabled = false;
}

// --- EXTRAIR IA INDIVIDUAL ---
async function extrairIAIndividual() {
    const files = Array.from(document.getElementById('inputNF').files);
    if (!files.length) return;

    const btn = document.getElementById('btnExtrairIA');
    btn.disabled = true;

    try {
        // Processa cada arquivo sequencialmente e mescla os resultados
        const resultados = [];
        for (let i = 0; i < files.length; i++) {
            btn.textContent = files.length > 1 ? `Extraindo ${i + 1}/${files.length}…` : 'Extraindo…';
            const formData = new FormData();
            formData.append('file', files[i]);
            // Passa referências do banco para melhorar o matching da IA
            formData.append('fornecedores', JSON.stringify(fornecedores));
            formData.append('obras',        JSON.stringify(obras));
            formData.append('etapas',       JSON.stringify(etapas));
            formData.append('categorias',   JSON.stringify(categorias));
            const res = await fetch(`${API_BASE}/api/ai/extrair`, { method: 'POST', body: formData });
            if (!res.ok) throw new Error(await res.text());
            resultados.push(await res.json());
        }

        // Mescla: primeira ocorrência não-nula de cada campo vence
        const ia = resultados.reduce((acc, r) => {
            for (const key of Object.keys(r)) {
                if (!acc[key] && r[key]) acc[key] = r[key];
            }
            return acc;
        }, {});

        // Soma valores se houver múltiplos (documentos distintos)
        if (resultados.length > 1) {
            const soma = resultados.reduce((s, r) => s + (parseFloat(r.VALOR_TOTAL) || 0), 0);
            if (soma > 0) ia.VALOR_TOTAL = soma.toFixed(2);
        }

        // Preencher form
        preencherCampoIA('fTipo',    ia.TIPO,    tipos);
        preencherCampoIA('fForma',   ia.FORMA,   formas);
        preencherCampoIA('fDespesa', ia.DESPESA, categorias);
        preencherFornecedorIA(ia.FORNECEDOR);
        if (ia.VALOR_TOTAL) document.getElementById('fValor').value = parseFloat(ia.VALOR_TOTAL).toFixed(2);
        if (ia.DATA)        document.getElementById('fData').value  = ia.DATA;
        if (ia.DESCRICAO)   document.getElementById('fDescricao').value = ia.DESCRICAO;

        document.getElementById('iaBanner').style.display = '';
        const msg = files.length > 1
            ? `${files.length} arquivos analisados. Valores somados: R$ ${parseFloat(ia.VALOR_TOTAL || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}. Revise antes de salvar.`
            : 'Dados extraídos pela IA. Revise antes de salvar.';
        toast.success(msg);
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
    if (!sel) return;
    const norm = valor.trim().toLowerCase();
    // 1. Match exato
    let match = lista.find(o => o.toLowerCase() === norm);
    // 2. Um contém o outro
    if (!match) match = lista.find(o => o.toLowerCase().includes(norm) || norm.includes(o.toLowerCase()));
    // 3. Qualquer palavra significativa em comum (≥4 chars)
    if (!match) {
        const palavras = norm.split(/\s+/).filter(p => p.length >= 4);
        if (palavras.length) match = lista.find(o => palavras.some(p => o.toLowerCase().includes(p)));
    }
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
        // Upsert fornecedor
        if (fornecedor) {
            await dbClient.from('fornecedores').upsert({ nome: fornecedor }, { onConflict: 'nome' });
            if (!fornecedores.includes(fornecedor)) {
                fornecedores.push(fornecedor);
                popularFornecedor();
            }
        }

        // Insert despesa — obtém ID para vincular NFs
        const { data: inserted, error } = await dbClient.from('c_despesas').insert({
            obra, etapa, tipo,
            fornecedor:  fornecedor || null,
            valor_total: valor,
            data,
            descricao:   descricao || null,
            despesa:     despesa   || null,
            banco:       banco     || null,
            forma:       forma     || null,
        }).select('id').single();
        if (error) throw error;

        // Upload NFs (múltiplas) → comprovantes_despesa
        const arquivos = Array.from(document.getElementById('inputNF').files);
        if (arquivos.length) {
            for (const file of arquivos) {
                const res = await uploadComprovante(file);
                if (res) {
                    await dbClient.from('comprovantes_despesa').insert({
                        despesa_id: inserted.id, url: res.url, nome_arquivo: res.nome,
                    });
                }
            }
            await dbClient.from('c_despesas').update({ tem_nota_fiscal: true }).eq('id', inserted.id);
        }

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
    }

    document.getElementById('loteProgresso').style.display = 'none';
    document.getElementById('btnExtrairLote').disabled = false;
    chatLoteContexto  = loteArquivos.map(a => a.nome).join(', ');
    chatLoteHistorico = [];
    renderizarTabeLote();
    iniciarChatLote();
}

function aplicarObraLoteGlobal(valor) {
    if (!valor) return;
    document.querySelectorAll('.obra-lote-linha').forEach(sel => { sel.value = valor; });
}

function renderizarTabeLote() {
    const tbody = document.getElementById('loteTableBody');
    tbody.innerHTML = '';

    popularSelect('lObraGlobal', obras, 'Aplicar obra a todas…');

    loteArquivos.forEach((item, idx) => {
        const d = item.dados || {};
        const tr = document.createElement('tr');
        const fornMatch = fornecedores.find(f => f.toLowerCase() === (d.FORNECEDOR || '').toLowerCase());
        const fornIsNovo = d.FORNECEDOR && !fornMatch;
        const obraVal = d.OBRA || '';
        tr.innerHTML = `
            <td style="font-size:0.8125rem;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${item.nome}">${item.nome}</td>
            <td style="min-width:140px;">
                <select class="form-select form-select-sm obra-lote-linha" data-idx="${idx}" style="font-size:0.8rem;padding:2px 6px;">
                    <option value="">— Obra —</option>
                    ${obras.map(o => `<option value="${esc(o)}"${o === obraVal ? ' selected' : ''}>${esc(o)}</option>`).join('')}
                </select>
            </td>
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
            <td>
                <select class="form-select form-select-sm" data-idx="${idx}" data-field="DESPESA">
                    <option value="">—</option>
                    ${categorias.map(c => `<option value="${c}" ${d.DESPESA===c?'selected':''}>${c}</option>`).join('')}
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
    loteArquivos      = [];
    chatLoteHistorico = [];
    chatLoteContexto  = '';
    document.getElementById('loteUploadText').textContent     = 'Arraste ou clique para selecionar NFs';
    document.getElementById('btnExtrairLote').disabled        = true;
    document.getElementById('loteRevisaoWrap').style.display  = 'none';
    document.getElementById('chatLoteWrap').style.display     = 'none';
    document.getElementById('inputLoteNFs').value             = '';
}

async function salvarLote() {
    if (!loteArquivos.length) return;

    const selects = Array.from(document.querySelectorAll('.obra-lote-linha'));
    const semObra = selects.filter(s => !s.value);
    if (semObra.length) { toast.warning(`Selecione a obra em ${semObra.length} linha(s).`); return; }

    const btn = document.getElementById('btnLoteSalvar');
    btn.disabled = true;

    let ok = 0, erros = 0;
    for (let i = 0; i < loteArquivos.length; i++) {
        const item = loteArquivos[i];
        const obra = selects[i]?.value || '';
        const d = item.dados || {};
        const valor = parseFloat(d.VALOR_TOTAL);
        if (!valor || valor <= 0) { erros++; continue; }
        try {
            const fornecedor = (d.FORNECEDOR || '').trim();
            if (fornecedor) {
                await dbClient.from('fornecedores').upsert({ nome: fornecedor }, { onConflict: 'nome' });
            }

            // Insert despesa → obtém ID para vincular NF
            const { data: inserted, error } = await dbClient.from('c_despesas').insert({
                obra,
                etapa:       d.ETAPA || null,
                tipo:        d.TIPO  || null,
                fornecedor:  fornecedor || null,
                valor_total: valor,
                data:        d.DATA  || null,
                descricao:   (d.DESCRICAO || '').trim() || null,
                despesa:     (d.DESPESA   || '') || null,
                forma:       (d.FORMA     || '') || null,
            }).select('id').single();
            if (error) throw error;

            // Upload NF → comprovantes_despesa
            const res = await uploadComprovante(item.file);
            if (res) {
                await dbClient.from('comprovantes_despesa').insert({
                    despesa_id: inserted.id, url: res.url, nome_arquivo: res.nome,
                });
                await dbClient.from('c_despesas').update({ tem_nota_fiscal: true }).eq('id', inserted.id);
            }
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

// ── CHAT DE REVISÃO IA — LOTE ───────────────────────────────────────────────

function iniciarChatLote() {
    const wrap = document.getElementById('chatLoteWrap');
    const msgs = document.getElementById('chatLoteMensagens');
    wrap.style.display = '';
    msgs.innerHTML = '';
    _appendMsgChatLote('ia', 'Olá! Posso explicar como extraí os dados de cada arquivo ou fazer correções no lote. O que deseja?');
}

function _appendMsgChatLote(role, texto) { _appendChatMsg('chatLoteMensagens', role, texto); }

async function enviarMensagemChatLote() {
    const input = document.getElementById('chatLoteInput');
    const btn   = document.getElementById('btnChatLoteEnviar');
    const texto = input.value.trim();
    if (!texto) return;

    input.value = '';
    btn.disabled = true;
    _appendMsgChatLote('user', texto);

    chatLoteHistorico.push({ role: 'user', content: texto });

    // Sincroniza loteArquivos com edições do DOM (obra, etapa)
    const obraSelects  = Array.from(document.querySelectorAll('.obra-lote-linha'));
    const etapaSelects = Array.from(document.querySelectorAll('[data-field="ETAPA"]'));
    const despesasLote = loteArquivos.map((a, i) => ({
        _arquivo: a.nome,
        ...a.dados,
        OBRA:  obraSelects[i]?.value  || a.dados?.OBRA  || null,
        ETAPA: etapaSelects[i]?.value || a.dados?.ETAPA || null,
    }));

    try {
        const res = await fetch(`${API_BASE}/api/ai/chat-despesas`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: chatLoteHistorico,
                despesas: despesasLote,
                contexto: `Lote de arquivos: ${chatLoteContexto}`,
            }),
        });
        if (!res.ok) throw new Error(await res.text());
        const { mensagem, despesas } = await res.json();

        chatLoteHistorico.push({ role: 'assistant', content: JSON.stringify({ mensagem, despesas }) });
        _appendMsgChatLote('ia', mensagem);

        if (Array.isArray(despesas)) {
            despesas.forEach((d, i) => {
                if (loteArquivos[i]) {
                    const { _arquivo, ...campos } = d;
                    loteArquivos[i].dados = campos;
                }
            });
            renderizarTabeLote();
            _appendMsgChatLote('system', '↑ Tabela atualizada');
        }
    } catch (e) {
        _appendMsgChatLote('ia', `Erro ao contactar IA: ${e.message}`);
    } finally {
        btn.disabled = false;
        document.getElementById('chatLoteInput').focus();
    }
}

// ── CHAT DE REVISÃO IA ──────────────────────────────────────────────────────

function iniciarChat() {
    const wrap = document.getElementById('chatRevisaoWrap');
    const msgs = document.getElementById('chatMensagens');
    wrap.style.display = '';
    msgs.innerHTML = '';
    _appendMsgChat('ia', 'Olá! Posso explicar como cheguei nessas despesas ou fazer correções. O que deseja?');
}

function _appendMsgChat(role, texto) { _appendChatMsg('chatMensagens', role, texto); }

function _appendChatMsg(containerId, role, texto) {
    const msgs  = document.getElementById(containerId);
    const isSys = role === 'system';
    const isIA  = role === 'ia';
    const wrap  = document.createElement('div');
    wrap.className = `chat-bubble chat-bubble-${isSys ? 'system' : isIA ? 'ia' : 'user'}`;
    if (!isSys) {
        const label = document.createElement('div');
        label.className = 'chat-bubble-label';
        label.textContent = isIA ? 'IA' : 'Você';
        wrap.appendChild(label);
    }
    const body = document.createElement('div');
    body.className = 'chat-bubble-body';
    body.textContent = texto;
    wrap.appendChild(body);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
}

async function enviarMensagemChat() {
    const input = document.getElementById('chatInput');
    const btn   = document.getElementById('btnChatEnviar');
    const texto = input.value.trim();
    if (!texto) return;

    input.value = '';
    btn.disabled = true;
    _appendMsgChat('user', texto);

    chatHistorico.push({ role: 'user', content: texto });

    // Sincroniza despesasTexto com o que está no DOM (selects de obra/etapa editados)
    const obraSelects  = Array.from(document.querySelectorAll('.obra-linha'));
    const etapaSelects = Array.from(document.querySelectorAll('.etapa-linha'));
    despesasTexto = despesasTexto.map((d, i) => ({
        ...d,
        OBRA:  obraSelects[i]?.value  || d.OBRA  || null,
        ETAPA: etapaSelects[i]?.value || d.ETAPA || null,
    }));

    try {
        const res = await fetch(`${API_BASE}/api/ai/chat-despesas`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages:  chatHistorico,
                despesas:  despesasTexto,
                contexto:  chatContexto,
            }),
        });
        if (!res.ok) throw new Error(await res.text());
        const { mensagem, despesas } = await res.json();

        chatHistorico.push({ role: 'assistant', content: JSON.stringify({ mensagem, despesas }) });
        _appendMsgChat('ia', mensagem);

        if (Array.isArray(despesas)) {
            despesasTexto = despesas;
            renderizarRevisaoTexto(despesasTexto, nfsTexto);
            _appendMsgChat('system', '↑ Tabela atualizada');
        }
    } catch (e) {
        _appendMsgChat('ia', `Erro ao contactar IA: ${e.message}`);
    } finally {
        btn.disabled = false;
        document.getElementById('chatInput').focus();
    }
}

function esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
