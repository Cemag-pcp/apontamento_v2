const state = {
    currentPage: 1,
    rowsPerPage: 20,
    totalPages: 1,
    totalItems: 0,
    setores: [],
    filtroSetor: '',
    filtroTipo: '',
    filtroAtivo: 'true',
};

const modalAdd = new bootstrap.Modal(document.getElementById('addMaquinaModal'));
const modalEdit = new bootstrap.Modal(document.getElementById('editMaquinaModal'));
const modalToggle = new bootstrap.Modal(document.getElementById('toggleMaquinaModal'));

let botaoClicado = null;

function showToast(tipo, titulo, mensagem) {
    Swal.fire({
        icon: tipo,
        title: titulo,
        text: mensagem,
        position: 'bottom-end',
        timer: 3000,
        timerProgressBar: true,
        toast: true,
        showConfirmButton: false,
    });
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function tipoLabel(tipo) {
    return tipo === 'maquina' ? 'Máquina' : tipo === 'processo' ? 'Processo' : tipo;
}

function buttonChangeStatus(btns) {
    btns.forEach(btn => {
        const spinner = btn.querySelector('.spinner-border');
        btn.disabled = !btn.disabled;
        if (spinner) spinner.style.display = btn.disabled ? 'inline-block' : 'none';
    });
}

function renderSummary(page, pageSize, total) {
    const summary = document.getElementById('maquinasSummary');
    if (!summary) return;
    const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, total);
    summary.textContent = `${start}-${end} de ${total}`;
}

function renderPagination(current, totalPages) {
    const pagination = document.getElementById('maquinasPagination');
    if (!pagination) return;

    const pages = new Set([1]);
    for (let p = current - 1; p <= current + 1; p++) {
        if (p > 1 && p < totalPages) pages.add(p);
    }
    if (totalPages > 1) pages.add(totalPages);

    const dedupedPages = [...pages].sort((a, b) => a - b);
    const items = [];

    items.push(`<button class="pagination-button" data-page="${Math.max(1, current - 1)}" ${current === 1 ? 'disabled' : ''} aria-label="Anterior"><i class="bi bi-chevron-left"></i></button>`);

    dedupedPages.forEach((page, i) => {
        const prev = dedupedPages[i - 1];
        if (prev && page - prev > 1) items.push('<span class="pagination-button" aria-hidden="true">...</span>');
        items.push(`<button class="pagination-button ${page === current ? 'is-active' : ''}" data-page="${page}">${page}</button>`);
    });

    items.push(`<button class="pagination-button" data-page="${Math.min(totalPages, current + 1)}" ${current === totalPages ? 'disabled' : ''} aria-label="Próxima"><i class="bi bi-chevron-right"></i></button>`);

    pagination.innerHTML = items.join('');
}

