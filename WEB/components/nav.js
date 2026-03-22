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
    { icon: "⚙️", label: "Configurações",    path: "/configuracoes/",    done: false },
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

function renderNav() {
    const container = document.getElementById("main-nav");
    if (!container) return;

    const BASE    = getAppBase();
    const current = window.location.pathname.replace(/\/index\.html$/, "/");

    const html = `
        <div class="nav-section-label">Módulos</div>
        <nav class="nav-links">
            ${NAV_ITEMS.map(item => {
                const href     = BASE + item.path;
                const basePath = BASE + "/";
                const isActive = (item.path === "/" && current === basePath)
                              || (item.path !== "/" && current.startsWith(BASE + item.path));
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
        </nav>`;

    container.innerHTML = html;
}

document.addEventListener("DOMContentLoaded", renderNav);
