/**
 * INDUSTRIAL ARCHITECT — Folha de Pagamento
 * app.js
 */

// ── Supabase ──────────────────────────────────────────────────────────────────
let dbClient;

function initSupabase() {
    if (window.ENV?.SUPABASE_URL && window.ENV?.SUPABASE_ANON_KEY) {
        dbClient = window.supabase.createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY);
    }
}

// ── Estado ────────────────────────────────────────────────────────────────────
let obras        = [];
let etapas       = [];
let regrasObra   = {};   // { servico: { tipo, valor } }
let folhaAtual   = null; // { id, obra, quinzena, status }
let linhasLocais = [];   // [{ _localId, id?, nome, pix, nome_conta, servico, etapa, diarias, valor, _deleted }]
let _localIdSeq  = 0;

const STATUS_LABEL = { rascunho: 'Rascunho', enviada: 'Enviada', fechada: 'Fechada' };
const STATUS_COLOR = { rascunho: 'var(--warning)', enviada: 'var(--secondary)', fechada: 'var(--success)' };

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    initSupabase();
    await Promise.all([carregarObras(), carregarEtapas()]);
    setupEventListeners();
});

// ── Carregar dados base ───────────────────────────────────────────────────────
async function carregarObras() {
    if (!dbClient) return;
    try {
        const { data } = await dbClient.from('obras').select('nome').order('nome');
        obras = (data || []).map(o => o.nome);
        popularSelectObra('selObra');
        popularSelectObra('modalNovaFolhaObra');
    } catch (e) {
        console.error('Erro ao carregar obras:', e);
    }
}

async function carregarEtapas() {
    if (!dbClient) return;
    try {
        const { data } = await dbClient.from('etapas').select('nome').order('nome');
        etapas = (data || []).map(e => e.nome);
    } catch (e) {
        console.error('Erro ao carregar etapas:', e);
    }
}

async function carregarRegras(obra) {
    regrasObra = {};
    if (!dbClient || !obra) return;
    try {
        const { data } = await dbClient.from('folha_regras').select('servico, tipo, valor').eq('obra', obra);
        (data || []).forEach(r => { regrasObra[r.servico] = { tipo: r.tipo, valor: parseFloat(r.valor || 0) }; });
    } catch (e) {
        console.error('Erro ao carregar regras:', e);
    }
}

async function carregarFolhas(obra) {
    const sel = document.getElementById('selQuinzena');
    sel.innerHTML = '<option value="">Carregando…</option>';
    folhaAtual = null;
    esconderSecoes();

    if (!dbClient || !obra) {
        sel.innerHTML = '<option value="">Selecione uma obra primeiro</option>';
        return;
    }
    try {
        const { data } = await dbClient.from('folhas').select('*').eq('obra', obra).order('quinzena', { ascending: false });
        if (!data || data.length === 0) {
            sel.innerHTML = '<option value="">Nenhuma folha — crie uma nova</option>';
            return;
        }
        sel.innerHTML = '';
        data.forEach(f => {
            const opt = document.createElement('option');
            opt.value = f.id;
            const emoji = { rascunho: '🟡', enviada: '🔵', fechada: '🟢' }[f.status] || '⚪';
            opt.textContent = `${f.quinzena}  ${emoji} ${(STATUS_LABEL[f.status] || f.status).toUpperCase()}`;
            opt.dataset.status = f.status;
            opt.dataset.quinzena = f.quinzena;
            opt.dataset.obra = f.obra;
            sel.appendChild(opt);
        });
        // Carrega a primeira automaticamente
        await selecionarFolha(data[0]);
    } catch (e) {
        console.error('Erro ao carregar folhas:', e);
        sel.innerHTML = '<option value="">Erro ao carregar</option>';
    }
}

async function selecionarFolha(folha) {
    folhaAtual = folha;
    await carregarRegras(folha.obra);
    await carregarFuncionarios(folha.id);
    await carregarComprovantes(folha.id);
    renderizarStatusBadge();
    atualizarKPIs();
    renderizarBotoesAcao();
    mostrarSecoes();
}

