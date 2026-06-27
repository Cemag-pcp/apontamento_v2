const state = {
    operadores: [],
    currentPage: 1,
    rowsPerPage: 10,
    selectedIds: new Set(),
};

function getElements() {
    return {
        tbody: document.getElementById('operatorsTableBody'),
        loading: document.getElementById('overlayLoading'),
        summary: document.getElementById('operatorsTableSummary'),
        pagination: document.getElementById('operatorsPagination'),
        rowsPerPage: document.getElementById('rowsPerPage'),
    };
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function buildInitials(nome) {
    return (nome || '')
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map(part => part[0]?.toUpperCase() || '')
        .join('') || '--';
}

function getVisibleOperadores() {
    const start = (state.currentPage - 1) * state.rowsPerPage;
    const end = start + state.rowsPerPage;
    return state.operadores.slice(start, end);
}

function updateToolbarState() {
    return;
}

function renderSummary() {
    const { summary } = getElements();
    const totalOperadores = state.operadores.length;
    const start = totalOperadores === 0 ? 0 : (state.currentPage - 1) * state.rowsPerPage + 1;
    const end = Math.min(state.currentPage * state.rowsPerPage, totalOperadores);

    if (summary) summary.textContent = `${start}-${end} of ${totalOperadores}`;
}

function renderPagination() {
    const { pagination } = getElements();
    if (!pagination) return;

    const totalPages = Math.max(1, Math.ceil(state.operadores.length / state.rowsPerPage));
    const current = state.currentPage;
    const pages = [];

    pages.push(1);
    for (let page = current - 1; page <= current + 1; page += 1) {
        if (page > 1 && page < totalPages) pages.push(page);
    }
    if (totalPages > 1) pages.push(totalPages);

    const dedupedPages = [...new Set(pages)].sort((a, b) => a - b);
    const items = [];

    items.push(`
        <button class="pagination-button" data-page="${Math.max(1, current - 1)}" ${current === 1 ? 'disabled' : ''} aria-label="Pagina anterior">
            <i class="bi bi-chevron-left"></i>
        </button>
    `);

    dedupedPages.forEach((page, index) => {
        const previous = dedupedPages[index - 1];
        if (previous && page - previous > 1) {
            items.push('<span class="pagination-button" aria-hidden="true">...</span>');
        }

        items.push(`
            <button class="pagination-button ${page === current ? 'is-active' : ''}" data-page="${page}">
                ${page}
            </button>
        `);
    });

    items.push(`
        <button class="pagination-button" data-page="${Math.min(totalPages, current + 1)}" ${current === totalPages ? 'disabled' : ''} aria-label="Proxima pagina">
            <i class="bi bi-chevron-right"></i>
        </button>
    `);

    pagination.innerHTML = items.join('');
}

function renderTable() {
    const { tbody } = getElements();
    if (!tbody) return;

    const visible = getVisibleOperadores();

    if (!visible.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    <div class="operators-empty-state">Nenhum operador encontrado.</div>
                </td>
            </tr>
        `;
        updateToolbarState();
        renderSummary();
        renderPagination();
        return;
    }

    tbody.innerHTML = visible.map(operador => {
        const isSelected = state.selectedIds.has(operador.id);
        const isActive = operador.status === 'ativo';
        const statusLabel = isActive ? 'Ativo' : 'Inativo';

        return `
            <tr data-id="${operador.id}" class="${isSelected ? 'is-selected' : ''}">
                <td id="operadorNome-${operador.id}">
                    <div class="operator-cell">
                        <div class="operator-avatar">${escapeHtml(buildInitials(operador.nome))}</div>
                        <div class="operator-details">
                            <div class="operator-name">${escapeHtml(operador.nome)}</div>
                            <div class="operator-subtitle">Operador cadastrado</div>
                        </div>
                    </div>
                </td>
                <td id="operadorMatricula-${operador.id}">
                    <span class="mono-text">${escapeHtml(operador.matricula)}</span>
                </td>
                <td id="operadorSetor-${operador.id}" data-id-setor="${operador.setor_id}">
                    <span class="role-pill">
                        <i class="bi bi-person-badge"></i>
                        ${escapeHtml(operador.setor)}
                    </span>
                </td>
                <td id="operadorStatus-${operador.id}">
                    <span class="status-pill ${isActive ? 'is-active' : 'is-inactive'}">
                        <span class="status-dot"></span>
                        ${statusLabel}
                    </span>
                </td>
                <td>
                    <div class="row-actions">
                        <button type="button" class="icon-action-button btnEditOperador" id="btnEditOperador-${operador.id}" aria-label="Editar operador ${escapeHtml(operador.nome)}" title="Editar">
                            <i class="bi bi-pencil-square"></i>
                        </button>
                        <button type="button" class="icon-action-button danger btnDesativarOperador" id="btnDesativarOperador-${operador.id}" ${!isActive ? 'disabled' : ''} aria-label="Desativar operador ${escapeHtml(operador.nome)}" title="Desativar">
                            <i class="bi bi-person-x"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    updateToolbarState();
    renderSummary();
    renderPagination();
}

function renderAll() {
    renderTable();
}

export function getSelectedOperadorIds() {
    return [...state.selectedIds];
}

export function clearSelection() {
    state.selectedIds.clear();
    renderAll();
}

export function getOperadorById(id) {
    return state.operadores.find(item => String(item.id) === String(id)) || null;
}

export async function carregarTabela() {
    const { loading } = getElements();
    if (loading) loading.style.display = 'flex';

    const response = await fetch('/cadastro/api/operadores/');
    const data = await response.json();

    state.operadores = (data.operadores || []).sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
    state.currentPage = 1;
    state.selectedIds.clear();

    if (loading) loading.style.display = 'none';
    renderAll();
}

function bindStaticControls() {
    const { rowsPerPage, pagination } = getElements();

    rowsPerPage?.addEventListener('change', event => {
        state.rowsPerPage = Number(event.target.value || 10);
        state.currentPage = 1;
        renderAll();
    });

    pagination?.addEventListener('click', event => {
        const button = event.target.closest('[data-page]');
        if (!button || button.disabled) return;
        state.currentPage = Number(button.dataset.page);
        renderAll();
    });

    document.addEventListener('change', event => {
        const checkbox = event.target.closest('.row-selector');
        if (!checkbox) return;

        const operadorId = Number(checkbox.dataset.id);
        if (checkbox.checked) state.selectedIds.add(operadorId);
        else state.selectedIds.delete(operadorId);

        renderAll();
    });
}

document.addEventListener('DOMContentLoaded', bindStaticControls);
