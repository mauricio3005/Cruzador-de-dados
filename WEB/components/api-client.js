/**
 * api-client.js — Helper global para chamadas autenticadas ao backend.
 * Injetado automaticamente via nav.js em todas as páginas.
 * Uso: await apiFetch('/api/ai/chat', { method: 'POST', body: ... })
 */
(function() {
    const API_BASE = `http://${location.hostname}:8000`;

    window.API_BASE = API_BASE;

    window.apiFetch = async function(path, options = {}) {
        // Obtém sessão do Supabase (usa o cliente já criado ou cria um temporário)
        let token = null;
        try {
            const sb = window._supabaseClient || window.supabase?.createClient(
                window.ENV?.SUPABASE_URL,
                window.ENV?.SUPABASE_ANON_KEY
            );
            if (sb) {
                const { data: { session } } = await sb.auth.getSession();
                token = session?.access_token || null;
            }
        } catch (_) {}

        const headers = { ...(options.headers || {}) };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        // Não definir Content-Type se for FormData (browser define automaticamente com boundary)
        if (!(options.body instanceof FormData) && !headers['Content-Type'] && options.body) {
            headers['Content-Type'] = 'application/json';
        }

        return fetch(`${API_BASE}${path}`, { ...options, headers });
    };
})();
