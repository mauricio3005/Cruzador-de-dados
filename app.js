/**
 * DASHBOARD FINANCEIRO GERENCIAL
 * Arquivo principal de lógica (app.js)
 */

// --- CONFIGURAÇÃO SUPABASE ---
// As chaves são carregadas do arquivo local .env
let SUPABASE_URL = '';
let SUPABASE_ANON_KEY = '';
let dbClient;

// Função para carregar variáveis de ambiente do aqruivo .env
async function carregarEnv() {
    if (window.ENV) {
        SUPABASE_URL = window.ENV.SUPABASE_URL;
        SUPABASE_ANON_KEY = window.ENV.SUPABASE_ANON_KEY;

        if (SUPABASE_URL && SUPABASE_ANON_KEY) {
            dbClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        } else {
            console.error("Chaves não encontradas no arquivo env.js");
        }
    } else {
        console.error("Variável window.ENV não encontrada. Verifique se env.js foi carregado no HTML.");
    }
}

// --- VARIÁVEIS DE ESTADO ---
let rawData = [];
let filteredData = [];
let currentObraFilters = [];
let currentEtapaFilters = [];
let currentTipoFilters = [];

// Referências de Gráficos (Chart.js instâncias)
let barrasChartInstance = null;
let roscaChartInstance = null;
let rankingChartInstance = null;

// --- TEMA (MODO ESCURO) ---
const getThemeColors = () => {
    const isDark = document.body.classList.contains('dark-mode');
    return {
        text: isDark ? '#9CA3AF' : '#6B7280',
        grid: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
        barBg: isDark ? '#4B5563' : '#D1D5DB'
    };
};

function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.body.classList.add('dark-mode');
    }
    updateThemeIcon(document.body.classList.contains('dark-mode'));

    document.getElementById('themeToggleBtn').addEventListener('click', () => {
        const isDark = document.body.classList.toggle('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        updateThemeIcon(isDark);
        atualizarGraficosTema();
    });
}

function updateThemeIcon(isDark) {
    const icon = document.getElementById('themeIcon');
    if (!icon) return;
    if (isDark) {
        icon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
    } else {
        icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
    }
}

function atualizarGraficosTema() {
    const theme = getThemeColors();
    Chart.defaults.color = theme.text;
    Chart.defaults.borderColor = theme.grid;

    if (barrasChartInstance) {
        barrasChartInstance.data.datasets[0].backgroundColor = theme.barBg;
        barrasChartInstance.update();
    }
    if (roscaChartInstance) {
        roscaChartInstance.update();
    }
    if (rankingChartInstance) {
        rankingChartInstance.data.datasets[0].backgroundColor = theme.barBg;
        rankingChartInstance.update();
    }
}

// --- INICIALIZAÇÃO DA APLICAÇÃO ---
document.addEventListener('DOMContentLoaded', async () => {
    // Inicializa o tema escuro
    initTheme();
    const theme = getThemeColors();

    // Registra plugin de labels no ChartJS
    Chart.register(ChartDataLabels);
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = theme.text;
    Chart.defaults.borderColor = theme.grid;
    Chart.defaults.plugins.datalabels.display = false; // Desliga por padrão para evitar poluição

    // Atualiza status na interface inicial
    document.getElementById('dataMode').textContent = 'Supabase (Ao Vivo)';
    document.getElementById('dataMode').style.color = '#10B981';

    // 1. Carrega as chaves do env.js primeiro
    carregarEnv();

    // 2. Carrega dados iniciais
    await carregarDados();

    // Configura eventos
    configurarFiltrosMultiplos('obraCheckboxes', 'obraDropdownText', 'obra');
    configurarFiltrosMultiplos('etapaCheckboxes', 'etapaDropdownText', 'etapa');
    configurarFiltrosMultiplos('tipoCheckboxes', 'tipoDropdownText', 'tipo');

    // Configura os Dropdowns
    setupDropdown('obraDropdownHeader', 'obraCheckboxes');
    setupDropdown('etapaDropdownHeader', 'etapaCheckboxes');
    setupDropdown('tipoDropdownHeader', 'tipoCheckboxes');

    document.getElementById('refreshBtn').addEventListener('click', async () => {
        const btn = document.getElementById('refreshBtn');
        btn.innerHTML = 'Atualizando...';
        await carregarDados();
        setTimeout(() => {
            btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg> Atualizar Dados';
        }, 500);
    });
});

