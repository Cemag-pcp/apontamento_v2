// Configuração do gráfico de produção
const productionCtx = document.getElementById('productionChart').getContext('2d');
const productionChart = new Chart(productionCtx, {
    type: 'bar',
    data: {
        labels: [],
        datasets: [
            {
                label: 'Peças Inspecionadas',
                data: [],
                backgroundColor: 'rgba(37, 99, 235, 0.65)',
                borderColor: 'rgba(37, 99, 235, 1)',
                borderWidth: 1
            },
            {
                label: 'Taxa de Não Conformidade (%)',
                data: [],
                type: 'line',
                backgroundColor: 'rgba(224, 90, 43, 0.15)',
                borderColor: 'rgba(224, 90, 43, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(224, 90, 43, 1)',
                tension: 0.3,
                yAxisID: 'y1'
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top' }
        },
        scales: {
            y: {
                beginAtZero: true,
                title: { display: true, text: 'Quantidade' }
            },
            y1: {
                beginAtZero: true,
                position: 'right',
                title: { display: true, text: 'Taxa (%)' },
                max: 100,
                grid: { drawOnChartArea: false }
            }
        }
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const today = new Date();
    const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    const sixMonthsAgo = new Date(today.getFullYear(), today.getMonth() - 5, 1);

    // Filtro global
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    startDateInput.valueAsDate = firstDayOfMonth;
    endDateInput.valueAsDate = today;

    // Filtro temporal (gráfico)
    const startDateTemporal = document.getElementById('startDateTemporal');
    const endDateTemporal = document.getElementById('endDateTemporal');
    startDateTemporal.valueAsDate = sixMonthsAgo;
    endDateTemporal.valueAsDate = today;

    // ── Gráfico de produção (filtro temporal) ──────────────────────────────
    async function carregarGraficoProducao(startDate, endDate) {
        const params = new URLSearchParams();
        if (startDate) params.append('data_inicio', startDate);
        if (endDate) params.append('data_fim', endDate);

        try {
            const response = await fetch(`/inspecao/tanque/api/indicador-tanque-analise-temporal/?${params}`);
            if (!response.ok) throw new Error('Erro ao buscar dados do gráfico.');
            const data = await response.json();

            productionChart.data.labels = data.map(item => item.mes);
            productionChart.data.datasets[0].data = data.map(item => item.qtd_peca_inspecionada);
            productionChart.data.datasets[1].data = data.map(item => item.taxa_nao_conformidade * 100);
            productionChart.update();
        } catch (error) {
            console.error(error);
        }
    }

    // ── KPIs ───────────────────────────────────────────────────────────────
    function atualizarKPIs(totalInsp, totalNC) {
        document.getElementById('kpi-pecas-inspecionadas').textContent =
            totalInsp.toLocaleString('pt-BR');
        document.getElementById('kpi-nao-conformidade').textContent =
            totalNC.toLocaleString('pt-BR');

        const pctNC = totalInsp > 0 ? (totalNC / totalInsp) * 100 : 0;
        document.getElementById('kpi-pct-nc').textContent =
            pctNC.toFixed(1).replace('.', ',') + '%';
        document.getElementById('kpi-indice-global').textContent =
            pctNC.toFixed(2).replace('.', ',') + '%';
    }

    // ── Tabela de produção ─────────────────────────────────────────────────
    async function carregarTabelaProducao(startDate, endDate) {
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        let url = '/inspecao/tanque/api/indicador-tanque-resumo-analise-temporal/';
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar dados de produção.');
            const data = await response.json();

            const tabela = document.querySelector('#table-producao tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">Nenhum dado encontrado para o período selecionado.</td></tr>`;
                atualizarKPIs(0, 0);
                return;
            }

            let totalInsp = 0, totalNC = 0;

            data.forEach(item => {
                const insp = Number(item["N° de inspeções"]) || 0;
                const nc   = Number(item["N° de não conformidades"]) || 0;
                totalInsp += insp;
                totalNC   += nc;

                const pct = insp > 0 ? ((nc / insp) * 100).toFixed(2).replace('.', ',') + '%' : '0,00%';

                tabela.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item.Data}</td>
                        <td>${insp.toLocaleString('pt-BR')}</td>
                        <td>${nc.toLocaleString('pt-BR')}</td>
                        <td>${pct}</td>
                    </tr>`);
            });

            atualizarKPIs(totalInsp, totalNC);
        } catch (error) {
            console.error('Erro ao carregar tabela de produção:', error);
        }
    }

    // ── Tabela de causas ───────────────────────────────────────────────────
    async function carregarTabelaCausas(startDate, endDate) {
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        let url = '/inspecao/tanque/api/causas-nao-conformidade/';
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar causas.');
            const data = await response.json();

            const tabela = document.querySelector('#table-causas tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">Nenhuma causa encontrada para o período selecionado.</td></tr>`;
                return;
            }

            data.forEach(item => {
                tabela.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item.data}</td>
                        <td>${item.peca}</td>
                        <td>${item.causa}</td>
                        <td>${item.quantidade}</td>
                    </tr>`);
            });
        } catch (error) {
            console.error('Erro ao carregar tabela de causas:', error);
        }
    }

    // ── Funções de carga global ────────────────────────────────────────────
    function carregarSecaoGlobal() {
        const s = startDateInput.value;
        const e = endDateInput.value;
        carregarTabelaProducao(s, e);
        carregarTabelaCausas(s, e);
    }

    // ── Botões filtro temporal ─────────────────────────────────────────────
    document.getElementById('filterBtnTemporal').addEventListener('click', function () {
        const s = startDateTemporal.value;
        const e = endDateTemporal.value;
        if (!s || !e) { alert('Selecione as datas de início e fim.'); return; }
        if (s > e) { alert('A data inicial deve ser anterior à data final.'); return; }
        carregarGraficoProducao(s, e);
    });

    document.getElementById('resetBtnTemporal').addEventListener('click', function () {
        startDateTemporal.valueAsDate = sixMonthsAgo;
        endDateTemporal.valueAsDate = today;
        carregarGraficoProducao(startDateTemporal.value, endDateTemporal.value);
    });

    // ── Botões filtro global ───────────────────────────────────────────────
    document.getElementById('filterBtn').addEventListener('click', function () {
        const s = startDateInput.value;
        const e = endDateInput.value;
        if (!s || !e) { alert('Selecione as datas de início e fim.'); return; }
        if (s > e) { alert('A data inicial deve ser anterior à data final.'); return; }
        carregarSecaoGlobal();
    });

    document.getElementById('resetBtn').addEventListener('click', function () {
        startDateInput.valueAsDate = firstDayOfMonth;
        endDateInput.valueAsDate = today;
        carregarSecaoGlobal();
    });

    // ── Carga inicial ──────────────────────────────────────────────────────
    carregarGraficoProducao(startDateTemporal.value, endDateTemporal.value);
    carregarSecaoGlobal();
});
