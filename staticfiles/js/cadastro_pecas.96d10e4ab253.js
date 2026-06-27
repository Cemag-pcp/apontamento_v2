document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('cadastro-pecas-estamparia-app');
    if (!app) return;

    const API_URL = app.dataset.apiUrl;
    const defaultSetorId = app.dataset.defaultSetorId;
    const csrftoken = (() => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; csrftoken=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    })();

    const state = {
        page: 1,
        pageSize: 10,
        filters: {
            search: '',
            setor: defaultSetorId || '',
        },
        meta: {
            conjuntos: [],
            maquinas: [],
            setores: [],
        },
    };

    const tbody = document.getElementById('pecas-cadastro-body');
    const summaryEl = document.getElementById('pagination-summary-cadastro');
    const pageSizeSelect = document.getElementById('page-size-cadastro');
    const paginationEl = document.getElementById('cadastro-pagination');
    const searchInput = document.getElementById('f-search');
    const setorFilter = document.getElementById('f-setor');
    const applyFiltersBtn = document.getElementById('apply-filters-cadastro');
    const clearFiltersBtn = document.getElementById('clear-filters-cadastro');

    const createBtn = document.getElementById('create-peca-btn');
    const clearFormBtn = document.getElementById('clear-form-btn');
    const cCodigo = document.getElementById('c-codigo');
    const cDescricao = document.getElementById('c-descricao');
    const cMp = document.getElementById('c-mp');
    const cComprimento = document.getElementById('c-comprimento');
    const cApelido = document.getElementById('c-apelido');
    const cConjunto = document.getElementById('c-conjunto');
    const cProcesso = document.getElementById('c-processo-1');
    const cSetores = document.getElementById('c-setores');
    const modalEl = document.getElementById('cadastro-peca-modal');
    const modal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl) : null;

    enableClickToggle(cSetores);

    function setLoading(isLoading) {
        if (!isLoading) return;

        tbody.innerHTML = `
            <tr>
                <td colspan="11">
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

    function setSelectOptions(selectEl, options, placeholder) {
        selectEl.innerHTML = '';
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = placeholder;
        selectEl.appendChild(emptyOption);

        options.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.id;
            opt.textContent = option.label;
            selectEl.appendChild(opt);
        });
    }

    function setMultiSelectOptions(selectEl, options) {
        selectEl.innerHTML = '';
        options.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.id;
            opt.textContent = option.label;
            selectEl.appendChild(opt);
        });
    }

    function buildSelect(name, options, selectedId, placeholder) {
        const select = document.createElement('select');
        select.className = 'form-select form-select-sm';
        select.name = name;

        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = placeholder;
        select.appendChild(emptyOption);

        options.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.id;
            opt.textContent = option.label;
            if (selectedId && String(option.id) === String(selectedId)) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });

        return select;
    }

    function buildMultiSelect(name, options, selectedIds) {
        const select = document.createElement('select');
        select.className = 'form-select form-select-sm';
        select.name = name;
        select.multiple = true;
        enableClickToggle(select);

        const selectedSet = new Set((selectedIds || []).map(String));
        options.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.id;
            opt.textContent = option.label;
            if (selectedSet.has(String(option.id))) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });

        return select;
    }

    function enableClickToggle(selectEl) {
        if (!selectEl || selectEl.dataset.clickToggle === 'true') return;

        selectEl.dataset.clickToggle = 'true';
        selectEl.addEventListener('mousedown', event => {
            if (event.target.tagName !== 'OPTION') return;
            event.preventDefault();
            const option = event.target;
            option.selected = !option.selected;
            selectEl.dispatchEvent(new Event('change', { bubbles: true }));
        });
    }

    function renderRows(items) {
        if (!items.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="11">
                        <div class="operators-empty-state">Nenhuma peça encontrada.</div>
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
        tr.appendChild(editCell('materia_prima', item.materia_prima));
        tr.appendChild(editCell('comprimento', item.comprimento, 'number', true));
        tr.appendChild(editCell('apelido', item.apelido));

        const setorTd = document.createElement('td');
        setorTd.appendChild(buildMultiSelect('setor_ids', state.meta.setores, item.setor_ids));
        tr.appendChild(setorTd);

        const conjuntoTd = document.createElement('td');
        conjuntoTd.appendChild(buildSelect('conjunto_id', state.meta.conjuntos, item.conjunto_id, 'Sem conjunto'));
        tr.appendChild(conjuntoTd);

        const processoTd = document.createElement('td');
        processoTd.appendChild(buildSelect('processo_1_id', state.meta.maquinas, item.processo_1_id, 'Sem processo'));
        tr.appendChild(processoTd);

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
        saveBtn.setAttribute('aria-label', `Salvar peça ${item.codigo || item.id}`);
        saveBtn.innerHTML = '<i class="bi bi-save"></i>';
        saveBtn.addEventListener('click', () => handleSave(tr, saveBtn));

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = `icon-action-button${item.ativo ? ' danger' : ''}`;
        toggleBtn.title = item.ativo ? 'Desabilitar' : 'Ativar';
        toggleBtn.setAttribute('aria-label', `${item.ativo ? 'Desabilitar' : 'Ativar'} peça ${item.codigo || item.id}`);
        toggleBtn.innerHTML = item.ativo
            ? '<i class="bi bi-slash-circle"></i>'
            : '<i class="bi bi-check-circle"></i>';
        toggleBtn.addEventListener('click', () => handleToggleAtivo(item.id, toggleBtn, statusTd));

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
        td.textContent = content ?? '-';
        return td;
    }

    function editCell(name, value, type = 'text', numeric = false) {
        const td = document.createElement('td');
        const input = document.createElement('input');
        input.className = `form-control form-control-sm${numeric ? ' text-end' : ''}`;
        input.name = name;
        input.type = type;
        if (type === 'number') input.step = '0.01';
        input.value = value ?? '';
        td.appendChild(input);
        return td;
    }

    function collectRowPayload(row) {
        const payload = { id: Number(row.dataset.id) };
        const fields = ['codigo', 'descricao', 'materia_prima', 'comprimento', 'apelido'];

        fields.forEach(field => {
            const input = row.querySelector(`[name="${field}"]`);
            if (!input) return;
            payload[field] = input.value;
        });

        const conjuntoSelect = row.querySelector('[name="conjunto_id"]');
        const processoSelect = row.querySelector('[name="processo_1_id"]');
        const setorSelect = row.querySelector('[name="setor_ids"]');

        payload.conjunto_id = conjuntoSelect ? conjuntoSelect.value : '';
        payload.processo_1_id = processoSelect ? processoSelect.value : '';
        payload.setor_ids = setorSelect ? Array.from(setorSelect.selectedOptions).map(option => Number(option.value)) : [];

        if (payload.comprimento !== '') {
            payload.comprimento = parseFloat(payload.comprimento);
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

    async function handleToggleAtivo(id, button, statusTd) {
        button.disabled = true;
        const originalHtml = button.innerHTML;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';

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
            const ativo = data.ativo;

            statusTd.innerHTML = buildStatusMarkup(ativo);
            button.className = `icon-action-button${ativo ? ' danger' : ''}`;
            button.title = ativo ? 'Desabilitar' : 'Ativar';
            button.setAttribute('aria-label', `${ativo ? 'Desabilitar' : 'Ativar'} peça ${id}`);
            button.innerHTML = ativo
                ? '<i class="bi bi-slash-circle"></i>'
                : '<i class="bi bi-check-circle"></i>';

            showAlert('success', data.success || 'Status atualizado.');
        } catch (error) {
            showAlert('error', error.message);
            button.innerHTML = originalHtml;
        } finally {
            button.disabled = false;
        }
    }

    async function handleCreate() {
        const payload = {
            codigo: cCodigo.value.trim(),
            descricao: cDescricao.value.trim(),
            materia_prima: cMp.value.trim(),
            comprimento: cComprimento.value,
            apelido: cApelido.value.trim(),
            conjunto_id: cConjunto.value,
            processo_1_id: cProcesso.value,
            setor_ids: Array.from(cSetores.selectedOptions).map(option => Number(option.value)),
        };

        if (!payload.codigo) {
            showAlert('error', 'Codigo e obrigatorio.');
            return;
        }

        if (!payload.setor_ids.length) {
            showAlert('error', 'Selecione ao menos um setor.');
            return;
        }

        if (payload.comprimento !== '') {
            payload.comprimento = parseFloat(payload.comprimento);
        }

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

            showAlert('success', 'Peça criada com sucesso.');
            clearForm();
            if (modal) {
                modal.hide();
            }
            loadPage();
        } catch (error) {
            showAlert('error', error.message);
        } finally {
            createBtn.disabled = false;
            createBtn.innerHTML = '<i class="bi bi-plus-lg me-1"></i>Criar peça';
        }
    }

    function clearForm() {
        cCodigo.value = '';
        cDescricao.value = '';
        cMp.value = '';
        cComprimento.value = '';
        cApelido.value = '';
        cConjunto.value = '';
        cProcesso.value = '';
        Array.from(cSetores.options).forEach(option => {
            option.selected = false;
        });
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
            if (state.filters.setor) {
                params.append('setor', state.filters.setor);
            }

            const response = await fetch(`${API_URL}?${params.toString()}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Nao foi possivel carregar os dados.');
            }

            const data = await response.json();

            if (data.meta) {
                state.meta = data.meta;
                setSelectOptions(cConjunto, state.meta.conjuntos, 'Sem conjunto');
                setSelectOptions(cProcesso, state.meta.maquinas, 'Sem processo');
                setMultiSelectOptions(cSetores, state.meta.setores);
                enableClickToggle(cSetores);

                const selectedSetor = state.filters.setor || setorFilter.value;
                setSelectOptions(setorFilter, state.meta.setores, 'Todos');
                setorFilter.value = selectedSetor;
            }

            renderRows(data.results || []);
            updateMeta(data);
        } catch (error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="11">
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
        state.filters.setor = setorFilter.value;
        loadPage();
    });

    clearFiltersBtn.addEventListener('click', () => {
        searchInput.value = '';
        setorFilter.value = '';
        state.page = 1;
        state.filters.search = '';
        state.filters.setor = '';
        loadPage();
    });

    createBtn.addEventListener('click', handleCreate);
    clearFormBtn.addEventListener('click', clearForm);

    if (modalEl) {
        modalEl.addEventListener('hidden.bs.modal', clearForm);
    }

    loadPage();
});