function setupDropdown(headerId, listId) {
    const header = document.getElementById(headerId);
    const list = document.getElementById(listId);

    // Toggle ao clicar no header
    header.addEventListener('click', (e) => {
        e.stopPropagation();

        // Fecha outros dropdowns abertos antes de abrir este
        document.querySelectorAll('.dropdown-list.show').forEach(el => {
            if (el.id !== listId) {
                el.classList.remove('show');
                const otherHeader = document.getElementById(el.id.replace('Checkboxes', 'DropdownHeader'));
                if (otherHeader) otherHeader.classList.remove('active');
            }
        });

        list.classList.toggle('show');
        header.classList.toggle('active');
    });

    // Fecha ao clicar fora
    document.addEventListener('click', (e) => {
        if (!header.contains(e.target) && !list.contains(e.target)) {
            list.classList.remove('show');
            header.classList.remove('active');
        }
    });
}

function configurarFiltrosMultiplos(containerId, textId, filterType) {
    const container = document.getElementById(containerId);
    const textElement = document.getElementById(textId);

    container.addEventListener('change', (e) => {
        if (e.target.tagName === 'INPUT' && e.target.type === 'checkbox') {
            const checkboxes = Array.from(container.querySelectorAll('input[type="checkbox"]'));
            const checkedBoxes = checkboxes.filter(cb => cb.checked);

            // Impede desmarcar a última opção para não deixar vazio
            if (checkedBoxes.length === 0) {
                e.target.checked = true;
                return;
            }

            const values = checkedBoxes.map(cb => cb.value);

            if (filterType === 'obra') {
                currentObraFilters = values;
                povoarFiltroEtapas(); // Atualiza etapas dependentes
            } else if (filterType === 'etapa') {
                currentEtapaFilters = values;
            } else if (filterType === 'tipo') {
                currentTipoFilters = values;
            }

            // Atualiza resumo textual do botão
            let textDefault = '';
            let textPlural = '';
            if (filterType === 'obra') { textDefault = 'Todas as Obras'; textPlural = 'obras selecionadas'; }
            else if (filterType === 'etapa') { textDefault = 'Todas as Etapas'; textPlural = 'etapas selecionadas'; }
            else if (filterType === 'tipo') { textDefault = 'Todos os Tipos'; textPlural = 'tipos selecionados'; }

            if (values.length === checkboxes.length) {
                textElement.textContent = textDefault;
            } else if (values.length === 1) {
                textElement.textContent = checkedBoxes[0].parentElement.textContent.trim();
            } else {
                textElement.textContent = `${values.length} ${textPlural}`;
            }

            atualizarDashboard();
        }
    });
}

// --- FUNÇÕES DE DADOS ---

async function carregarDados() {
    try {
        if (!dbClient) {
            console.error("Cliente Supabase não inicializado. Verifique se o env.js está correto.");
            throw new Error("Cliente Supabase não inicializado.");
        }

        // Consulta real no Supabase
        const { data, error } = await dbClient
            .from('relatorios')
            .select('OBRA, ETAPA, "TIPO_CUSTO", "ORÇAMENTO_ESTIMADO", "GASTO_REALIZADO", "SALDO_ETAPA"');

        if (error) {
            console.error("Erro reportado pelo Supabase:", error);
            throw error;
        }

        rawData = data || [];
        rawData.forEach(item => {
            if (!item.TIPO_CUSTO) item.TIPO_CUSTO = 'Geral';
        });

        if (rawData.length === 0) {
            console.warn("A consulta retornou um array vazio. O banco está vazio ou há bloqueio de RLS.");
        }

        document.getElementById('connectionStatus').textContent = 'Online';
        document.getElementById('connectionStatus').className = 'status-indicator online';

        // Povoar o Slicer (Checkboxes) apenas na primeira carga
        if (document.getElementById('obraCheckboxes').children.length === 0) {
            currentObraFilters = [...new Set(rawData.map(item => item.OBRA))].filter(Boolean).sort();
            currentEtapaFilters = [...new Set(rawData.map(item => item.ETAPA))].filter(Boolean).sort();
            currentTipoFilters = [...new Set(rawData.map(item => item.TIPO_CUSTO))].filter(Boolean).sort();

            povoarFiltroObras();
            povoarFiltroEtapas();
            povoarFiltroTipos();

            document.getElementById('obraDropdownText').textContent = 'Todas as Obras';
            document.getElementById('etapaDropdownText').textContent = 'Todas as Etapas';
            document.getElementById('tipoDropdownText').textContent = 'Todos os Tipos';
        }

        atualizarDashboard();

    } catch (error) {
        console.error("Erro ao carregar dados:", error);
        document.getElementById('connectionStatus').textContent = 'Erro ao conectar';
        document.getElementById('connectionStatus').className = 'status-indicator offline';
    }
}

