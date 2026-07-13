const config = document.getElementById('historicoConfig');
const API_URL = config.dataset.apiUrl;

const tbody = document.getElementById('historicoTabela');
const paginationInfoEl = document.getElementById('historicoPaginationInfo');
const paginationControlsEl = document.getElementById('historicoPaginationControls');
const loadingState = document.getElementById('historicoLoadingState');
const resumoEl = document.getElementById('historicoResumo');
const form = document.getElementById('historicoFiltrosForm');

let currentPage = 1;
let currentFiltros = {};

const STATUS_LABELS = {
    aguardando_iniciar: 'Aguardando iniciar',
    iniciada: 'Iniciada',
    finalizada: 'Finalizada',
    interrompida: 'Interrompida',
    agua_prox_proc: 'Aguard. prox. processo',
};

const STATUS_BADGE = {
    aguardando_iniciar: 'secondary',
    iniciada: 'primary',
    finalizada: 'success',
    interrompida: 'warning',
    agua_prox_proc: 'info',
};

function escapeHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatNumber(val) {
    const n = parseFloat(val);
    return isNaN(n) ? '-' : n.toLocaleString('pt-BR');
}

function badgeStatus(status) {
    const label = STATUS_LABELS[status] || status || '-';
    const cor = STATUS_BADGE[status] || 'secondary';
    return `<span class="badge bg-${cor}">${escapeHtml(label)}</span>`;
}

function lerFiltros() {
    const data = new FormData(form);
    const filtros = {};
    for (const [key, val] of data.entries()) {
        if (val.trim()) filtros[key] = val.trim();
    }
    return filtros;
}

function buildQueryString(filtros, page) {
    const params = new URLSearchParams(filtros);
    params.set('page', page);
    return params.toString();
}

function renderRows(rows) {
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center text-muted py-4">Nenhum registro encontrado.</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map((row) => `
        <tr>
            <td>${escapeHtml(row.ordem || '')}</td>
            <td>${escapeHtml(row.peca_codigo || '')}</td>
            <td>${escapeHtml(row.peca_descricao || '')}</td>
            <td>${escapeHtml(row.maquina || '-')}</td>
            <td>${escapeHtml(row.operador || '-')}</td>
            <td class="text-end">${formatNumber(row.qtd_planejada)}</td>
            <td class="text-end">${formatNumber(row.qtd_boa)}</td>
            <td class="text-end">${formatNumber(row.qtd_morta)}</td>
            <td>${badgeStatus(row.status)}</td>
            <td>${escapeHtml(row.data_inicio || '-')}</td>
            <td>${escapeHtml(row.data_producao || '-')}</td>
            <td>${escapeHtml(row.data_carga || '-')}</td>
        </tr>
    `).join('');
}

function renderPagination(pagination) {
    const { page, total_items, total_pages, has_next, has_previous, page_size } = pagination;

    const inicio = (page - 1) * page_size + 1;
    const fim = Math.min(page * page_size, total_items);
    paginationInfoEl.textContent = total_items
        ? `Exibindo ${inicio}–${fim} de ${total_items.toLocaleString('pt-BR')} registros`
        : 'Nenhum registro';

    const controls = [];
    if (has_previous) {
        controls.push(`<button class="btn btn-outline-secondary btn-sm" data-page="${page - 1}">&#8592; Anterior</button>`);
    }

    const startPage = Math.max(1, page - 2);
    const endPage = Math.min(total_pages, page + 2);
    for (let p = startPage; p <= endPage; p++) {
        controls.push(
            `<button class="btn btn-sm ${p === page ? 'btn-primary' : 'btn-outline-secondary'}" data-page="${p}">${p}</button>`
        );
    }

    if (has_next) {
        controls.push(`<button class="btn btn-outline-secondary btn-sm" data-page="${page + 1}">Proximo &#8594;</button>`);
    }

    paginationControlsEl.innerHTML = controls.join('');

    paginationControlsEl.querySelectorAll('button[data-page]').forEach((btn) => {
        btn.addEventListener('click', () => {
            currentPage = Number(btn.dataset.page);
            carregar();
        });
    });
}

async function carregar() {
    loadingState.classList.remove('d-none');
    tbody.innerHTML = '<tr><td colspan="12" class="text-center text-muted py-3">Carregando...</td></tr>';
    paginationControlsEl.innerHTML = '';
    paginationInfoEl.textContent = '-';

    try {
        const qs = buildQueryString(currentFiltros, currentPage);
        const resp = await fetch(`${API_URL}?${qs}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const payload = await resp.json();

        renderRows(payload.results || []);
        renderPagination(payload.pagination);

        const total = payload.pagination?.total_items ?? 0;
        resumoEl.textContent = `${total.toLocaleString('pt-BR')} registros encontrados`;
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="12" class="text-center text-danger py-4">Falha ao carregar: ${escapeHtml(err.message)}</td></tr>`;
        resumoEl.textContent = '';
    } finally {
        loadingState.classList.add('d-none');
    }
}

function exportarCSV() {
    const params = new URLSearchParams(currentFiltros);
    params.set('formato', 'csv');
    window.location.href = `${API_URL}?${params.toString()}`;
}

// Pré-preenche data_producao_inicio com 30 dias atras
function preencherDataPadrao() {
    const hoje = new Date();
    const trintaDiasAtras = new Date(hoje);
    trintaDiasAtras.setDate(hoje.getDate() - 30);
    const fmt = (d) => d.toISOString().slice(0, 10);
    document.getElementById('filtroDataProdIni').value = fmt(trintaDiasAtras);
    document.getElementById('filtroDataProdFim').value = fmt(hoje);
}

form.addEventListener('submit', (e) => {
    e.preventDefault();
    currentPage = 1;
    currentFiltros = lerFiltros();
    carregar();
});

document.getElementById('btnLimparFiltros').addEventListener('click', () => {
    form.reset();
    preencherDataPadrao();
    currentPage = 1;
    currentFiltros = lerFiltros();
    carregar();
});

document.getElementById('btnAtualizarTabela').addEventListener('click', () => {
    carregar();
});

document.getElementById('btnExportarCSV').addEventListener('click', () => {
    exportarCSV();
});

preencherDataPadrao();
currentFiltros = lerFiltros();
carregar();
