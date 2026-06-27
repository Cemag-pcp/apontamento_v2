// Configuração do gráfico de produção
const productionCtx = document.getElementById('productionChart').getContext('2d');
const productionChart = new Chart(productionCtx, {
    type: 'bar',
    data: {
        labels: [],
        datasets: [
            {
                label: 'Peças Produzidas',
                data: [],
                backgroundColor: 'rgba(27, 42, 74, 0.75)',
                borderColor: 'rgba(27, 42, 74, 1)',
                borderWidth: 1
            },
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

// Configuração do gráfico de causas
const causesChart = new Chart(document.getElementById('causesChart').getContext('2d'), {
    type: 'pie',
    data: {
        labels: [],
        datasets: [{
            data: [],
            backgroundColor: [
                'rgba(224, 90, 43, 0.8)',
                'rgba(27, 42, 74, 0.8)',
                'rgba(37, 99, 235, 0.8)',
                'rgba(15, 123, 108, 0.8)',
                'rgba(155, 89, 182, 0.8)',
                'rgba(241, 196, 15, 0.8)',
                'rgba(127, 140, 141, 0.8)'
            ],
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'right' },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        const label = context.label || '';
                        const value = context.raw || 0;
                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                        const pct = Math.round((value / total) * 100);
                        return `${label}: ${value} (${pct}%)`;
                    }
                }
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
            const response = await fetch(`/inspecao/usinagem/api/indicador-usinagem-analise-temporal/?${params}`);
            if (!response.ok) throw new Error('Erro ao buscar dados do gráfico.');
            const data = await response.json();

            productionChart.data.labels = data.map(item => item.mes);
            productionChart.data.datasets[0].data = data.map(item => item.qtd_peca_produzida);
            productionChart.data.datasets[1].data = data.map(item => item.qtd_peca_inspecionada);
            productionChart.data.datasets[2].data = data.map(item => item.taxa_nao_conformidade * 100);
            productionChart.update();
        } catch (error) {
            console.error(error);
        }
    }

    // ── KPIs ───────────────────────────────────────────────────────────────
    function atualizarKPIs(totalProd, totalInsp, totalNC) {
        document.getElementById('kpi-pecas-produzidas').textContent =
            totalProd.toLocaleString('pt-BR');
        document.getElementById('kpi-pecas-inspecionadas').textContent =
            totalInsp.toLocaleString('pt-BR');
        document.getElementById('kpi-nao-conformidade').textContent =
            totalNC.toLocaleString('pt-BR');

        const pctInsp = totalProd > 0 ? (totalInsp / totalProd) * 100 : 0;
        document.getElementById('kpi-pct-inspecao').textContent =
            pctInsp.toFixed(1).replace('.', ',') + '%';

        const indice = totalInsp > 0 ? (totalNC / totalInsp) * 100 : 0;
        document.getElementById('kpi-indice-global').textContent =
            indice.toFixed(2).replace('.', ',') + '%';
    }

    // ── Tabela de produção ─────────────────────────────────────────────────
    async function carregarTabelaProducao(startDate, endDate) {
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        let url = '/inspecao/usinagem/api/indicador-usinagem-resumo-analise-temporal/';
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar dados de produção.');
            const data = await response.json();

            const tabela = document.querySelector('#table-producao tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-3">Nenhum dado encontrado para o período selecionado.</td></tr>`;
                atualizarKPIs(0, 0, 0);
                return;
            }

            let totalProd = 0, totalInsp = 0, totalNC = 0;
            let anoAtual = null;

            data.forEach(item => {
                const ano = item.Data.split('/')[1];
                if (anoAtual !== null && ano !== anoAtual) {
                    tabela.insertAdjacentHTML('beforeend', `
                        <tr class="table-dark">
                            <td colspan="9" class="text-center py-1" style="border-top:2px solid #6c757d;border-bottom:2px solid #6c757d;letter-spacing:2px;">
                                <small>── fim de ${anoAtual} ──</small>
                            </td>
                        </tr>`);
                }
                anoAtual = ano;

                const prod = Number(item["Quantidade de pç produzidas"]) || 0;
                const insp = Number(item["Quantidade pç inspecionada"]) || 0;
                const nc   = Number(item["Quantidade pç não conforme"]) || 0;
                totalProd += prod;
                totalInsp += insp;
                totalNC   += nc;

                tabela.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item.Data}</td>
                        <td>${item["N° de peças produzidas"]}</td>
                        <td>${item["N° de inspeções"]}</td>
                        <td>${item["N° de não conformidades"]}</td>
                        <td>${item["% de inspeção"]}</td>
                        <td>${prod.toLocaleString('pt-BR')}</td>
                        <td>${insp.toLocaleString('pt-BR')}</td>
                        <td>${nc.toLocaleString('pt-BR')}</td>
                        <td>${item["% de inspeção por total de peça"]}</td>
                    </tr>`);
            });

            atualizarKPIs(totalProd, totalInsp, totalNC);
        } catch (error) {
            console.error('Erro ao carregar tabela de produção:', error);
        }
    }

    // ── Tabela de causas ───────────────────────────────────────────────────
    async function carregarTabelaCausas(startDate, endDate) {
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        let url = '/inspecao/usinagem/api/causas-nao-conformidade/';
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar causas.');
            const data = await response.json();

            const tabela = document.querySelector('#table-causas tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-3">Nenhuma causa encontrada para o período selecionado.</td></tr>`;
                return;
            }

            data.forEach(item => {
                tabela.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item["ID Inspeção"]}</td>
                        <td>${item.Data}</td>
                        <td>${item["Peça"]}</td>
                        <td>${item.Causa}</td>
                        <td>${item["Soma do N° Total de não conformidades"]}</td>
                        <td>${item.Destino}</td>
                    </tr>`);
            });
        } catch (error) {
            console.error('Erro ao carregar tabela de causas:', error);
        }
    }

    // ── Gráfico de causas ──────────────────────────────────────────────────
    async function carregarGraficoCausas(startDate, endDate) {
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        let url = '/inspecao/usinagem/api/causas-nao-conformidade/';
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar causas.');
            const data = await response.json();

            const causesCount = {};
            data.forEach(item => {
                const causa = item.Causa;
                const total = item["Soma do N° Total de não conformidades"];
                causesCount[causa] = (causesCount[causa] || 0) + total;
            });

            causesChart.data.labels = Object.keys(causesCount);
            causesChart.data.datasets[0].data = Object.values(causesCount);
            causesChart.update();
        } catch (error) {
            console.error('Erro ao carregar gráfico de causas:', error);
        }
    }

    // ── Carrossel de imagens ───────────────────────────────────────────────
    async function carregarCarrosselImagens(startDate, endDate) {
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        let url = '/inspecao/usinagem/api/imagens-nao-conformidade/';
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar imagens.');
            const imagens = await response.json();

            const carouselInner = document.querySelector('#imageCarousel .carousel-inner');
            carouselInner.innerHTML = '';

            if (imagens.length === 0) {
                carouselInner.innerHTML = `
                    <div class="carousel-item active">
                        <div class="d-flex justify-content-center align-items-center" style="height:300px;">
                            <p class="text-muted">Nenhuma imagem encontrada no período selecionado.</p>
                        </div>
                    </div>`;
                return;
            }

            imagens.forEach((item, index) => {
                const causas = item.causas.join(', ');
                carouselInner.insertAdjacentHTML('beforeend', `
                    <div class="carousel-item ${index === 0 ? 'active' : ''}">
                        <img src="${item.imagem_url}" class="d-block w-100" alt="Imagem de não conformidade" style="max-height:500px;object-fit:contain;">
                        <div class="carousel-caption d-none d-md-block">
                            <h5>${causas}</h5>
                            <p>Data: ${item.data_execucao} | Quantidade: ${item.quantidade}</p>
                        </div>
                    </div>`);
            });
        } catch (error) {
            console.error('Erro ao carregar carrossel de imagens:', error);
        }
    }

    // ── Carrossel de fichas ────────────────────────────────────────────────
    async function carregarCarrosselFichas(startDate, endDate) {
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate) params.push(`data_fim=${endDate}`);
        let url = '/inspecao/usinagem/api/fichas-inspecao/';
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar fichas.');
            const fichas = await response.json();

            const carouselInner = document.querySelector('#fichaCarousel .carousel-inner');
            carouselInner.innerHTML = '';

            if (fichas.length === 0) {
                carouselInner.innerHTML = `
                    <div class="carousel-item active">
                        <div class="d-flex justify-content-center align-items-center" style="height:300px;">
                            <p class="text-muted">Nenhuma ficha encontrada no período selecionado.</p>
                        </div>
                    </div>`;
                return;
            }

            fichas.forEach((ficha, index) => {
                const status = ficha.inspecao_completa ? 'Completa' : 'Parcial';
                carouselInner.insertAdjacentHTML('beforeend', `
                    <div class="carousel-item ${index === 0 ? 'active' : ''}">
                        <img src="${ficha.ficha_url}" class="d-block w-100" alt="Ficha de inspeção" style="max-height:500px;object-fit:contain;">
                        <div class="carousel-caption d-none d-md-block bg-dark bg-opacity-75 rounded">
                            <h5>Inspeção ${status}</h5>
                            <p>Data: ${ficha.data_execucao}</p>
                        </div>
                    </div>`);
            });

            if (typeof bootstrap !== 'undefined') {
                new bootstrap.Carousel(document.getElementById('fichaCarousel'));
            }
        } catch (error) {
            console.error('Erro ao carregar fichas:', error);
        }
    }

    // ── Funções de carga global (KPIs + tabelas + carrosséis) ──────────────
    function carregarSecaoGlobal() {
        const s = startDateInput.value;
        const e = endDateInput.value;
        carregarTabelaProducao(s, e);
        carregarTabelaCausas(s, e);
        carregarGraficoCausas(s, e);
        carregarCarrosselImagens(s, e);
        carregarCarrosselFichas(s, e);
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