function povoarFiltroObras() {
    const container = document.getElementById('obraCheckboxes');
    container.innerHTML = '';

    // Extrai nomes únicos
    const obrasUnicas = [...new Set(rawData.map(item => item.OBRA))].filter(Boolean).sort();

    obrasUnicas.forEach(obra => {
        const isChecked = currentObraFilters.includes(obra) ? 'checked' : '';
        container.innerHTML += `<label class="checkbox-item"><input type="checkbox" value="${obra}" ${isChecked}> ${obra}</label>`;
    });
}

function povoarFiltroEtapas() {
    const container = document.getElementById('etapaCheckboxes');
    container.innerHTML = '';

    // Pega as etapas baseadas na obra selecionada
    let dataForEtapas = rawData.filter(item => currentObraFilters.includes(item.OBRA));
    const etapasUnicas = [...new Set(dataForEtapas.map(item => item.ETAPA))].filter(Boolean).sort();

    // Filtra as etapas atuais para manter apenas as que ainda existem
    const stillValid = currentEtapaFilters.filter(e => etapasUnicas.includes(e));

    // Se a lista de ainda válidas está vazia, marcamos tudo
    if (stillValid.length === 0 && etapasUnicas.length > 0) {
        currentEtapaFilters = [...etapasUnicas];
    } else {
        currentEtapaFilters = stillValid;
    }

    etapasUnicas.forEach(etapa => {
        const isChecked = currentEtapaFilters.includes(etapa) ? 'checked' : '';
        container.innerHTML += `<label class="checkbox-item"><input type="checkbox" value="${etapa}" ${isChecked}> ${etapa}</label>`;
    });

    const textElement = document.getElementById('etapaDropdownText');
    if (currentEtapaFilters.length === etapasUnicas.length) {
        textElement.textContent = 'Todas as Etapas';
    } else if (currentEtapaFilters.length === 1) {
        textElement.textContent = currentEtapaFilters[0];
    } else {
        textElement.textContent = `${currentEtapaFilters.length} etapas selecionadas`;
    }
}

function povoarFiltroTipos() {
    const container = document.getElementById('tipoCheckboxes');
    container.innerHTML = '';

    const tiposUnicos = [...new Set(rawData.map(item => item.TIPO_CUSTO))].filter(Boolean).sort();

    const stillValid = currentTipoFilters.filter(e => tiposUnicos.includes(e));

    if (stillValid.length === 0 && tiposUnicos.length > 0) {
        currentTipoFilters = [...tiposUnicos];
    } else {
        currentTipoFilters = stillValid;
    }

    tiposUnicos.forEach(tipo => {
        const isChecked = currentTipoFilters.includes(tipo) ? 'checked' : '';
        container.innerHTML += `<label class="checkbox-item"><input type="checkbox" value="${tipo}" ${isChecked}> ${tipo}</label>`;
    });

    const textElement = document.getElementById('tipoDropdownText');
    if (currentTipoFilters.length === tiposUnicos.length) {
        textElement.textContent = 'Todos os Tipos';
    } else if (currentTipoFilters.length === 1) {
        textElement.textContent = currentTipoFilters[0];
    } else {
        textElement.textContent = `${currentTipoFilters.length} tipos selecionados`;
    }
}

