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
        hasNext: false,
        hasPrevious: false,
        filters: { search: '', carreta: '' },
        deleteId: null,
    };

    const tbody = document.getElementById('table-body');
    const summaryEl = document.getElementById('pagination-summary');
    const totalIndicator = document.getElementById('total-indicator');
    const pageSizeSelect = document.getElementById('page-size-select');
    const prevBtn = document.getElementById('prev-page-btn');
    const nextBtn = document.getElementById('next-page-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const searchInput = document.getElementById('f-search');
    const carretaInput = document.getElementById('f-carreta');
    const carretaDatalist = document.getElementById('carretas-datalist');
    const applyFiltersBtn = document.getElementById('apply-filters-btn');
    const clearFiltersBtn = document.getElementById('clear-filters-btn');

    // Modal criar/editar
    const modalEl = document.getElementById('carreta-explodida-modal');
    const modal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl) : null;
    const modalLabel = document.getElementById('carreta-explodida-modal-label');
    const saveModalBtn = document.getElementById('save-modal-btn');
    const clearModalBtn = document.getElementById('clear-modal-btn');
    const openCreateBtn = document.getElementById('open-create-modal-btn');

    // Modal exclusao
    const deleteModalEl = document.getElementById('confirm-delete-modal');
    const deleteModal = window.bootstrap && deleteModalEl ? new bootstrap.Modal(deleteModalEl) : null;
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    const deleteInfo = document.getElementById('delete-info');

    function getField(campo) {
        return document.getElementById(`m-${campo}`);
    }

    function clearModalForm() {
        document.getElementById('m-id').value = '';
        CAMPOS.forEach(c => { const el = getField(c); if (el) el.value = ''; });
    }

    function fillModalForm(item) {
        document.getElementById('m-id').value = item.id;
        CAMPOS.forEach(c => { const el = getField(c); if (el) el.value = item[c] ?? ''; });
    }

    function setEditMode(isEdit) {
        modalLabel.textContent = isEdit ? 'Editar registro' : 'Novo registro';
        saveModalBtn.innerHTML = isEdit
            ? '<i class="bi bi-save me-1"></i>Salvar alteracoes'
            : '<i class="bi bi-plus-lg me-1"></i>Criar registro';
    }

    function showAlert(type, message) {
        if (window.Swal) {
            Swal.fire({ icon: type, title: type === 'success' ? 'Sucesso' : 'Erro', text: message, timer: 2400, showConfirmButton: false });
        } else {
            alert(message);
        }
    }

    function setLoading(isLoading) {
        refreshBtn.disabled = isLoading;
        prevBtn.disabled = isLoading || !state.hasPrevious;
        nextBtn.disabled = isLoading || !state.hasNext;
        if (isLoading) {
            tbody.innerHTML = `<tr><td colspan="10"><div class="loading-ghost w-100"></div></td></tr>`;
        }
    }

    function renderRows(items) {
        if (!items.length) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-4">Nenhum registro encontrado.</td></tr>`;
            return;
        }
        tbody.innerHTML = '';
        items.forEach(item => tbody.appendChild(buildRow(item)));
    }

    function cell(text) {
        const td = document.createElement('td');
        td.textContent = text ?? '-';
        return td;
    }

    function buildRow(item) {
        const tr = document.createElement('tr');
        tr.dataset.id = item.id;

        tr.appendChild(cell(item.id));
        tr.appendChild(cell(item.codigo_peca));
        tr.appendChild(cell(item.descricao_peca));
        tr.appendChild(cell(item.carreta));
        tr.appendChild(cell(item.grupo1));
        tr.appendChild(cell(item.grupo2));
        tr.appendChild(cell(item.grupo));
        tr.appendChild(cell(item.primeiro_processo));
        tr.appendChild(cell(item.segundo_processo));

        const actionTd = document.createElement('td');
        actionTd.className = 'text-center';

        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-outline-primary btn-sm me-1';
        editBtn.innerHTML = '<i class="bi bi-pencil"></i>';
        editBtn.title = 'Editar';
        editBtn.addEventListener('click', () => {
            fillModalForm(item);
            setEditMode(true);
            if (modal) modal.show();
        });

        const delBtn = document.createElement('button');
        delBtn.className = 'btn btn-outline-danger btn-sm';
        delBtn.innerHTML = '<i class="bi bi-trash"></i>';
        delBtn.title = 'Excluir';
        delBtn.addEventListener('click', () => {
            state.deleteId = item.id;
            deleteInfo.textContent = `ID ${item.id} — ${item.codigo_peca ?? ''} ${item.descricao_peca ?? ''}`.trim();
            if (deleteModal) deleteModal.show();
        });

        actionTd.appendChild(editBtn);
        actionTd.appendChild(delBtn);
        tr.appendChild(actionTd);
        return tr;
    }

    function collectModalPayload() {
        const payload = {};
        const idVal = document.getElementById('m-id').value;
        if (idVal) payload.id = Number(idVal);
        CAMPOS.forEach(c => {
            const el = getField(c);
            payload[c] = el ? el.value.trim() : '';
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
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
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
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
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
        carretas.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            carretaDatalist.appendChild(opt);
        });
    }

    async function loadPage() {
        setLoading(true);
        try {
            const params = new URLSearchParams({ page: state.page, page_size: state.pageSize });
            if (state.filters.search) params.append('search', state.filters.search);
            if (state.filters.carreta) params.append('carreta', state.filters.carreta);

            const response = await fetch(`${API_URL}?${params.toString()}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel carregar os dados.');
            }
            const data = await response.json();
            state.hasNext = data.has_next;
            state.hasPrevious = data.has_previous;

            renderRows(data.results || []);
            updateMeta(data);

            if (data.meta && data.meta.carretas) {
                populateCarretaFilter(data.meta.carretas);
            }
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-danger text-center py-4">${error.message}</td></tr>`;
        } finally {
            setLoading(false);
        }
    }

    function updateMeta(data) {
        summaryEl.textContent = `Pagina ${data.page} de ${data.total_pages || 1}`;
        totalIndicator.textContent = `Total: ${data.total_items || 0} registros`;
        prevBtn.disabled = !state.hasPrevious;
        nextBtn.disabled = !state.hasNext;
    }

    pageSizeSelect.addEventListener('change', () => { state.pageSize = Number(pageSizeSelect.value); state.page = 1; loadPage(); });
    prevBtn.addEventListener('click', () => { if (!state.hasPrevious) return; state.page -= 1; loadPage(); });
    nextBtn.addEventListener('click', () => { if (!state.hasNext) return; state.page += 1; loadPage(); });
    refreshBtn.addEventListener('click', () => loadPage());

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
