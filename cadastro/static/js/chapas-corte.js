const app = document.getElementById('chapas-corte-app');
const apiUrl = app?.dataset.apiUrl || '/cadastro/api/chapas-corte/';

const state = {
    currentPage: 1,
    rowsPerPage: 50,
    totalPages: 1,
    totalItems: 0,
    search: '',
    ativo: 'true',
};

const chapaModal = new bootstrap.Modal(document.getElementById('chapa-modal'));
const toggleModal = new bootstrap.Modal(document.getElementById('toggle-chapa-modal'));

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getCSRFToken(form) {
    return form.querySelector('[name=csrfmiddlewaretoken]')?.value || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

function showToast(icon, title, text) {
    Swal.fire({
        icon,
        title,
        text,
        toast: true,
        position: 'bottom-end',
        timer: 3000,
        timerProgressBar: true,
        showConfirmButton: false,
    });
}

function renderSummary(page, pageSize, total) {
    const summary = document.getElementById('pagination-summary-chapa');
    const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, total);
    summary.textContent = `${start}-${end} de ${total}`;
}

function renderPagination(current, totalPages) {
    const pagination = document.getElementById('chapas-corte-pagination');
    const pages = new Set([1]);
    for (let page = current - 1; page <= current + 1; page++) {
        if (page > 1 && page < totalPages) pages.add(page);
    }
    if (totalPages > 1) pages.add(totalPages);

    const orderedPages = [...pages].sort((a, b) => a - b);
    const items = [
        `<button class="pagination-button" data-page="${Math.max(1, current - 1)}" ${current === 1 ? 'disabled' : ''} aria-label="Anterior"><i class="bi bi-chevron-left"></i></button>`,
    ];

    orderedPages.forEach((page, index) => {
        const previous = orderedPages[index - 1];
        if (previous && page - previous > 1) items.push('<span class="pagination-button" aria-hidden="true">...</span>');
        items.push(`<button class="pagination-button ${page === current ? 'is-active' : ''}" data-page="${page}">${page}</button>`);
    });

    items.push(`<button class="pagination-button" data-page="${Math.min(totalPages, current + 1)}" ${current === totalPages ? 'disabled' : ''} aria-label="Proxima"><i class="bi bi-chevron-right"></i></button>`);
    pagination.innerHTML = items.join('');
}

