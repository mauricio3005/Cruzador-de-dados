/* Despesas Recorrentes — app.js */

const API_BASE  = window.API_BASE || `http://${location.hostname}:8000`;
let dbClient    = null;
let registros   = [];       // todos os templates carregados
let filtroAtual = 'ativas'; // 'ativas' | 'todas'
let editandoId  = null;     // id do template em edição (null = novo)

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    if (!window.ENV) { toast.error('ENV não carregado'); return; }
    dbClient = window.supabase.createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY);

    // Registrar listeners antes do carregamento para não perder cliques em caso de erro
    document.getElementById('btnNova').addEventListener('click', () => abrirModal(null));
    document.getElementById('btnProcessar').addEventListener('click', processarVencidas);
    document.getElementById('btnSalvarModal').addEventListener('click', salvarModal);
    document.getElementById('btnFiltroAtivas').classList.add('active');

    try {
        await Promise.all([carregarReferencias(), carregarRecorrentes()]);
    } catch (e) {
        toast.error('Erro ao carregar dados: ' + e.message);
    }
});

// ── Referências (selects) ─────────────────────────────────────────────────────

async function carregarReferencias() {
    const [obras, etapas, tipos, forn, cats, formas] = await Promise.all([
        dbClient.from('obras').select('nome').order('nome'),
        dbClient.from('etapas').select('nome').order('nome'),
        dbClient.from('tipos_custo').select('nome'),
        dbClient.from('fornecedores').select('nome').order('nome'),
        dbClient.from('categorias_despesa').select('nome').order('nome'),
        dbClient.from('formas_pagamento').select('nome').order('nome'),
    ]);

    preencherSelect('mObra',       obras.data,  'nome', '— Selecione —');
    preencherSelect('mEtapa',      etapas.data, 'nome', '— Selecione —');
    preencherSelect('mTipo',       tipos.data,  'nome', '— Selecione —');
    preencherSelect('mFornecedor', forn.data,   'nome', '— Selecione —');
    preencherSelect('mDespesa',    cats.data,   'nome', '— Selecione —');
    preencherSelect('mForma',      formas.data, 'nome', '— Selecione —');
}

function preencherSelect(id, items, campo, placeholder) {
    const sel = document.getElementById(id);
    sel.innerHTML = `<option value="">${placeholder}</option>`;
    (items || []).forEach(r => {
        const o = document.createElement('option');
        o.value = r[campo]; o.textContent = r[campo];
        sel.appendChild(o);
    });
}

// ── Carregar lista ────────────────────────────────────────────────────────────

async function carregarRecorrentes() {
    try {
        const res = await (window.apiFetch ? window.apiFetch('/api/recorrentes') : fetch(`${API_BASE}/api/recorrentes`));
        if (!res.ok) { toast.error('Erro ao carregar recorrentes'); return; }
        registros = await res.json();
        atualizarStats();
        renderTabela();
    } catch (e) {
        toast.error('API indisponível — verifique se o servidor está rodando');
    }
}

// ── Stats ─────────────────────────────────────────────────────────────────────

function atualizarStats() {
    const hoje    = new Date().toISOString().slice(0, 10);
    const ativas  = registros.filter(r => r.ativa);
    const vencidas = ativas.filter(r => r.proxima_data <= hoje);

    // Valor mensal estimado (normalizado para 1 mês)
    const MULT = { mensal: 1, trimestral: 1/3, semestral: 1/6, anual: 1/12 };
    const mensal = ativas.reduce((s, r) => s + (r.valor_total * (MULT[r.frequencia] || 1)), 0);

    document.getElementById('statAtivas').textContent  = ativas.length;
    document.getElementById('statVencidas').textContent = vencidas.length || '0';
    document.getElementById('statMensal').textContent  = 'R$ ' + mensal.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
}

// ── Filtro ────────────────────────────────────────────────────────────────────

function setFiltro(f) {
    filtroAtual = f;
    document.getElementById('btnFiltroAtivas').classList.toggle('active', f === 'ativas');
    document.getElementById('btnFiltroTodas').classList.toggle('active',  f === 'todas');
    renderTabela();
}