function atualizarDashboard() {
    // 1. Filtrar os dados com base nos filtros
    filteredData = rawData.filter(item =>
        currentObraFilters.includes(item.OBRA) &&
        currentEtapaFilters.includes(item.ETAPA) &&
        currentTipoFilters.includes(item.TIPO_CUSTO)
    );

    // Configuração de Títulos baseada nos filtros
    const todasObrasQtd = [...new Set(rawData.map(item => item.OBRA))].filter(Boolean).length;
    const todasEtapasQtd = [...new Set(rawData.filter(i => currentObraFilters.includes(i.OBRA)).map(i => i.ETAPA))].filter(Boolean).length;

    if (currentObraFilters.length === todasObrasQtd && currentEtapaFilters.length === todasEtapasQtd) {
        document.getElementById('dashboardTitle').textContent = 'Visão Geral do Portfólio';
        document.getElementById('rankingTitle').textContent = 'Comparativo (Todas as Obras)';
    } else {
        let titleInfo = [];
        if (currentObraFilters.length < todasObrasQtd) titleInfo.push(`Obras (${currentObraFilters.length})`);
        if (currentEtapaFilters.length < todasEtapasQtd) titleInfo.push(`Etapas (${currentEtapaFilters.length})`);
        if (titleInfo.length === 0) titleInfo.push(`Filtro Específico`);

        document.getElementById('dashboardTitle').textContent = `Filtro | ${titleInfo.join(' - ')}`;
        document.getElementById('rankingTitle').textContent = 'Comparativo (Seleção Atual)';
    }

    // 2. Calcular KPIs (Medidas DAX em JS)
    const orcamentoTotal = filteredData.reduce((acc, curr) => acc + (Number(curr.ORÇAMENTO_ESTIMADO) || 0), 0);
    const gastoRealizado = filteredData.reduce((acc, curr) => acc + (Number(curr.GASTO_REALIZADO) || 0), 0);
    const saldoTotal = orcamentoTotal - gastoRealizado; // Equivalente a soma de saldo_etapa
    const percentualConsumo = orcamentoTotal > 0 ? (gastoRealizado / orcamentoTotal) * 100 : 0;

    // 3. Atualizar Cartões na UI
    document.getElementById('kpiOrcamento').textContent = formatCurrency(orcamentoTotal);
    document.getElementById('kpiRealizado').textContent = formatCurrency(gastoRealizado);
    document.getElementById('kpiSaldo').textContent = formatCurrency(saldoTotal);
    document.getElementById('kpiConsumo').textContent = `${percentualConsumo.toFixed(1)}%`;

    // 3.1 Formatação Condicional do Cartão de Saldo
    const cardSaldo = document.getElementById('cardSaldo');
    const saldoValue = document.getElementById('kpiSaldo');
    const saldoSubtitle = document.getElementById('kpiSaldoSubtitle');

    if (saldoTotal >= 0) {
        saldoValue.className = 'kpi-value text-green';
        saldoSubtitle.textContent = 'Dentro da meta / Economia';
        cardSaldo.style.borderTop = '4px solid var(--success-green)';
    } else {
        saldoValue.className = 'kpi-value text-red';
        saldoSubtitle.textContent = 'Atenção: Estouro de Orçamento';
        cardSaldo.style.borderTop = '4px solid var(--danger-red)';
    }

    // 3.2 Formatação Condicional da Barra de Progresso
    const barra = document.getElementById('kpiConsumoBar');
    barra.style.width = `${Math.min(percentualConsumo, 100)}%`; // Limita o visual max 100%
    if (percentualConsumo > 100) {
        barra.className = 'progress-bar over-budget';
    } else {
        barra.className = 'progress-bar';
    }

    // 4. Atualizar Gráficos
    renderizarGraficoBarrasAgrupadas();
    renderizarGraficoRosca();
    renderizarGraficoRanking();

    // 5. Atualizar Tabela (Matriz)
    renderizarTabela();
}

// --- UTILITÁRIOS ---
const formatCurrency = (value) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
};

// --- GRÁFICOS ---

function renderizarGraficoBarrasAgrupadas() {
    const ctx = document.getElementById('barrasAgrupadasChart').getContext('2d');

    // Agrupar dados por Etapa (Group By)
    const agrupadoPorEtapa = {};
    filteredData.forEach(item => {
        if (!agrupadoPorEtapa[item.ETAPA]) {
            agrupadoPorEtapa[item.ETAPA] = { previsto: 0, realizado: 0 };
        }
        agrupadoPorEtapa[item.ETAPA].previsto += Number(item.ORÇAMENTO_ESTIMADO);
        agrupadoPorEtapa[item.ETAPA].realizado += Number(item.GASTO_REALIZADO);
    });

    const labels = Object.keys(agrupadoPorEtapa);
    const previstoData = labels.map(l => agrupadoPorEtapa[l].previsto);
    const realizadoData = labels.map(l => agrupadoPorEtapa[l].realizado);

    // Arrays de cores dinâmicas (Vermelho se estourar fase, Verde/Azul se ok)
    const backgroundRealizado = realizadoData.map((val, index) => {
        return val > previstoData[index] ? 'rgba(239, 68, 68, 0.8)' : 'rgba(16, 185, 129, 0.8)';
    });

    if (barrasChartInstance) {
        barrasChartInstance.destroy(); // Limpa antes de redesenhar
    }

    barrasChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Orçamento Estimado',
                    data: previstoData,
                    backgroundColor: getThemeColors().barBg,
                    borderRadius: 4
                },
                {
                    label: 'Gasto Realizado',
                    data: realizadoData,
                    backgroundColor: backgroundRealizado,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return context.dataset.label + ': ' + formatCurrency(context.raw);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function (value) {
                            return value >= 1000 ? 'R$ ' + (value / 1000) + 'k' : 'R$ ' + value;
                        }
                    }
                }
            }
        }
    });
}

