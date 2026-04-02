// ── Gráfico de produção (combinado: Montagem + Tanque + Tubos) ────────────
const productionChart = new Chart(document.getElementById('productionChart').getContext('2d'), {
    type: 'bar',
    data: {
        labels: [],
        datasets: [
            {
                label: 'Total de Inspeções',
                data: [],
                backgroundColor: 'rgba(27, 42, 74, 0.75)',
                borderColor: 'rgba(27, 42, 74, 1)',
                borderWidth: 1
            },
            {
                label: 'Total de Não Conformidades',
                data: [],
                backgroundColor: 'rgba(224, 90, 43, 0.75)',
                borderColor: 'rgba(224, 90, 43, 1)',
                borderWidth: 1
            },
            {
                label: 'Taxa NC (%)',
                data: [],
                type: 'line',
                backgroundColor: 'rgba(15, 123, 108, 0.15)',
                borderColor: 'rgba(15, 123, 108, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(15, 123, 108, 1)',
                tension: 0.3,
                yAxisID: 'y1'
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        scales: {
            y:  { beginAtZero: true, title: { display: true, text: 'Quantidade' } },
            y1: { beginAtZero: true, position: 'right', title: { display: true, text: 'Taxa (%)' },
                  max: 100, grid: { drawOnChartArea: false } }
        }
    }
});

// ── Gráfico de causas combinado ───────────────────────────────────────────
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
                'rgba(109, 40, 217, 0.8)',
                'rgba(234, 179, 8, 0.8)',
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
                        const pct = Math.round((value / total) * 100);
                        return `${context.label}: ${value} (${pct}%)`;
                    }
                }
            }
        }
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const today          = new Date();
    const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    const sixMonthsAgo   = new Date(today.getFullYear(), today.getMonth() - 5, 1);

    // Filtro global
    const startDateInput = document.getElementById('startDate');
    const endDateInput   = document.getElementById('endDate');
    startDateInput.valueAsDate = firstDayOfMonth;
    endDateInput.valueAsDate   = today;

    // Filtro temporal (gráfico)
    const startDateTemporal = document.getElementById('startDateTemporal');
    const endDateTemporal   = document.getElementById('endDateTemporal');
    startDateTemporal.valueAsDate = sixMonthsAgo;
    endDateTemporal.valueAsDate   = today;

    // ── Helper ──────────────────────────────────────────────────────────────
    function formatDateBr(value) {
        const raw = String(value || '').trim();
        const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!match) return raw;
        const [, y, m, d] = match;
        return `${d}/${m}/${y}`;
    }

    function buildParams(s, e) {
        const p = [];
        if (s) p.push(`data_inicio=${s}`);
        if (e) p.push(`data_fim=${e}`);
        return p.length ? '?' + p.join('&') : '';
    }

    async function safeFetch(url) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`Erro ao buscar ${url}`);
        return r.json();
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

    // ── Gráfico temporal combinado ─────────────────────────────────────────
    async function carregarGraficoProducao(s, e) {
        const qs = buildParams(s, e);
        try {
            const [dataMon, dataTan, dataTub] = await Promise.all([
                safeFetch(`/inspecao/montagem/api/indicador-montagem-analise-temporal/${qs}`),
                safeFetch(`/inspecao/tanque/api/indicador-tanque-analise-temporal/${qs}`),
                safeFetch(`/inspecao/tubos-cilindros/api/indicador-tubos-cilindros-analise-temporal/${qs}`)
            ]);

            // Merge by month label; preserve order from all three sources
            const mesSet = new Map();
            const addToMap = (arr) => arr.forEach(item => {
                if (!mesSet.has(item.mes)) mesSet.set(item.mes, { mon: 0, tan: 0, tub: 0, nc: 0, insp: 0 });
            });
            addToMap(dataMon); addToMap(dataTan); addToMap(dataTub);

            [...dataMon, ...dataTan, ...dataTub].forEach(item => {
                const v = mesSet.get(item.mes);
                v.insp += item.qtd_peca_inspecionada;
                v.nc   += Math.round(item.taxa_nao_conformidade * item.qtd_peca_inspecionada);
            });

            const labels = [...mesSet.keys()];
            const vals   = [...mesSet.values()];

            productionChart.data.labels = labels;
            productionChart.data.datasets[0].data = vals.map(v => v.insp);
            productionChart.data.datasets[1].data = vals.map(v => v.nc);
            productionChart.data.datasets[2].data = vals.map(v =>
                v.insp > 0 ? parseFloat((v.nc / v.insp * 100).toFixed(2)) : 0
            );
            productionChart.update();
        } catch (error) {
            console.error('Erro ao carregar gráfico combinado:', error);
        }
    }

    // ── Tabela Montagem ────────────────────────────────────────────────────
    async function carregarTabelaMontagem(s, e) {
        try {
            const data = await safeFetch(
                `/inspecao/montagem/api/indicador-montagem-resumo-analise-temporal/${buildParams(s, e)}`
            );
            const tbody = document.querySelector('#table-montagem tbody');
            tbody.innerHTML = '';
            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-2">Sem dados.</td></tr>`;
                return { insp: 0, nc: 0 };
            }
            let insp = 0, nc = 0;
            data.forEach(item => {
                insp += Number(item["N° de inspeções"]) || 0;
                nc   += Number(item["N° de não conformidades"]) || 0;
                tbody.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${formatDateBr(item.Data)}</td>
                        <td>${item["N° de peças produzidas"]}</td>
                        <td>${item["N° de inspeções"]}</td>
                        <td>${item["N° de não conformidades"]}</td>
                        <td>${item["% de inspeção"]}</td>
                    </tr>`);
            });
            return { insp, nc };
        } catch (err) {
            console.error(err);
            return { insp: 0, nc: 0 };
        }
    }

    // ── Tabela Tanque ──────────────────────────────────────────────────────
    async function carregarTabelaTanque(s, e) {
        try {
            const data = await safeFetch(
                `/inspecao/tanque/api/indicador-tanque-resumo-analise-temporal/${buildParams(s, e)}`
            );
            const tbody = document.querySelector('#table-tanque tbody');
            tbody.innerHTML = '';
            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-2">Sem dados.</td></tr>`;
                return { insp: 0, nc: 0 };
            }
            let insp = 0, nc = 0;
            data.forEach(item => {
                const i = Number(item["N° de inspeções"]) || 0;
                const n = Number(item["N° de não conformidades"]) || 0;
                insp += i; nc += n;
                const pct = i > 0 ? ((n / i) * 100).toFixed(2).replace('.', ',') + '%' : '0,00%';
                tbody.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item.Data}</td>
                        <td>${i.toLocaleString('pt-BR')}</td>
                        <td>${n.toLocaleString('pt-BR')}</td>
                        <td>${pct}</td>
                    </tr>`);
            });
            return { insp, nc };
        } catch (err) {
            console.error(err);
            return { insp: 0, nc: 0 };
        }
    }

    // ── Tabela Tubos ───────────────────────────────────────────────────────
    async function carregarTabelaTubos(s, e) {
        try {
            const data = await safeFetch(
                `/inspecao/tubos-cilindros/api/indicador-tubos-cilindros-resumo-analise-temporal/${buildParams(s, e)}`
            );
            const tbody = document.querySelector('#table-tubos tbody');
            tbody.innerHTML = '';
            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-2">Sem dados.</td></tr>`;
                return { insp: 0, nc: 0 };
            }
            let insp = 0, nc = 0;
            data.forEach(item => {
                insp += Number(item["N° de inspeções"]) || 0;
                nc   += Number(item["N° de não conformidades"]) || 0;
                tbody.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item.Data}</td>
                        <td>${item["N° de inspeções"]}</td>
                        <td>${item["N° de não conformidades"]}</td>
                        <td>${item["% de não conformidade"]}</td>
                    </tr>`);
            });
            return { insp, nc };
        } catch (err) {
            console.error(err);
            return { insp: 0, nc: 0 };
        }
    }

    // ── Causas Montagem ────────────────────────────────────────────────────
    async function carregarCausasMontagem(s, e) {
        try {
            const data = await safeFetch(
                `/inspecao/montagem/api/causas-nao-conformidade/${buildParams(s, e)}`
            );
            const tbody = document.querySelector('#table-causas-montagem tbody');
            tbody.innerHTML = '';
            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-2">Sem dados.</td></tr>`;
                return [];
            }
            data.forEach(item => {
                tbody.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${formatDateBr(item.data)}</td>
                        <td>${item.peca}</td>
                        <td>${item.causa}</td>
                        <td>${item.quantidade}</td>
                    </tr>`);
            });
            return data.map(item => ({ causa: item.causa, qtd: Number(item.quantidade) || 0 }));
        } catch (err) {
            console.error(err);
            return [];
        }
    }

    // ── Causas Tanque ──────────────────────────────────────────────────────
    async function carregarCausasTanque(s, e) {
        try {
            const data = await safeFetch(
                `/inspecao/tanque/api/causas-nao-conformidade/${buildParams(s, e)}`
            );
            const tbody = document.querySelector('#table-causas-tanque tbody');
            tbody.innerHTML = '';
            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-2">Sem dados.</td></tr>`;
                return [];
            }
            data.forEach(item => {
                tbody.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item.data}</td>
                        <td>${item.peca}</td>
                        <td>${item.causa}</td>
                        <td>${item.quantidade}</td>
                    </tr>`);
            });
            return data.map(item => ({ causa: item.causa, qtd: Number(item.quantidade) || 0 }));
        } catch (err) {
            console.error(err);
            return [];
        }
    }

    // ── Causas Tubos ───────────────────────────────────────────────────────
    async function carregarCausasTubos(s, e) {
        try {
            const data = await safeFetch(
                `/inspecao/tubos-cilindros/api/causas-nao-conformidade/${buildParams(s, e)}`
            );
            const tbody = document.querySelector('#table-causas-tubos tbody');
            tbody.innerHTML = '';
            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-2">Sem dados.</td></tr>`;
                return [];
            }
            data.forEach(item => {
                tbody.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td>${item.Data}</td>
                        <td>${item.Peca}</td>
                        <td>${item.Causa}</td>
                        <td>${item["Soma do N° Total de não conformidades"]}</td>
                    </tr>`);
            });
            return data.map(item => ({
                causa: item.Causa,
                qtd: Number(item["Soma do N° Total de não conformidades"]) || 0
            }));
        } catch (err) {
            console.error(err);
            return [];
        }
    }

    // ── Gráfico de causas combinado ────────────────────────────────────────
    function atualizarGraficoCausas(listaMon, listaTan, listaTub) {
        const combined = {};
        [...listaMon, ...listaTan, ...listaTub].forEach(({ causa, qtd }) => {
            if (!causa) return;
            combined[causa] = (combined[causa] || 0) + qtd;
        });
        causesChart.data.labels = Object.keys(combined);
        causesChart.data.datasets[0].data = Object.values(combined);
        causesChart.update();
    }

    // ── Carrossel de imagens (Montagem + Tubos) ────────────────────────────
    async function carregarCarrosselImagens(s, e) {
        try {
            const qs = buildParams(s, e);
            const [imgMon, imgTub] = await Promise.all([
                safeFetch(`/inspecao/montagem/api/imagens-nao-conformidade/${qs}`),
                safeFetch(`/inspecao/tubos-cilindros/api/imagens-nao-conformidade/${qs}`)
            ]);

            const carouselInner = document.querySelector('#imageCarousel .carousel-inner');
            carouselInner.innerHTML = '';

            // Normaliza: montagem usa arquivo_url, tubos usa imagem_url
            const imagens = [
                ...imgMon.map(i => ({ ...i, url: i.arquivo_url })),
                ...imgTub.map(i => ({ ...i, url: i.imagem_url }))
            ];

            if (!imagens.length) {
                carouselInner.innerHTML = `
                    <div class="carousel-item active">
                        <div class="d-flex justify-content-center align-items-center" style="height:300px;">
                            <p class="text-muted">Nenhuma imagem encontrada no período selecionado.</p>
                        </div>
                    </div>`;
                return;
            }

            imagens.forEach((item, index) => {
                const causas = Array.isArray(item.causas) ? item.causas.join(', ') : (item.causas || '');
                carouselInner.insertAdjacentHTML('beforeend', `
                    <div class="carousel-item ${index === 0 ? 'active' : ''}">
                        <img src="${item.url}" class="d-block w-100" alt="Imagem de não conformidade" style="max-height:500px;object-fit:contain;">
                        <div class="carousel-caption d-none d-md-block">
                            <h5>${causas}</h5>
                            <p>Data: ${item.data_execucao} | Quantidade: ${item.quantidade}</p>
                        </div>
                    </div>`);
            });
        } catch (err) {
            console.error('Erro ao carregar carrossel:', err);
        }
    }

    // ── Carga global (KPIs + tabelas + causas + carrossel) ─────────────────
    async function carregarSecaoGlobal() {
        const s = startDateInput.value;
        const e = endDateInput.value;

        const [
            kpiMon, kpiTan, kpiTub,
            causMon, causTan, causTub
        ] = await Promise.all([
            carregarTabelaMontagem(s, e),
            carregarTabelaTanque(s, e),
            carregarTabelaTubos(s, e),
            carregarCausasMontagem(s, e),
            carregarCausasTanque(s, e),
            carregarCausasTubos(s, e)
        ]);

        const totalInsp = kpiMon.insp + kpiTan.insp + kpiTub.insp;
        const totalNC   = kpiMon.nc  + kpiTan.nc  + kpiTub.nc;
        atualizarKPIs(totalInsp, totalNC);
        atualizarGraficoCausas(causMon, causTan, causTub);
        carregarCarrosselImagens(s, e);
    }

    // ── Botões filtro temporal ─────────────────────────────────────────────
    document.getElementById('filterBtnTemporal').addEventListener('click', function () {
        const s = startDateTemporal.value;
        const e = endDateTemporal.value;
        if (!s || !e) { alert('Selecione as datas de início e fim.'); return; }
        if (s > e)    { alert('A data inicial deve ser anterior à data final.'); return; }
        carregarGraficoProducao(s, e);
    });

    document.getElementById('resetBtnTemporal').addEventListener('click', function () {
        startDateTemporal.valueAsDate = sixMonthsAgo;
        endDateTemporal.valueAsDate   = today;
        carregarGraficoProducao(startDateTemporal.value, endDateTemporal.value);
    });

    // ── Botões filtro global ───────────────────────────────────────────────
    document.getElementById('filterBtn').addEventListener('click', function () {
        const s = startDateInput.value;
        const e = endDateInput.value;
        if (!s || !e) { alert('Selecione as datas de início e fim.'); return; }
        if (s > e)    { alert('A data inicial deve ser anterior à data final.'); return; }
        carregarSecaoGlobal();
    });

    document.getElementById('resetBtn').addEventListener('click', function () {
        startDateInput.valueAsDate = firstDayOfMonth;
        endDateInput.valueAsDate   = today;
        carregarSecaoGlobal();
    });

    // ── Carga inicial ──────────────────────────────────────────────────────
    carregarGraficoProducao(startDateTemporal.value, endDateTemporal.value);
    carregarSecaoGlobal();
});