// ── Render tabela ─────────────────────────────────────────────────────────────

function renderTabela() {
    const hoje  = new Date().toISOString().slice(0, 10);
    const lista = filtroAtual === 'ativas' ? registros.filter(r => r.ativa) : registros;
    const tbody = document.getElementById('tabelaBody');

    if (!lista.length) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--on-surface-muted);padding:var(--sp-6);">Nenhuma recorrente cadastrada.</td></tr>`;
        return;
    }

    tbody.innerHTML = lista.map(r => {
        const vencida   = r.ativa && r.proxima_data <= hoje;
        const dataLabel = formatData(r.proxima_data);
        const dataStyle = vencida ? 'color:var(--danger);font-weight:600;' : '';
        const badge     = r.ativa
            ? `<span style="background:rgba(34,197,94,.15);color:#16a34a;border-radius:999px;padding:2px 10px;font-size:0.75rem;font-weight:600;">Ativa</span>`
            : `<span style="background:rgba(148,163,184,.12);color:var(--on-surface-muted);border-radius:999px;padding:2px 10px;font-size:0.75rem;">Inativa</span>`;

        return `<tr>
            <td>
                <div style="font-weight:500;">${r.descricao || '—'}</div>
                ${r.fornecedor ? `<div style="font-size:0.78rem;color:var(--on-surface-muted);">${r.fornecedor}</div>` : ''}
            </td>
            <td>${r.obra || '—'}</td>
            <td>${r.tipo || '—'}</td>
            <td style="text-transform:capitalize;">${r.frequencia}</td>
            <td style="${dataStyle}">${dataLabel}${vencida ? ' ⚠' : ''}</td>
            <td class="text-right">R$ ${Number(r.valor_total).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
            <td>${badge}</td>
            <td>
                <div style="display:flex;gap:var(--sp-2);justify-content:flex-end;">
                    <button class="btn btn-outline btn-sm" onclick="abrirModal(${r.id})" title="Editar" style="padding:4px 10px;">✏</button>
                    <button class="btn btn-outline btn-sm" onclick="toggleAtiva(${r.id},${r.ativa})" title="${r.ativa ? 'Desativar' : 'Ativar'}" style="padding:4px 10px;">${r.ativa ? '⏸' : '▶'}</button>
                    <button class="btn btn-outline btn-sm" onclick="deletar(${r.id})" title="Excluir" style="padding:4px 10px;color:var(--danger);">✕</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function formatData(iso) {
    if (!iso) return '—';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function abrirModal(id) {
    editandoId = id;
    document.getElementById('modalTitulo').textContent = id ? 'Editar Despesa Recorrente' : 'Nova Despesa Recorrente';

    if (id) {
        const r = registros.find(x => x.id === id);
        if (!r) return;
        setVal('mObra',          r.obra        || '');
        setVal('mEtapa',         r.etapa       || '');
        setVal('mTipo',          r.tipo        || '');
        setVal('mFornecedor',    r.fornecedor  || '');
        setVal('mDespesa',       r.despesa     || '');
        setVal('mForma',         r.forma       || '');
        setVal('mValor',         r.valor_total);
        setVal('mFrequencia',    r.frequencia);
        setVal('mProximaData',   r.proxima_data);
        setVal('mDataFim',       r.data_fim    || '');
        setVal('mBanco',         r.banco       || '');
        setVal('mDescricao',     r.descricao   || '');
        document.getElementById('mAtiva').checked = r.ativa;
    } else {
        // Reset
        ['mObra','mEtapa','mTipo','mFornecedor','mDespesa','mForma','mBanco','mDescricao','mDataFim'].forEach(id => setVal(id, ''));
        setVal('mValor', '');
        setVal('mFrequencia', 'mensal');
        setVal('mProximaData', new Date().toISOString().slice(0, 10));
        document.getElementById('mAtiva').checked = true;
    }

    const modal = document.getElementById('modal');
    modal.style.display = 'flex';
}

function fecharModal(e) {
    if (e && e.target !== document.getElementById('modal')) return;
    document.getElementById('modal').style.display = 'none';
}

function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val ?? '';
}

// ── Salvar ────────────────────────────────────────────────────────────────────

async function salvarModal() {
    const valor      = parseFloat(document.getElementById('mValor').value);
    const proxData   = document.getElementById('mProximaData').value;
    const descricao  = document.getElementById('mDescricao').value.trim();

    if (!valor || valor <= 0) { toast.warning('Informe um valor válido'); return; }
    if (!proxData)            { toast.warning('Informe a próxima data'); return; }
    if (!descricao)           { toast.warning('Informe uma descrição'); return; }

    const payload = {
        obra:           document.getElementById('mObra').value         || null,
        etapa:          document.getElementById('mEtapa').value        || null,
        tipo:           document.getElementById('mTipo').value         || null,
        fornecedor:     document.getElementById('mFornecedor').value   || null,
        despesa:        document.getElementById('mDespesa').value      || null,
        forma:          document.getElementById('mForma').value        || null,
        banco:          document.getElementById('mBanco').value        || null,
        descricao,
        valor_total:    valor,
        frequencia:     document.getElementById('mFrequencia').value,
        proxima_data:   proxData,
        data_fim:       document.getElementById('mDataFim').value      || null,
        ativa:          document.getElementById('mAtiva').checked,
    };

    const btn = document.getElementById('btnSalvarModal');
    btn.disabled = true; btn.textContent = 'Salvando…';

    try {
        const path   = editandoId ? `/api/recorrentes/${editandoId}` : '/api/recorrentes';
        const method = editandoId ? 'PUT' : 'POST';
        const res    = await (window.apiFetch
            ? window.apiFetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            : fetch(`${API_BASE}${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }));

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Erro ao salvar');
        }

        toast.success(editandoId ? 'Recorrente atualizada!' : 'Recorrente criada!');
        document.getElementById('modal').style.display = 'none';
        await carregarRecorrentes();
    } catch (e) {
        toast.error(e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Salvar';
    }
}

