'use strict';

// ── paleta ──────────────────────────────────────────────────────────────────
const COLOR_GREEN  = '#059669';
const COLOR_RED    = '#dc2626';
const COLOR_NAVY   = '#1b2a4a';
const COLOR_ORANGE = '#e05a2b';
const COLOR_TEAL   = '#0f7b6c';
const COLOR_BLUE   = '#2563eb';
const PALETTE = ['#2563eb','#0f7b6c','#e05a2b','#7c3aed','#0891b2','#d97706','#be123c','#166534','#1e40af','#9a3412'];

// ── charts ──────────────────────────────────────────────────────────────────
let chartTemporal  = null;
let chartResultado = null;
let chartClasse    = null;
let chartTipo      = null;

function fmt(n) {
    if (n === null || n === undefined) return '—';
    return Number(n).toLocaleString('pt-BR');
}

function fmtPct(n) {
    return (n ?? 0).toFixed(1) + '%';
}

function getParams() {
    const tipoData = document.querySelector('input[name="tipoData"]:checked')?.value || 'inspecao';
    return {
        data_inicio: document.getElementById('startDate').value || '',
        data_fim:    document.getElementById('endDate').value   || '',
        tipo_data:   tipoData,
    };
}

function qs(params) {
    return Object.entries(params)
        .filter(([, v]) => v)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&');
}

// ── KPIs ────────────────────────────────────────────────────────────────────
async function carregarResumo(params) {
    try {
        const r = await fetch(`/inspecao/recebimento/api/resumo/?${qs(params)}`);
        const d = await r.json();

        document.getElementById('kpi-total').textContent     = fmt(d.total);
        document.getElementById('kpi-conforme').textContent  = fmt(d.conforme);
        document.getElementById('kpi-nc').textContent        = fmt(d.nao_conforme);
        document.getElementById('kpi-pendentes').textContent = fmt(d.pendentes);
        document.getElementById('kpi-taxa-conf').textContent = fmtPct(d.taxa_conformidade);
        document.getElementById('kpi-taxa-nc').textContent   = fmtPct(d.taxa_nao_conformidade);

        // Atualiza donut
        if (chartResultado) {
            chartResultado.data.datasets[0].data = [d.conforme, d.nao_conforme];
            chartResultado.update();
        }
    } catch (e) {
        console.error('Erro KPIs:', e);
    }
}

// ── Evolução temporal ───────────────────────────────────────────────────────
async function carregarTemporal(params) {
    try {
        const r = await fetch(`/inspecao/recebimento/api/analise-temporal/?${qs(params)}`);
        const d = await r.json();

        const labels   = d.map(i => i.mes);
        const conforme = d.map(i => i.conforme);
        const nc       = d.map(i => i.nao_conforme);
        const taxaNC   = d.map(i => i.taxa_nc);

        if (chartTemporal) {
            chartTemporal.data.labels = labels;
            chartTemporal.data.datasets[0].data = conforme;
            chartTemporal.data.datasets[1].data = nc;
            chartTemporal.data.datasets[2].data = taxaNC;
            chartTemporal.update();
        }
    } catch (e) {
        console.error('Erro temporal:', e);
    }
}

