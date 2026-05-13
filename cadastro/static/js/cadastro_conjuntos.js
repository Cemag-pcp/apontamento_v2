document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('cadastro-conjuntos-app');
    if (!app) return;

    const API_URL = app.dataset.apiUrl;
    const csrftoken = (() => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; csrftoken=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    })();

    const state = {
        page: 1,
        pageSize: 50,
        filters: {
            search: '',
        },
    };

    const tbody = document.getElementById('conjuntos-cadastro-body');
    const summaryEl = document.getElementById('pagination-summary-cadastro');
    const pageSizeSelect = document.getElementById('page-size-cadastro');
    const paginationEl = document.getElementById('cadastro-pagination');
    const searchInput = document.getElementById('f-search');
    const applyFiltersBtn = document.getElementById('apply-filters-cadastro');
    const clearFiltersBtn = document.getElementById('clear-filters-cadastro');

    const createBtn = document.getElementById('create-conjunto-btn');
    const clearFormBtn = document.getElementById('clear-form-btn');
    const cCodigo = document.getElementById('c-codigo');
    const cDescricao = document.getElementById('c-descricao');
    const cQuantidade = document.getElementById('c-quantidade');
    const modalEl = document.getElementById('cadastro-conjunto-modal');
    const modal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl) : null;
    const confirmStatusModalEl = document.getElementById('confirmar-status-conjunto-modal');
    const confirmStatusText = document.getElementById('confirmar-status-conjunto-texto');
    const confirmStatusBtn = document.getElementById('confirmar-status-conjunto-btn');
    const confirmStatusModal = window.bootstrap && confirmStatusModalEl ? new bootstrap.Modal(confirmStatusModalEl) : null;
    let pendingStatusChange = null;

    function setLoading(isLoading) {
        if (!isLoading) return;

        tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    <div class="loading-ghost w-100"></div>
                </td>
            </tr>
        `;
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

    function renderRows(items) {
        if (!items.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="operators-empty-state">Nenhum conjunto encontrado.</div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = '';
        items.forEach(item => tbody.appendChild(buildRow(item)));
    }

    function buildRow(item) {
        const tr = document.createElement('tr');
        tr.dataset.id = item.id;

        tr.appendChild(textCell(item.id));
        tr.appendChild(editCell('codigo', item.codigo));
        tr.appendChild(editCell('descricao', item.descricao));
        tr.appendChild(editCell('quantidade', item.quantidade, 'number', true));

        const statusTd = document.createElement('td');
        statusTd.innerHTML = buildStatusMarkup(item.ativo);
        tr.appendChild(statusTd);

        const actionTd = document.createElement('td');
        const actionsWrapper = document.createElement('div');
        actionsWrapper.className = 'row-actions';

        const saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'icon-action-button';
        saveBtn.title = 'Salvar';
        saveBtn.setAttribute('aria-label', `Salvar conjunto ${item.codigo || item.id}`);
        saveBtn.innerHTML = '<i class="bi bi-save"></i>';
        saveBtn.addEventListener('click', () => handleSave(tr, saveBtn));

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = `icon-action-button${item.ativo ? ' danger' : ''}`;
        toggleBtn.title = item.ativo ? 'Inativar' : 'Ativar';
        toggleBtn.setAttribute('aria-label', `${item.ativo ? 'Inativar' : 'Ativar'} conjunto ${item.codigo || item.id}`);
        toggleBtn.innerHTML = item.ativo
            ? '<i class="bi bi-slash-circle"></i>'
            : '<i class="bi bi-check-circle"></i>';
        toggleBtn.addEventListener('click', () => openStatusConfirm(item, toggleBtn, statusTd));

        actionsWrapper.appendChild(saveBtn);
        actionsWrapper.appendChild(toggleBtn);
        actionTd.appendChild(actionsWrapper);
        tr.appendChild(actionTd);

        return tr;
    }

    function buildStatusMarkup(isActive) {
        return `
            <span class="status-pill ${isActive ? 'is-active' : 'is-inactive'}">
                <span class="status-dot"></span>
                ${isActive ? 'Ativo' : 'Inativo'}
            </span>
        `;
    }

    function textCell(content) {
        const td = document.createElement('td');
        td.className = 'table-id-cell';
        td.textContent = content ?? '-';
        return td;
    }

    function editCell(name, value, type = 'text', numeric = false) {
        const td = document.createElement('td');
        td.className = numeric ? 'table-input-cell is-numeric' : 'table-input-cell';
        const input = document.createElement('input');
        input.className = `form-control form-control-sm table-inline-input${numeric ? ' text-end' : ''}`;
        input.name = name;
        input.type = type;
        input.value = value ?? '';
        td.appendChild(input);
        return td;
    }

    function collectRowPayload(row) {
        const payload = { id: Number(row.dataset.id) };
        const fields = ['codigo', 'descricao', 'quantidade'];

        fields.forEach(field => {
            const input = row.querySelector(`[name="${field}"]`);
            if (!input) return;
            payload[field] = input.value;
        });

        if (payload.quantidade !== '') {
            payload.quantidade = parseInt(payload.quantidade, 10);
        }

        return payload;
    }

    async function handleSave(row, button) {
        const payload = collectRowPayload(row);
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';

        try {
            const response = await fetch(API_URL, {
                method: 'PATCH',
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
        } catch (error) {
            showAlert('error', error.message);
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="bi bi-save"></i>';
        }
    }

    function openStatusConfirm(item, button, statusTd) {
        pendingStatusChange = {
            id: item.id,
            codigo: item.codigo || item.id,
            button,
            statusTd,
            active: !!item.ativo,
            item,
        };

        if (confirmStatusText) {
            confirmStatusText.textContent = pendingStatusChange.active
                ? `Deseja inativar o conjunto ${pendingStatusChange.codigo}?`
                : `Deseja ativar o conjunto ${pendingStatusChange.codigo}?`;
        }

        if (confirmStatusBtn) {
            confirmStatusBtn.className = `btn btn-sm ${pendingStatusChange.active ? 'btn-danger' : 'btn-primary'}`;
            confirmStatusBtn.textContent = pendingStatusChange.active ? 'Inativar' : 'Ativar';
        }

        if (confirmStatusModal) {
            confirmStatusModal.show();
        }
    }

    async function handleToggleAtivo() {
        if (!pendingStatusChange) return;

        const { id, codigo, button, statusTd, item } = pendingStatusChange;
        button.disabled = true;
        const originalHtml = button.innerHTML;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
        if (confirmStatusBtn) {
            confirmStatusBtn.disabled = true;
        }

        try {
            const response = await fetch(API_URL, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify({ id }),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel alterar o status.');
            }

            const data = await response.json();
            const ativo = !!data.ativo;
            item.ativo = ativo;

            statusTd.innerHTML = buildStatusMarkup(ativo);
            button.className = `icon-action-button${ativo ? ' danger' : ''}`;
            button.title = ativo ? 'Inativar' : 'Ativar';
            button.setAttribute('aria-label', `${ativo ? 'Inativar' : 'Ativar'} conjunto ${codigo}`);
            button.innerHTML = ativo
                ? '<i class="bi bi-slash-circle"></i>'
                : '<i class="bi bi-check-circle"></i>';

            if (confirmStatusModal) {
                confirmStatusModal.hide();
            }
            pendingStatusChange = null;
            showAlert('success', data.success || 'Status atualizado.');
        } catch (error) {
            showAlert('error', error.message);
            button.innerHTML = originalHtml;
        } finally {
            button.disabled = false;
            if (confirmStatusBtn) {
                confirmStatusBtn.disabled = false;
            }
        }
    }

    async function handleCreate() {
        const payload = {
            codigo: cCodigo.value.trim(),
            descricao: cDescricao.value.trim(),
            quantidade: cQuantidade.value,
        };

        if (!payload.codigo) {
            showAlert('error', 'Codigo e obrigatorio.');
            return;
        }

        if (payload.quantidade === '') {
            showAlert('error', 'Quantidade e obrigatoria.');
            return;
        }

        payload.quantidade = parseInt(payload.quantidade, 10);

        createBtn.disabled = true;
        createBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel criar.');
            }

            showAlert('success', 'Conjunto criado com sucesso.');
            clearForm();
            if (modal) {
                modal.hide();
            }
            loadPage();
        } catch (error) {
            showAlert('error', error.message);
        } finally {
            createBtn.disabled = false;
            createBtn.innerHTML = '<i class="bi bi-plus-lg me-1"></i>Criar conjunto';
        }
    }

    function clearForm() {
        cCodigo.value = '';
        cDescricao.value = '';
        cQuantidade.value = '';
    }

    async function loadPage() {
        setLoading(true);

        try {
            const params = new URLSearchParams({
                page: state.page,
                page_size: state.pageSize,
            });

            if (state.filters.search) {
                params.append('search', state.filters.search);
            }

            const response = await fetch(`${API_URL}?${params.toString()}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel carregar os dados.');
            }

            const data = await response.json();
            renderRows(data.results || []);
            updateMeta(data);
        } catch (error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="operators-empty-state text-danger">${error.message}</div>
                    </td>
                </tr>
            `;
        }
    }

    function updateMeta(meta) {
        const total = Number(meta.total_items || 0);
        const currentPage = Number(meta.page || 1);
        const pageSize = Number(meta.page_size || state.pageSize || 10);
        const totalPages = Math.max(1, Number(meta.total_pages || 1));
        const start = total === 0 ? 0 : ((currentPage - 1) * pageSize) + 1;
        const end = total === 0 ? 0 : Math.min(currentPage * pageSize, total);

        summaryEl.textContent = `${start}-${end} of ${total}`;
        renderPagination(currentPage, totalPages);
    }

    function renderPagination(currentPage, totalPages) {
        if (!paginationEl) return;

        const pages = [1];
        for (let page = currentPage - 1; page <= currentPage + 1; page += 1) {
            if (page > 1 && page < totalPages) {
                pages.push(page);
            }
        }
        if (totalPages > 1) {
            pages.push(totalPages);
        }

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
        loadPage();
    });

    clearFiltersBtn.addEventListener('click', () => {
        searchInput.value = '';
        state.page = 1;
        state.filters.search = '';
        loadPage();
    });

    createBtn.addEventListener('click', handleCreate);
    clearFormBtn.addEventListener('click', clearForm);
    confirmStatusBtn?.addEventListener('click', handleToggleAtivo);

    if (modalEl) {
        modalEl.addEventListener('hidden.bs.modal', clearForm);
    }
    if (confirmStatusModalEl) {
        confirmStatusModalEl.addEventListener('hidden.bs.modal', () => {
            pendingStatusChange = null;
            if (confirmStatusBtn) {
                confirmStatusBtn.disabled = false;
            }
        });
    }

    loadPage();
});
