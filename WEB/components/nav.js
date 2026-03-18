/**
 * nav.js — Navegação principal injetada em todas as páginas.
 * Uso: adicione <div id="main-nav"></div> na sidebar e importe este script.
 */

const NAV_ITEMS = [
    { icon: "📊", label: "Dashboard",       href: "/",                  done: true  },
    { icon: "📋", label: "Despesas",         href: "/despesas/",         done: false },
    { icon: "🗂️", label: "Histórico",        href: "/historico/",        done: false },
    { icon: "👥", label: "Folha",            href: "/folha/",            done: false },
    { icon: "📄", label: "Documentos",       href: "/documentos/",       done: false },
    { icon: "💳", label: "Contas a Pagar",   href: "/contas/",           done: false },
    { icon: "💰", label: "Recebimentos",     href: "/recebimentos/",     done: false },
    { icon: "⚙️", label: "Configurações",    href: "/configuracoes/",    done: false },
];

function renderNav() {
    const container = document.getElementById("main-nav");
    if (!container) return;

    const current = window.location.pathname.replace(/\/index\.html$/, "/");

    const html = `
        <div class="nav-section-label">Módulos</div>
        <nav class="nav-links">
            ${NAV_ITEMS.map(item => {
                const href = item.href;
                const isActive = current === href || (href !== "/" && current.startsWith(href));
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
