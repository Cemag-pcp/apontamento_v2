const configEl = document.getElementById('erpApontamentosConfig');
const apiUrl = configEl?.dataset?.apiUrl;
const apontarUrlTemplate = configEl?.dataset?.apontarUrlTemplate;
const csrfToken = configEl?.dataset?.csrfToken;

const form = document.getElementById('erpFiltrosForm');
const tbody = document.getElementById('erpTabelaApontamentos');
const loadingState = document.getElementById('erpLoadingState');
const resumoEl = document.getElementById('erpResumoTabela');
const paginationInfoEl = document.getElementById('erpPaginationInfo');
const paginationControlsEl = document.getElementById('erpPaginationControls');
const btnLimparFiltros = document.getElementById('btnLimparFiltros');
const btnAtualizarTabela = document.getElementById('btnAtualizarTabela');
const modalResumoEl = document.getElementById('erpApontamentoResumoModal');
const btnConfirmarApontamentoERP = document.getElementById('btnConfirmarApontamentoERP');
const btnApontarViaApiERP = document.getElementById('btnApontarViaApiERP');
const detalhesResumoEl = document.getElementById('erpDetalhesResumoModal');
const detalheApontadoStatusEl = document.getElementById('detalheApontadoStatus');
const detalheTipoApontamentoEl = document.getElementById('detalheTipoApontamento');
const detalheDataApontamentoEl = document.getElementById('detalheDataApontamento');
const detalheRespApontamentoEl = document.getElementById('detalheRespApontamento');
const detalheChaveApontamentoEl = document.getElementById('detalheChaveApontamento');
const detalheItemApontadoIdEl = document.getElementById('detalheItemApontadoId');
const erroResumoEl = document.getElementById('erpErroResumoModal');
const erroDescricaoEl = document.getElementById('erpErroDescricaoModal');

let apontamentoSelecionado = null;
let modalConfirmarApontamentoInstance = null;
let modalDetalhesApontamentoInstance = null;
let modalErroApontamentoInstance = null;
const pendingApontamentoIds = new Set();

const state = {
    page: 1,
    lastPagination: null,
};

let debounceTimer = null;
let activeController = null;

function setLoading(isLoading) {
    loadingState?.classList.toggle('d-none', !isLoading);
}

function readFilters() {
    const data = new FormData(form);
    return {
        ordem: (data.get('ordem') || '').trim(),
        peca: (data.get('peca') || '').trim(),
        apontado: (data.get('apontado') || '').trim(),
        chave_apontamento: (data.get('chave_apontamento') || '').trim(),
        resp_apontamento: (data.get('resp_apontamento') || '').trim(),
        data_apontamento_inicio: (data.get('data_apontamento_inicio') || '').trim(),
        data_apontamento_fim: (data.get('data_apontamento_fim') || '').trim(),
        data_producao_inicio: (data.get('data_producao_inicio') || '').trim(),
        data_producao_fim: (data.get('data_producao_fim') || '').trim(),
        limit: (data.get('limit') || '50').trim(),
    };
}

function badgeApontado(value) {
    if (value) {
        return '<span class="badge text-bg-success">Sim</span>';
    }
    return '<span class="badge text-bg-secondary">Não</span>';
}

function renderActionButton(row) {
    const primaryButton = (row.ordem_ja_apontada || row.apontado) ? `
        <button type="button"
                class="btn btn-sm btn-outline-secondary btn-erp-detalhes"
                title="Ver detalhes do apontamento"
                aria-label="Ver detalhes do apontamento"
                data-row='${escapeAttrJson(row)}'>
            <i class="fas fa-circle-info"></i>
        </button>
    ` : `
        <button type="button"
                class="btn btn-sm btn-outline-success btn-erp-apontar"
                title="Apontar no ERP"
                aria-label="Apontar no ERP"
                data-row='${escapeAttrJson(row)}'>
            <i class="fas fa-check-circle"></i>
        </button>
    `;

    const errorButton = row.erro_apontamento ? `
        <button type="button"
                class="btn btn-sm btn-outline-danger btn-erp-ver-erro"
                title="Ver erro"
                aria-label="Ver erro"
                data-row='${escapeAttrJson(row)}'>
            <i class="fas fa-triangle-exclamation"></i>
        </button>
    ` : '';

    return `<div class="d-inline-flex gap-1">${primaryButton}${errorButton}</div>`;
}