function renderTable(results) {
    const tbody = document.getElementById('chapas-corte-body');

    if (!results.length) {
        tbody.innerHTML = '<tr><td colspan="5"><div class="operators-empty-state">Nenhuma chapa encontrada.</div></td></tr>';
        return;
    }

    tbody.innerHTML = results.map(item => {
        const statusLabel = item.ativo ? 'Ativa' : 'Inativa';
        const toggleLabel = item.ativo ? 'Inativar' : 'Ativar';
        const toggleIcon = item.ativo ? 'bi-toggle-on' : 'bi-toggle-off';

        return `
            <tr data-id="${item.id}">
                <td class="mono-text">${escapeHtml(item.como_aparece_planilha)}</td>
                <td class="text-end">${escapeHtml(item.espessura)}</td>
                <td>${escapeHtml(item.codigo || '-')}</td>
                <td>
                    <span class="status-pill ${item.ativo ? 'is-active' : 'is-inactive'}">
                        <span class="status-dot"></span>${statusLabel}
                    </span>
                </td>
                <td>
                    <div class="row-actions">
                        <button type="button" class="icon-action-button btn-edit-chapa"
                            data-id="${item.id}"
                            data-como-aparece="${escapeHtml(item.como_aparece_planilha)}"
                            data-espessura="${escapeHtml(item.espessura)}"
                            data-codigo="${escapeHtml(item.codigo || '')}"
                            title="Editar">
                            <i class="bi bi-pencil-square"></i>
                        </button>
                        <button type="button" class="icon-action-button btn-toggle-chapa"
                            data-id="${item.id}"
                            data-nome="${escapeHtml(item.como_aparece_planilha)}"
                            data-ativo="${item.ativo}"
                            title="${toggleLabel}">
                            <i class="bi ${toggleIcon}"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

async function carregarTabela() {
    const tbody = document.getElementById('chapas-corte-body');
    tbody.innerHTML = `
        <tr>
            <td colspan="5">
                <div class="operators-loading">
                    <div class="spinner-border text-primary" role="status"></div>
                    <span>Carregando chapas...</span>
                </div>
            </td>
        </tr>
    `;

    const params = new URLSearchParams({
        page: state.currentPage,
        page_size: state.rowsPerPage,
        ativo: state.ativo,
    });
    if (state.search) params.set('search', state.search);

    const response = await fetch(`${apiUrl}?${params}`);
    const data = await response.json();

    if (!response.ok) {
        showToast('error', 'Erro', data.error || 'Nao foi possivel carregar as chapas.');
        return;
    }

    state.totalPages = data.total_pages || 1;
    state.totalItems = data.total_items || 0;

    renderTable(data.results || []);
    renderSummary(data.page, data.page_size, data.total_items);
    renderPagination(data.page, data.total_pages || 1);
}

function abrirModalCriacao() {
    document.getElementById('chapa-form').reset();
    document.getElementById('chapa-id').value = '';
    document.getElementById('chapa-modal-label').textContent = 'Nova chapa de corte';
    chapaModal.show();
}

function abrirModalEdicao(btn) {
    document.getElementById('chapa-form').reset();
    document.getElementById('chapa-id').value = btn.dataset.id;
    document.getElementById('chapa-como-aparece').value = btn.dataset.comoAparece || '';
    document.getElementById('chapa-espessura').value = btn.dataset.espessura || '';
    document.getElementById('chapa-codigo').value = btn.dataset.codigo || '';
    document.getElementById('chapa-modal-label').textContent = 'Editar chapa de corte';
    chapaModal.show();
}

function abrirModalStatus(btn) {
    const isAtivo = btn.dataset.ativo === 'true';
    document.getElementById('toggle-chapa-id').value = btn.dataset.id;
    document.getElementById('toggle-chapa-modal-label').textContent = isAtivo ? 'Inativar chapa' : 'Ativar chapa';
    document.getElementById('toggle-chapa-texto').innerHTML = isAtivo
        ? `Confirma a <strong>inativacao</strong> da chapa <strong>${escapeHtml(btn.dataset.nome)}</strong>?`
        : `Confirma a <strong>ativacao</strong> da chapa <strong>${escapeHtml(btn.dataset.nome)}</strong>?`;
    document.getElementById('toggle-chapa-btn').className = `btn btn-sm ${isAtivo ? 'btn-warning' : 'btn-success'}`;
    document.getElementById('toggle-chapa-btn').textContent = isAtivo ? 'Inativar' : 'Ativar';
    toggleModal.show();
}

function normalizarEspessuraInput(input) {
    let value = input.value.replace(/[^0-9,.]/g, '');
    const decimalIndex = value.search(/[,.]/);

    if (decimalIndex >= 0) {
        const beforeDecimal = value.slice(0, decimalIndex + 1);
        const afterDecimal = value.slice(decimalIndex + 1).replace(/[,.]/g, '');
        value = beforeDecimal + afterDecimal;
    }

    input.value = value;
}

function bindEvents() {
    document.getElementById('btn-add-chapa').addEventListener('click', abrirModalCriacao);

    document.getElementById('chapa-espessura').addEventListener('input', event => {
        normalizarEspessuraInput(event.target);
    });

    document.getElementById('apply-filters-chapa').addEventListener('click', () => {
        state.search = document.getElementById('f-search-chapa').value.trim();
        state.ativo = document.getElementById('f-ativo-chapa').value;
        state.currentPage = 1;
        carregarTabela();
    });

    document.getElementById('clear-filters-chapa').addEventListener('click', () => {
        document.getElementById('f-search-chapa').value = '';
        document.getElementById('f-ativo-chapa').value = 'true';
        state.search = '';
        state.ativo = 'true';
        state.currentPage = 1;
        carregarTabela();
    });

    document.getElementById('f-search-chapa').addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            document.getElementById('apply-filters-chapa').click();
        }
    });

    document.getElementById('page-size-chapa').addEventListener('change', event => {
        state.rowsPerPage = Number(event.target.value);
        state.currentPage = 1;
        carregarTabela();
    });

    document.getElementById('chapas-corte-pagination').addEventListener('click', event => {
        const btn = event.target.closest('[data-page]');
        if (!btn || btn.disabled) return;
        state.currentPage = Number(btn.dataset.page);
        carregarTabela();
    });

    document.getElementById('chapas-corte-body').addEventListener('click', event => {
        const editBtn = event.target.closest('.btn-edit-chapa');
        const toggleBtn = event.target.closest('.btn-toggle-chapa');
        if (editBtn) abrirModalEdicao(editBtn);
        if (toggleBtn) abrirModalStatus(toggleBtn);
    });
}

function bindForms() {
    document.getElementById('chapa-form').addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.target;
        const formData = Object.fromEntries(new FormData(form).entries());
        const isEdit = Boolean(formData.id);
        const btn = document.getElementById('save-chapa-btn');
        btn.disabled = true;

        try {
            const response = await fetch(apiUrl, {
                method: isEdit ? 'PATCH' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(form),
                },
                body: JSON.stringify(formData),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Nao foi possivel salvar a chapa.');

            chapaModal.hide();
            await carregarTabela();
            showToast('success', 'Salvo', data.success || 'Chapa salva com sucesso.');
        } catch (error) {
            showToast('error', 'Erro', error.message);
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById('toggle-chapa-form').addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.target;
        const formData = Object.fromEntries(new FormData(form).entries());
        const btn = document.getElementById('toggle-chapa-btn');
        btn.disabled = true;

        try {
            const response = await fetch(apiUrl, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(form),
                },
                body: JSON.stringify({ id: formData.id }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Nao foi possivel alterar o status.');

            toggleModal.hide();
            await carregarTabela();
            showToast('success', 'Atualizado', data.success || 'Status atualizado com sucesso.');
        } catch (error) {
            showToast('error', 'Erro', error.message);
        } finally {
            btn.disabled = false;
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    bindForms();
    carregarTabela();
});
