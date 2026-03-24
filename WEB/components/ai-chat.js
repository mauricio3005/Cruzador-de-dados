/**
 * ai-chat.js — Widget de chat com IA, global para todas as páginas.
 * Injetado automaticamente em quem importar este script.
 */
(function () {
    const API_BASE = `http://${location.hostname}:8000`;
    const STORAGE_KEY = 'ai_chat_historico';
    const VISUAL_KEY  = 'ai_chat_visual';
    let historico = [];   // [{role, content}]
    let aberto    = false;

    function salvarHistorico() {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(historico));
        } catch (_) {}
    }

    function salvarVisual() {
        const msgs = document.getElementById('ai-chat-messages');
        if (!msgs) return;
        try {
            sessionStorage.setItem(VISUAL_KEY, msgs.innerHTML);
        } catch (_) {}
    }

    function restaurarHistorico() {
        try {
            const h = sessionStorage.getItem(STORAGE_KEY);
            if (h) historico = JSON.parse(h);
        } catch (_) {}
    }

    function restaurarVisual() {
        const msgs = document.getElementById('ai-chat-messages');
        if (!msgs) return;
        try {
            const v = sessionStorage.getItem(VISUAL_KEY);
            if (v) {
                msgs.innerHTML = v;
                msgs.scrollTop = msgs.scrollHeight;
                // Oculta sugestões se já há conversa
                if (historico.length > 0) {
                    const sug = document.getElementById('ai-chat-sugestoes');
                    if (sug) sug.style.display = 'none';
                }
            }
        } catch (_) {}
    }

    // ── Detecta obra/página atualmente "ativa" no contexto da página ──
    function getContexto() {
        const pagina = location.pathname.split('/').filter(Boolean).pop() || 'dashboard';
        // Tenta ler filtro de obra de selects comuns
        const obraEl = document.getElementById('filtroObra')
                    || document.getElementById('fObra')
                    || document.getElementById('obraDropdownText');
        const obra = (obraEl && obraEl.value && obraEl.value !== '' && obraEl.value !== 'Selecionar Obras')
            ? obraEl.value : null;
        return { pagina, obra };
    }

    // ── Injeta HTML do widget ──
    function injectWidget() {
        const el = document.createElement('div');
        el.id = 'ai-chat-widget';
        el.innerHTML = `
<style>
#ai-chat-widget {
    position: fixed;
    bottom: var(--sp-6, 24px);
    right: var(--sp-6, 24px);
    z-index: 9999;
    font-family: var(--font-body, 'Inter', sans-serif);
    /* Dark-theme token overrides — isola o widget do light theme da página */
    --on-surface: #e8e8f0;
    --on-surface-muted: #888;
    --surface-elevated: #22222e;
    --surface-base: #0f0f14;
    --surface-card: #1a1a24;
    --outline: rgba(255,255,255,.1);
    --outline-ghost: rgba(255,255,255,.07);
}

#ai-chat-btn {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--primary, #7c5cbf);
    color: #fff;
    box-shadow: 0 4px 20px rgba(0,0,0,.35);
    transition: transform .2s, box-shadow .2s;
    font-size: 1.35rem;
}
#ai-chat-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 28px rgba(0,0,0,.45);
}
#ai-chat-btn .ai-badge {
    position: absolute;
    top: -3px;
    right: -3px;
    width: 14px;
    height: 14px;
    background: var(--secondary, #7bb8f5);
    border-radius: 50%;
    border: 2px solid var(--surface-base, #0f0f14);
    animation: pulse-badge 2s infinite;
}
@keyframes pulse-badge {
    0%, 100% { transform: scale(1); opacity: 1; }
    50%       { transform: scale(1.15); opacity: .7; }
}

#ai-chat-panel {
    display: none;
    position: absolute;
    bottom: 64px;
    right: 0;
    width: 480px;
    max-height: 820px;
    background: var(--surface-card, #1a1a24);
    border-radius: var(--r-xl, 16px);
    box-shadow: 0 8px 40px rgba(0,0,0,.6);
    flex-direction: column;
    overflow: hidden;
    border: 1px solid var(--outline-ghost, rgba(255,255,255,.07));
    animation: slide-up .22s ease;
}
@keyframes slide-up {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
#ai-chat-panel.open { display: flex; }

.ai-chat-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    background: var(--primary, #7c5cbf);
    color: #fff;
    flex-shrink: 0;
}
.ai-chat-header-icon {
    font-size: 1.2rem;
}
.ai-chat-header-title {
    font-weight: 700;
    font-size: .92rem;
    font-family: var(--font-display, 'Manrope', sans-serif);
    flex: 1;
}
.ai-chat-header-sub {
    font-size: .72rem;
    opacity: .8;
}
.ai-chat-close {
    background: none;
    border: none;
    color: rgba(255,255,255,.8);
    cursor: pointer;
    font-size: 1.1rem;
    line-height: 1;
    padding: 4px;
}
.ai-chat-close:hover { color: #fff; }

.ai-chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 14px 14px 8px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    scrollbar-width: thin;
}

.ai-msg {
    max-width: 88%;
    padding: 9px 12px;
    border-radius: 12px;
    font-size: .84rem;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
}
.ai-msg.user {
    align-self: flex-end;
    background: var(--primary, #7c5cbf);
    color: #fff;
    border-bottom-right-radius: 4px;
}
.ai-msg.assistant {
    align-self: flex-start;
    background: var(--surface-elevated, #22222e);
    color: var(--on-surface, #e8e8f0);
    border-bottom-left-radius: 4px;
}
.ai-msg.loading {
    align-self: flex-start;
    background: var(--surface-elevated, #22222e);
    color: var(--on-surface-muted, #888);
}
.ai-typing-dots { display: inline-flex; gap: 4px; align-items: center; height: 18px; }
.ai-typing-dots span {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--on-surface-muted, #888);
    animation: ai-bounce 1.2s infinite ease-in-out;
}
.ai-typing-dots span:nth-child(2) { animation-delay: .2s; }
.ai-typing-dots span:nth-child(3) { animation-delay: .4s; }
@keyframes ai-bounce {
    0%, 80%, 100% { transform: translateY(0); opacity: .4; }
    40%            { transform: translateY(-5px); opacity: 1; }
}

.ai-chat-sugestoes {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 0 14px 10px;
}
.ai-chat-sugestao {
    font-size: .75rem;
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid var(--outline-ghost, rgba(255,255,255,.1));
    background: none;
    color: var(--on-surface-muted, #888);
    cursor: pointer;
    transition: border-color .15s, color .15s;
}
.ai-chat-sugestao:hover {
    border-color: var(--primary, #7c5cbf);
    color: var(--primary, #7c5cbf);
}

.ai-chat-input-wrap {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 10px 14px 14px;
    border-top: 1px solid var(--outline-ghost, rgba(255,255,255,.06));
    flex-shrink: 0;
}
#ai-chat-input {
    flex: 1;
    border: 1px solid var(--outline, rgba(255,255,255,.1));
    border-radius: 10px;
    padding: 8px 12px;
    font-size: .84rem;
    background: var(--surface-elevated, #22222e);
    color: var(--on-surface, #e8e8f0);
    resize: none;
    font-family: var(--font-body, 'Inter', sans-serif);
    line-height: 1.4;
    max-height: 100px;
    outline: none;
    transition: border-color .15s;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,.15) transparent;
}
#ai-chat-input::-webkit-scrollbar { width: 4px; }
#ai-chat-input::-webkit-scrollbar-track { background: transparent; }
#ai-chat-input::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,.15);
    border-radius: 4px;
}
#ai-chat-input::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,.28); }
#ai-chat-input:focus {
    border-color: var(--primary, #7c5cbf);
}
#ai-chat-input::placeholder { color: var(--on-surface-muted, #666); }

#ai-chat-send {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: none;
    background: var(--primary, #7c5cbf);
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: opacity .15s;
}
#ai-chat-send:disabled { opacity: .4; cursor: default; }
#ai-chat-send:not(:disabled):hover { opacity: .85; }

.ai-action-banner {
    margin: 4px 14px 10px;
    padding: 10px 14px;
    background: var(--secondary-container, rgba(123,184,245,.1));
    border-radius: 10px;
    font-size: .82rem;
    color: var(--on-surface, #e8e8f0);
    border-left: 3px solid var(--secondary, #7bb8f5);
}
.ai-action-banner strong { display: block; margin-bottom: 4px; color: var(--secondary, #7bb8f5); }
.ai-action-banner .ai-action-btns { display: flex; gap: 8px; margin-top: 8px; }
.ai-action-btn {
    font-size: .78rem;
    padding: 4px 12px;
    border-radius: 6px;
    border: 1px solid var(--secondary, #7bb8f5);
    background: none;
    color: var(--secondary, #7bb8f5);
    cursor: pointer;
}
.ai-action-btn.primary {
    background: var(--secondary, #7bb8f5);
    color: #000;
}
</style>

<button id="ai-chat-btn" title="Assistente IA" aria-label="Abrir assistente de IA">
    ✨
    <span class="ai-badge"></span>
</button>

<div id="ai-chat-panel" role="dialog" aria-label="Chat com assistente de IA">
    <div class="ai-chat-header">
        <span class="ai-chat-header-icon">🤖</span>
        <div style="flex:1">
            <div class="ai-chat-header-title">Assistente IA</div>
            <div class="ai-chat-header-sub">Industrial Architect Finance Suite</div>
        </div>
        <button class="ai-chat-close" id="ai-chat-clear-btn" title="Limpar conversa" style="font-size:.85rem;opacity:.7;margin-right:2px">🗑</button>
        <button class="ai-chat-close" id="ai-chat-close-btn" title="Fechar">✕</button>
    </div>

    <div class="ai-chat-messages" id="ai-chat-messages">
        <div class="ai-msg assistant">Como posso ajudar?</div>
    </div>

    <div class="ai-chat-sugestoes" id="ai-chat-sugestoes">
        <button class="ai-chat-sugestao" onclick="aiChatSugerir(this)">Resumo financeiro</button>
        <button class="ai-chat-sugestao" onclick="aiChatSugerir(this)">Maiores fornecedores</button>
        <button class="ai-chat-sugestao" onclick="aiChatSugerir(this)">Obras com mais gastos</button>
        <button class="ai-chat-sugestao" onclick="aiChatSugerir(this)">Como cadastrar despesa?</button>
    </div>

    <div id="ai-action-area"></div>

    <div class="ai-chat-input-wrap">
        <textarea id="ai-chat-input" placeholder="Pergunte algo ou descreva uma despesa…" rows="1"></textarea>
        <button id="ai-chat-send" title="Enviar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
        </button>
    </div>
</div>
`;
        document.body.appendChild(el);

        // Restaura histórico e visual da sessão anterior
        restaurarHistorico();
        restaurarVisual();

        // Eventos
        document.getElementById('ai-chat-btn').addEventListener('click', () => toggleChat(true));
        document.getElementById('ai-chat-close-btn').addEventListener('click', () => toggleChat(false));
        document.getElementById('ai-chat-clear-btn').addEventListener('click', () => {
            historico = [];
            sessionStorage.removeItem(STORAGE_KEY);
            sessionStorage.removeItem(VISUAL_KEY);
            const msgs = document.getElementById('ai-chat-messages');
            msgs.innerHTML = '<div class="ai-msg assistant">Como posso ajudar?</div>';
            document.getElementById('ai-chat-sugestoes').style.display = '';
        });
        document.getElementById('ai-chat-send').addEventListener('click', enviarMensagem);
        const input = document.getElementById('ai-chat-input');
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarMensagem(); }
        });
        // Auto-resize textarea
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 100) + 'px';
        });
    }

    function toggleChat(force) {
        aberto = (force !== undefined) ? force : !aberto;
        const panel = document.getElementById('ai-chat-panel');
        if (aberto) {
            panel.classList.add('open');
            document.getElementById('ai-chat-input').focus();
            // Esconde badge ao abrir
            document.querySelector('#ai-chat-btn .ai-badge').style.display = 'none';
        } else {
            panel.classList.remove('open');
        }
    }

    function appendMsg(role, text) {
        const msgs = document.getElementById('ai-chat-messages');
        const div  = document.createElement('div');
        div.className = `ai-msg ${role}`;
        div.textContent = text;
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
        salvarVisual();
        return div;
    }

    function showLoading() {
        const msgs = document.getElementById('ai-chat-messages');
        const div  = document.createElement('div');
        div.className = 'ai-msg loading';
        div.innerHTML = '<div class="ai-typing-dots"><span></span><span></span><span></span></div>';
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
        return div;
    }

    async function enviarMensagem() {
        const input = document.getElementById('ai-chat-input');
        const send  = document.getElementById('ai-chat-send');
        const texto = input.value.trim();
        if (!texto) return;

        // Limpa sugestões na primeira mensagem real
        document.getElementById('ai-chat-sugestoes').style.display = 'none';

        appendMsg('user', texto);
        historico.push({ role: 'user', content: texto });
        salvarHistorico();
        input.value = '';
        input.style.height = 'auto';
        send.disabled = true;

        const loader = showLoading();

        const { pagina, obra } = getContexto();

        try {
            const res = await fetch(`${API_BASE}/api/ai/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mensagem: texto,
                    historico: historico.slice(-10),   // últimas 10 trocas
                    obra,
                    pagina,
                }),
            });

            if (!res.ok) {
                const err = await res.text();
                throw new Error(err);
            }

            const data = await res.json();
            loader.remove();

            // Ação especial: cadastrar despesa
            if (data.acao === 'cadastrar_despesa') {
                const msg = data.mensagem || 'Identifiquei uma despesa. Deseja abrir o formulário?';
                const despesaSugerida = data.despesa || {};
                appendMsg('assistant', msg);
                historico.push({ role: 'assistant', content: msg });
                salvarHistorico();
                mostrarAcaoCadastro(despesaSugerida);
            } else {
                const resposta = data.resposta || '(sem resposta)';
                appendMsg('assistant', resposta);
                historico.push({ role: 'assistant', content: resposta });
                salvarHistorico();
            }
        } catch (err) {
            loader.remove();
            appendMsg('assistant', '⚠️ Erro ao contatar o servidor: ' + err.message);
        } finally {
            send.disabled = false;
            input.focus();
        }
    }

    function mostrarAcaoCadastro(despesa) {
        const area = document.getElementById('ai-action-area');
        const linhas = [
            despesa.FORNECEDOR ? `Fornecedor: ${despesa.FORNECEDOR}` : '',
            despesa.DESCRICAO  ? `Descrição: ${despesa.DESCRICAO}`   : '',
            despesa.VALOR_TOTAL ? `Valor: R$ ${Number(despesa.VALOR_TOTAL).toLocaleString('pt-BR', {minimumFractionDigits:2})}` : '',
            despesa.DATA       ? `Data: ${despesa.DATA.split('-').reverse().join('/')}` : '',
            despesa.OBRA       ? `Obra: ${despesa.OBRA}`             : '',
            despesa.ETAPA      ? `Etapa: ${despesa.ETAPA}`           : '',
        ].filter(Boolean);

        area.innerHTML = `
            <div class="ai-action-banner">
                <strong>💡 Despesa identificada</strong>
                ${linhas.join(' · ')}
                <div class="ai-action-btns">
                    <button class="ai-action-btn primary" onclick="aiChatAbrirDespesas(${JSON.stringify(despesa).replace(/"/g,'&quot;')})">Abrir em Despesas</button>
                    <button class="ai-action-btn" onclick="document.getElementById('ai-action-area').innerHTML=''">Dispensar</button>
                </div>
            </div>`;
    }

    // Expõe globais para uso nos botões inline
    window.aiChatSugerir = function(btn) {
        const txt = btn.textContent.trim();
        document.getElementById('ai-chat-input').value = txt;
        enviarMensagem();
    };

    window.aiChatAbrirDespesas = function(despesaStr) {
        let despesa;
        try { despesa = typeof despesaStr === 'string' ? JSON.parse(despesaStr) : despesaStr; }
        catch { despesa = {}; }

        // Navega para despesas com dados pré-preenchidos (usuário revisa e confirma)
        sessionStorage.setItem('ai_despesa_prefill', JSON.stringify(despesa));
        const base = new URL('../', location.href).href;
        location.href = base + 'despesas/';
    };

    // ── Inicializa quando o DOM estiver pronto ──
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectWidget);
    } else {
        injectWidget();
    }
})();
