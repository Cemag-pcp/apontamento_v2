// Funcionalidade do filtro de datas
document.addEventListener('DOMContentLoaded', function() {
    const filterBtn = document.getElementById('filterBtn');
    const resetBtn = document.getElementById('resetBtn');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');

    const today = new Date();
    const lastMonth = new Date();
    lastMonth.setMonth(today.getMonth() - 1);

    startDateInput.valueAsDate = lastMonth;
    endDateInput.valueAsDate = today;

    async function carregarGraficoProducao(startDate, endDate) {
        const queryParams = new URLSearchParams();
        if (startDate) queryParams.append('data_inicio', startDate);
        if (endDate) queryParams.append('data_fim', endDate);

        const url = `/inspecao/tanque/api/indicador-tanque-analise-temporal/?${queryParams.toString()}`;

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar os dados do gráfico.');

            const productionData = await response.json();

            // Atualiza o gráfico
            productionChart.data.labels = productionData.map(item => item.mes);
            productionChart.data.datasets[0].data = productionData.map(item => item.qtd_peca_inspecionada);
            productionChart.data.datasets[1].data = productionData.map(item => item.taxa_nao_conformidade * 100);
            productionChart.update();
        } catch (error) {
            console.error(error);
            alert('Erro ao carregar gráfico de produção.');
        }
    }

    async function carregarTabelaCausas(startDate, endDate) {

        let url = '/inspecao/tanque/api/causas-nao-conformidade/';
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar causas.');
            const data = await response.json();

            const tabela = document.querySelector('#table-causas tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `
                    <tr>
                        <td colspan="3" class="text-center text-muted">Nenhuma causa encontrada para o período selecionado.</td>
                    </tr>
                `;
                return;
            }

            data.forEach(item => {
                const row = `
                    <tr>
                        <td>${item.data}</td>
                        <td>${item.causa}</td>
                        <td>${item.quantidade}</td>
                    </tr>
                `;
                tabela.insertAdjacentHTML('beforeend', row);
            });

        } catch (error) {
            console.error('Erro ao carregar tabela de causas:', error);
            alert('Erro ao carregar dados de causas.');
        }
    }

    async function carregarTabelaProducao(startDate, endDate) {

        let url = '/inspecao/tanque/api/indicador-tanque-resumo-analise-temporal/';
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar dados de produção.');
            const data = await response.json();

            const tabela = document.querySelector('#table-producao tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center text-muted">Nenhum dado encontrado para o período selecionado.</td>
                    </tr>
                `;
                return;
            }

            data.forEach(item => {
                const row = `
                    <tr>
                        <td>${item.Data}</td>
                        <td>${item["N° de inspeções"]}</td>
                        <td>${item["N° de não conformidades"]}</td>
                        <td>${(item["N° de não conformidades"]/(item["N° de inspeções"])*100).toFixed(2)}%</td>
                    </tr>
                `;
                tabela.insertAdjacentHTML('beforeend', row);
            });

        } catch (error) {
            console.error('Erro ao carregar tabela de produção:', error);
            alert('Erro ao carregar dados de produção.');
        }
    }

    // Botão FILTRAR
    filterBtn.addEventListener('click', function() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;

        if (!startDate || !endDate) {
            alert('Por favor, selecione as datas de início e fim.');
            return;
        }

        if (startDate > endDate) {
            alert('A data inicial deve ser anterior à data final.');
            return;
        }

        // Limpa alertas antigos e mostra o atual
        document.querySelectorAll('.alert-info').forEach(el => el.remove());

        const filterInfo = document.createElement('div');
        filterInfo.className = 'alert alert-info mt-3';
        filterInfo.innerText = `Filtro aplicado: ${startDate} até ${endDate}`;
        document.querySelector('.card-body').appendChild(filterInfo);

        carregarGraficoProducao(startDate, endDate);
        carregarTabelaCausas(startDateInput.value, endDateInput.value);
        carregarTabelaProducao(startDateInput.value, endDateInput.value);

    });

    // Botão RESET
    resetBtn.addEventListener('click', function() {
        startDateInput.valueAsDate = lastMonth;
        endDateInput.valueAsDate = today;
        document.querySelectorAll('.alert-info').forEach(el => el.remove());
        carregarGraficoProducao(startDateInput.value, endDateInput.value);
        carregarTabelaCausas(startDateInput.value, endDateInput.value);
        carregarTabelaProducao(startDateInput.value, endDateInput.value);
    });

    // Carrega dados ao abrir a página
    carregarGraficoProducao(startDateInput.value, endDateInput.value);
    carregarTabelaCausas(startDateInput.value, endDateInput.value);
    carregarTabelaProducao(startDateInput.value, endDateInput.value);
});

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
                backgroundColor: 'rgba(46, 204, 113, 0.7)',
                borderColor: 'rgba(46, 204, 113, 1)',
                borderWidth: 1
            },
            {
                label: 'Taxa de Não Conformidade',
                data: [],
                type: 'line',
                backgroundColor: 'rgba(231, 76, 60, 0.2)',
                borderColor: 'rgba(231, 76, 60, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(231, 76, 60, 1)',
                yAxisID: 'y1'
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'Quantidade'
                }
            },
            y1: {
                beginAtZero: true,
                position: 'right',
                title: {
                    display: true,
                    text: 'Taxa (%)'
                },
                max: 100,
                grid: {
                    drawOnChartArea: false
                }
            }
        }
    }
});

// Configuração do gráfico de causas
const causesCtx = document.getElementById('causesChart').getContext('2d');
const causesChart = new Chart(document.getElementById('causesChart').getContext('2d'), {
    type: 'pie',
    data: {
        labels: [],
        datasets: [{
            data: [],
            backgroundColor: [
                'rgba(231, 76, 60, 0.7)',
                'rgba(241, 196, 15, 0.7)',
                'rgba(52, 152, 219, 0.7)',
                'rgba(39, 174, 96, 0.7)',
                'rgba(155, 89, 182, 0.7)',
                'rgba(127, 140, 141, 0.7)'
            ],
            borderColor: [
                'rgba(231, 76, 60, 1)',
                'rgba(241, 196, 15, 1)',
                'rgba(52, 152, 219, 1)',
                'rgba(39, 174, 96, 1)',
                'rgba(155, 89, 182, 1)',
                'rgba(127, 140, 141, 1)'
            ],
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'right'
            },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        const label = context.label || '';
                        const value = context.raw || 0;
                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                        const percentage = Math.round((value / total) * 100);
                        return `${label}: ${value} (${percentage}%)`;
                    }
                }
            }
        }
    }
});