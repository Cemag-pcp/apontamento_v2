document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('carretas-explodidas-app');
    if (!app) return;

    const API_URL = app.dataset.apiUrl;
    const csrftoken = (() => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; csrftoken=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    })();

    const CAMPOS = [
        'grupo1', 'grupo2', 'codigo_peca', 'descricao_peca',
        'mp_peca', 'total_peca', 'conjunto_peca',
        'primeiro_processo', 'segundo_processo', 'carreta', 'grupo', 'peso',
    ];

    const state = {
        page: 1,
        pageSize: 50,
        filters: { search: '', carreta: '' },
        deleteId: null,
    };

    const tbody = document.getElementById('table-body');
    const summaryEl = document.getElementById('pagination-summary');
    const pageSizeSelect = document.getElementById('page-size-select');
    const paginationEl = document.getElementById('carretas-pagination');
    const searchInput = document.getElementById('f-search');
    const carretaInput = document.getElementById('f-carreta');
    const carretaDatalist = document.getElementById('carretas-datalist');
    const applyFiltersBtn = document.getElementById('apply-filters-btn');
    const clearFiltersBtn = document.getElementById('clear-filters-btn');

    const modalEl = document.getElementById('carreta-explodida-modal');
    const modal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl) : null;
    const modalLabel = document.getElementById('carreta-explodida-modal-label');
    const saveModalBtn = document.getElementById('save-modal-btn');
    const clearModalBtn = document.getElementById('clear-modal-btn');
    const openCreateBtn = document.getElementById('open-create-modal-btn');

    const deleteModalEl = document.getElementById('confirm-delete-modal');
    const deleteModal = window.bootstrap && deleteModalEl ? new bootstrap.Modal(deleteModalEl) : null;
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    const deleteInfo = document.getElementById('delete-info');

    function getField(campo) {
        return document.getElementById(`m-${campo}`);
    }

    function clearModalForm() {
        document.getElementById('m-id').value = '';
        CAMPOS.forEach(campo => {
            const field = getField(campo);
            if (field) field.value = '';
        });
    }

    function fillModalForm(item) {
        document.getElementById('m-id').value = item.id;
        CAMPOS.forEach(campo => {
            const field = getField(campo);
            if (field) field.value = item[campo] ?? '';
        });
    }

    function setEditMode(isEdit) {
        modalLabel.textContent = isEdit ? 'Editar registro' : 'Novo registro';
        saveModalBtn.innerHTML = isEdit
            ? '<i class="bi bi-save me-1"></i>Salvar alteracoes'
            : '<i class="bi bi-plus-lg me-1"></i>Criar registro';
    }

    function showAlert(type, message) {
        if (window.Swal) {
            Swal.fire({
                icon: type,
                title: type === 'success' ? 'Sucesso' : 'Erro',
                text: message,
                timer: 2400,
                showConfirmButton: false,
            });
        } else {
            alert(message);
        }
    }

    function setLoading(isLoading) {
        if (!isLoading) return;

        tbody.innerHTML = `
            <tr>
                <td colspan="10">
                    <div class="loading-ghost w-100"></div>
                </td>
            </tr>
        `;
    }

    function renderRows(items) {
        if (!items.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10">
                        <div class="operators-empty-state">Nenhum registro encontrado.</div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = '';
        items.forEach(item => tbody.appendChild(buildRow(item)));
    }

    function cell(text, className = '') {
        const td = document.createElement('td');
        if (className) td.className = className;
        td.textContent = text ?? '-';
        return td;
    }

    function buildRow(item) {
        const tr = document.createElement('tr');
        tr.dataset.id = item.id;

        tr.appendChild(cell(item.id, 'mono-text'));
        tr.appendChild(cell(item.codigo_peca));
        tr.appendChild(cell(item.descricao_peca));
        tr.appendChild(cell(item.carreta));
        tr.appendChild(cell(item.grupo1));
        tr.appendChild(cell(item.grupo2));
        tr.appendChild(cell(item.grupo));
        tr.appendChild(cell(item.primeiro_processo));
        tr.appendChild(cell(item.segundo_processo));

        const actionTd = document.createElement('td');
        const actionsWrapper = document.createElement('div');
        actionsWrapper.className = 'row-actions';

        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'icon-action-button';
        editBtn.innerHTML = '<i class="bi bi-pencil"></i>';
        editBtn.title = 'Editar';
        editBtn.setAttribute('aria-label', `Editar registro ${item.id}`);
        editBtn.addEventListener('click', () => {
            fillModalForm(item);
            setEditMode(true);
            if (modal) modal.show();
        });

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'icon-action-button danger';
        delBtn.innerHTML = '<i class="bi bi-trash"></i>';
        delBtn.title = 'Excluir';
        delBtn.setAttribute('aria-label', `Excluir registro ${item.id}`);
        delBtn.addEventListener('click', () => {
            state.deleteId = item.id;
            deleteInfo.textContent = `ID ${item.id} - ${item.codigo_peca ?? ''} ${item.descricao_peca ?? ''}`.trim();
            if (deleteModal) deleteModal.show();
        });

        actionsWrapper.appendChild(editBtn);
        actionsWrapper.appendChild(delBtn);
        actionTd.appendChild(actionsWrapper);
        tr.appendChild(actionTd);

        return tr;
    }

    function collectModalPayload() {
        const payload = {};
        const idValue = document.getElementById('m-id').value;
        if (idValue) payload.id = Number(idValue);

        CAMPOS.forEach(campo => {
            const field = getField(campo);
            payload[campo] = field ? field.value.trim() : '';
        });

        return payload;
    }

    async function handleSaveModal() {
        const payload = collectModalPayload();
        const isEdit = !!payload.id;
        const method = isEdit ? 'PATCH' : 'POST';

        saveModalBtn.disabled = true;
        saveModalBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        try {
            const response = await fetch(API_URL, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel salvar.');
            }

            const data = await response.json();
            showAlert('success', data.success || 'Salvo com sucesso.');
            if (modal) modal.hide();
            loadPage();
        } catch (error) {
            showAlert('error', error.message);
        } finally {
            saveModalBtn.disabled = false;
            setEditMode(!!document.getElementById('m-id').value);
        }
    }

    async function handleDelete() {
        if (!state.deleteId) return;

        confirmDeleteBtn.disabled = true;
        confirmDeleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        try {
            const response = await fetch(API_URL, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify({ id: state.deleteId }),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel excluir.');
            }

            const data = await response.json();
            showAlert('success', data.success || 'Excluido com sucesso.');
            if (deleteModal) deleteModal.hide();
            loadPage();
        } catch (error) {
            showAlert('error', error.message);
        } finally {
            confirmDeleteBtn.disabled = false;
            confirmDeleteBtn.innerHTML = 'Excluir';
            state.deleteId = null;
        }
    }

    function populateCarretaFilter(carretas) {
        carretaDatalist.innerHTML = '';
        carretas.forEach(carreta => {
            const option = document.createElement('option');
            option.value = carreta;
            carretaDatalist.appendChild(option);
        });
    }

    async function loadPage() {
        setLoading(true);

        try {
            const params = new URLSearchParams({
                page: state.page,
                page_size: state.pageSize,
            });
            if (state.filters.search) params.append('search', state.filters.search);
            if (state.filters.carreta) params.append('carreta', state.filters.carreta);

            const response = await fetch(`${API_URL}?${params.toString()}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel carregar os dados.');
            }

            const data = await response.json();
            renderRows(data.results || []);
            updateMeta(data);

            if (data.meta && data.meta.carretas) {
                populateCarretaFilter(data.meta.carretas);
            }
        } catch (error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10">
                        <div class="operators-empty-state text-danger">${error.message}</div>
                    </td>
                </tr>
            `;
        }
    }

    function updateMeta(data) {
        const total = Number(data.total_items || 0);
        const currentPage = Number(data.page || 1);
        const pageSize = Number(data.page_size || state.pageSize || 10);
        const totalPages = Math.max(1, Number(data.total_pages || 1));
        const start = total === 0 ? 0 : ((currentPage - 1) * pageSize) + 1;
        const end = total === 0 ? 0 : Math.min(currentPage * pageSize, total);

        summaryEl.textContent = `${start}-${end} of ${total}`;
        renderPagination(currentPage, totalPages);
    }

    function renderPagination(currentPage, totalPages) {
        if (!paginationEl) return;

        const pages = [1];
        for (let page = currentPage - 1; page <= currentPage + 1; page += 1) {
            if (page > 1 && page < totalPages) pages.push(page);
        }
        if (totalPages > 1) pages.push(totalPages);

        const dedupedPages = [...new Set(pages)].sort((a, b) => a - b);
        const items = [];

        items.push(`
            <button class="pagination-button" data-page="${Math.max(1, currentPage - 1)}" ${currentPage === 1 ? 'disabled' : ''} aria-label="Pagina anterior">
                <i class="bi bi-chevron-left"></i>
            </button>
        `);

        dedupedPages.forEach((page, index) => {
            const previous = dedupedPages[index - 1];
            if (previous && page - previous > 1) {
                items.push('<span class="pagination-button" aria-hidden="true">...</span>');
            }

            items.push(`
                <button class="pagination-button ${page === currentPage ? 'is-active' : ''}" data-page="${page}">
                    ${page}
                </button>
            `);
        });

        items.push(`
            <button class="pagination-button" data-page="${Math.min(totalPages, currentPage + 1)}" ${currentPage === totalPages ? 'disabled' : ''} aria-label="Proxima pagina">
                <i class="bi bi-chevron-right"></i>
            </button>
        `);

        paginationEl.innerHTML = items.join('');
    }

    pageSizeSelect.addEventListener('change', () => {
        state.pageSize = Number(pageSizeSelect.value);
        state.page = 1;
        loadPage();
    });

    paginationEl?.addEventListener('click', event => {
        const button = event.target.closest('[data-page]');
        if (!button || button.disabled) return;
        state.page = Number(button.dataset.page);
        loadPage();
    });

    applyFiltersBtn.addEventListener('click', () => {
        state.page = 1;
        state.filters.search = searchInput.value.trim();
        state.filters.carreta = carretaInput.value.trim();
        loadPage();
    });

    clearFiltersBtn.addEventListener('click', () => {
        searchInput.value = '';
        carretaInput.value = '';
        state.page = 1;
        state.filters.search = '';
        state.filters.carreta = '';
        loadPage();
    });

    openCreateBtn.addEventListener('click', () => {
        clearModalForm();
        setEditMode(false);
    });

    clearModalBtn.addEventListener('click', () => {
        clearModalForm();
        setEditMode(false);
    });

    if (modalEl) {
        modalEl.addEventListener('hidden.bs.modal', () => {
            clearModalForm();
            setEditMode(false);
        });
    }

    saveModalBtn.addEventListener('click', handleSaveModal);
    confirmDeleteBtn.addEventListener('click', handleDelete);

    loadPage();
});
