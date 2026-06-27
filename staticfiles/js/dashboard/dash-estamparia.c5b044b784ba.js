document.addEventListener('DOMContentLoaded', function() {
    const filterBtn      = document.getElementById('filterBtn');
    const resetBtn       = document.getElementById('resetBtn');
    const startDateInput = document.getElementById('startDate');
    const endDateInput   = document.getElementById('endDate');

    const filterBtnTemporal = document.getElementById('filterBtnTemporal');
    const resetBtnTemporal  = document.getElementById('resetBtnTemporal');
    const startDateTemporal = document.getElementById('startDateTemporal');
    const endDateTemporal   = document.getElementById('endDateTemporal');

    const today           = new Date();
    const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    const sixMonthsAgo    = new Date(today.getFullYear(), today.getMonth() - 5, 1);

    startDateInput.valueAsDate    = firstDayOfMonth;
    endDateInput.valueAsDate      = today;
    startDateTemporal.valueAsDate = sixMonthsAgo;
    endDateTemporal.valueAsDate   = today;

    // ── Helpers ──────────────────────────────────────────────
    function formatDateBr(value) {
        const raw = String(value || '').trim();
        if (!raw) return '';
        const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!match) return raw;
        const [, y, m, d] = match;
        return `${d}/${m}/${y}`;
    }

    function atualizarKPIs(totalProd, totalInsp, totalNC) {
        const pctInsp      = totalProd > 0 ? (totalInsp / totalProd * 100).toFixed(0) : 0;
        const indiceGlobal = totalInsp > 0
            ? (totalNC / totalInsp * 100).toFixed(2).replace('.', ',')
            : '0,00';

        document.getElementById('kpi-pecas-produzidas').textContent    = totalProd.toLocaleString('pt-BR');
        document.getElementById('kpi-pecas-inspecionadas').textContent = totalInsp.toLocaleString('pt-BR');
        document.getElementById('kpi-pct-inspecao').textContent        = pctInsp + '%';
        document.getElementById('kpi-nao-conformidade').textContent    = totalNC.toLocaleString('pt-BR');
        document.getElementById('kpi-indice-global').textContent       = indiceGlobal + '%';
    }

    // ── Funções de carregamento ───────────────────────────────
    async function carregarGraficoProducao(startDate, endDate) {
        const queryParams = new URLSearchParams();
        if (startDate) queryParams.append('data_inicio', startDate);
        if (endDate)   queryParams.append('data_fim', endDate);

        const url = `/inspecao/estamparia/api/indicador-estamparia-analise-temporal/?${queryParams.toString()}`;
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar os dados do gráfico.');
            const productionData = await response.json();

            productionChart.data.labels = productionData.map(item => item.mes);
            productionChart.data.datasets[0].data = productionData.map(item => item.qtd_peca_produzida);
            productionChart.data.datasets[1].data = productionData.map(item => item.qtd_peca_inspecionada);
            productionChart.data.datasets[2].data = productionData.map(item => item.taxa_nao_conformidade * 100);
            productionChart.update();
        } catch (error) {
            console.error(error);
        }
    }

    async function carregarTabelaProducao(startDate, endDate) {
        let url = '/inspecao/estamparia/api/indicador-estamparia-resumo-analise-temporal/';
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate)   params.push(`data_fim=${endDate}`);
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar dados de produção.');
            const data = await response.json();

            const tabela = document.querySelector('#table-producao tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `<tr><td colspan="9" class="text-center text-muted">Nenhum dado encontrado para o período selecionado.</td></tr>`;
                atualizarKPIs(0, 0, 0);
                return;
            }

            let anoAtual = null;
            data.forEach(item => {
                const ano = item.Data.split('-')[0];
                if (anoAtual !== null && ano !== anoAtual) {
                    tabela.insertAdjacentHTML('beforeend', `
                        <tr class="table-dark">
                            <td colspan="9" class="text-center py-1" style="letter-spacing:2px;">
                                <small>── fim de ${anoAtual} ──</small>
                            </td>
                        </tr>
                    `);
                }
                anoAtual = ano;
                tabela.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${formatDateBr(item.Data)}</td>
                        <td>${item["N° de peças produzidas"]}</td>
                        <td>${item["N° de inspeções"]}</td>
                        <td>${item["N° de não conformidades"]}</td>
                        <td>${item["% de inspeção"]}</td>
                        <td>${item["Quantidade de pç produzidas"]}</td>
                        <td>${item["Quantidade pç inspecionada"]}</td>
                        <td>${item["Quantidade pç não conforme"]}</td>
                        <td>${item["% de inspeção por total de peça"]}</td>
                    </tr>
                `);
            });

            // KPIs usam os valores absolutos de peças
            const totalProd = data.reduce((s, i) => s + (i["Quantidade de pç produzidas"] || 0), 0);
            const totalInsp = data.reduce((s, i) => s + (i["Quantidade pç inspecionada"] || 0), 0);
            const totalNC   = data.reduce((s, i) => s + (i["Quantidade pç não conforme"] || 0), 0);
            atualizarKPIs(totalProd, totalInsp, totalNC);

        } catch (error) {
            console.error('Erro ao carregar tabela de produção:', error);
        }
    }

    async function carregarGraficoCausas(startDate, endDate) {
        let url = '/inspecao/estamparia/api/causas-nao-conformidade/';
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate)   params.push(`data_fim=${endDate}`);
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar causas.');
            const causesData = await response.json();

            const causesCount = {};
            causesData.forEach(item => {
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

    async function carregarCarrosselImagens(startDate, endDate) {
        let url = '/inspecao/estamparia/api/imagens-nao-conformidade/';
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate)   params.push(`data_fim=${endDate}`);
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
                    </div>
                `);
            });
        } catch (error) {
            console.error('Erro ao carregar carrossel de imagens:', error);
        }
    }

    async function carregarCarrosselFichas(startDate, endDate) {
        let url = '/inspecao/estamparia/api/fichas-inspecao/';
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate)   params.push(`data_fim=${endDate}`);
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
                const statusInspecao = ficha.inspecao_completa ? 'Completa' : 'Parcial';
                const motivos = ficha.motivos_mortas.length > 0
                    ? `Motivos: ${ficha.motivos_mortas.join(', ')}`
                    : 'Sem motivos registrados';

                carouselInner.insertAdjacentHTML('beforeend', `
                    <div class="carousel-item ${index === 0 ? 'active' : ''}">
                        <img src="${ficha.ficha_url}" class="d-block w-100" alt="Ficha de inspeção" style="max-height:500px;object-fit:contain;">
                        <div class="carousel-caption d-none d-md-block bg-dark bg-opacity-75 rounded">
                            <h5>Inspeção ${statusInspecao}</h5>
                            <p>Data: ${ficha.data_execucao}</p>
                            <p>${motivos}</p>
                        </div>
                    </div>
                `);
            });

            if (typeof bootstrap !== 'undefined') {
                new bootstrap.Carousel(document.getElementById('fichaCarousel'));
            }
        } catch (error) {
            console.error('Erro ao carregar fichas:', error);
        }
    }

    async function carregarTabelaCausas(startDate, endDate) {
        let url = '/inspecao/estamparia/api/causas-nao-conformidade/';
        const params = [];
        if (startDate) params.push(`data_inicio=${startDate}`);
        if (endDate)   params.push(`data_fim=${endDate}`);
        if (params.length) url += '?' + params.join('&');

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erro ao buscar causas.');
            const data = await response.json();

            const tabela = document.querySelector('#table-causas tbody');
            tabela.innerHTML = '';

            if (data.length === 0) {
                tabela.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Nenhuma causa encontrada para o período selecionado.</td></tr>`;
                return;
            }

            data.forEach(item => {
                tabela.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${formatDateBr(item.Data)}</td>
                        <td>${item["ID Ordem"]}</td>
                        <td>${item["Peça"]}</td>
                        <td>${item.Causa}</td>
                        <td>${item["Soma do N° Total de não conformidades"]}</td>
                        <td>${item.Destino}</td>
                    </tr>
                `);
            });
        } catch (error) {
            console.error('Erro ao carregar tabela de causas:', error);
        }
    }

    // ── Filtro TEMPORAL (apenas o gráfico) ───────────────────
    filterBtnTemporal.addEventListener('click', function() {
        const s = startDateTemporal.value;
        const e = endDateTemporal.value;
        if (!s || !e) { alert('Selecione as datas do período temporal.'); return; }
        if (s > e)    { alert('A data inicial deve ser anterior à data final.'); return; }
        carregarGraficoProducao(s, e);
    });

    resetBtnTemporal.addEventListener('click', function() {
        startDateTemporal.valueAsDate = sixMonthsAgo;
        endDateTemporal.valueAsDate   = today;
        carregarGraficoProducao(startDateTemporal.value, endDateTemporal.value);
    });

    // ── Filtro GLOBAL (KPIs + demais seções) ─────────────────
    filterBtn.addEventListener('click', function() {
        const startDate = startDateInput.value;
        const endDate   = endDateInput.value;

        if (!startDate || !endDate) {
            alert('Por favor, selecione as datas de início e fim.');
            return;
        }
        if (startDate > endDate) {
            alert('A data inicial deve ser anterior à data final.');
            return;
        }

        document.querySelectorAll('.alert-info').forEach(el => el.remove());
        const filterInfo = document.createElement('div');
        filterInfo.className = 'alert alert-info mt-3';
        filterInfo.innerText = `Filtro aplicado: ${formatDateBr(startDate)} até ${formatDateBr(endDate)}`;
        document.querySelector('.card-body').appendChild(filterInfo);

        carregarTabelaProducao(startDate, endDate);
        carregarGraficoCausas(startDate, endDate);
        carregarCarrosselImagens(startDate, endDate);
        carregarCarrosselFichas(startDate, endDate);
        carregarTabelaCausas(startDate, endDate);
    });

    resetBtn.addEventListener('click', function() {
        startDateInput.valueAsDate = firstDayOfMonth;
        endDateInput.valueAsDate   = today;
        document.querySelectorAll('.alert-info').forEach(el => el.remove());
        carregarTabelaProducao(startDateInput.value, endDateInput.value);
        carregarGraficoCausas(startDateInput.value, endDateInput.value);
        carregarCarrosselImagens(startDateInput.value, endDateInput.value);
        carregarCarrosselFichas(startDateInput.value, endDateInput.value);
        carregarTabelaCausas(startDateInput.value, endDateInput.value);
    });

    // ── Carga inicial ─────────────────────────────────────────
    carregarGraficoProducao(startDateTemporal.value, endDateTemporal.value); // gráfico → filtro temporal
    carregarTabelaProducao(startDateInput.value, endDateInput.value);         // KPIs → filtro global
    carregarGraficoCausas(startDateInput.value, endDateInput.value);
    carregarCarrosselImagens(startDateInput.value, endDateInput.value);
    carregarCarrosselFichas(startDateInput.value, endDateInput.value);
    carregarTabelaCausas(startDateInput.value, endDateInput.value);
});