function renderizarGraficoRosca() {
    const ctx = document.getElementById('roscaChart').getContext('2d');

    // Agrupar GASTO REALIZADO por etapa
    const agrupado = {};
    filteredData.forEach(item => {
        const val = Number(item.GASTO_REALIZADO);
        if (val > 0) {
            agrupado[item.ETAPA] = (agrupado[item.ETAPA] || 0) + val;
        }
    });

    const labels = Object.keys(agrupado);
    const data = labels.map(l => agrupado[l]);

    // Paleta azul/roxa
    const colors = ['#2563EB', '#60A5FA', '#8B5CF6', '#C4B5FD', '#10B981', '#34D399'];

    if (roscaChartInstance) roscaChartInstance.destroy();

    roscaChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { position: 'right' },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return ' ' + formatCurrency(context.raw);
                        }
                    }
                }
            }
        }
    });
}

function renderizarGraficoRanking() {
    const ctx = document.getElementById('rankingChart').getContext('2d');

    // Agrupar por Obra ou Etapa dependendo do filtro
    const agrupado = {};
    const labelKey = currentObraFilters.length === 1 ? 'ETAPA' : 'OBRA';

    filteredData.forEach(item => {
        if (!agrupado[item[labelKey]]) {
            agrupado[item[labelKey]] = { previsto: 0, realizado: 0, saldo: 0 };
        }
        agrupado[item[labelKey]].previsto += Number(item.ORÇAMENTO_ESTIMADO);
        agrupado[item[labelKey]].realizado += Number(item.GASTO_REALIZADO);
        agrupado[item[labelKey]].saldo += Number(item.SALDO_ETAPA);
    });

    // Ordenar pelo maior orçamento para fazer mais sentido visualmente na comparação
    const ordenado = Object.entries(agrupado).sort((a, b) => b[1].previsto - a[1].previsto);

    const labels = ordenado.map(i => i[0]);
    const previstoData = ordenado.map(i => i[1].previsto);
    const realizadoData = ordenado.map(i => i[1].realizado);
    const saldoData = ordenado.map(i => i[1].saldo);

    // Cores condicionais
    const saldoColors = saldoData.map(val => val < 0 ? 'rgba(239, 68, 68, 0.8)' : 'rgba(16, 185, 129, 0.8)');

    if (rankingChartInstance) rankingChartInstance.destroy();

    rankingChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Orçamento Estimado',
                    data: previstoData,
                    backgroundColor: getThemeColors().barBg,
                    borderRadius: 4
                },
                {
                    label: 'Gasto Realizado',
                    data: realizadoData,
                    backgroundColor: '#8B5CF6', // Roxo vibrante para contrastar
                    borderRadius: 4
                },
                {
                    label: 'Saldo Financeiro',
                    data: saldoData,
                    backgroundColor: saldoColors, // Vermelho se negativo, verde se positivo
                    borderRadius: 4
                }
            ]
        },
        options: {
            indexAxis: 'y', // Barras horizontais agrupadas
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                datalabels: {
                    display: false // Desligado para não poluir esse gráfico novo
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return ' ' + context.dataset.label + ': ' + formatCurrency(context.raw);
                        }
                    }
                }
            },
            layout: {
                padding: { right: 20 }
            },
            scales: {
                x: {
                    display: true,
                    beginAtZero: true,
                    ticks: {
                        callback: function (value) {
                            return value >= 1000 ? 'R$ ' + (value / 1000) + 'k' : 'R$ ' + value;
                        }
                    }
                },
                y: { grid: { display: false } }
            }
        }
    });
}

// --- MATRIZ FINANCEIRA (TABELA) ---

