/**
 * toast.js — Sistema de notificações toast.
 * Uso: toast.success("Salvo!") | toast.error("Erro!") | toast.info("Info")
 */

const toast = (() => {
    let container = null;

    function _getContainer() {
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            document.body.appendChild(container);
        }
        return container;
    }

    function _show(message, type = "info", duration = 4000) {
        const c = _getContainer();
        const el = document.createElement("div");
        el.className = `toast toast-${type}`;

        const icons = { success: "✅", error: "❌", info: "ℹ️", warning: "⚠️" };
        el.innerHTML = `
            <span class="toast-icon">${icons[type] || "ℹ️"}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>`;

        c.appendChild(el);

        // Animação de entrada
        requestAnimationFrame(() => el.classList.add("toast-visible"));

        // Auto-remover
        setTimeout(() => {
            el.classList.remove("toast-visible");
            el.addEventListener("transitionend", () => el.remove(), { once: true });
        }, duration);
    }

    return {
        success: (msg, duration) => _show(msg, "success", duration),
        error:   (msg, duration) => _show(msg, "error",   duration),
        info:    (msg, duration) => _show(msg, "info",    duration),
        warning: (msg, duration) => _show(msg, "warning", duration),
    };
})();