function renderRows(rows) {
    const visibleRows = rows.filter((row) => !pendingApontamentoIds.has(Number(row.id)));

    if (!visibleRows.length) {
        tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted py-4">Nenhum apontamento encontrado.</td></tr>';
        return;
    }

    tbody.innerHTML = visibleRows.map((row) => `
        <tr data-item-id="${Number(row.id)}">
            <td>${escapeHtml(row.ordem || '')}</td>
            <td>${escapeHtml(row.peca_codigo || '')}</td>
            <td>${escapeHtml(row.peca_descricao || '')}</td>
            <td>${escapeHtml(row.maquina || '-')}</td>
            <td>${escapeHtml(row.operador || '-')}</td>
            <td class="text-end">${formatNumber(row.qtd_boa)}</td>
            <td class="text-end">${formatNumber(row.qtd_morta)}</td>
            <td>${badgeApontado(row.apontado)}</td>
            <td>${escapeHtml(row.chave_apontamento || '-')}</td>
            <td>${escapeHtml(row.resp_apontamento || row.resp_apontamento_username || '-')}</td>
            <td>${escapeHtml(row.data_producao || '-')}</td>
            <td>${escapeHtml(row.data_apontamento || '-')}</td>
            <td class="text-center">
                ${renderActionButton(row)}
            </td>
        </tr>
    `).join('');

    bindRowActionButtons();
}

function removeRowFromTable(itemId) {
    const rowEl = tbody.querySelector(`tr[data-item-id="${Number(itemId)}"]`);
    if (rowEl) {
        rowEl.remove();
    }

    const hasDataRows = tbody.querySelector('tr[data-item-id]');
    if (!hasDataRows) {
        tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted py-4">Nenhum apontamento encontrado.</td></tr>';
    }
}

function renderPagination(pagination) {
    state.lastPagination = pagination;

    paginationInfoEl.textContent = `Página ${pagination.page} de ${pagination.total_pages} | ${pagination.total_items} registros`;
    resumoEl.textContent = `${pagination.total_items} apontamentos com qtd_boa > 0`;

    const controls = [];
    controls.push(buttonHtml('Anterior', pagination.has_previous, pagination.page - 1, 'btn-outline-secondary'));

    const totalPages = pagination.total_pages;
    let start = Math.max(1, pagination.page - 2);
    let end = Math.min(totalPages, pagination.page + 2);

    if (start > 1) {
        controls.push(pageButtonHtml(1, pagination.page));
        if (start > 2) controls.push('<span class="px-1 text-muted">...</span>');
    }

    for (let p = start; p <= end; p += 1) {
        controls.push(pageButtonHtml(p, pagination.page));
    }

    if (end < totalPages) {
        if (end < totalPages - 1) controls.push('<span class="px-1 text-muted">...</span>');
        controls.push(pageButtonHtml(totalPages, pagination.page));
    }

    controls.push(buttonHtml('Próxima', pagination.has_next, pagination.page + 1, 'btn-outline-secondary'));

    paginationControlsEl.innerHTML = controls.join('');
    paginationControlsEl.querySelectorAll('button[data-page]').forEach((btn) => {
        btn.addEventListener('click', () => loadPage(Number(btn.dataset.page)));
    });
}

function buttonHtml(label, enabled, page, cls) {
    return `<button type="button" class="btn btn-sm ${cls}" ${enabled ? `data-page="${page}"` : 'disabled'}>${label}</button>`;
}

function pageButtonHtml(page, currentPage) {
    const cls = page === currentPage ? 'btn-primary' : 'btn-outline-primary';
    return `<button type="button" class="btn btn-sm ${cls}" data-page="${page}">${page}</button>`;
}

function formatNumber(value) {
    const num = Number(value);
    if (Number.isNaN(num)) return '-';
    return num.toLocaleString('pt-BR');
}

