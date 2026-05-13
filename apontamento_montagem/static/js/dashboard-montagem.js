document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('montagem-dashboard-app');
    if (!app) return;

    const dataUrl = app.dataset.dashboardUrl;
    const form = document.getElementById('montagemDashboardFilters');
    const resetBtn = document.getElementById('resetDashboardFilters');
    const startInput = document.getElementById('f-data-inicio');
    const endInput = document.getElementById('f-data-fim');
    const machineInput = document.getElementById('f-maquina');

    const periodBadge = document.getElementById('dashboardPeriodBadge');
    const topConjuntosList = document.getElementById('topConjuntosList');
    const interruptionRankingList = document.getElementById('interruptionRankingList');
    const missingPiecesTable = document.getElementById('missingPiecesTable');
    const tmfTable           = document.getElementById('tmfTable');
    const tmfUrl             = app.dataset.tmfUrl;
    const tmfMinOrdens       = document.getElementById('tmf-min-ordens');
    const tmfReload          = document.getElementById('tmf-reload');

    let statusChart;
    let machineChart;
    let cargaChart;
    let activityChart;

    function formatNumber(value) {
        return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(Number(value || 0));
    }

    function applyDefaultDates() {
        const today = new Date();
        const start = new Date();
        start.setDate(today.getDate() - 29);

        startInput.value = start.toISOString().slice(0, 10);
        endInput.value = today.toISOString().slice(0, 10);
    }

    function destroyCharts() {
        [statusChart, machineChart, cargaChart, activityChart].forEach(chart => {
            if (chart) chart.destroy();
        });
    }

    function renderKpis(payload) {
        if (periodBadge) periodBadge.textContent = `${payload.periodo.data_inicio} ate ${payload.periodo.data_fim}`;
    }

    function renderTopConjuntos(items) {
        if (!items.length) {
            topConjuntosList.innerHTML = '<div class="dashboard-empty">Nenhum conjunto produzido no periodo.</div>';
            return;
        }

        topConjuntosList.innerHTML = items.map((item, index) => `
            <article class="top-list-item">
                <div class="top-list-rank">${index + 1}</div>
                <div class="top-list-name">
                    ${item.nome || 'Sem descricao'}
                    <span>Planejada: ${formatNumber(item.planejada)}</span>
                </div>
                <div class="top-list-metric">
                    <strong>${formatNumber(item.produzida)}</strong>
                    <small>Boas</small>
                </div>

                <div class="top-list-metric">
                    <strong>${item.planejada > 0 ? formatNumber((item.produzida / item.planejada) * 100) : '0'}%</strong>
                    <small>Atingimento</small>
                </div>
            </article>
        `).join('');
    }

    function renderInterruptionRanking(items) {
        if (!items.length) {
            interruptionRankingList.innerHTML = '<div class="dashboard-empty">Nenhuma interrupcao registrada no periodo.</div>';
            return;
        }

        interruptionRankingList.innerHTML = items.map((item, index) => `
            <article class="top-list-item interruption-item">
                <div class="top-list-rank">${index + 1}</div>
                <div class="top-list-name">
                    ${item.motivo}
                    <span>${item.maquina}</span>
                </div>
                <div class="top-list-metric">
                    <strong>${formatNumber(item.total)}</strong>
                    <small>Ocorrencias</small>
                </div>
                <div class="top-list-metric interruption-latest">
                    <strong>${item.ultima}</strong>
                    <small>Ultimo registro</small>
                </div>
            </article>
        `).join('');
    }

    function renderMissingPiecesTable(items) {
        if (!items.length) {
            missingPiecesTable.innerHTML = '<div class="dashboard-empty">Nenhum registro de falta de peça no periodo.</div>';
            return;
        }

        missingPiecesTable.innerHTML = `
            <table class="dashboard-data-table">
                <thead>
                    <tr>
                        <th>Peça</th>
                        <th>Conjunto</th>
                        <th>Célula</th>
                        <th>Qtd. total</th>
                        <th>Último registro</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map(item => `
                        <tr>
                            <td>${item.nome_peca}</td>
                            <td style="font-size:0.8em;">${(item.conjuntos || []).length ? item.conjuntos.join('<br>') : '-'}</td>
                            <td>${(item.celulas || []).length ? item.celulas.join(', ') : '-'}</td>
                            <td>${formatNumber(item.quantidade_total)}</td>
                            <td>${item.ultima}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    function buildStatusChart(data) {
        const ctx = document.getElementById('statusChart');
        statusChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(item => item.label),
                datasets: [{
                    data: data.map(item => item.value),
                    backgroundColor: ['#0f766e', '#0284c7', '#f59e0b', '#ef4444', '#6366f1'],
                    borderWidth: 0,
                }],
            },
            options: {
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 18 },
                    },
                },
                cutout: '68%',
            },
        });
    }

    function buildMachineChart(data) {
        const ctx = document.getElementById('machineChart');
        machineChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.label),
                datasets: [
                    {
                        label: 'Planejada',
                        data: data.map(item => item.planejada),
                        backgroundColor: '#cbd5e1',
                        borderRadius: 10,
                    },
                    {
                        label: 'Produzida',
                        data: data.map(item => item.produzida),
                        backgroundColor: '#0f766e',
                        borderRadius: 10,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    x: { grid: { display: false } },
                    y: { beginAtZero: true },
                },
            },
        });
    }

    function buildCargaChart(data) {
        const ctx = document.getElementById('cargaChart');
        cargaChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.label),
                datasets: [
                    {
                        label: 'Planejada',
                        data: data.map(item => item.planejada),
                        borderColor: '#94a3b8',
                        backgroundColor: 'rgba(148, 163, 184, 0.12)',
                        tension: 0.3,
                        fill: false,
                    },
                    {
                        label: 'Produzida',
                        data: data.map(item => item.produzida),
                        borderColor: '#0f766e',
                        backgroundColor: 'rgba(15, 118, 110, 0.14)',
                        tension: 0.3,
                        fill: true,
                    },
                    {
                        label: 'Avanco (%)',
                        data: data.map(item => item.percentual),
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.12)',
                        tension: 0.3,
                        yAxisID: 'y1',
                        fill: false,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: { beginAtZero: true },
                    y1: {
                        beginAtZero: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                    },
                },
            },
        });
    }

    function buildActivityChart(data) {
        const ctx = document.getElementById('activityChart');
        activityChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.label),
                datasets: [
                    {
                        label: 'Iniciadas',
                        data: data.map(item => item.iniciada),
                        backgroundColor: '#0284c7',
                        borderRadius: 8,
                    },
                    {
                        label: 'Interrompidas',
                        data: data.map(item => item.interrompida),
                        backgroundColor: '#ef4444',
                        borderRadius: 8,
                    },
                    {
                        label: 'Finalizadas',
                        data: data.map(item => item.finalizada),
                        backgroundColor: '#16a34a',
                        borderRadius: 8,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                scales: {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, beginAtZero: true },
                },
            },
        });
    }

    function renderCharts(payload) {
        destroyCharts();
        buildStatusChart(payload.charts.status);
        buildMachineChart(payload.charts.producao_por_maquina);
        buildCargaChart(payload.charts.andamento_cargas);
        buildActivityChart(payload.charts.atividade_diaria);
    }

    async function loadDashboard() {
        const params = new URLSearchParams({
            data_inicio: startInput.value,
            data_fim: endInput.value,
        });
        if (machineInput.value) params.append('maquina_id', machineInput.value);

        try {
            const response = await fetch(`${dataUrl}?${params.toString()}`);
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || 'Nao foi possivel carregar o dashboard.');
            }

            const payload = await response.json();
            renderKpis(payload);
            renderCharts(payload);
            renderTopConjuntos(payload.top_conjuntos || []);
            renderInterruptionRanking(payload.interruption_ranking || []);
            renderMissingPiecesTable(payload.falta_peca_items || []);
        } catch (error) {
            destroyCharts();
            topConjuntosList.innerHTML = `<div class="dashboard-empty">${error.message}</div>`;
            interruptionRankingList.innerHTML = `<div class="dashboard-empty">${error.message}</div>`;
            missingPiecesTable.innerHTML = `<div class="dashboard-empty">${error.message}</div>`;
        }
    }

    // ── Tempo médio de fabricação ─────────────────────────────────────────
    function renderTmfTable(items) {
        if (!items.length) {
            tmfTable.innerHTML = '<div class="dashboard-empty">Nenhum dado encontrado para o período e filtros selecionados.</div>';
            return;
        }
        tmfTable.innerHTML = `
            <table class="dashboard-data-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Conjunto / Produto</th>
                        <th>Tempo médio / lote</th>
                        <th>Tempo médio / unidade</th>
                        <th>Ordens</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map((item, i) => `
                        <tr>
                            <td><span class="tmf-rank">${i + 1}</span></td>
                            <td style="white-space:normal;max-width:340px;font-size:0.85rem;">${item.peca}</td>
                            <td><span class="tmf-badge-media">${item.media_lote_formatado}</span></td>
                            <td><span class="tmf-badge-media" style="background:#f0fdf4;color:#15803d;">${item.media_unidade_formatado}</span></td>
                            <td style="font-weight:700;">${item.ordens}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    async function loadTmf() {
        if (!tmfUrl || !tmfTable) return;
        tmfTable.innerHTML = '<div class="dashboard-empty">Carregando...</div>';
        const params = new URLSearchParams({
            data_inicio:       startInput.value,
            data_fim:          endInput.value,
            apenas_finalizadas: '1',
            min_ordens:        tmfMinOrdens ? tmfMinOrdens.value : '2',
            limit:             '50',
        });
        if (machineInput.value) params.set('maquina_id', machineInput.value);
        try {
            const res = await fetch(`${tmfUrl}?${params}`);
            if (!res.ok) throw new Error(`Erro ${res.status}`);
            const data = await res.json();
            renderTmfTable(data.items || []);
        } catch (err) {
            tmfTable.innerHTML = `<div class="dashboard-empty">${err.message}</div>`;
        }
    }

    if (tmfReload) tmfReload.addEventListener('click', loadTmf);

    form.addEventListener('submit', event => {
        event.preventDefault();
        loadDashboard();
        loadTmf();
    });

    resetBtn.addEventListener('click', () => {
        machineInput.value = '';
        applyDefaultDates();
        loadDashboard();
        loadTmf();
    });

    applyDefaultDates();
    loadDashboard();
    loadTmf();
});
