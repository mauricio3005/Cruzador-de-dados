/**
 * nav.js — Navegação principal injetada em todas as páginas.
 * Uso: adicione <div id="main-nav"></div> na sidebar e importe este script.
 */

const NAV_ITEMS = [
    { icon: "📊", label: "Dashboard",       path: "/",                  done: true  },
    { icon: "📋", label: "Despesas",         path: "/despesas/",         done: true  },
    { icon: "🗂️", label: "Histórico",        path: "/historico/",        done: true  },
    { icon: "👥", label: "Folha",            path: "/folha/",            done: true  },
    { icon: "📄", label: "Documentos",       path: "/documentos/",       done: true  },
    { icon: "💳", label: "Contas a Pagar",   path: "/contas/",           done: true  },
    { icon: "💰", label: "Recebimentos",     path: "/recebimentos/",     done: true  },
    { icon: "📝", label: "Contratos",        path: "/contratos/",        done: true  },
    { icon: "🔁", label: "Recorrentes",      path: "/recorrentes/",      done: true  },
    { icon: "🏦", label: "Remessas",         path: "/remessas/",         done: true  },
{ icon: "⚙️", label: "Configurações",    path: "/configuracoes/",    done: true  },
];

// Detecta o base path (ex: "/WEB" se servido de diretório pai)
function getAppBase() {
    const scripts = document.querySelectorAll('script[src]');
    for (const s of scripts) {
        if (s.src.includes('components/nav.js')) {
            return new URL('../', s.src).pathname.replace(/\/$/, '');
        }
    }
    return '';
}

// Verificação de auth + exposição do cliente Supabase
async function initAuth() {
    if (!window.ENV || !window.supabase) return;
    const appBase = getAppBase();
    // Não verificar na própria página de auth
    if (window.location.pathname.endsWith('/auth/') || window.location.pathname.endsWith('/auth/index.html')) return;

    const sb = window.supabase.createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY);
    window._supabaseClient = sb;

    window.getAuthToken = async function() {
        const { data: { session } } = await sb.auth.getSession();
        return session?.access_token || null;
    };

    const { data: { session } } = await sb.auth.getSession();
    if (!session) {
        window.location.replace(appBase + '/auth/');
        return false;
    }
    return true;
}

function iniciarUserDropdown(sb, appBase) {
    const avatarBtn = document.getElementById('userAvatarBtn');
    if (!avatarBtn) return;

    // Injeta o dropdown se ainda não existir no HTML
    if (!document.getElementById('userDropdown')) {
        const wrapper = avatarBtn.parentElement;
        wrapper.style.position = 'relative';
        const dd = document.createElement('div');
        dd.id = 'userDropdown';
        dd.style.cssText = 'display:none;position:fixed;top:52px;right:16px;z-index:999;background:var(--surface-card);border-radius:var(--r-xl);box-shadow:var(--shadow-lg);min-width:210px;padding:var(--sp-2) 0;overflow:hidden;';
        dd.innerHTML = `
            <div style="padding:var(--sp-4) var(--sp-5) var(--sp-3);border-bottom:1px solid var(--outline-ghost);">
                <div style="font-size:0.75rem;font-weight:600;color:var(--on-surface-muted);margin-bottom:2px;">Conectado como</div>
                <div id="userEmail" style="font-size:0.875rem;font-weight:600;color:var(--on-surface);word-break:break-all;">—</div>
            </div>
            <button id="logoutBtn" style="width:100%;text-align:left;padding:var(--sp-3) var(--sp-5);background:none;border:none;cursor:pointer;font-size:0.875rem;color:var(--error);font-weight:500;display:flex;align-items:center;gap:var(--sp-3);">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
                Sair
            </button>`;
        wrapper.appendChild(dd);
    }

    const dropdown = document.getElementById('userDropdown');
    const emailEl  = document.getElementById('userEmail');

    // Preencher e-mail
    sb.auth.getSession().then(({ data: { session } }) => {
        if (session?.user?.email && emailEl) emailEl.textContent = session.user.email;
    });

    avatarBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    });

    document.addEventListener('click', (e) => {
        if (!avatarBtn.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });

    document.getElementById('logoutBtn').addEventListener('click', async () => {
        await sb.auth.signOut();
        window.location.replace(appBase + '/auth/');
    });
}

function renderNav() {
    const container = document.getElementById("main-nav");
    if (!container) return;

    const BASE    = getAppBase();
    const current = window.location.pathname.replace(/\/index\.html$/, "/");
    const currentTab = new URLSearchParams(window.location.search).get('tab');

    const html = `
        <div class="nav-section-label">Módulos</div>
        <nav class="nav-links">
            ${NAV_ITEMS.map(item => {
                const href     = BASE + item.path;
                const basePath = BASE + "/";
                const itemTab  = item.path.includes('?tab=') ? item.path.split('?tab=')[1] : null;
                const isActive = itemTab
                    ? (current === basePath && currentTab === itemTab)
                    : (item.path === "/" && current === basePath && !currentTab)
                      || (item.path !== "/" && !item.path.includes('?') && current.startsWith(BASE + item.path));
                const classes = ["nav-link", isActive ? "active" : "", !item.done ? "nav-coming-soon" : ""].filter(Boolean).join(" ");
                return `
                    <a href="${item.done ? href : "#"}"
                       class="${classes}"
                       ${!item.done ? 'onclick="return false" title="Em breve"' : ""}>
                        <span class="nav-icon">${item.icon}</span>
                        <span class="nav-label">${item.label}</span>
                        ${!item.done ? '<span class="nav-badge">Em breve</span>' : ""}
                    </a>`;
            }).join("")}
        </nav>
        <button class="nav-logout" id="nav-logout-btn">Sair</button>`;

    container.innerHTML = html;

    document.getElementById('nav-logout-btn')?.addEventListener('click', async () => {
        if (window._supabaseClient) await window._supabaseClient.auth.signOut();
        const appBase = getAppBase();
        window.location.replace(appBase + '/auth/');
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    await initAuth();
    renderNav();
    if (window._supabaseClient) iniciarUserDropdown(window._supabaseClient, getAppBase());

    // Filtro global com tecla Enter
    document.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            const el = document.activeElement;
            if (el && (el.tagName === 'INPUT' || el.tagName === 'SELECT')) {
                // Ignora se estiver num modal ou se o ID for buscaTexto
                if (el.closest('[id^="modal"]')) return;
                
                const btn = document.getElementById('btnFiltrar');
                if (btn) {
                    e.preventDefault();
                    btn.click();
                }
            }
        }
    });
});

// ── Injeta o widget de chat de IA automaticamente ──
(function () {
    function getAiChatBase() {
        const scripts = document.querySelectorAll('script[src]');
        for (const s of scripts) {
            if (s.src.includes('components/nav.js')) {
                return new URL('./', s.src).href;
            }
        }
        return '';
    }
    const base = getAiChatBase();
    if (base) {
        // Injeta api-client.js primeiro (disponibiliza apiFetch antes do ai-chat.js)
        const apiClient = document.createElement('script');
        apiClient.src = base + 'api-client.js';
        document.head.appendChild(apiClient);

        const s = document.createElement('script');
        s.src = base + 'ai-chat.js';
        document.head.appendChild(s);
    }
})();
