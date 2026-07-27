const config = document.getElementById('timelineConfig');
const API_URL = config.dataset.apiUrl;
const OPERADORES_URL = config.dataset.operadoresUrl;

const container = document.getElementById('timelineContainer');
const vazioEl = document.getElementById('timelineVazio');
const paginationInfoEl = document.getElementById('timelinePaginationInfo');
const paginationControlsEl = document.getElementById('timelinePaginationControls');
const loadingState = document.getElementById('timelineLoadingState');
const resumoEl = document.getElementById('timelineResumo');
const form = document.getElementById('timelineFiltrosForm');
const selectOperador = document.getElementById('filtroOperador');
const btnExportarCSV = document.getElementById('btnExportarCSV');

let currentPage = 1;
let currentFiltros = {};

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

async function carregarOperadores() {
    try {
        const resp = await fetch(OPERADORES_URL);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const payload = await resp.json();
        const operadores = payload.operadores || [];
        operadores.sort((a, b) => (a.nome || '').localeCompare(b.nome || ''));

        selectOperador.innerHTML = '<option value="">Selecione...</option>' +
            operadores.map((op) => `<option value="${op.id}">${escapeHtml(op.matricula)} - ${escapeHtml(op.nome)}</option>`).join('');
    } catch (err) {
        selectOperador.innerHTML = '<option value="">Falha ao carregar operadores</option>';
    }
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

// Agrupa as linhas (ja ordenadas do mais recente pro mais antigo) em blocos
// consecutivos por dia, preservando a ordem.
function agruparPorDia(rows) {
    const grupos = [];
    let grupoAtual = null;
    for (const row of rows) {
        if (!grupoAtual || grupoAtual.data !== row.data) {
            grupoAtual = { data: row.data, itens: [] };
            grupos.push(grupoAtual);
        }
        grupoAtual.itens.push(row);
    }
    return grupos;
}

function renderTimeline(rows) {
    if (!rows.length) {
        container.innerHTML = '';
        vazioEl.classList.remove('d-none');
        vazioEl.textContent = 'Nenhum registro encontrado pra esse operador nesse periodo.';
        return;
    }
    vazioEl.classList.add('d-none');

    const grupos = agruparPorDia(rows);
    container.innerHTML = grupos.map((grupo) => `
        <div class="card mb-3">
            <div class="card-header bg-light fw-semibold">${escapeHtml(grupo.data)}</div>
            <ul class="list-group list-group-flush">
                ${grupo.itens.map((item) => `
                    <li class="list-group-item d-flex flex-wrap align-items-center gap-3">
                        <span class="badge bg-primary" style="min-width:3.5rem;">${escapeHtml(item.hora)}</span>
                        <span class="flex-grow-1">
                            <strong>Ordem ${escapeHtml(item.ordem)}</strong> —
                            ${escapeHtml(item.peca_codigo)} ${item.peca_descricao ? '- ' + escapeHtml(item.peca_descricao) : ''}
                            <span class="text-muted">(${escapeHtml(item.celula || '-')})</span>
                        </span>
                        <span class="text-success small">Boa: ${formatNumber(item.qtd_boa)}</span>
                        <span class="text-danger small">Morta: ${formatNumber(item.qtd_morta)}</span>
                        ${item.duracao_processo ? `<span class="text-muted small" title="Tempo que a ordem ficou rodando (iniciada) ate esse evento fechar o processo">Rodando: ${escapeHtml(item.duracao_processo)}</span>` : ''}
                    </li>
                `).join('')}
            </ul>
        </div>
    `).join('');
}

function renderPagination(pagination) {
    const { page, total_items, total_pages, has_next, has_previous, page_size } = pagination;

    const inicio = total_items ? (page - 1) * page_size + 1 : 0;
    const fim = Math.min(page * page_size, total_items);
    paginationInfoEl.textContent = total_items
        ? `Exibindo ${inicio}–${fim} de ${total_items.toLocaleString('pt-BR')} eventos`
        : '';

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
    if (!currentFiltros.operador_id) {
        container.innerHTML = '';
        vazioEl.classList.remove('d-none');
        vazioEl.textContent = 'Selecione um operador e clique em "Buscar".';
        paginationInfoEl.textContent = '';
        paginationControlsEl.innerHTML = '';
        resumoEl.textContent = '';
        btnExportarCSV.disabled = true;
        return;
    }

    loadingState.classList.remove('d-none');
    vazioEl.classList.add('d-none');
    container.innerHTML = '';
    paginationControlsEl.innerHTML = '';
    paginationInfoEl.textContent = '';
    btnExportarCSV.disabled = false;

    try {
        const qs = buildQueryString(currentFiltros, currentPage);
        const resp = await fetch(`${API_URL}?${qs}`);
        if (!resp.ok) {
            const erroPayload = await resp.json().catch(() => ({}));
            throw new Error(erroPayload.erro || `HTTP ${resp.status}`);
        }
        const payload = await resp.json();

        renderTimeline(payload.results || []);
        renderPagination(payload.pagination);

        const total = payload.pagination?.total_items ?? 0;
        resumoEl.textContent = `${total.toLocaleString('pt-BR')} eventos encontrados`;
    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">Falha ao carregar: ${escapeHtml(err.message)}</div>`;
        resumoEl.textContent = '';
    } finally {
        loadingState.classList.add('d-none');
    }
}

function exportarCSV() {
    if (!currentFiltros.operador_id) return;
    const params = new URLSearchParams(currentFiltros);
    params.set('formato', 'csv');
    window.location.href = `${API_URL}?${params.toString()}`;
}

form.addEventListener('submit', (e) => {
    e.preventDefault();
    currentPage = 1;
    currentFiltros = lerFiltros();
    carregar();
});

document.getElementById('btnAtualizarTabela').addEventListener('click', () => {
    carregar();
});

btnExportarCSV.addEventListener('click', () => {
    exportarCSV();
});

carregarOperadores();
btnExportarCSV.disabled = true;
vazioEl.classList.remove('d-none');
