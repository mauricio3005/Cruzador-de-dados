/**
 * helpers.js — Funções utilitárias compartilhadas entre todos os módulos.
 * Carregado via <script> antes de cada app.js.
 * Expõe tudo em window.* para compatibilidade com vanilla JS sem módulos ES.
 */

window.esc = function (s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
};

window.setStatus = function (estado, texto) {
    const el = document.getElementById('connectionStatus');
    if (!el) return;
    el.textContent = texto;
    el.className   = 'status-dot ' + estado;
};

window.formatarData = function (d) {
    if (!d) return '\u2014';
    const p = d.split('-');
    return p[2] + '/' + p[1] + '/' + p[0];
};

window.formatarValor = function (v) {
    return Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

window.formatarMoeda = function (v) {
    return Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

window.hoje = function () {
    return new Date().toISOString().split('T')[0];
};
