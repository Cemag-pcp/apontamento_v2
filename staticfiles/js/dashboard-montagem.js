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
    const tmfLimitInput      = document.getElementById('tmf-limit');
    const tmfReload          = document.getElementById('tmf-reload');

    let statusChart;
    let machineChart;
    let cargaChart;
    let activityChart;
    let taktChart = null;

    // ── Takt Time — configurações ────────────────────────────────────────────
    // Nomes exatos conforme cadastro no banco de dados
    const TAKT_CELL_DEFAULTS = [
        { nome: 'PLAT. TANQUE. CAÇAM.', ops: 4   },
        { nome: 'CHASSI',               ops: 1   },
        { nome: 'CONJ INTERMED',        ops: 1   },
        { nome: 'CILINDRO',             ops: 1   },
        { nome: 'CILINDRO 2',           ops: 0.5 },
        { nome: 'IÇAMENTO',             ops: 1   },
    ];

    // Fallback por palavra-chave para células não listadas acima
    const TAKT_KEYWORD_OPS = [
        { key: 'plat',         ops: 4   },
        { key: 'cacam',        ops: 4   },
        { key: 'tanque',       ops: 4   },
        { key: 'chassi',       ops: 1   },
        { key: 'intermed',     ops: 1   },
        { key: 'icamento',     ops: 1   },
        { key: 'cilindro 2',   ops: 0.5 },
        { key: 'eixo completo',ops: 0.5 },
        { key: 'cilindro',     ops: 1   },
        { key: 'lateral',      ops: 2   },
        { key: 'fueiro',       ops: 1   },
        { key: 'solda eixo',   ops: 1   },
        { key: 'eixo simples', ops: 2   },
        { key: 'cubo',         ops: 1   },
    ];

    // cellName -> operator count (state)
    let taktOperators = Object.fromEntries(TAKT_CELL_DEFAULTS.map(c => [c.nome, c.ops]));
    // track which cells came from the API (for the config table)
    let taktApiCells = [];
    // última resposta da API — reutilizada ao mudar operadores sem nova requisição
    let lastTaktData = null;

    // Tempo disponível por dia (base). O input de tempo exibe dailyDisp × numDays.
    let taktDailyDisp = 540;

    function getTaktNumDays() {
        const s = document.getElementById('takt-data-inicio');
        const e = document.getElementById('takt-data-fim');
        if (!s?.value || !e?.value) return 1;
        const diff = Math.round((new Date(e.value) - new Date(s.value)) / 86400000);
        return Math.max(1, diff + 1);
    }

    function syncTempoInput() {
        const el = document.getElementById('takt-tempo-disp');
        if (el) el.value = taktDailyDisp * getTaktNumDays();
    }

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
            limit:             tmfLimitInput ? tmfLimitInput.value : '200',
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

    // ── Takt Time — funções ──────────────────────────────────────────────────

    function normCell(s) {
        return s.toLowerCase()
            .normalize('NFD')
            .replace(/\p{Diacritic}/gu, '')
            .replace(/[^\w\s]/g, ' ')
            .trim();
    }

    function getDefaultOps(apiName) {
        const norm = normCell(apiName);
        // Exact match
        for (const { nome, ops } of TAKT_CELL_DEFAULTS) {
            if (normCell(nome) === norm) return ops;
        }
        // Substring match
        for (const { nome, ops } of TAKT_CELL_DEFAULTS) {
            const normDef = normCell(nome);
            if (norm.includes(normDef) || normDef.includes(norm)) return ops;
        }
        // Keyword fallback (order matters — more specific first)
        for (const { key, ops } of TAKT_KEYWORD_OPS) {
            if (norm.includes(normCell(key))) return ops;
        }
        return 1;
    }

    function getTotalCurrentOps() {
        const allCells = taktApiCells.length ? taktApiCells : TAKT_CELL_DEFAULTS.map(c => c.nome);
        return allCells.reduce((s, nome) => s + (taktOperators[nome] ?? getDefaultOps(nome)), 0);
    }

    function renderTaktOpConfig() {
        const container = document.getElementById('takt-op-config');
        if (!container) return;

        const cellList = taktApiCells.length
            ? taktApiCells
            : TAKT_CELL_DEFAULTS.map(c => c.nome);

        container.innerHTML = `
            <div class="takt-op-grid">
                ${cellList.map(nome => {
                    const ops = taktOperators[nome] ?? getDefaultOps(nome);
                    return `
                        <label class="takt-op-item">
                            <span class="takt-op-name" title="${nome}">${nome}</span>
                            <input class="takt-op-input" type="number" min="0.5" step="0.5"
                                   value="${ops}" data-cell="${nome}">
                            <small>op.</small>
                        </label>`;
                }).join('')}
            </div>`;

        container.querySelectorAll('.takt-op-input').forEach(inp => {
            inp.addEventListener('change', () => {
                taktOperators[inp.dataset.cell] = parseFloat(inp.value) || 1;
                if (lastTaktData) buildTaktChart(lastTaktData);
            });
        });
    }

    // Último estado recebido da API para células e exclusões
    let taktTodasCelulas = [];
    let taktCelulasExcluidas = new Set();

    function renderTaktCelulasConfig(data) {
        const container = document.getElementById('takt-celulas-config');
        if (!container) return;

        taktTodasCelulas = data.todas_celulas || [];
        taktCelulasExcluidas = new Set(data.celulas_excluidas || []);

        if (!taktTodasCelulas.length) {
            container.innerHTML = '<p style="font-size:0.78rem;color:#94a3b8;">Nenhuma célula encontrada.</p>';
            return;
        }

        container.innerHTML = `
            <div class="takt-celulas-grid">
                ${taktTodasCelulas.map(cel => {
                    const excluida = taktCelulasExcluidas.has(cel.id);
                    return `
                        <button class="takt-celula-chip ${excluida ? 'takt-celula-excluida' : ''}"
                                data-id="${cel.id}" title="${excluida ? 'Excluída — clique para incluir' : 'Incluída — clique para excluir'}">
                            ${excluida ? '✕ ' : ''}${cel.nome}
                        </button>`;
                }).join('')}
            </div>`;

        container.querySelectorAll('.takt-celula-chip').forEach(btn => {
            btn.addEventListener('click', () => toggleCelulaExcluida(parseInt(btn.dataset.id)));
        });
    }

    async function toggleCelulaExcluida(maquinaId) {
        const toggleUrl = app.dataset.taktToggleUrl;
        if (!toggleUrl) return;
        try {
            const res = await fetch(toggleUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ maquina_id: maquinaId }),
            });
            if (!res.ok) throw new Error();
            const result = await res.json();
            if (result.status === 'excluida') {
                taktCelulasExcluidas.add(maquinaId);
            } else {
                taktCelulasExcluidas.delete(maquinaId);
            }
            // Atualiza visual sem recarregar tudo
            const container = document.getElementById('takt-celulas-config');
            if (container) {
                container.querySelectorAll('.takt-celula-chip').forEach(btn => {
                    const id = parseInt(btn.dataset.id);
                    const excluida = taktCelulasExcluidas.has(id);
                    const cel = taktTodasCelulas.find(c => c.id === id);
                    btn.className = `takt-celula-chip ${excluida ? 'takt-celula-excluida' : ''}`;
                    btn.title = excluida ? 'Excluída — clique para incluir' : 'Incluída — clique para excluir';
                    btn.textContent = (excluida ? '✕ ' : '') + (cel?.nome || '');
                });
            }
        } catch {
            alert('Erro ao atualizar célula. Tente novamente.');
        }
    }

    function getCookie(name) {
        const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
        return v ? v[2] : '';
    }

    async function loadTaktTime() {
        const taktUrl = app.dataset.taktUrl;
        if (!taktUrl) return;

        const btn      = document.getElementById('takt-reload');
        const startEl  = document.getElementById('takt-data-inicio');
        const endEl    = document.getElementById('takt-data-fim');
        const qtEl     = document.getElementById('takt-qt-carretas');
        const tempoEl  = document.getElementById('takt-tempo-disp');
        const wrap     = document.getElementById('takt-chart-wrap');
        const summary  = document.getElementById('takt-summary');

        if (btn) { btn.disabled = true; btn.textContent = 'Calculando…'; }
        if (summary) summary.style.display = 'none';

        const params = new URLSearchParams({
            data_inicio:   startEl ? startEl.value : '',
            data_fim:      endEl   ? endEl.value   : '',
            qt_carretas:   qtEl    ? qtEl.value    : '10',
            tempo_disp_min: tempoEl ? tempoEl.value : '540',
        });

        try {
            const res = await fetch(`${taktUrl}?${params}`);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.error || `Erro ${res.status}`);
            }
            const data = await res.json();

            // Update API cell list and merge into operator state
            taktApiCells = data.cells.map(c => c.nome);
            taktApiCells.forEach(nome => {
                if (taktOperators[nome] === undefined) {
                    taktOperators[nome] = getDefaultOps(nome);
                }
            });

            // Sempre atualiza o estado de células a partir da API
            lastTaktData = data;
            taktTodasCelulas = data.todas_celulas || [];
            taktCelulasExcluidas = new Set(data.celulas_excluidas || []);

            // Só re-renderiza o painel se estiver visível
            const taktConfigPanel = document.getElementById('takt-config');
            if (taktConfigPanel && taktConfigPanel.style.display !== 'none') {
                renderTaktOpConfig();
                renderTaktCelulasConfig(data);
            }

            buildTaktChart(data);
        } catch (err) {
            if (taktChart) { taktChart.destroy(); taktChart = null; }
            if (wrap) wrap.innerHTML = `<div class="dashboard-empty">${err.message}</div>`;
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Calcular'; }
        }
    }

    // Fator de ajuste: ciclo_ajustado = ciclo_histórico / ops_atual
    function getOpsFactor(cellNome) {
        const opsCurrent = taktOperators[cellNome] ?? getDefaultOps(cellNome);
        return opsCurrent > 0 ? 1 / opsCurrent : 1;
    }

    function buildTaktChart(data) {
        const wrap = document.getElementById('takt-chart-wrap');

        if (wrap && !wrap.querySelector('canvas')) {
            wrap.innerHTML = '<canvas id="taktChart"></canvas>';
        }
        const ctx = document.getElementById('taktChart');
        if (!ctx) return;

        if (taktChart) { taktChart.destroy(); taktChart = null; }

        const planned = data.planned_production || [];
        const historicalCells = data.cells || [];

        if (!planned.length && !historicalCells.length) {
            if (wrap) wrap.innerHTML = '<div class="dashboard-empty">Sem dados no período selecionado.</div>';
            return;
        }

        const palette = [
            '#0f766e', '#0284c7', '#7c3aed', '#d97706', '#16a34a',
            '#db2777', '#2563eb', '#ea580c', '#0891b2', '#65a30d',
        ];

        // Mapa de ciclo por célula: { cellNome: { pecaNome: min, _avg: min } }
        // Também indexa pelo código numérico (antes de " - ") para resolver
        // divergências de nome entre planejado ("030493") e histórico ("030493 - CHASSI ...").
        const cycleMap = {};
        historicalCells.forEach(cell => {
            cycleMap[cell.nome] = { _avg: cell.cycle_time_min };
            cell.conjuntos.forEach(c => {
                cycleMap[cell.nome][c.nome] = c.cycle_time_min;
                const codigo = c.nome.split(' - ')[0].trim();
                if (codigo && codigo !== c.nome && cycleMap[cell.nome][codigo] == null) {
                    cycleMap[cell.nome][codigo] = c.cycle_time_min;
                }
            });
        });

        // Ciclo global por peça (fallback quando a peça não tem histórico na célula)
        const globalCycleByPeca = data.cycle_by_peca || {};

        if (planned.length) {
            // ── Modo planejado: barras = horas estimadas (qtd × ciclo histórico) ──

            // Coleta todas as peças únicas do planejado
            const seenPecas = new Set();
            const pecaList = [];
            planned.forEach(cell => cell.pecas.forEach(p => {
                if (!seenPecas.has(p.peca)) { seenPecas.add(p.peca); pecaList.push(p.peca); }
            }));

            // Ciclo: 1º célula+peça, 2º global por peça, 3º média da célula
            function getCycleTime(cellName, pecaName) {
                const cellCycles = cycleMap[cellName] || {};
                if (cellCycles[pecaName] != null) return { ct: cellCycles[pecaName], fonte: 'celula' };
                if (globalCycleByPeca[pecaName] != null) return { ct: globalCycleByPeca[pecaName], fonte: 'global' };
                if (cellCycles._avg != null) return { ct: cellCycles._avg, fonte: 'media_celula' };
                return { ct: 0, fonte: 'sem_dado' };
            }

            const barDatasets = pecaList.map((peca, i) => ({
                label: peca.length > 45 ? peca.slice(0, 42) + '…' : peca,
                type:  'bar',
                data:  planned.map(cell => {
                    const p = cell.pecas.find(pp => pp.peca === peca);
                    if (!p || p.qtd_planejada <= 0) return 0;
                    const { ct } = getCycleTime(cell.cell, peca);
                    return ct > 0 ? parseFloat(((p.qtd_planejada * ct * getOpsFactor(cell.cell)) / 60).toFixed(2)) : 0;
                }),
                backgroundColor: palette[i % palette.length],
                stack: 'planned',
            }));

            // Linha de capacidade: tempo_disp_min já vem ajustado pelo nº de dias via input
            const numDays = getTaktNumDays();
            const capH = data.tempo_disp_min / 60;
            const capLabel = numDays > 1
                ? `Capacidade ${numDays} dias (${capH.toFixed(1)}h)`
                : `Capacidade/dia (${capH.toFixed(1)}h)`;
            const capDataset = {
                label: capLabel,
                type:  'line',
                data:  planned.map(() => capH),
                borderColor: '#ef4444',
                borderWidth: 2.5,
                borderDash: [7, 4],
                pointRadius: 0,
                pointHoverRadius: 0,
                fill: false,
                tension: 0,
                order: 0,
            };

            const labels = planned.map(cell => {
                const ops = taktOperators[cell.cell] ?? getDefaultOps(cell.cell);
                return [cell.cell, `${ops} oper.`];
            });

            taktChart = new Chart(ctx, {
                type: 'bar',
                data: { labels, datasets: [...barDatasets, capDataset] },
                options: {
                    maintainAspectRatio: false,
                    responsive: true,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        x: {
                            stacked: true,
                            grid: { display: false },
                            ticks: { maxRotation: 45, font: { size: 10 } },
                        },
                        y: {
                            stacked: true,
                            beginAtZero: true,
                            grid: { color: '#f1f5f9' },
                            title: { display: true, text: 'horas estimadas', font: { size: 11 } },
                        },
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label(context) {
                                    if (context.dataset.type === 'line') return null;
                                    if (!context.raw || context.raw === 0) return null;
                                    const cellItem = planned[context.dataIndex];
                                    const pecaNome = cellItem?.pecas.find(pp =>
                                        pp.peca === context.dataset.label ||
                                        context.dataset.label.startsWith(pp.peca.slice(0, 42))
                                    )?.peca ?? context.dataset.label;
                                    const p = cellItem?.pecas.find(pp => pp.peca === pecaNome);
                                    const { ct, fonte } = getCycleTime(cellItem?.cell, pecaNome);
                                    const fonteLabel = fonte === 'celula' ? '' : fonte === 'global' ? ' ~global' : ' ~média célula';
                                    const qtdStr = p ? ` × ${formatNumber(p.qtd_planejada)} un.` : '';
                                    const cicloStr = ct > 0 ? ` (${ct.toFixed(1)} min/un${fonteLabel})` : '';
                                    return `${context.dataset.label}${qtdStr}${cicloStr}: ${Number(context.raw).toFixed(1)}h`;
                                },
                                footer(items) {
                                    const total = items
                                        .filter(i => i.dataset.type === 'bar')
                                        .reduce((s, i) => s + (i.raw || 0), 0);
                                    if (total === 0) return null;
                                    const diff = total - capH;
                                    const capLabelTip = numDays > 1 ? `capacidade (${numDays} dias)` : 'capacidade/dia';
                                    return diff > 0.05
                                        ? [`Total: ${total.toFixed(1)}h  ⚠ +${diff.toFixed(1)}h acima da ${capLabelTip}`]
                                        : [`Total: ${total.toFixed(1)}h  ✓ ${Math.abs(diff).toFixed(1)}h de folga`];
                                },
                            },
                        },
                    },
                },
            });

            // KPIs resumo do modo planejado
            const totalHoras = planned.reduce((s, cell) => {
                return s + cell.pecas.reduce((ss, p) => {
                    const cellCycles = cycleMap[cell.cell] || {};
                    const ct = cellCycles[p.peca] ?? cellCycles._avg ?? 0;
                    return ss + (ct > 0 ? (p.qtd_planejada * ct * getOpsFactor(cell.cell)) / 60 : 0);
                }, 0);
            }, 0);
            const totalQtd = planned.reduce((s, cell) =>
                s + cell.pecas.reduce((ss, p) => ss + p.qtd_planejada, 0), 0);
            renderTaktSummary(data, totalHoras * 60, totalHoras / capH);

        } else {
            // ── Fallback: modo ciclo histórico (sem ordens planejadas no período) ──

            const seenConj = new Set();
            const conjuntoList = [];
            historicalCells.forEach(cell => cell.conjuntos.forEach(c => {
                if (!seenConj.has(c.nome)) { seenConj.add(c.nome); conjuntoList.push(c.nome); }
            }));

            const barDatasets = conjuntoList.map((nome, i) => ({
                label: nome.length > 45 ? nome.slice(0, 42) + '…' : nome,
                type:  'bar',
                data:  historicalCells.map(cell => {
                    const c = cell.conjuntos.find(j => j.nome === nome);
                    if (!c || !c.cycle_time_min) return 0;
                    const totalConj = cell.conjuntos.reduce((s, j) => s + j.cycle_time_min, 0);
                    const proporcao = totalConj > 0 ? c.cycle_time_min / totalConj : 0;
                    return cell.cycle_time_min * proporcao * getOpsFactor(cell.nome);
                }),
                backgroundColor: palette[i % palette.length],
                stack: 'cycle',
            }));

            const taktDataset = {
                label: `Takt (${data.takt_time_min.toFixed(1)} min)`,
                type:  'line',
                data:  historicalCells.map(() => data.takt_time_min),
                borderColor: '#ef4444',
                borderWidth: 2.5,
                borderDash: [7, 4],
                pointRadius: 0,
                pointHoverRadius: 0,
                fill: false,
                tension: 0,
                order: 0,
            };

            const labels = historicalCells.map(cell => {
                const ops = taktOperators[cell.nome] ?? getDefaultOps(cell.nome);
                return [cell.nome, `${ops} oper.`];
            });

            const adjustedTotal  = historicalCells.reduce((s, cell) => s + cell.cycle_time_min * getOpsFactor(cell.nome), 0);
            const adjustedNumOps = data.takt_time_min > 0 ? adjustedTotal / data.takt_time_min : 0;

            taktChart = new Chart(ctx, {
                type: 'bar',
                data: { labels, datasets: [...barDatasets, taktDataset] },
                options: {
                    maintainAspectRatio: false,
                    responsive: true,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        x: { stacked: true, grid: { display: false }, ticks: { maxRotation: 45, font: { size: 10 } } },
                        y: {
                            stacked: true, beginAtZero: true, grid: { color: '#f1f5f9' },
                            title: { display: true, text: 'min / unidade', font: { size: 11 } },
                        },
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label(context) {
                                    if (context.dataset.type === 'line') return null;
                                    if (!context.raw || context.raw === 0) return null;
                                    return `${context.dataset.label}: ${Number(context.raw).toFixed(1)} min/un`;
                                },
                                footer(items) {
                                    const total = items.filter(i => i.dataset.type === 'bar').reduce((s, i) => s + (i.raw || 0), 0);
                                    if (total === 0) return null;
                                    const diff = total - data.takt_time_min;
                                    return diff > 0.01
                                        ? [`Total: ${total.toFixed(1)} min/un`, `⚠ Acima do takt em ${diff.toFixed(1)} min`]
                                        : [`Total: ${total.toFixed(1)} min/un`, `✓ ${Math.abs(diff).toFixed(1)} min de folga`];
                                },
                            },
                        },
                    },
                },
            });

            renderTaktSummary(data, adjustedTotal, adjustedNumOps);
        }
    }

    function renderTaktSummary(data, adjustedTotal, adjustedNumOps) {
        const summary = document.getElementById('takt-summary');
        if (!summary) return;

        const currentOps = getTotalCurrentOps();
        summary.style.display = '';
        summary.innerHTML = `
            <div class="takt-summary-grid">
                <div class="takt-kpi">
                    <span>Takt time</span>
                    <strong>${data.takt_time_min.toFixed(1)}<small>min/un</small></strong>
                </div>
                <div class="takt-kpi">
                    <span>Tempo disponível</span>
                    <strong>${(data.tempo_disp_min / 60).toFixed(1)}<small>h</small></strong>
                </div>
                <div class="takt-kpi">
                    <span>Qt. carretas</span>
                    <strong>${data.qt_carretas}</strong>
                </div>
                <div class="takt-kpi takt-kpi-highlight">
                    <span>Op. necessários</span>
                    <strong>${adjustedNumOps.toFixed(1)}</strong>
                </div>
                <div class="takt-kpi">
                    <span>Op. atuais</span>
                    <strong>${currentOps}</strong>
                </div>
                <div class="takt-kpi">
                    <span>Σ Ciclo ajustado</span>
                    <strong>${adjustedTotal.toFixed(1)}<small>min</small></strong>
                </div>
            </div>`;
    }

    // ── Takt info popover (fixed, scrollável) ────────────────────────────────
    const taktInfoAnchor  = document.querySelector('.takt-info-anchor');
    const taktInfoPopover = document.querySelector('.takt-info-popover');
    if (taktInfoAnchor && taktInfoPopover) {
        let hideTimer = null;

        function positionPopover() {
            const anchor = taktInfoAnchor.getBoundingClientRect();
            const pop    = taktInfoPopover.getBoundingClientRect();
            const gap    = 6;
            const vw     = window.innerWidth;
            const vh     = window.innerHeight;

            let top  = anchor.bottom + gap;
            let left = anchor.left;

            // não sair pela direita
            if (left + pop.width > vw - 8) left = vw - pop.width - 8;
            // se não couber embaixo, abre para cima
            if (top + pop.height > vh - 8) top = anchor.top - pop.height - gap;
            // garante mínimo 8px do topo
            if (top < 8) top = 8;

            taktInfoPopover.style.top  = `${Math.round(top)}px`;
            taktInfoPopover.style.left = `${Math.round(left)}px`;
        }

        function showPopover() {
            clearTimeout(hideTimer);
            // Adiciona classe primeiro para o elemento ter dimensões reais
            taktInfoPopover.classList.add('is-visible');
            // Posiciona após render
            requestAnimationFrame(positionPopover);
        }

        function scheduleHide() {
            hideTimer = setTimeout(() => taktInfoPopover.classList.remove('is-visible'), 150);
        }

        taktInfoAnchor.addEventListener('mouseenter', showPopover);
        taktInfoAnchor.addEventListener('mouseleave', scheduleHide);
        taktInfoPopover.addEventListener('mouseenter', () => clearTimeout(hideTimer));
        taktInfoPopover.addEventListener('mouseleave', scheduleHide);
        taktInfoAnchor.addEventListener('focus', showPopover);
        taktInfoAnchor.addEventListener('blur', scheduleHide);
    }

    // ── Takt Time — event listeners ──────────────────────────────────────────

    const taktConfigToggle = document.getElementById('takt-config-toggle');
    const taktConfigPanel  = document.getElementById('takt-config');
    if (taktConfigToggle && taktConfigPanel) {
        taktConfigToggle.addEventListener('click', () => {
            const isHidden = taktConfigPanel.style.display === 'none';
            taktConfigPanel.style.display = isHidden ? '' : 'none';
            taktConfigToggle.textContent  = isHidden ? 'Fechar' : 'Configurar';
            if (isHidden) {
                if (!taktTodasCelulas.length) {
                    // Dados ainda não carregados — dispara cálculo; ao retornar, o
                    // painel já estará visível e renderTaktCelulasConfig será chamado.
                    loadTaktTime();
                } else {
                    renderTaktOpConfig();
                    renderTaktCelulasConfig({ todas_celulas: taktTodasCelulas, celulas_excluidas: [...taktCelulasExcluidas] });
                }
            }
        });
    }

    const taktReload = document.getElementById('takt-reload');
    if (taktReload) taktReload.addEventListener('click', loadTaktTime);

    // Initialise takt date inputs to today
    (function applyTaktDefaultDates() {
        const today = new Date().toISOString().slice(0, 10);
        const s = document.getElementById('takt-data-inicio');
        const e = document.getElementById('takt-data-fim');
        if (s) s.value = today;
        if (e) e.value = today;
        syncTempoInput();
    })();

    // Quando as datas mudam → recalcula o input de tempo (dailyDisp × numDias)
    ['takt-data-inicio', 'takt-data-fim'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', syncTempoInput);
    });

    // Quando o usuário edita manualmente o tempo → atualiza o valor diário base
    const tempoDispEl = document.getElementById('takt-tempo-disp');
    if (tempoDispEl) {
        tempoDispEl.addEventListener('change', () => {
            const total = parseFloat(tempoDispEl.value) || 540;
            taktDailyDisp = Math.max(1, Math.round(total / getTaktNumDays()));
            syncTempoInput(); // re-normaliza para evitar frações
        });
    }

    // ── Main form ────────────────────────────────────────────────────────────
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