function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function escapeAttrJson(value) {
    return JSON.stringify(value)
        .replaceAll('&', '&amp;')
        .replaceAll("'", '&#039;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
}

function bindRowActionButtons() {
    tbody.querySelectorAll('.btn-erp-apontar').forEach((btn) => {
        btn.addEventListener('click', () => {
            const raw = btn.getAttribute('data-row');
            if (!raw) return;
            try {
                apontamentoSelecionado = JSON.parse(raw);
            } catch (error) {
                console.error(error);
                return;
            }
            openConfirmModal(apontamentoSelecionado);
        });
    });

    tbody.querySelectorAll('.btn-erp-detalhes').forEach((btn) => {
        btn.addEventListener('click', () => {
            const raw = btn.getAttribute('data-row');
            if (!raw) return;
            try {
                const row = JSON.parse(raw);
                openDetailsModal(row);
            } catch (error) {
                console.error(error);
            }
        });
    });

    tbody.querySelectorAll('.btn-erp-ver-erro').forEach((btn) => {
        btn.addEventListener('click', () => {
            const raw = btn.getAttribute('data-row');
            if (!raw) return;
            try {
                const row = JSON.parse(raw);
                openErrorModal(row);
            } catch (error) {
                console.error(error);
            }
        });
    });
}

function openConfirmModal(row) {
    if (!modalConfirmarApontamentoInstance) return;
    modalResumoEl.textContent = `Ordem ${row.ordem || '-'} | Peça ${row.peca_codigo || '-'} | Qtd. boa ${formatNumber(row.qtd_boa)} | Data produzida ${row.data_producao || '-'}`;
    modalConfirmarApontamentoInstance.show();
}

function openDetailsModal(row) {
    if (!modalDetalhesApontamentoInstance) return;

    const tipo = row.tipo_apontamento || row.ordem_tipo_apontamento || '-';
    const dataApont = row.data_apontamento || row.ordem_data_apontamento || '-';
    const resp = row.resp_apontamento || row.ordem_resp_apontamento_username || '-';
    const chave = row.chave_apontamento || row.ordem_chave_apontamento || '-';
    const itemApontadoId = row.apontado ? row.id : (row.ordem_item_apontado_id || '-');

    detalhesResumoEl.textContent = `Ordem ${row.ordem || '-'} | Peça ${row.peca_codigo || '-'} | Qtd. boa ${formatNumber(row.qtd_boa)}`;
    detalheApontadoStatusEl.textContent = (row.ordem_ja_apontada || row.apontado) ? 'Apontado' : 'Não apontado';
    detalheTipoApontamentoEl.textContent = tipo || '-';
    detalheDataApontamentoEl.textContent = dataApont || '-';
    detalheRespApontamentoEl.textContent = resp || '-';
    detalheChaveApontamentoEl.textContent = chave || '-';
    detalheItemApontadoIdEl.textContent = itemApontadoId || '-';

    modalDetalhesApontamentoInstance.show();
}

function openErrorModal(row) {
    if (!modalErroApontamentoInstance) return;

    erroResumoEl.textContent = `Ordem ${row.ordem || '-'} | Peça ${row.peca_codigo || '-'} | Tipo ${row.tipo_apontamento || '-'}`;
    erroDescricaoEl.textContent = row.erro_apontamento || 'Sem descrição de erro.';

    modalErroApontamentoInstance.show();
}

async function loadPage(page = 1) {
    if (!apiUrl) return;

    state.page = Math.max(1, page);
    const filters = readFilters();
    const params = new URLSearchParams({
        page: String(state.page),
        limit: filters.limit,
    });

    Object.entries(filters).forEach(([key, value]) => {
        if (key === 'limit') return;
        if (value) params.set(key, value);
    });

    if (activeController) {
        activeController.abort();
    }
    activeController = new AbortController();

    setLoading(true);
    try {
        const response = await fetch(`${apiUrl}?${params.toString()}`, {
            signal: activeController.signal,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        renderRows(payload.results || []);
        renderPagination(payload.pagination || {
            page: 1, total_pages: 1, total_items: 0, has_previous: false, has_next: false,
        });
    } catch (error) {
        if (error.name === 'AbortError') return;
        tbody.innerHTML = '<tr><td colspan="13" class="text-center text-danger py-4">Falha ao carregar os apontamentos.</td></tr>';
        paginationControlsEl.innerHTML = '';
        paginationInfoEl.textContent = '-';
        resumoEl.textContent = 'Erro ao consultar dados';
        console.error(error);
    } finally {
        setLoading(false);
    }
}

function scheduleReload() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => loadPage(1), 350);
}

function bindEvents() {
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        loadPage(1);
    });

    btnLimparFiltros.addEventListener('click', () => {
        form.reset();
        loadPage(1);
    });

    btnAtualizarTabela?.addEventListener('click', () => {
        loadPage(state.page || 1);
    });

    form.querySelectorAll('input[type="text"]').forEach((input) => {
        input.addEventListener('input', scheduleReload);
    });

    form.querySelectorAll('input[type="date"], select').forEach((field) => {
        field.addEventListener('change', () => loadPage(1));
    });

    btnConfirmarApontamentoERP?.addEventListener('click', () => {
        confirmarApontamentoSelecionado('manual');
    });

    btnApontarViaApiERP?.addEventListener('click', () => {
        confirmarApontamentoSelecionado('api');
    });
}

