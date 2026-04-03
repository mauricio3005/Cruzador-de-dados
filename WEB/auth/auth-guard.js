// auth-guard.js — incluir em páginas que precisam de autenticação
// nav.js já inclui esta verificação automaticamente; este arquivo é backup.
(async function() {
    if (window.__AUTH_CHECKED__) return;
    window.__AUTH_CHECKED__ = true;

    // Aguarda env.js e SDK carregarem
    if (!window.ENV || !window.supabase) return;

    // Não redireciona se já estiver na página de auth
    if (window.location.pathname.includes('/auth/')) return;

    const sb = window.supabase.createClient(window.ENV.SUPABASE_URL, window.ENV.SUPABASE_ANON_KEY);
    const { data: { session } } = await sb.auth.getSession();
    if (!session) {
        const base = window.location.pathname.split('/').slice(0, -2).join('/') || '';
        window.location.replace(base + '/auth/');
    }
})();
