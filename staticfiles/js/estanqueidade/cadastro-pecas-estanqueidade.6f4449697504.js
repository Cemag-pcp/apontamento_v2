document.addEventListener('DOMContentLoaded', function () {
    const tabela = document.getElementById('tabela-pecas-estanqueidade');
    const tbody = tabela.querySelector('tbody');
    const pagination = document.getElementById('pagination');
    const rowsPerPage = 10;

    const filtroCodigo = document.getElementById('filtro-codigo');
    const filtroDescricao = document.getElementById('filtro-descricao');
    const filtroTipo = document.getElementById('filtro-tipo');
    const btnFiltrar = document.getElementById('btn-filtrar');
    const btnLimpar = document.getElementById('btn-limpar-filtros');

    const modalFormElement = document.getElementById('modal-form-peca');
    const modalForm = new bootstrap.Modal(modalFormElement);

    const inputCodigoOriginal = document.getElementById('codigo-original');
    const inputCodigo = document.getElementById('codigo');
    const inputDescricao = document.getElementById('descricao');
    const inputTipo = document.getElementById('tipo');
    const tituloModal = document.getElementById('modal-form-peca-label');
    const btnSalvar = document.getElementById('salvar-peca');

    let currentPage = 1;
    let filteredRows = [];
    let modoEdicao = false;

    const Toast = Swal.mixin({
        toast: true,
        position: 'bottom-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.onmouseenter = Swal.stopTimer;
            toast.onmouseleave = Swal.resumeTimer;
        }
    });

    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    function getRows() {
        return Array.from(tbody.querySelectorAll('tr')).filter((row) => !row.id);
    }

    function ensureEmptyState() {
        const existing = document.getElementById('linha-vazia');
        const rows = getRows();

        if (!rows.length) {
            if (!existing) {
                const tr = document.createElement('tr');
                tr.id = 'linha-vazia';
                tr.innerHTML = '<td colspan="4" class="text-center text-muted">Nenhum item cadastrado.</td>';
                tbody.appendChild(tr);
            }
        } else if (existing) {
            existing.remove();
        }

        const initialEmpty = document.getElementById('linha-vazia-inicial');
        if (initialEmpty && rows.length) {
            initialEmpty.remove();
        }
    }

    function applyFilters() {
        const codigo = filtroCodigo.value.trim().toLowerCase();
        const descricao = filtroDescricao.value.trim().toLowerCase();
        const tipo = filtroTipo.value.trim().toLowerCase();

        filteredRows = getRows().filter((row) => {
            const rowCodigo = (row.dataset.codigo || '').toLowerCase();
            const rowDescricao = (row.dataset.descricao || '').toLowerCase();
            const rowTipo = (row.dataset.tipo || '').toLowerCase();

            return rowCodigo.includes(codigo)
                && rowDescricao.includes(descricao)
                && (!tipo || rowTipo === tipo);
        });

        currentPage = 1;
        showPage(currentPage);
    }

    function createPageItem(text, page, active, disabled) {
        const li = document.createElement('li');
        li.className = `page-item${active ? ' active' : ''}${disabled ? ' disabled' : ''}`;

        const a = document.createElement('a');
        a.className = 'page-link';
        a.href = '#';
        a.textContent = text;

        if (!disabled && page) {
            a.addEventListener('click', function (event) {
                event.preventDefault();
                showPage(page);
            });
        }

        li.appendChild(a);
        pagination.appendChild(li);
    }

    function updatePagination() {
        pagination.innerHTML = '';
        const totalPages = Math.ceil(filteredRows.length / rowsPerPage);

        if (!totalPages) {
            return;
        }

        createPageItem('Anterior', currentPage - 1, false, currentPage === 1);

        for (let i = 1; i <= totalPages; i += 1) {
            createPageItem(String(i), i, i === currentPage, false);
        }

        createPageItem('Proximo', currentPage + 1, false, currentPage === totalPages);
    }

    function showPage(page) {
        ensureEmptyState();

        const rows = getRows();
        rows.forEach((row) => {
            row.style.display = 'none';
        });

        const totalPages = Math.max(1, Math.ceil(filteredRows.length / rowsPerPage));
        currentPage = Math.min(page, totalPages);

        const start = (currentPage - 1) * rowsPerPage;
        const end = start + rowsPerPage;

        filteredRows.slice(start, end).forEach((row) => {
            row.style.display = '';
        });

        updatePagination();
    }

    function refreshTable() {
        ensureEmptyState();
        applyFilters();
    }

    function buildRow(item) {
        const tr = document.createElement('tr');
        tr.dataset.codigo = item.codigo;
        tr.dataset.descricao = item.descricao || '';
        tr.dataset.tipo = item.tipo;
        tr.innerHTML = `
            <td>${item.codigo}</td>
            <td>${item.descricao || ''}</td>
            <td data-tipo-label="${item.tipo_label}">${item.tipo_label}</td>
            <td>
                <button class="btn btn-outline-primary btn-sm abrir-modal-editar" type="button">Editar</button>
            </td>
        `;
        return tr;
    }

    function resetModalForm() {
        inputCodigoOriginal.value = '';
        inputCodigo.value = '';
        inputDescricao.value = '';
        inputTipo.value = '';
        modoEdicao = false;
        tituloModal.textContent = 'Adicionar item';
        btnSalvar.textContent = 'Salvar';
    }

    document.getElementById('btn-abrir-modal-adicionar').addEventListener('click', function () {
        resetModalForm();
        modalForm.show();
    });

    btnFiltrar.addEventListener('click', applyFilters);

    btnLimpar.addEventListener('click', function () {
        filtroCodigo.value = '';
        filtroDescricao.value = '';
        filtroTipo.value = '';
        refreshTable();
    });

    tabela.addEventListener('click', function (event) {
        const row = event.target.closest('tr');
        if (!row || row.id) {
            return;
        }

        if (event.target.classList.contains('abrir-modal-editar')) {
            modoEdicao = true;
            inputCodigoOriginal.value = row.dataset.codigo || '';
            inputCodigo.value = row.dataset.codigo || '';
            inputDescricao.value = row.dataset.descricao || '';
            inputTipo.value = row.dataset.tipo || '';
            tituloModal.textContent = 'Editar item';
            btnSalvar.textContent = 'Salvar alteracoes';
            modalForm.show();
        }
    });

    btnSalvar.addEventListener('click', async function () {
        const codigoOriginal = inputCodigoOriginal.value.trim();
        const payload = {
            codigo: inputCodigo.value.trim(),
            descricao: inputDescricao.value.trim(),
            tipo: inputTipo.value.trim()
        };

        if (!payload.codigo || !payload.tipo) {
            Toast.fire({ icon: 'error', title: 'Codigo e tipo sao obrigatorios' });
            return;
        }

        btnSalvar.disabled = true;
        const originalText = btnSalvar.textContent;
        btnSalvar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Salvando...';

        try {
            const url = modoEdicao
                ? `/inspecao/api/cadastro-pecas-estanqueidade/${encodeURIComponent(codigoOriginal)}/`
                : '/inspecao/api/cadastro-pecas-estanqueidade/';
            const method = modoEdicao ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Erro ao salvar item');
            }

            if (modoEdicao) {
                const row = getRows().find((item) => item.dataset.codigo === codigoOriginal);
                if (row) {
                    const novaLinha = buildRow(data.item);
                    row.replaceWith(novaLinha);
                }
            } else {
                tbody.appendChild(buildRow(data.item));
            }

            modalForm.hide();
            resetModalForm();
            refreshTable();
            Toast.fire({ icon: 'success', title: data.success || 'Cadastro salvo com sucesso' });
        } catch (error) {
            Toast.fire({ icon: 'error', title: error.message || 'Erro ao salvar item' });
        } finally {
            btnSalvar.disabled = false;
            btnSalvar.textContent = originalText;
        }
    });

    refreshTable();
});