async function carregarFuncionarios(folhaId) {
    linhasLocais = [];
    if (!dbClient) return;
    try {
        const { data } = await dbClient.from('folha_funcionarios').select('*').eq('folha_id', folhaId).order('id');
        (data || []).forEach(f => {
            linhasLocais.push({
                _localId:  ++_localIdSeq,
                id:        f.id,
                nome:      f.nome || '',
                pix:       f.pix || '',
                nome_conta: f.nome_conta || '',
                servico:   f.servico || '',
                etapa:     f.etapa || '',
                diarias:   parseFloat(f.diarias || 0),
                valor:     parseFloat(f.valor || 0),
                _deleted:  false,
            });
        });
    } catch (e) {
        console.error('Erro ao carregar funcionários:', e);
    }
    renderizarTabela();
}

async function carregarComprovantes(folhaId) {
    const lista = document.getElementById('listaComprovantes');
    lista.innerHTML = '<p style="font-size:0.875rem;color:var(--on-surface-muted);">Carregando…</p>';
    if (!dbClient) { lista.innerHTML = ''; return; }
    try {
        // Busca despesas vinculadas a esta folha
        const { data: despesas } = await dbClient.from('c_despesas').select('id').eq('folha_id', folhaId);
        const ids = (despesas || []).map(d => d.id);
        if (ids.length === 0) { lista.innerHTML = '<p style="font-size:0.875rem;color:var(--on-surface-muted);">Nenhum comprovante vinculado ainda.</p>'; return; }

        const { data: comps } = await dbClient.from('comprovantes_despesa').select('url, nome_arquivo').in('despesa_id', ids);
        const unicos = [...new Map((comps || []).map(c => [c.url, c])).values()];
        if (unicos.length === 0) {
            lista.innerHTML = '<p style="font-size:0.875rem;color:var(--on-surface-muted);">Nenhum comprovante vinculado ainda.</p>';
            return;
        }
        lista.innerHTML = unicos.map(c => {
            const label = c.nome_arquivo || c.url.split('/').pop();
            return `<div style="margin-bottom:4px;font-size:0.875rem;">
                <a href="${c.url}" target="_blank" style="color:var(--secondary);text-decoration:none;">
                    📎 ${label}
                </a>
            </div>`;
        }).join('');
    } catch (e) {
        lista.innerHTML = '<p style="font-size:0.875rem;color:var(--on-surface-muted);">Não foi possível carregar comprovantes.</p>';
    }
}

// ── Cálculo de valor ──────────────────────────────────────────────────────────
function calcularValor(servico, diarias) {
    const regra = regrasObra[servico];
    if (!regra) return 0;
    return regra.tipo === 'fixo' ? regra.valor : regra.valor * (parseFloat(diarias) || 0);
}