async function confirmarApontamentoSelecionado(tipoApontamento = 'manual') {
    if (!apontamentoSelecionado?.id || !apontarUrlTemplate) return;
    if (pendingApontamentoIds.has(Number(apontamentoSelecionado.id))) return;

    const url = apontarUrlTemplate.replace('/0/apontar/', `/${apontamentoSelecionado.id}/apontar/`);
    const previousText = btnConfirmarApontamentoERP?.innerHTML;
    const previousApiText = btnApontarViaApiERP?.innerHTML;
    const selectedId = Number(apontamentoSelecionado.id);

    pendingApontamentoIds.add(selectedId);
    removeRowFromTable(selectedId);
    modalConfirmarApontamentoInstance?.hide();

    if (btnConfirmarApontamentoERP) {
        btnConfirmarApontamentoERP.disabled = true;
        btnConfirmarApontamentoERP.innerHTML = tipoApontamento === 'manual' ? 'Confirmando...' : previousText;
    }
    if (btnApontarViaApiERP) {
        btnApontarViaApiERP.disabled = true;
        btnApontarViaApiERP.innerHTML = tipoApontamento === 'api' ? 'Confirmando...' : previousApiText;
    }

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ tipo_apontamento: tipoApontamento }),
        });

        const payload = await response.json();
        if (!response.ok || payload.status !== 'success') {
            if (response.status === 409 && payload?.already_apontado) {
                const detalhes = payload.detalhes || {};
                openDetailsModal({
                    ...apontamentoSelecionado,
                    ordem_ja_apontada: true,
                    ordem_item_apontado_id: detalhes.item_id,
                    ordem_tipo_apontamento: detalhes.tipo_apontamento,
                    ordem_data_apontamento: detalhes.data_apontamento,
                    ordem_resp_apontamento_username: detalhes.resp_apontamento,
                    ordem_chave_apontamento: detalhes.chave_apontamento,
                });
            }
            const backendErrorText =
                payload.description ||
                payload.retorno_api ||
                payload.message ||
                'Falha ao confirmar apontamento.';
            throw new Error(backendErrorText);
        }

        if (window.Swal) {
            Swal.fire({
                icon: 'success',
                title: 'Apontado',
                text: `Item apontado (${tipoApontamento === 'api' ? 'via API' : 'manual'}).`,
                timer: 1400,
                showConfirmButton: false
            });
        }

        await loadPage(state.page || 1);
    } catch (error) {
        pendingApontamentoIds.delete(selectedId);
        await loadPage(state.page || 1);
        console.error(error);
        if (window.Swal) {
            Swal.fire({
                icon: 'error',
                title: 'Erro ao apontar',
                text: error.message || 'Não foi possível concluir o apontamento.',
            });
        }
    } finally {
        if (!pendingApontamentoIds.has(selectedId)) {
            // no-op: line already restored by reload on error
        }
        if (btnConfirmarApontamentoERP) {
            btnConfirmarApontamentoERP.disabled = false;
            btnConfirmarApontamentoERP.innerHTML = previousText || 'Confirmar';
        }
        if (btnApontarViaApiERP) {
            btnApontarViaApiERP.disabled = false;
            btnApontarViaApiERP.innerHTML = previousApiText || 'Apontar via API';
        }
        // Keep item hidden after success until next user refresh (or reload that already runs above)
        // and ensure pending lock is released after backend response.
        pendingApontamentoIds.delete(selectedId);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (!form || !tbody || !apiUrl) return;
    const modalEl = document.getElementById('modalConfirmarApontamentoERP');
    const modalDetalhesEl = document.getElementById('modalDetalhesApontamentoERP');
    const modalErroEl = document.getElementById('modalErroApontamentoERP');
    if (modalEl && window.bootstrap?.Modal) {
        modalConfirmarApontamentoInstance = new window.bootstrap.Modal(modalEl);
    }
    if (modalDetalhesEl && window.bootstrap?.Modal) {
        modalDetalhesApontamentoInstance = new window.bootstrap.Modal(modalDetalhesEl);
    }
    if (modalErroEl && window.bootstrap?.Modal) {
        modalErroApontamentoInstance = new window.bootstrap.Modal(modalErroEl);
    }
    bindEvents();
    loadPage(1);
});
