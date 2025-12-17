document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('pecas-usinagem-app');
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
            ordem: '',
            peca: '',
        },
    };

    const tbody = document.getElementById('pecas-usinagem-body');
    const summaryEl = document.getElementById('pagination-summary-usinagem');
    const totalIndicator = document.getElementById('total-indicator-usinagem');
    const pageSizeSelect = document.getElementById('page-size-usinagem');
    const prevBtn = document.getElementById('prev-page-usinagem');
    const nextBtn = document.getElementById('next-page-usinagem');
    const refreshBtn = document.getElementById('refresh-pecas-usinagem-btn');
    const ordemInput = document.getElementById('f-ordem-usinagem');
    const pecaInput = document.getElementById('f-peca-usinagem');
    const applyFiltersBtn = document.getElementById('apply-filters-usinagem');
    const clearFiltersBtn = document.getElementById('clear-filters-usinagem');

    function setLoading(isLoading) {
        refreshBtn.disabled = isLoading;
        prevBtn.disabled = isLoading || !state.hasPrevious;
        nextBtn.disabled = isLoading || !state.hasNext;
        if (isLoading) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9">
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
                    <td colspan="9" class="text-center text-muted py-4">
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
        tr.appendChild(textCell(item.ordem_numero ?? '-'));
        tr.appendChild(textCell(item.grupo_maquina ?? '-'));
        tr.appendChild(textCell(item.peca_display ?? '-'));
        tr.appendChild(numberCell(item.qtd_planejada));
        tr.appendChild(editCell('qtd_boa', item.qtd_boa));
        tr.appendChild(editCell('qtd_morta', item.qtd_morta));
        tr.appendChild(textCell(item.data ?? '-'));

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
        td.textContent = content;
        return td;
    }

    function numberCell(value) {
        const td = document.createElement('td');
        td.className = 'text-end';
        td.textContent = value ?? '-';
        return td;
    }

    function editCell(name, value) {
        const td = document.createElement('td');
        td.className = 'text-end';
        const input = document.createElement('input');
        input.className = 'form-control form-control-sm text-end';
        input.name = name;
        input.type = 'number';
        input.step = '0.01';
        input.value = value ?? '';
        td.appendChild(input);
        return td;
    }

    async function handleSave(row, button) {
        const id = row.dataset.id;
        const payload = { id: Number(id) };
        const fields = ['qtd_boa', 'qtd_morta'];

        fields.forEach(field => {
            const input = row.querySelector(`[name="${field}"]`);
            if (!input) return;
            if (input.value !== '') payload[field] = parseFloat(input.value);
        });

        if (Object.keys(payload).length === 1) {
            showAlert('error', 'Informe ao menos um campo para salvar.');
            return;
        }

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
                throw new Error(err.error || 'Não foi possível salvar.');
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

    async function loadPage() {
        setLoading(true);
        try {
            const params = new URLSearchParams({
                page: state.page,
                page_size: state.pageSize,
            });

            Object.entries(state.filters).forEach(([key, value]) => {
                if (value !== '' && value !== null && value !== undefined) {
                    params.append(key, value);
                }
            });

            const response = await fetch(`${API_URL}?${params.toString()}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Não foi possível carregar os dados.');
            }

            const data = await response.json();
            state.hasNext = data.has_next;
            state.hasPrevious = data.has_previous;

            renderRows(data.results || []);
            updateMeta(data);
        } catch (error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-danger text-center py-4">
                        ${error.message}
                    </td>
                </tr>
            `;
        } finally {
            setLoading(false);
        }
    }

    function updateMeta(meta) {
        summaryEl.textContent = `Página ${meta.page} de ${meta.total_pages || 1}`;
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

    function applyFilters() {
        state.page = 1;
        state.filters = {
            ordem: ordemInput.value.trim(),
            peca: pecaInput.value.trim(),
        };
        loadPage();
    }

    applyFiltersBtn.addEventListener('click', applyFilters);

    clearFiltersBtn.addEventListener('click', () => {
        ordemInput.value = '';
        pecaInput.value = '';
        applyFilters();
    });

    loadPage();
});