// ── Render tabela ─────────────────────────────────────────────────────────────
function renderizarTabela() {
    const tbody   = document.getElementById('tabelaBody');
    const ativas  = linhasLocais.filter(l => !l._deleted);
    const isClosed = folhaAtual?.status === 'fechada';
    const servicos = Object.keys(regrasObra);

    if (ativas.length === 0) {
        tbody.innerHTML = `<tr id="trVazio"><td colspan="8" style="text-align:center;padding:var(--sp-8);color:var(--on-surface-muted);font-size:0.875rem;">Nenhum funcionário cadastrado nesta folha.</td></tr>`;
        atualizarTotal();
        return;
    }

    tbody.innerHTML = ativas.map(l => {
        const val = calcularValor(l.servico, l.diarias);
        const disabled = isClosed ? 'disabled' : '';
        return `
        <tr data-lid="${l._localId}">
            <td><input class="tbl-input" type="text" value="${esc(l.nome)}" data-field="nome" ${disabled} placeholder="Nome completo"></td>
            <td><input class="tbl-input" type="text" value="${esc(l.pix)}" data-field="pix" ${disabled} placeholder="Chave PIX"></td>
            <td><input class="tbl-input" type="text" value="${esc(l.nome_conta)}" data-field="nome_conta" ${disabled} placeholder="Titular da conta"></td>
            <td>
                <select class="tbl-select" data-field="servico" ${disabled}>
                    <option value="">— Serviço —</option>
                    ${servicos.map(s => `<option value="${esc(s)}" ${l.servico === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}
                </select>
            </td>
            <td>
                <select class="tbl-select" data-field="etapa" ${disabled} style="${!l.etapa && !isClosed ? 'border-color:var(--error);background:rgba(255,80,80,0.07);' : ''}">
                    <option value="">— Etapa —</option>
                    ${etapas.map(e => `<option value="${esc(e)}" ${l.etapa === e ? 'selected' : ''}>${esc(e)}</option>`).join('')}
                </select>
            </td>
            <td><input class="tbl-input text-right" type="number" min="0" step="0.5" value="${l.diarias || ''}" data-field="diarias" ${disabled} placeholder="0" style="max-width:90px;"></td>
            <td class="text-right fin-num" data-valor="${val}" style="white-space:nowrap;">${formatCurrency(val)}</td>
            <td style="text-align:center;">
                ${!isClosed ? `<button class="btn-row-delete" data-lid="${l._localId}" title="Remover linha">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>` : ''}
            </td>
        </tr>`;
    }).join('');

    atualizarTotal();
}

function atualizarTotal() {
    const ativas = linhasLocais.filter(l => !l._deleted);
    const total  = ativas.reduce((s, l) => s + calcularValor(l.servico, l.diarias), 0);
    document.getElementById('totalRodape').textContent = formatCurrency(total);

    // Aviso de etapa faltando
    const semEtapa = ativas.filter(l => !l.etapa && calcularValor(l.servico, l.diarias) > 0);
    const aviso    = document.getElementById('avisoSemEtapa');
    const isClosed = folhaAtual?.status === 'fechada';
    if (semEtapa.length > 0 && !isClosed) {
        document.getElementById('avisoSemEtapaTexto').textContent =
            `${semEtapa.length} funcionário(s) sem etapa — preencha antes de fechar a folha.`;
        aviso.style.display = 'flex';
    } else {
        aviso.style.display = 'none';
    }

    atualizarKPIs();
}

// ── KPIs ──────────────────────────────────────────────────────────────────────
function atualizarKPIs() {
    const ativas   = linhasLocais.filter(l => !l._deleted);
    const total    = ativas.reduce((s, l) => s + calcularValor(l.servico, l.diarias), 0);
    const etapasSet = new Set(ativas.map(l => l.etapa).filter(Boolean));
    const status    = folhaAtual?.status || '—';

    document.getElementById('kpiTotal').textContent        = formatCurrency(total);
    document.getElementById('kpiFuncionarios').textContent = ativas.length;
    document.getElementById('kpiEtapas').textContent       = etapasSet.size;
    document.getElementById('kpiStatus').textContent       = STATUS_LABEL[status] || status;
    document.getElementById('kpiStatus').style.color       = STATUS_COLOR[status] || 'var(--on-surface)';
    document.getElementById('kpiStatusSub').textContent    = folhaAtual?.quinzena || '';
}

// ── Status badge ──────────────────────────────────────────────────────────────
function renderizarStatusBadge() {
    const wrap  = document.getElementById('statusBadgeWrap');
    const st    = folhaAtual?.status;
    const emoji = { rascunho: '🟡', enviada: '🔵', fechada: '🟢' }[st] || '⚪';
    wrap.innerHTML = st
        ? `<span style="font-size:0.875rem;font-weight:600;color:${STATUS_COLOR[st]||'var(--on-surface)'};">${emoji} ${STATUS_LABEL[st] || st}</span>`
        : '';
}

// ── Botões de ação (Fechar / Reabrir) ─────────────────────────────────────────
function renderizarBotoesAcao() {
    const status   = folhaAtual?.status;
    const isClosed = status === 'fechada';
    const isRascunho = status === 'rascunho';
    document.getElementById('btnFecharFolha').style.display  = isClosed ? 'none' : '';
    document.getElementById('btnReabrirFolha').style.display = isClosed ? '' : 'none';
    document.getElementById('btnExcluirFolha').style.display = isRascunho ? '' : 'none';
    document.getElementById('btnSalvar').disabled            = isClosed;
    document.getElementById('btnAddLinha').disabled          = isClosed;
}

// ── Mostrar / esconder seções ─────────────────────────────────────────────────
function mostrarSecoes() {
    document.getElementById('kpiSection').style.display          = '';
    document.getElementById('tabelaSection').style.display       = '';
    document.getElementById('comprovantesSection').style.display = '';
}

function esconderSecoes() {
    document.getElementById('kpiSection').style.display          = 'none';
    document.getElementById('tabelaSection').style.display       = 'none';
    document.getElementById('comprovantesSection').style.display = 'none';
    document.getElementById('mensagemSection').style.display     = 'none';
}

// ── Event listeners ───────────────────────────────────────────────────────────
function setupEventListeners() {
    // Obra selecionada
    document.getElementById('selObra').addEventListener('change', async (e) => {
        await carregarFolhas(e.target.value);
    });

    // Quinzena selecionada
    document.getElementById('selQuinzena').addEventListener('change', async (e) => {
        const id = parseInt(e.target.value);
        if (!id) return;
        const opt = e.target.selectedOptions[0];
        await selecionarFolha({
            id:       id,
            obra:     opt.dataset.obra,
            quinzena: opt.dataset.quinzena,
            status:   opt.dataset.status,
        });
    });

    // Edição na tabela (delegação de eventos)
    document.getElementById('tabelaBody').addEventListener('input', (e) => {
        const tr  = e.target.closest('tr[data-lid]');
        if (!tr) return;
        const lid   = parseInt(tr.dataset.lid);
        const field = e.target.dataset.field;
        const linha = linhasLocais.find(l => l._localId === lid);
        if (!linha || !field) return;
        linha[field] = e.target.type === 'number' ? parseFloat(e.target.value || 0) : e.target.value;

        // Recalcula valor ao mudar serviço ou diárias
        if (field === 'servico' || field === 'diarias') {
            const val = calcularValor(linha.servico, linha.diarias);
            const tdVal = tr.querySelector('td[data-valor]');
            if (tdVal) { tdVal.dataset.valor = val; tdVal.textContent = formatCurrency(val); }
            atualizarTotal();
        }
    });

    // Deletar linha
    document.getElementById('tabelaBody').addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-row-delete');
        if (!btn) return;
        const lid   = parseInt(btn.dataset.lid);
        const linha = linhasLocais.find(l => l._localId === lid);
        if (linha) { linha._deleted = true; renderizarTabela(); }
    });

    // Adicionar linha
    document.getElementById('btnAddLinha').addEventListener('click', () => {
        linhasLocais.push({
            _localId:  ++_localIdSeq,
            id:        null,
            nome:      '', pix: '', nome_conta: '',
            servico:   '', etapa: '', diarias: 0, valor: 0,
            _deleted:  false,
        });
        renderizarTabela();
        // Foca no primeiro input da nova linha
        const tbody = document.getElementById('tabelaBody');
        const novaLinha = tbody.lastElementChild;
        novaLinha?.querySelector('input')?.focus();
    });

    // Salvar
    document.getElementById('btnSalvar').addEventListener('click', salvarFolha);

    // Gerar mensagem
    document.getElementById('btnGerarMensagem').addEventListener('click', gerarMensagem);
    document.getElementById('btnCopiarMensagem').addEventListener('click', copiarMensagem);

    // Fechar folha
    document.getElementById('btnFecharFolha').addEventListener('click', abrirModalFechar);
    document.getElementById('modalFecharFolhaClose').addEventListener('click', fecharModalFechar);
    document.getElementById('modalFecharFolhaCancelar').addEventListener('click', fecharModalFechar);
    document.getElementById('modalFecharFolhaConfirmar').addEventListener('click', confirmarFecharFolha);

    // Reabrir folha
    document.getElementById('btnReabrirFolha').addEventListener('click', reabrirFolha);

    // Excluir rascunho
    document.getElementById('btnExcluirFolha').addEventListener('click', excluirRascunho);

    // Nova folha
    document.getElementById('btnNovaFolha').addEventListener('click', abrirModalNovaFolha);
    document.getElementById('modalNovaFolhaClose').addEventListener('click', fecharModalNovaFolha);
    document.getElementById('modalNovaFolhaCancelar').addEventListener('click', fecharModalNovaFolha);
    document.getElementById('modalNovaFolhaConfirmar').addEventListener('click', criarNovaFolha);

    // Enviar comprovantes
    document.getElementById('btnEnviarComprovantes').addEventListener('click', enviarComprovantes);
}

// ── Salvar folha ──────────────────────────────────────────────────────────────
async function salvarFolha() {
    if (!dbClient || !folhaAtual) return;
    const btn = document.getElementById('btnSalvar');
    btn.disabled = true;
    btn.textContent = 'Salvando…';

    try {
        for (const l of linhasLocais) {
            const valor = calcularValor(l.servico, l.diarias);
            const payload = {
                nome: l.nome || null,
                pix:  l.pix  || null,
                nome_conta: l.nome_conta || null,
                servico:    l.servico    || null,
                etapa:      l.etapa      || null,
                diarias:    l.diarias    || 0,
                valor:      valor,
            };

            if (l._deleted && l.id) {
                await dbClient.from('folha_funcionarios').delete().eq('id', l.id);
            } else if (!l._deleted) {
                if (l.id) {
                    await dbClient.from('folha_funcionarios').update(payload).eq('id', l.id);
                } else {
                    const { data } = await dbClient.from('folha_funcionarios').insert({ ...payload, folha_id: folhaAtual.id }).select('id');
                    if (data?.[0]) l.id = data[0].id;
                }
            }
        }
        // Remove deletados da memória
        linhasLocais = linhasLocais.filter(l => !l._deleted);
        renderizarTabela();
        toast.success('Folha salva com sucesso!');
    } catch (e) {
        toast.error('Erro ao salvar: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Salvar`;
    }
}

// ── Gerar mensagem PIX ────────────────────────────────────────────────────────
function gerarMensagem() {
    if (!folhaAtual) return;
    const ativas = linhasLocais.filter(l => !l._deleted);
    const grupos = {};
    ativas.forEach(l => {
        const pix  = l.pix  || '—';
        const nome = l.nome || '—';
        const conta = l.nome_conta || '—';
        const val   = calcularValor(l.servico, l.diarias);
        if (!grupos[pix]) grupos[pix] = { nome, conta, valor: 0 };
        grupos[pix].valor += val;
    });

    const total = ativas.reduce((s, l) => s + calcularValor(l.servico, l.diarias), 0);
    const linhas = [
        '📋 FOLHA DE PAGAMENTO',
        `Obra: ${folhaAtual.obra}`,
        `Quinzena: ${formatarData(folhaAtual.quinzena)}`,
        '',
    ];
    Object.entries(grupos).forEach(([pix, d], i) => {
        linhas.push(`${i + 1}. ${d.nome}`);
        linhas.push(`   PIX: ${pix}`);
        linhas.push(`   Conta: ${d.conta}`);
        linhas.push(`   Valor: ${formatCurrency(d.valor)}`);
        linhas.push('');
    });
    linhas.push(`TOTAL: ${formatCurrency(total)}`);

    document.getElementById('mensagemTexto').textContent = linhas.join('\n');
    document.getElementById('mensagemSection').style.display = '';
    document.getElementById('mensagemSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function copiarMensagem() {
    const txt = document.getElementById('mensagemTexto').textContent;
    navigator.clipboard.writeText(txt).then(() => toast.success('Mensagem copiada!'));
}

// ── Modal: Nova Folha ─────────────────────────────────────────────────────────
let _ultimaFolhaId = null; // folha mais recente da obra para cópia

async function abrirModalNovaFolha() {
    const obraAtual = document.getElementById('selObra').value;
    const sel = document.getElementById('modalNovaFolhaObra');
    if (obraAtual) sel.value = obraAtual;

    document.getElementById('modalNovaFolhaData').value = new Date().toISOString().split('T')[0];
    document.getElementById('chkCopiarUltima').checked   = false;

    // Verifica se existe folha anterior para oferecer a cópia
    await verificarUltimaFolha(obraAtual);

    // Ao trocar a obra no modal, reavalia
    sel.onchange = () => verificarUltimaFolha(sel.value);

    const modal = document.getElementById('modalNovaFolha');
    modal.style.display = 'flex';
    requestAnimationFrame(() => modal.classList.add('active'));
}

async function verificarUltimaFolha(obra) {
    _ultimaFolhaId = null;
    const wrap  = document.getElementById('copiarUltimaWrap');
    const label = document.getElementById('copiarUltimaLabel');
    wrap.style.display = 'none';
    if (!obra || !dbClient) return;

    try {
        const { data } = await dbClient
            .from('folhas').select('id, quinzena, status')
            .eq('obra', obra)
            .order('quinzena', { ascending: false })
            .limit(1);

        if (data?.[0]) {
            _ultimaFolhaId = data[0].id;
            const emoji = { rascunho: '🟡', enviada: '🔵', fechada: '🟢' }[data[0].status] || '⚪';
            label.textContent = `Última: ${formatarData(data[0].quinzena)} ${emoji}`;
            wrap.style.display = '';
        }
    } catch (e) {
        console.error('Erro ao buscar última folha:', e);
    }
}

function fecharModalNovaFolha() {
    const modal = document.getElementById('modalNovaFolha');
    modal.classList.remove('active');
    setTimeout(() => { modal.style.display = 'none'; }, 200);
}

async function criarNovaFolha() {
    const obra   = document.getElementById('modalNovaFolhaObra').value;
    const data   = document.getElementById('modalNovaFolhaData').value;
    const copiar = document.getElementById('chkCopiarUltima').checked && _ultimaFolhaId;
    if (!obra || !data) { toast.warning('Selecione obra e data.'); return; }

    const btn = document.getElementById('modalNovaFolhaConfirmar');
    btn.disabled = true;
    btn.textContent = 'Criando…';

    try {
        // Cria a folha
        const { data: novaFolha } = await dbClient
            .from('folhas').insert({ obra, quinzena: data }).select('id').single();

        // Copia funcionários da última folha se solicitado
        if (copiar && novaFolha?.id) {
            const { data: funcs } = await dbClient
                .from('folha_funcionarios').select('nome, pix, nome_conta, servico, etapa, diarias, valor')
                .eq('folha_id', _ultimaFolhaId);

            if (funcs?.length) {
                const registros = funcs.map(f => ({ ...f, folha_id: novaFolha.id }));
                await dbClient.from('folha_funcionarios').insert(registros);
                toast.success(`Folha criada com ${funcs.length} funcionário(s) copiado(s)!`);
            } else {
                toast.success('Folha criada! (última folha estava vazia)');
            }
        } else {
            toast.success('Folha criada!');
        }

        fecharModalNovaFolha();
        document.getElementById('selObra').value = obra;
        await carregarFolhas(obra);
    } catch (e) {
        toast.error('Erro ao criar folha: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Criar Folha';
    }
}

// ── Modal: Fechar Folha ───────────────────────────────────────────────────────
function abrirModalFechar() {
    if (!folhaAtual) return;
    const ativas    = linhasLocais.filter(l => !l._deleted && calcularValor(l.servico, l.diarias) > 0);

    // Valida que todos os funcionários ativos têm etapa
    const semEtapa = ativas.filter(l => !l.etapa);
    if (semEtapa.length > 0) {
        const nomes = semEtapa.map(l => l.nome || '(sem nome)').join(', ');
        toast.warning(`Etapa obrigatória para: ${nomes}`);
        return;
    }

    const porEtapa  = {};
    ativas.forEach(l => {
        const e = l.etapa;
        porEtapa[e] = (porEtapa[e] || 0) + calcularValor(l.servico, l.diarias);
    });
    const total = Object.values(porEtapa).reduce((s, v) => s + v, 0);

    const linhasResumo = Object.entries(porEtapa).map(([e, v]) =>
        `<div style="display:flex;justify-content:space-between;"><span>${e}</span><strong class="fin-num">${formatCurrency(v)}</strong></div>`
    ).join('');

    document.getElementById('resumoFechar').innerHTML = `
        ${linhasResumo}
        <div style="border-top:1px solid var(--outline-ghost);margin-top:var(--sp-3);padding-top:var(--sp-3);display:flex;justify-content:space-between;">
            <span><strong>Total</strong></span>
            <strong class="fin-num" style="color:var(--success);">${formatCurrency(total)}</strong>
        </div>`;

    const modal = document.getElementById('modalFecharFolha');
    modal.style.display = 'flex';
    requestAnimationFrame(() => modal.classList.add('active'));
}

function fecharModalFechar() {
    const modal = document.getElementById('modalFecharFolha');
    modal.classList.remove('active');
    setTimeout(() => { modal.style.display = 'none'; }, 200);
}

async function confirmarFecharFolha() {
    if (!folhaAtual) return;
    const btn = document.getElementById('modalFecharFolhaConfirmar');
    btn.disabled = true;
    btn.textContent = 'Fechando…';

    try {
        // Salva primeiro para garantir que os dados estão atualizados
        await salvarFolha();

        // Monta payload para API
        const comprovantesInput = document.getElementById('inputComprovantesFechar');
        const comprovantes      = [];
        const compTipos         = [];

        for (const file of (comprovantesInput.files || [])) {
            const b64 = await fileToBase64(file);
            comprovantes.push(b64);
            compTipos.push(file.type);
        }

        const res = await fetch(`http://${location.hostname}:8000/api/folha/fechar`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                folha_id:           folhaAtual.id,
                obra:               folhaAtual.obra,
                quinzena:           folhaAtual.quinzena,
                comprovantes:       comprovantes,
                comprovantes_tipos: compTipos,
            }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
            throw new Error(err.detail || res.statusText);
        }

        fecharModalFechar();
        toast.success('Folha fechada! Despesas geradas em c_despesas.');

        // Atualiza estado local
        folhaAtual.status = 'fechada';
        atualizarOpcaoQuinzena(folhaAtual.id, 'fechada');
        renderizarStatusBadge();
        renderizarBotoesAcao();
        atualizarKPIs();
        renderizarTabela();
        await carregarComprovantes(folhaAtual.id);

    } catch (e) {
        toast.error('Erro ao fechar folha: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Confirmar Fechamento`;
    }
}

// ── Excluir rascunho ──────────────────────────────────────────────────────────
async function excluirRascunho() {
    if (!folhaAtual || folhaAtual.status !== 'rascunho') return;
    if (!confirm(`Excluir a folha de ${formatarData(folhaAtual.quinzena)}? Esta ação não pode ser desfeita.`)) return;
    try {
        await dbClient.from('folha_funcionarios').delete().eq('folha_id', folhaAtual.id);
        await dbClient.from('folhas').delete().eq('id', folhaAtual.id);
        toast.success('Folha excluída.');
        const obra = folhaAtual.obra;
        folhaAtual = null;
        esconderSecoes();
        await carregarFolhas(obra);
    } catch (e) {
        toast.error('Erro ao excluir: ' + e.message);
    }
}

// ── Reabrir folha ─────────────────────────────────────────────────────────────
async function reabrirFolha() {
    if (!folhaAtual || !confirm('Reabrir a folha irá remover os lançamentos em c_despesas. Confirmar?')) return;
    try {
        await dbClient.from('c_despesas').delete().eq('folha_id', folhaAtual.id);
        await dbClient.from('folhas').update({ status: 'rascunho' }).eq('id', folhaAtual.id);
        folhaAtual.status = 'rascunho';
        atualizarOpcaoQuinzena(folhaAtual.id, 'rascunho');
        renderizarStatusBadge();
        renderizarBotoesAcao();
        atualizarKPIs();
        renderizarTabela();
        toast.success('Folha reaberta!');
    } catch (e) {
        toast.error('Erro ao reabrir: ' + e.message);
    }
}

// ── Enviar comprovantes ───────────────────────────────────────────────────────
async function enviarComprovantes() {
    const input = document.getElementById('inputComprovantes');
    if (!input.files?.length) { toast.warning('Selecione ao menos um arquivo.'); return; }
    if (!folhaAtual) return;

    const btn = document.getElementById('btnEnviarComprovantes');
    btn.disabled = true;
    btn.textContent = 'Enviando…';

    try {
        // Precisa de despesas vinculadas
        const { data: despesas, error: errDespesas } = await dbClient.from('c_despesas').select('id').eq('folha_id', folhaAtual.id);
        if (errDespesas) throw new Error(`Erro ao buscar despesas: ${errDespesas.message}`);
        const ids = (despesas || []).map(d => d.id);
        if (ids.length === 0) {
            toast.warning('Nenhuma despesa vinculada a esta folha. Verifique se a coluna folha_id existe em c_despesas.');
            return;
        }

        const supabaseUrl = window.ENV.SUPABASE_URL.replace(/\/$/, '');
        for (const file of input.files) {
            const ext  = file.name.split('.').pop().toLowerCase();
            const nome = `folha_${folhaAtual.quinzena}_${folhaAtual.obra.slice(0, 15).replace(/\s+/g, '_')}_${Date.now()}.${ext}`;
            const { error } = await dbClient.storage.from('comprovantes').upload(nome, file, { upsert: true });
            if (error) throw error;
            const url = `${supabaseUrl}/storage/v1/object/public/comprovantes/${nome}`;
            for (const did of ids) {
                await dbClient.from('comprovantes_despesa').insert({ despesa_id: did, url, nome_arquivo: nome });
            }
        }
        // Atualiza tem_nota_fiscal em todas as despesas desta folha
        for (const did of ids) {
            await dbClient.from('c_despesas').update({ tem_nota_fiscal: true }).eq('id', did);
        }
        input.value = '';
        toast.success(`${input.files?.length || 0} comprovante(s) enviado(s)!`);
        await carregarComprovantes(folhaAtual.id);
    } catch (e) {
        toast.error('Erro ao enviar: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg> Enviar comprovantes`;
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function popularSelectObra(id) {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = '<option value="">Selecione uma obra</option>';
    obras.forEach(o => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = o;
        sel.appendChild(opt);
    });
}

function atualizarOpcaoQuinzena(folhaId, novoStatus) {
    const sel = document.getElementById('selQuinzena');
    const opt = sel.querySelector(`option[value="${folhaId}"]`);
    if (!opt) return;
    const emoji  = { rascunho: '🟡', enviada: '🔵', fechada: '🟢' }[novoStatus] || '⚪';
    const quinz  = opt.dataset.quinzena;
    opt.textContent = `${quinz}  ${emoji} ${(STATUS_LABEL[novoStatus] || novoStatus).toUpperCase()}`;
    opt.dataset.status = novoStatus;
}

function formatarData(dateStr) {
    if (!dateStr) return '';
    const [y, m, d] = dateStr.split('-');
    return `${d}/${m}/${y}`;
}

function formatCurrency(v) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0);
}

function esc(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload  = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}