// ── Toggle ativa / Deletar ────────────────────────────────────────────────────

async function toggleAtiva(id, ativa) {
    const r = registros.find(x => x.id === id);
    if (!r) return;
    await (window.apiFetch
        ? window.apiFetch(`/api/recorrentes/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...r, ativa: !ativa }) })
        : fetch(`${API_BASE}/api/recorrentes/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...r, ativa: !ativa }) }));
    toast.success(!ativa ? 'Recorrente ativada' : 'Recorrente desativada');
    await carregarRecorrentes();
}

async function deletar(id) {
    if (!confirm('Excluir esta despesa recorrente?')) return;
    const res = await (window.apiFetch ? window.apiFetch(`/api/recorrentes/${id}`, { method: 'DELETE' }) : fetch(`${API_BASE}/api/recorrentes/${id}`, { method: 'DELETE' }));
    if (res.ok || res.status === 204) {
        toast.success('Excluída com sucesso');
        await carregarRecorrentes();
    } else {
        toast.error('Erro ao excluir');
    }
}

// ── Processar vencidas ────────────────────────────────────────────────────────

async function processarVencidas() {
    const btn = document.getElementById('btnProcessar');
    btn.disabled = true; btn.textContent = 'Processando…';

    try {
        const res  = await (window.apiFetch ? window.apiFetch('/api/recorrentes/processar', { method: 'POST' }) : fetch(`${API_BASE}/api/recorrentes/processar`, { method: 'POST' }));
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || 'Erro ao processar');

        if (data.despesas_criadas === 0) {
            toast.info('Nenhuma recorrente vencida no momento');
        } else {
            toast.success(`${data.despesas_criadas} despesa(s) gerada(s) com sucesso!`);
        }
        await carregarRecorrentes();
    } catch (e) {
        toast.error(e.message);
    } finally {
        btn.disabled = false; btn.textContent = 'Processar Vencidas';
    }
}
