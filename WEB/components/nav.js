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
    { icon: "📈", label: "Relatórios",       path: "/?tab=relatorio",    done: true  },
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