function renderizarTabela() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    // Precisamos construir a árvore: Obra -> Etapas
    // Mas se o filtro for apenas uma obra, focar apenas nela.

    const obrasAgrupadas = {};
    filteredData.forEach(item => {
        if (!obrasAgrupadas[item.OBRA]) {
            obrasAgrupadas[item.OBRA] = {
                previsto_total: 0,
                realizado_total: 0,
                etapas: []
            };
        }

        obrasAgrupadas[item.OBRA].previsto_total += Number(item.ORÇAMENTO_ESTIMADO);
        obrasAgrupadas[item.OBRA].realizado_total += Number(item.GASTO_REALIZADO);
        obrasAgrupadas[item.OBRA].etapas.push(item);
    });

    Object.keys(obrasAgrupadas).forEach((obraName, index) => {
        const obraData = obrasAgrupadas[obraName];
        const saldoTotal = obraData.previsto_total - obraData.realizado_total;
        const consPerc = obraData.previsto_total > 0 ? (obraData.realizado_total / obraData.previsto_total) * 100 : 0;

        // Formatação Condicional do Saldo
        let saldoClass = saldoTotal < 0 ? 'bg-danger-light' : 'bg-success-light';
        let consPercClass = consPerc > 100 ? 'text-red' : '';

        // Linha Principal (Nível Obra)
        const trObra = document.createElement('tr');
        trObra.className = 'row-obra';
        trObra.dataset.obraId = index;
        trObra.innerHTML = `
            <td><span class="expand-icon">▶</span> ${obraName}</td>
            <td class="text-right"><strong>${formatCurrency(obraData.previsto_total)}</strong></td>
            <td class="text-right"><strong>${formatCurrency(obraData.realizado_total)}</strong></td>
            <td class="text-right ${saldoClass}">${formatCurrency(saldoTotal)}</td>
            <td class="text-center ${consPercClass}"><strong>${consPerc.toFixed(1)}%</strong></td>
        `;

        // Total de etapas disponíveis para a obra atual
        const totalEtapasDaObra = [...new Set(rawData.filter(i => i.OBRA === obraName).map(i => i.ETAPA))].filter(Boolean).length;
        const totalObrasDisponiveis = [...new Set(rawData.map(i => i.OBRA))].filter(Boolean).length;

        // Expande automático se houver um filtro específico focado nas etapas ou poucas obras
        if (currentEtapaFilters.length < totalEtapasDaObra || currentObraFilters.length === 1) {
            trObra.classList.add('expanded');
        } else {
            // Adiciona evento de clique para expandir/colapsar
            trObra.addEventListener('click', function () {
                this.classList.toggle('expanded');
                const etapas = document.querySelectorAll(`.etapa-of-${index}`);
                const isExpanded = this.classList.contains('expanded');

                etapas.forEach(el => {
                    el.style.display = isExpanded ? 'table-row' : 'none';
                });
            });
        }

        tbody.appendChild(trObra);

        // Linhas de Detalhe (Nível Etapa)
        obraData.etapas.forEach(etapa => {
            const trEtapa = document.createElement('tr');
            trEtapa.className = `row-etapa etapa-of-${index}`;

            // Se filtrado especificamente, abre as etapas por padrão
            if (currentEtapaFilters.length < totalEtapasDaObra || currentObraFilters.length === 1) {
                trEtapa.style.display = 'table-row';
            }

            const saldoEt = Number(etapa.SALDO_ETAPA);
            let corSaldoEt = saldoEt < 0 ? 'text-red' : 'text-green';
            let consPercEt = Number(etapa.ORÇAMENTO_ESTIMADO) > 0 ? (Number(etapa.GASTO_REALIZADO) / Number(etapa.ORÇAMENTO_ESTIMADO)) * 100 : 0;

            trEtapa.innerHTML = `
                <td>${etapa.ETAPA} <span style="opacity: 0.7; font-size: 0.85em;">(${etapa.TIPO_CUSTO || 'Geral'})</span></td>
                <td class="text-right">${formatCurrency(etapa.ORÇAMENTO_ESTIMADO)}</td>
                <td class="text-right">${formatCurrency(etapa.GASTO_REALIZADO)}</td>
                <td class="text-right ${corSaldoEt}"><strong>${formatCurrency(saldoEt)}</strong></td>
                <td class="text-center">${consPercEt.toFixed(1)}%</td>
            `;

            tbody.appendChild(trEtapa);
        });
    });
}
