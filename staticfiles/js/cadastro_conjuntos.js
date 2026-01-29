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
        hasNext: false,
        hasPrevious: false,
        filters: {
            search: '',
        },
    };

    const tbody = document.getElementById('conjuntos-cadastro-body');
    const summaryEl = document.getElementById('pagination-summary-cadastro');
    const totalIndicator = document.getElementById('total-indicator-cadastro');
    const pageSizeSelect = document.getElementById('page-size-cadastro');
    const prevBtn = document.getElementById('prev-page-cadastro');
    const nextBtn = document.getElementById('next-page-cadastro');
    const refreshBtn = document.getElementById('refresh-conjuntos-cadastro-btn');
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

    function setLoading(isLoading) {
        refreshBtn.disabled = isLoading;
        prevBtn.disabled = isLoading || !state.hasPrevious;
        nextBtn.disabled = isLoading || !state.hasNext;
        if (isLoading) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="loading-ghost w-100"></div>
                    </td>
                </tr>
            `;
        }
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
                    <td colspan="5" class="text-center text-muted py-4">
                        Nenhum registro encontrado.
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

        const actionTd = document.createElement('td');
        actionTd.className = 'text-center';

        const saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn-primary btn-sm';
        saveBtn.innerHTML = '<i class="bi bi-save me-1"></i>Salvar';
        saveBtn.addEventListener('click', () => handleSave(tr, saveBtn));

        actionTd.appendChild(saveBtn);
        tr.appendChild(actionTd);

        return tr;
    }

    function textCell(content) {
        const td = document.createElement('td');
        td.textContent = content ?? '-';
        return td;
    }

    function editCell(name, value, type = 'text', numeric = false) {
        const td = document.createElement('td');
        const input = document.createElement('input');
        input.className = `form-control form-control-sm${numeric ? ' text-end' : ''}`;
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
            button.innerHTML = '<i class="bi bi-save me-1"></i>Salvar';
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
            state.hasNext = data.has_next;
            state.hasPrevious = data.has_previous;

            renderRows(data.results || []);
            updateMeta(data);
        } catch (error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-danger text-center py-4">
                        ${error.message}
                    </td>
                </tr>
            `;
        } finally {
            setLoading(false);
        }
    }

    function updateMeta(meta) {
        summaryEl.textContent = `Pagina ${meta.page} de ${meta.total_pages || 1}`;
        totalIndicator.textContent = `Total: ${meta.total_items || 0} registros`;
        prevBtn.disabled = !state.hasPrevious;
        nextBtn.disabled = !state.hasNext;
    }

    pageSizeSelect.addEventListener('change', () => {
        state.pageSize = Number(pageSizeSelect.value);
        state.page = 1;
        loadPage();
    });

    prevBtn.addEventListener('click', () => {
        if (!state.hasPrevious) return;
        state.page -= 1;
        loadPage();
    });

    nextBtn.addEventListener('click', () => {
        if (!state.hasNext) return;
        state.page += 1;
        loadPage();
    });

    refreshBtn.addEventListener('click', () => loadPage());
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
    if (modalEl) {
        modalEl.addEventListener('hidden.bs.modal', clearForm);
    }

    loadPage();
});
