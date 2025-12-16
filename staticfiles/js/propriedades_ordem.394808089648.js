document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('propriedades-app');
    if (!app) return;

    const API_URL = app.dataset.apiUrl;
    const csrftoken = (() => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; csrftoken=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    })();

    const state = {
        page: 1,
        pageSize: 50,
        hasNext: false,
        hasPrevious: false,
        filters: {
            ordem: '',
            mp_codigo: '',
            descricao_mp: '',
            tipo_chapa: '',
            retalho: '',
        },
    };

    const tbody = document.getElementById('propriedades-body');
    const summaryEl = document.getElementById('pagination-summary');
    const totalIndicator = document.getElementById('total-indicator');
    const pageSizeSelect = document.getElementById('page-size');
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    const refreshBtn = document.getElementById('refresh-btn');
    const ordemInput = document.getElementById('f-ordem');
    // const mpCodigoInput = document.getElementById('f-mp-codigo');
    const descricaoInput = document.getElementById('f-descricao');
    const tipoChapaSelect = document.getElementById('f-tipo-chapa');
    const retalhoSelect = document.getElementById('f-retalho');
    const applyFiltersBtn = document.getElementById('apply-filters');
    const clearFiltersBtn = document.getElementById('clear-filters');

    function setLoading(isLoading) {
        refreshBtn.disabled = isLoading;
        prevBtn.disabled = isLoading || !state.hasPrevious;
        nextBtn.disabled = isLoading || !state.hasNext;
        if (isLoading) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="13">
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
                    <td colspan="13" class="text-center text-muted py-4">
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
        tr.appendChild(textCell(item.grupo_maquina_display ?? item.grupo_maquina ?? '-'));
        tr.appendChild(editCell('descricao_mp', item.descricao_mp));
        tr.appendChild(editCell('tamanho', item.tamanho));
        tr.appendChild(editCell('espessura', item.espessura));
        tr.appendChild(editCell('quantidade', item.quantidade, 'number'));
        tr.appendChild(textCell(item.aproveitamento ?? '-'));
        tr.appendChild(textCell(item.tipo_chapa ?? '-'));
        tr.appendChild(textCell(item.retalho ? 'Sim' : 'Não'));
        tr.appendChild(textCell(item.nova_mp_id ?? '-'));

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

    function editCell(name, value, type = 'text') {
        const td = document.createElement('td');
        const input = document.createElement('input');
        input.className = 'form-control form-control-sm';
        input.name = name;
        input.type = type;
        input.value = value ?? '';
        td.appendChild(input);
        return td;
    }

    async function handleSave(row, button) {
        const id = row.dataset.id;
        const payload = { id: Number(id) };
        const fields = ['descricao_mp', 'tamanho', 'espessura', 'quantidade'];

        fields.forEach(field => {
            const input = row.querySelector(`[name="${field}"]`);
            if (!input) return;
            if (field === 'quantidade') {
                if (input.value !== '') payload[field] = parseFloat(input.value);
            } else {
                payload[field] = input.value;
            }
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
                    <td colspan="13" class="text-danger text-center py-4">
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
            ordem: ordemInput.value,
            // mp_codigo: mpCodigoInput.value,
            descricao_mp: descricaoInput.value,
            tipo_chapa: tipoChapaSelect.value,
            retalho: retalhoSelect.value,
        };
        loadPage();
    }

    applyFiltersBtn.addEventListener('click', applyFilters);

    clearFiltersBtn.addEventListener('click', () => {
        ordemInput.value = '';
        // mpCodigoInput.value = '';
        descricaoInput.value = '';
        tipoChapaSelect.value = '';
        retalhoSelect.value = '';
        applyFilters();
    });

    loadPage();
});