// ── Fornecedores ────────────────────────────────────────────────────────────
async function carregarFornecedores(params) {
    const tbody = document.getElementById('tbody-fornecedores');
    try {
        const r = await fetch(`/inspecao/recebimento/api/por-fornecedor/?${qs(params)}`);
        const d = await r.json();

        if (!d.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Sem dados no período.</td></tr>';
            return;
        }

        tbody.innerHTML = d.map((row, idx) => {
            const pctNC = row.total ? (row.nao_conforme / row.total * 100).toFixed(1) : '0.0';
            const cor   = row.nao_conforme > 0 ? `color:${COLOR_RED};font-weight:700;` : '';
            return `<tr>
                <td><span class="rank-index">${idx + 1}</span></td>
                <td>${row.fornecedor}</td>
                <td class="col-num">${fmt(row.total)}</td>
                <td class="col-num" style="color:${COLOR_GREEN};">${fmt(row.conforme)}</td>
                <td class="col-num" style="${cor}">${fmt(row.nao_conforme)}</td>
                <td class="col-num" style="${cor}">${pctNC}%</td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-3">Erro ao carregar.</td></tr>';
    }
}

// ── Classe de Inspeção ──────────────────────────────────────────────────────
async function carregarClasse(params) {
    try {
        const r = await fetch(`/inspecao/recebimento/api/por-classe/?${qs(params)}`);
        const d = await r.json();

        if (chartClasse) {
            chartClasse.data.labels = d.map(i => i.classe);
            chartClasse.data.datasets[0].data = d.map(i => i.total);
            chartClasse.data.datasets[1].data = d.map(i => i.nao_conforme);
            chartClasse.update();
        }
    } catch (e) {
        console.error('Erro classe:', e);
    }
}

// ── Tipo de Material ────────────────────────────────────────────────────────
async function carregarTipoMaterial(params) {
    try {
        const r = await fetch(`/inspecao/recebimento/api/por-tipo-material/?${qs(params)}`);
        const d = await r.json();

        if (chartTipo) {
            chartTipo.data.labels = d.map(i => i.tipo);
            chartTipo.data.datasets[0].data = d.map(i => i.conforme);
            chartTipo.data.datasets[1].data = d.map(i => i.nao_conforme);
            chartTipo.update();
        }
    } catch (e) {
        console.error('Erro tipo material:', e);
    }
}

// ── Carrega tudo ────────────────────────────────────────────────────────────
function carregarTudo() {
    const params = getParams();
    carregarResumo(params);
    carregarTemporal(params);
    carregarFornecedores(params);
    carregarClasse(params);
    carregarTipoMaterial(params);
}

// ── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    document.getElementById('startDate').valueAsDate = firstDay;
    document.getElementById('endDate').valueAsDate   = today;

    // ── Gráfico Temporal (barras + linha taxa NC)
    chartTemporal = new Chart(document.getElementById('chartTemporal'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Conforme',
                    data: [],
                    backgroundColor: COLOR_GREEN,
                    borderRadius: 4,
                    order: 2,
                },
                {
                    label: 'Não Conforme',
                    data: [],
                    backgroundColor: COLOR_RED,
                    borderRadius: 4,
                    order: 2,
                },
                {
                    label: '% Não Conforme',
                    data: [],
                    type: 'line',
                    borderColor: COLOR_ORANGE,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    pointRadius: 4,
                    yAxisID: 'yPct',
                    order: 1,
                },
            ],
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'bottom' } },
            scales: {
                x: { stacked: true, grid: { display: false } },
                y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Qtd.' } },
                yPct: {
                    position: 'right',
                    beginAtZero: true,
                    max: 100,
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: '% NC' },
                    ticks: { callback: v => v + '%' },
                },
            },
        },
    });

    // ── Donut Resultado
    chartResultado = new Chart(document.getElementById('chartResultado'), {
        type: 'doughnut',
        data: {
            labels: ['Conforme', 'Não Conforme'],
            datasets: [{ data: [0, 0], backgroundColor: [COLOR_GREEN, COLOR_RED], borderWidth: 2 }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}` } },
            },
            cutout: '60%',
        },
    });

    // ── Barras Classe de Inspeção
    chartClasse = new Chart(document.getElementById('chartClasse'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                { label: 'Total', data: [], backgroundColor: COLOR_BLUE, borderRadius: 3 },
                { label: 'Não Conforme', data: [], backgroundColor: COLOR_RED, borderRadius: 3 },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { position: 'bottom' } },
            scales: { x: { beginAtZero: true }, y: { grid: { display: false } } },
        },
    });

    // ── Barras agrupadas Tipo de Material
    chartTipo = new Chart(document.getElementById('chartTipo'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                { label: 'Conforme',     data: [], backgroundColor: COLOR_GREEN,  borderRadius: 4 },
                { label: 'Não Conforme', data: [], backgroundColor: COLOR_RED,    borderRadius: 4 },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom' } },
            scales: { x: { grid: { display: false } }, y: { beginAtZero: true } },
        },
    });

    carregarTudo();

    document.getElementById('filterBtn').addEventListener('click', carregarTudo);
    document.getElementById('resetBtn').addEventListener('click', () => {
        document.getElementById('startDate').valueAsDate = new Date(today.getFullYear(), today.getMonth(), 1);
        document.getElementById('endDate').valueAsDate   = today;
        carregarTudo();
    });
});