// ── Gráfico de produção ───────────────────────────────────────
const productionChart = new Chart(document.getElementById('productionChart').getContext('2d'), {
    type: 'bar',
    data: {
        labels: [],
        datasets: [
            {
                label: 'Peças Produzidas',
                data: [],
                backgroundColor: 'rgba(37, 99, 235, 0.7)',
                borderColor: 'rgba(37, 99, 235, 1)',
                borderWidth: 1
            },
            {
                label: 'Peças Inspecionadas',
                data: [],
                backgroundColor: 'rgba(15, 123, 108, 0.7)',
                borderColor: 'rgba(15, 123, 108, 1)',
                borderWidth: 1
            },
            {
                label: 'Taxa de Não Conformidade (%)',
                data: [],
                type: 'line',
                backgroundColor: 'rgba(224, 90, 43, 0.2)',
                borderColor: 'rgba(224, 90, 43, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(224, 90, 43, 1)',
                yAxisID: 'y1'
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y:  { beginAtZero: true, title: { display: true, text: 'Quantidade' } },
            y1: { beginAtZero: true, position: 'right', title: { display: true, text: 'Taxa (%)' },
                  max: 100, grid: { drawOnChartArea: false } }
        }
    }
});

// ── Gráfico de causas ─────────────────────────────────────────
const causesChart = new Chart(document.getElementById('causesChart').getContext('2d'), {
    type: 'pie',
    data: {
        labels: [],
        datasets: [{
            data: [],
            backgroundColor: [
                'rgba(224, 90, 43, 0.8)',
                'rgba(37, 99, 235, 0.8)',
                'rgba(15, 123, 108, 0.8)',
                'rgba(234, 179, 8, 0.8)',
                'rgba(139, 92, 246, 0.8)',
                'rgba(100, 116, 139, 0.8)'
            ],
            borderColor: '#fff',
            borderWidth: 2
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
                        const value = context.raw || 0;
                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                        const pct   = Math.round((value / total) * 100);
                        return `${context.label}: ${value} (${pct}%)`;
                    }
                }
            }
        }
    }
});