function renderTable(results) {
    const tbody = document.getElementById('maquinasTableBody');
    if (!tbody) return;

    if (!results.length) {
        tbody.innerHTML = '<tr><td colspan="5"><div class="operators-empty-state">Nenhuma máquina encontrada.</div></td></tr>';
        return;
    }

    tbody.innerHTML = results.map(m => {
        const isAtivo = m.ativo;
        const statusLabel = isAtivo ? 'Ativa' : 'Inativa';
        const toggleTitle = isAtivo ? 'Desativar' : 'Ativar';
        const toggleIcon = isAtivo ? 'bi-toggle-on' : 'bi-toggle-off';

        return `
        <tr data-id="${m.id}">
            <td>${escapeHtml(m.nome)}</td>
            <td><span class="role-pill"><i class="bi bi-building"></i>${escapeHtml(m.setor_nome)}</span></td>
            <td><span class="role-pill" style="background:#f0fdf4;color:#16a34a;">${escapeHtml(tipoLabel(m.tipo))}</span></td>
            <td>
                <span class="status-pill ${isAtivo ? 'is-active' : 'is-inactive'}">
                    <span class="status-dot"></span>${statusLabel}
                </span>
            </td>
            <td>
                <div class="row-actions">
                    <button type="button" class="icon-action-button btnEditMaquina"
                        data-id="${m.id}" data-nome="${escapeHtml(m.nome)}"
                        data-setor="${m.setor_id}" data-tipo="${escapeHtml(m.tipo)}"
                        title="Editar">
                        <i class="bi bi-pencil-square"></i>
                    </button>
                    <button type="button" class="icon-action-button btnToggleMaquina"
                        data-id="${m.id}" data-nome="${escapeHtml(m.nome)}" data-ativo="${isAtivo}"
                        title="${toggleTitle}">
                        <i class="bi ${toggleIcon}"></i>
                    </button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

async function carregarTabela() {
    const loading = document.getElementById('overlayLoading');
    if (loading) loading.style.display = 'flex';

    const params = new URLSearchParams({
        page: state.currentPage,
        page_size: state.rowsPerPage,
        ativo: state.filtroAtivo,
    });
    if (state.filtroSetor) params.set('setor', state.filtroSetor);
    if (state.filtroTipo) params.set('tipo', state.filtroTipo);

    const response = await fetch(`/cadastro/api/maquinas/?${params}`);
    const data = await response.json();

    if (loading) loading.style.display = 'none';

    state.totalPages = data.total_pages || 1;
    state.totalItems = data.total_items || 0;

    if (data.meta?.setores && state.setores.length === 0) {
        state.setores = data.meta.setores;
        popularSetores(data.meta.setores);
    }

    renderTable(data.results || []);
    renderSummary(data.page, data.page_size, data.total_items);
    renderPagination(data.page, data.total_pages);
}

function popularSetores(setores) {
    const selects = [
        document.getElementById('addMaquinaSetor'),
        document.getElementById('editMaquinaSetor'),
        document.getElementById('filtroSetor'),
    ];

    selects.forEach(sel => {
        if (!sel) return;
        const isFilter = sel.id === 'filtroSetor';
        if (!isFilter) sel.innerHTML = '<option value="">-----</option>';
        setores.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.nome;
            sel.appendChild(opt);
        });
    });
}

function bindEvents() {
    document.getElementById('btnAddMaquina').addEventListener('click', () => {
        modalAdd.show();
    });

    document.getElementById('maquinasTableBody').addEventListener('click', event => {
        const btnEdit = event.target.closest('.btnEditMaquina');
        const btnToggle = event.target.closest('.btnToggleMaquina');

        if (btnEdit) {
            botaoClicado = btnEdit;
            btnEdit.disabled = true;
            document.getElementById('editMaquinaId').value = btnEdit.dataset.id;
            document.getElementById('editMaquinaNome').value = btnEdit.dataset.nome;
            document.getElementById('editMaquinaSetor').value = btnEdit.dataset.setor;
            document.getElementById('editMaquinaTipo').value = btnEdit.dataset.tipo;
            modalEdit.show();
        }

        if (btnToggle) {
            botaoClicado = btnToggle;
            btnToggle.disabled = true;
            const isAtivo = btnToggle.dataset.ativo === 'true';
            document.getElementById('toggleMaquinaId').value = btnToggle.dataset.id;
            document.getElementById('toggleMaquinaAtivo').value = isAtivo;
            document.getElementById('toggleMaquinaNome').textContent = btnToggle.dataset.nome;
            document.getElementById('toggleMaquinaTitle').textContent = isAtivo ? 'Desativar Máquina' : 'Ativar Máquina';
            document.getElementById('toggleMaquinaTexto').innerHTML = isAtivo
                ? `Confirma a <strong>desativação</strong> da máquina <strong>${escapeHtml(btnToggle.dataset.nome)}</strong>?`
                : `Confirma a <strong>ativação</strong> da máquina <strong>${escapeHtml(btnToggle.dataset.nome)}</strong>?`;
            document.getElementById('toggleMaquinaBtnLabel').textContent = isAtivo ? 'Desativar' : 'Ativar';
            document.getElementById('toggleMaquinaBtn').className = `btn ${isAtivo ? 'btn-warning' : 'btn-success'}`;
            modalToggle.show();
        }
    });

    $('#editMaquinaModal').on('hidden.bs.modal', () => {
        if (botaoClicado) { botaoClicado.disabled = false; botaoClicado = null; }
        document.getElementById('formEditMaquina').reset();
    });

    $('#toggleMaquinaModal').on('hidden.bs.modal', () => {
        if (botaoClicado) { botaoClicado.disabled = false; botaoClicado = null; }
    });

    $('#addMaquinaModal').on('hidden.bs.modal', () => {
        document.getElementById('formAddMaquina').reset();
    });

    document.getElementById('rowsPerPage').addEventListener('change', e => {
        state.rowsPerPage = Number(e.target.value);
        state.currentPage = 1;
        carregarTabela();
    });

    document.getElementById('maquinasPagination').addEventListener('click', e => {
        const btn = e.target.closest('[data-page]');
        if (!btn || btn.disabled) return;
        state.currentPage = Number(btn.dataset.page);
        carregarTabela();
    });

    document.getElementById('filtroSetor').addEventListener('change', e => {
        state.filtroSetor = e.target.value;
        state.currentPage = 1;
        carregarTabela();
    });

    document.getElementById('filtroTipo').addEventListener('change', e => {
        state.filtroTipo = e.target.value;
        state.currentPage = 1;
        carregarTabela();
    });

    document.getElementById('filtroAtivo').addEventListener('change', e => {
        state.filtroAtivo = e.target.value;
        state.currentPage = 1;
        carregarTabela();
    });
}

function bindForms() {
    document.getElementById('formAddMaquina').addEventListener('submit', async e => {
        e.preventDefault();
        const form = e.target;
        const btns = form.querySelectorAll('.btn');
        const dados = Object.fromEntries(new FormData(form).entries());
        buttonChangeStatus(btns);

        try {
            const res = await fetch('/cadastro/api/maquinas/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': dados.csrfmiddlewaretoken },
                body: JSON.stringify({ nome: dados.nome, setor_id: dados.setor_id, tipo: dados.tipo }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro desconhecido.');
            modalAdd.hide();
            await carregarTabela();
            showToast('success', 'Adicionado', 'Máquina criada com sucesso.');
        } catch (err) {
            showToast('error', 'Erro', err.message);
        } finally {
            buttonChangeStatus(btns);
        }
    });

    document.getElementById('formEditMaquina').addEventListener('submit', async e => {
        e.preventDefault();
        const form = e.target;
        const btns = form.querySelectorAll('.btn');
        const dados = Object.fromEntries(new FormData(form).entries());
        buttonChangeStatus(btns);

        try {
            const res = await fetch('/cadastro/api/maquinas/', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': dados.csrfmiddlewaretoken },
                body: JSON.stringify({ id: dados.id, nome: dados.nome, setor_id: dados.setor_id, tipo: dados.tipo }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro desconhecido.');
            modalEdit.hide();
            await carregarTabela();
            showToast('success', 'Editado', 'Máquina atualizada com sucesso.');
        } catch (err) {
            showToast('error', 'Erro', err.message);
        } finally {
            buttonChangeStatus(btns);
        }
    });

    document.getElementById('formToggleMaquina').addEventListener('submit', async e => {
        e.preventDefault();
        const form = e.target;
        const btns = form.querySelectorAll('.btn');
        const dados = Object.fromEntries(new FormData(form).entries());
        buttonChangeStatus(btns);

        try {
            const res = await fetch('/cadastro/api/maquinas/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': dados.csrfmiddlewaretoken },
                body: JSON.stringify({ id: dados.id }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro desconhecido.');
            modalToggle.hide();
            await carregarTabela();
            const label = data.ativo ? 'ativada' : 'desativada';
            showToast('success', 'Atualizado', `Máquina ${label} com sucesso.`);
        } catch (err) {
            showToast('error', 'Erro', err.message);
        } finally {
            buttonChangeStatus(btns);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    carregarTabela();
    bindEvents();
    bindForms();
});
