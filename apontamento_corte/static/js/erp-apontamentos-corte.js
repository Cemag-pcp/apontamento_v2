const configEl = document.getElementById('erpApontamentosConfig');
const apiUrl = configEl?.dataset?.apiUrl;
const transferirUrlTemplate = configEl?.dataset?.transferirUrlTemplate;
const apontarUrlTemplate = configEl?.dataset?.apontarUrlTemplate;
const apontarBlocoUrl = configEl?.dataset?.apontarBlocoUrl;
const csrfToken = configEl?.dataset?.csrfToken;

const form = document.getElementById('erpFiltrosForm');
const tbody = document.getElementById('erpTabelaApontamentos');
const loadingState = document.getElementById('erpLoadingState');
const resumoEl = document.getElementById('erpResumoTabela');
const paginationInfoEl = document.getElementById('erpPaginationInfo');
const paginationControlsEl = document.getElementById('erpPaginationControls');
const filtrosFeedbackEl = document.getElementById('erpFiltrosFeedback');
const btnAplicarFiltros = document.getElementById('btnAplicarFiltros');
const btnLimparFiltros = document.getElementById('btnLimparFiltros');
const btnAtualizarTabela = document.getElementById('btnAtualizarTabela');
const btnApontarEmBloco = document.getElementById('btnApontarEmBloco');
const chkSelecionarTodosApontamentos = document.getElementById('chkSelecionarTodosApontamentos');
const modalResumoEl = document.getElementById('erpApontamentoResumoModal');
const transferenciaCodigoChapaEl = document.getElementById('transferenciaCodigoChapa');
const transferenciaPesoTotalEl = document.getElementById('transferenciaPesoTotal');
const transferenciaQuantidadeChapasEl = document.getElementById('transferenciaQuantidadeChapas');
const transferenciaDescricaoChapaEl = document.getElementById('transferenciaDescricaoChapa');
const btnConfirmarApontamentoERP = document.getElementById('btnConfirmarApontamentoERP');
const btnApontarViaApiERP = document.getElementById('btnApontarViaApiERP');
const modalApontamentoResumoEl = document.getElementById('erpApontamentoCorteResumoModal');
const btnConfirmarApontamentoCorteERP = document.getElementById('btnConfirmarApontamentoCorteERP');
const btnApontarCorteViaApiERP = document.getElementById('btnApontarCorteViaApiERP');
const modalApontamentoBlocoResumoEl = document.getElementById('erpApontamentoBlocoResumoModal');
const btnConfirmarApontamentoBlocoERP = document.getElementById('btnConfirmarApontamentoBlocoERP');
const btnApontarBlocoViaApiERP = document.getElementById('btnApontarBlocoViaApiERP');
const erroApontamentoCorteTextoEl = document.getElementById('erroApontamentoCorteTexto');
const detalhesResumoEl = document.getElementById('erpDetalhesResumoModal');
const detalheDescricaoChapaEl = document.getElementById('detalheDescricaoChapa');
const detalheEspessuraPlanilhaEl = document.getElementById('detalheEspessuraPlanilha');
const detalheEspessuraMmEl = document.getElementById('detalheEspessuraMm');
const detalheCodigoChapaEl = document.getElementById('detalheCodigoChapa');
const detalheQuantidadeChapasEl = document.getElementById('detalheQuantidadeChapas');
const detalhePesoTotalEl = document.getElementById('detalhePesoTotal');
const detalheChapaEncontradaEl = document.getElementById('detalheChapaEncontrada');
const detalheTransferenciaStatusEl = document.getElementById('detalheTransferenciaStatus');
const detalheTransferidoEmEl = document.getElementById('detalheTransferidoEm');
const detalheChaveTransferenciaEl = document.getElementById('detalheChaveTransferencia');
const detalheTransferenciaErroEl = document.getElementById('detalheTransferenciaErro');
const detalheApontamentoStatusEl = document.getElementById('detalheApontamentoStatus');
const detalheTipoApontamentoEl = document.getElementById('detalheTipoApontamento');
const detalheDataApontamentoEl = document.getElementById('detalheDataApontamento');
const detalheRespApontamentoEl = document.getElementById('detalheRespApontamento');
const detalheChaveApontamentoEl = document.getElementById('detalheChaveApontamento');
const detalheErroApontamentoEl = document.getElementById('detalheErroApontamento');

let modalDetalhesApontamentoInstance = null;
let modalConfirmarApontamentoInstance = null;
let modalConfirmarApontamentoCorteInstance = null;
let modalApontamentoEmBlocoInstance = null;
let modalErroApontamentoCorteInstance = null;
let apontamentoSelecionado = null;
let debounceTimer = null;
let activeController = null;
const apontamentosSelecionados = new Map();

const state = {
    page: 1,
    lastPagination: null,
};

function setLoading(isLoading) {
    loadingState?.classList.toggle('d-none', !isLoading);
    filtrosFeedbackEl?.classList.toggle('d-none', !isLoading);

    form?.querySelectorAll('input, select, button').forEach((control) => {
        control.disabled = isLoading;
    });
    if (btnAtualizarTabela) {
        btnAtualizarTabela.disabled = isLoading;
    }
    if (paginationControlsEl) {
        paginationControlsEl.querySelectorAll('button').forEach((button) => {
            button.disabled = isLoading;
        });
    }
    if (btnAplicarFiltros) {
        btnAplicarFiltros.innerHTML = isLoading
            ? '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Aplicando...'
            : '<span class="btn-label">Aplicar</span>';
    }
}

function readFilters() {
    const data = new FormData(form);
    return {
        ordem: (data.get('ordem') || '').trim(),
        peca: (data.get('peca') || '').trim(),
        chapa: (data.get('chapa') || '').trim(),
        data_producao_inicio: (data.get('data_producao_inicio') || '').trim(),
        data_producao_fim: (data.get('data_producao_fim') || '').trim(),
        apontado: (data.get('apontado') || 'nao').trim(),
        limit: (data.get('limit') || '50').trim(),
    };
}

function renderRows(rows) {
    apontamentosSelecionados.clear();
    updateBulkButton();

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="19" class="text-center text-muted py-4">Nenhuma transferencia encontrada.</td></tr>';
        updateMasterCheckbox();
        return;
    }

    tbody.innerHTML = rows.map((row) => `
        <tr data-item-id="${Number(row.id)}">
            <td class="text-center">${renderSelectCheckbox(row)}</td>
            <td>${escapeHtml(row.ordem || '')}</td>
            <td><span class="col-peca-truncada" title="${escapeHtml(formatPecaCodigo(row.peca || ''))}">${escapeHtml(formatPecaCodigo(row.peca || ''))}</span></td>
            <td><span class="col-chapa-descricao" title="${escapeHtml(row.descricao_chapa || '-')}">${escapeHtml(row.descricao_chapa || '-')}</span></td>
            <td>${renderCodigoChapa(row)}</td>
            <td>${escapeHtml(row.tipo_chapa_display || '-')}</td>
            <td class="text-end">${formatNumber(row.peso_total)}</td>
            <td class="text-end">${formatNumber(row.quantidade_chapas)}</td>
            <td>${escapeHtml(row.maquina || '-')}</td>
            <td><span class="col-operador-truncado" title="${escapeHtml(row.operador || '-')}">${escapeHtml(row.operador || '-')}</span></td>
            <td class="text-end">${formatNumber(row.qtd_boa)}</td>
            <td class="text-end">${formatNumber(row.qtd_morta)}</td>
            <td>${badgeTransferencia(row.transferencia_status)}</td>
            <td>${escapeHtml(row.chave_transferencia || '-')}</td>
            <td>${badgeApontamento(row)}</td>
            <td>${escapeHtml(row.chave_apontamento || '-')}</td>
            <td>${escapeHtml(row.transferido_em || '-')}</td>
            <td>${escapeHtml(row.data_producao || '-')}</td>
            <td class="text-center">
                ${renderActionButtons(row)}
            </td>
        </tr>
    `).join('');

    bindRowActionButtons();
    updateMasterCheckbox();
}

function renderSelectCheckbox(row) {
    const habilitado = podeApontar(row);
    return `
        <input type="checkbox"
               class="form-check-input chk-apontamento-bloco"
               aria-label="Selecionar item para apontamento em bloco"
               ${habilitado ? '' : 'disabled'}
               title="${habilitado ? 'Selecionar item' : 'Item precisa estar transferido e pendente de apontamento'}"
               data-row='${escapeAttrJson(row)}'>
    `;
}

function podeApontar(row) {
    return String(row.transferencia_status || '').toLowerCase() === 'sucesso' && !Boolean(row.apontado);
}

function renderActionButtons(row) {
    const transferido = String(row.transferencia_status || '').toLowerCase() === 'sucesso';
    const apontado = Boolean(row.apontado);
    const erro = erroVisivelAcoes(row.erro_apontamento || row.transferencia_erro || '');
    const transferButton = transferido ? '' : `
        <button type="button"
                class="btn btn-sm btn-outline-success btn-erp-transferir"
                title="Transferir chapa"
                aria-label="Transferir chapa"
                data-row='${escapeAttrJson(row)}'>
            <i class="fas fa-right-left"></i>
        </button>
    `;
    const apontarButton = transferido && !apontado ? `
        <button type="button"
                class="btn btn-sm btn-outline-primary btn-erp-apontar-corte"
                title="Apontar"
                aria-label="Apontar"
                data-row='${escapeAttrJson(row)}'>
            <i class="fas fa-clipboard-check"></i>
        </button>
    ` : '';

    return `
        <div class="d-inline-flex gap-1">
            ${transferButton}
            ${apontarButton}
            ${erro ? `
                <button type="button"
                        class="btn btn-sm btn-outline-danger btn-erro-apontamento-corte"
                        title="Ver erro"
                        aria-label="Ver erro"
                        data-erro="${escapeHtml(erro)}">
                    <i class="fas fa-triangle-exclamation"></i>
                </button>
            ` : ''}
        </div>
    `;
}

function badgeApontamento(row) {
    if (row.apontado) return '<span class="badge text-bg-success">Apontado</span>';
    if (row.erro_apontamento) return '<span class="badge text-bg-danger">Erro</span>';
    return '<span class="badge text-bg-light text-dark">Pendente</span>';
}

function erroVisivelAcoes(erro) {
    const texto = String(erro || '').trim();
    if (texto.toLowerCase() === 'chapa nao encontrada no cadastro.') return '';
    return texto;
}

function renderCodigoChapa(row) {
    if (!row.chapa_encontrada) {
        return '<span class="badge text-bg-danger">Nao encontrada</span>';
    }
    return escapeHtml(row.codigo_chapa || '-');
}

function formatPecaCodigo(peca) {
    const texto = String(peca || '').trim();
    return texto.replace(/^(\d{5})(\b|\s)/, '0$1$2');
}

function badgeTransferencia(status) {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'sucesso') return '<span class="badge text-bg-success">Sucesso</span>';
    if (normalized === 'erro') return '<span class="badge text-bg-danger">Erro</span>';
    if (normalized === 'pendente') return '<span class="badge text-bg-warning">Pendente</span>';
    if (normalized === 'ignorada') return '<span class="badge text-bg-secondary">Ignorada</span>';
    return '<span class="badge text-bg-light text-dark">Nao enviada</span>';
}

function updateRowTransferencia(itemId, transferencia) {
    const tr = tbody?.querySelector(`tr[data-item-id="${Number(itemId)}"]`);
    if (!tr || !transferencia) return;

    const cells = tr.querySelectorAll('td');
    if (cells.length < 19) return;

    const status = transferencia.status || '';
    const chave = transferencia.chave_transferencia || '';
    cells[12].innerHTML = badgeTransferencia(status);
    cells[13].textContent = chave || '-';
    cells[16].textContent = transferencia.transferido_em || '-';

    const transferido = String(status).toLowerCase() === 'sucesso';
    if (transferido && apontamentoSelecionado) {
        apontamentoSelecionado.transferencia_status = status;
        apontamentoSelecionado.chave_transferencia = chave;
        apontamentoSelecionado.transferido_em = transferencia.transferido_em || '';
        cells[0].innerHTML = renderSelectCheckbox(apontamentoSelecionado);
        cells[18].innerHTML = renderActionButtons(apontamentoSelecionado);
        bindActionButtonsWithin(tr);
    }
}

function updateRowApontamento(itemId, apontamento) {
    const tr = tbody?.querySelector(`tr[data-item-id="${Number(itemId)}"]`);
    if (!tr || !apontamento || !apontamentoSelecionado) return;

    const cells = tr.querySelectorAll('td');
    if (cells.length < 19) return;

    apontamentoSelecionado.apontado = true;
    apontamentoSelecionado.tipo_apontamento = apontamento.tipo_apontamento || apontamentoSelecionado.tipo_apontamento;
    apontamentoSelecionado.chave_apontamento = apontamento.chave_apontamento || '';
    apontamentoSelecionado.data_apontamento = apontamento.data_apontamento || apontamentoSelecionado.data_apontamento;
    apontamentoSelecionado.erro_apontamento = '';

    cells[14].innerHTML = badgeApontamento(apontamentoSelecionado);
    cells[15].textContent = apontamentoSelecionado.chave_apontamento || '-';
    cells[0].innerHTML = renderSelectCheckbox(apontamentoSelecionado);
    cells[18].innerHTML = renderActionButtons(apontamentoSelecionado);
    bindActionButtonsWithin(tr);
}

function renderPagination(pagination) {
    state.lastPagination = pagination;

    paginationInfoEl.textContent = `Pagina ${pagination.page} de ${pagination.total_pages} | ${pagination.total_items} registros`;
    resumoEl.textContent = `${pagination.total_items} transferencias de corte`;

    const controls = [];
    controls.push(buttonHtml('Anterior', pagination.has_previous, pagination.page - 1, 'btn-outline-secondary'));

    const totalPages = pagination.total_pages;
    const start = Math.max(1, pagination.page - 2);
    const end = Math.min(totalPages, pagination.page + 2);

    if (start > 1) {
        controls.push(pageButtonHtml(1, pagination.page));
        if (start > 2) controls.push('<span class="px-1 text-muted">...</span>');
    }

    for (let page = start; page <= end; page += 1) {
        controls.push(pageButtonHtml(page, pagination.page));
    }

    if (end < totalPages) {
        if (end < totalPages - 1) controls.push('<span class="px-1 text-muted">...</span>');
        controls.push(pageButtonHtml(totalPages, pagination.page));
    }

    controls.push(buttonHtml('Proxima', pagination.has_next, pagination.page + 1, 'btn-outline-secondary'));

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
    if (value === null || value === undefined || value === '') return '-';
    const num = Number(value);
    if (Number.isNaN(num)) return '-';
    return num.toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

function shortText(text, maxLength = 60) {
    const value = String(text || '').trim();
    if (value.length <= maxLength) return value;
    return `${value.slice(0, maxLength - 3)}...`;
}

function escapeHtml(text) {
    return String(text ?? '')
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

function bindActionButtonsWithin(container) {
    container.querySelectorAll('.btn-erro-apontamento-corte').forEach((btn) => {
        btn.addEventListener('click', () => {
            openErroModal(btn.getAttribute('data-erro') || '');
        });
    });

    container.querySelectorAll('.chk-apontamento-bloco').forEach((checkbox) => {
        checkbox.addEventListener('change', () => {
            const raw = checkbox.getAttribute('data-row');
            if (!raw) return;
            try {
                const row = JSON.parse(raw);
                if (checkbox.checked) {
                    apontamentosSelecionados.set(Number(row.id), row);
                } else {
                    apontamentosSelecionados.delete(Number(row.id));
                }
                updateBulkButton();
                updateMasterCheckbox();
            } catch (error) {
                console.error(error);
            }
        });
    });

    container.querySelectorAll('.btn-erp-apontar-corte').forEach((btn) => {
        btn.addEventListener('click', () => {
            const raw = btn.getAttribute('data-row');
            if (!raw) return;
            try {
                apontamentoSelecionado = JSON.parse(raw);
                openApontamentoModal(apontamentoSelecionado);
            } catch (error) {
                console.error(error);
            }
        });
    });

    container.querySelectorAll('.btn-erp-transferir').forEach((btn) => {
        btn.addEventListener('click', () => {
            const raw = btn.getAttribute('data-row');
            if (!raw) return;
            try {
                apontamentoSelecionado = JSON.parse(raw);
                openConfirmModal(apontamentoSelecionado);
            } catch (error) {
                console.error(error);
            }
        });
    });
}

function bindRowActionButtons() {
    bindActionButtonsWithin(tbody);
}

function openErroModal(erro) {
    if (!modalErroApontamentoCorteInstance || !erroApontamentoCorteTextoEl) return;
    erroApontamentoCorteTextoEl.textContent = erro || '-';
    modalErroApontamentoCorteInstance.show();
}

function updateBulkButton() {
    btnApontarEmBloco?.classList.toggle('d-none', apontamentosSelecionados.size === 0);
    if (btnApontarEmBloco) {
        btnApontarEmBloco.innerHTML = `<i class="fas fa-clipboard-check me-1"></i> Apontar em bloco (${apontamentosSelecionados.size})`;
    }
}

function updateMasterCheckbox() {
    if (!chkSelecionarTodosApontamentos || !tbody) return;

    const checkboxes = Array.from(tbody.querySelectorAll('.chk-apontamento-bloco:not(:disabled)'));
    const total = checkboxes.length;
    const selecionados = checkboxes.filter((checkbox) => checkbox.checked).length;

    chkSelecionarTodosApontamentos.disabled = total === 0;
    chkSelecionarTodosApontamentos.checked = total > 0 && selecionados === total;
    chkSelecionarTodosApontamentos.indeterminate = selecionados > 0 && selecionados < total;
}

function openConfirmModal(row) {
    if (!modalConfirmarApontamentoInstance) return;
    const codigoChapa = row.codigo_chapa || '-';
    const pesoTotal = row.peso_total ? `${formatNumber(row.peso_total)} kg` : '-';
    const quantidadeChapas = formatNumber(row.quantidade_chapas);
    modalResumoEl.innerHTML = `
        <div>Ordem ${escapeHtml(row.ordem || '-')} | Peca ${escapeHtml(row.peca || '-')} | Qtd. boa ${formatNumber(row.qtd_boa)} | Data produzida ${escapeHtml(row.data_producao || '-')}</div>
        <div class="mt-2 fw-semibold text-dark">Codigo da chapa que sera transferida: ${escapeHtml(codigoChapa)}</div>
        <div class="fw-semibold text-dark">Peso que sera transferido: ${escapeHtml(pesoTotal)}</div>
        <div class="text-dark">Quantidade de chapas: ${escapeHtml(quantidadeChapas)}</div>
        <div class="mt-1 text-dark">Chapa: ${escapeHtml(row.descricao_chapa || '-')}</div>
    `;
    transferenciaCodigoChapaEl.textContent = codigoChapa;
    transferenciaPesoTotalEl.textContent = pesoTotal;
    transferenciaQuantidadeChapasEl.textContent = quantidadeChapas;
    transferenciaDescricaoChapaEl.textContent = row.descricao_chapa || '-';
    modalConfirmarApontamentoInstance.show();
}

function openApontamentoModal(row) {
    if (!modalConfirmarApontamentoCorteInstance) return;
    modalApontamentoResumoEl.textContent = `Ordem ${row.ordem || '-'} | Peca ${row.peca || '-'} | Qtd. boa ${formatNumber(row.qtd_boa)} | Data produzida ${row.data_producao || '-'}`;
    modalConfirmarApontamentoCorteInstance.show();
}

function openDetailsModal(row) {
    if (!modalDetalhesApontamentoInstance) return;

    detalhesResumoEl.textContent = `Ordem ${row.ordem || '-'} | Peca ${row.peca || '-'} | Qtd. boa ${formatNumber(row.qtd_boa)}`;
    detalheDescricaoChapaEl.textContent = row.descricao_chapa || '-';
    detalheEspessuraPlanilhaEl.textContent = row.espessura_planilha || '-';
    detalheEspessuraMmEl.textContent = row.espessura_mm || '-';
    detalheCodigoChapaEl.textContent = row.codigo_chapa || '-';
    detalheQuantidadeChapasEl.textContent = formatNumber(row.quantidade_chapas);
    detalhePesoTotalEl.textContent = row.peso_total ? `${formatNumber(row.peso_total)} kg` : '-';
    detalheChapaEncontradaEl.textContent = row.chapa_encontrada ? 'Sim' : 'Nao';
    detalheTransferenciaStatusEl.textContent = row.transferencia_status || 'Nao enviada';
    detalheTransferidoEmEl.textContent = row.transferido_em || '-';
    detalheChaveTransferenciaEl.textContent = row.chave_transferencia || '-';
    detalheTransferenciaErroEl.textContent = row.transferencia_erro || '-';
    detalheApontamentoStatusEl.textContent = row.apontado ? 'Apontado' : 'Pendente';
    detalheTipoApontamentoEl.textContent = row.tipo_apontamento || '-';
    detalheDataApontamentoEl.textContent = row.data_apontamento || '-';
    detalheRespApontamentoEl.textContent = row.resp_apontamento || '-';
    detalheChaveApontamentoEl.textContent = row.chave_apontamento || '-';
    detalheErroApontamentoEl.textContent = row.erro_apontamento || '-';

    modalDetalhesApontamentoInstance.show();
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

    if (activeController) activeController.abort();
    const requestController = new AbortController();
    activeController = requestController;

    setLoading(true);
    tbody.innerHTML = `
        <tr>
            <td colspan="19" class="text-center text-muted py-4">
                <span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
                Consultando apontamentos...
            </td>
        </tr>
    `;
    resumoEl.textContent = 'Aplicando filtros...';
    try {
        const response = await fetch(`${apiUrl}?${params.toString()}`, {
            signal: requestController.signal,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const payload = await response.json();
        renderRows(payload.results || []);
        renderPagination(payload.pagination || {
            page: 1, total_pages: 1, total_items: 0, has_previous: false, has_next: false,
        });
    } catch (error) {
        if (error.name === 'AbortError') return;
        tbody.innerHTML = '<tr><td colspan="19" class="text-center text-danger py-4">Falha ao carregar as transferencias.</td></tr>';
        paginationControlsEl.innerHTML = '';
        paginationInfoEl.textContent = '-';
        resumoEl.textContent = 'Erro ao consultar dados';
        console.error(error);
    } finally {
        if (activeController === requestController) {
            setLoading(false);
            activeController = null;
        }
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

    chkSelecionarTodosApontamentos?.addEventListener('change', () => {
        const marcar = chkSelecionarTodosApontamentos.checked;
        tbody.querySelectorAll('.chk-apontamento-bloco:not(:disabled)').forEach((checkbox) => {
            checkbox.checked = marcar;
            const raw = checkbox.getAttribute('data-row');
            if (!raw) return;
            try {
                const row = JSON.parse(raw);
                if (marcar) {
                    apontamentosSelecionados.set(Number(row.id), row);
                } else {
                    apontamentosSelecionados.delete(Number(row.id));
                }
            } catch (error) {
                console.error(error);
            }
        });
        updateBulkButton();
        updateMasterCheckbox();
    });

    form.querySelectorAll('input[type="text"]').forEach((input) => {
        input.addEventListener('input', scheduleReload);
    });

    form.querySelectorAll('input[type="date"], select').forEach((field) => {
        field.addEventListener('change', () => loadPage(1));
    });

    btnConfirmarApontamentoERP?.addEventListener('click', () => {
        confirmarTransferenciaSelecionada('manual');
    });

    btnApontarViaApiERP?.addEventListener('click', () => {
        confirmarTransferenciaSelecionada('api');
    });

    btnConfirmarApontamentoCorteERP?.addEventListener('click', () => {
        confirmarApontamentoSelecionado('manual');
    });

    btnApontarCorteViaApiERP?.addEventListener('click', () => {
        confirmarApontamentoSelecionado('api');
    });

    btnApontarEmBloco?.addEventListener('click', () => {
        openApontamentoEmBlocoModal();
    });

    btnConfirmarApontamentoBlocoERP?.addEventListener('click', () => {
        confirmarApontamentoEmBloco('manual');
    });

    btnApontarBlocoViaApiERP?.addEventListener('click', () => {
        confirmarApontamentoEmBloco('api');
    });
}

function openApontamentoEmBlocoModal() {
    if (!modalApontamentoEmBlocoInstance || apontamentosSelecionados.size === 0) return;

    const itens = Array.from(apontamentosSelecionados.values());
    const preview = itens.slice(0, 5).map((row) => (
        `<div>Ordem ${escapeHtml(row.ordem || '-')} | Peca ${escapeHtml(shortText(row.peca || '-', 48))} | Qtd. boa ${formatNumber(row.qtd_boa)}</div>`
    )).join('');
    const restante = itens.length > 5 ? `<div class="mt-1">+ ${itens.length - 5} item(ns)</div>` : '';

    modalApontamentoBlocoResumoEl.innerHTML = `
        <div class="mb-2 fw-semibold text-dark">${itens.length} item(ns) selecionado(s)</div>
        ${preview}
        ${restante}
    `;
    modalApontamentoEmBlocoInstance.show();
}

async function confirmarTransferenciaSelecionada(tipoApontamento = 'api') {
    if (!apontamentoSelecionado?.id || !transferirUrlTemplate) return;

    const url = transferirUrlTemplate.replace('/0/transferir/', `/${apontamentoSelecionado.id}/transferir/`);
    const previousManualText = btnConfirmarApontamentoERP?.innerHTML;
    const previousApiText = btnApontarViaApiERP?.innerHTML;

    if (btnConfirmarApontamentoERP) {
        btnConfirmarApontamentoERP.disabled = true;
        btnConfirmarApontamentoERP.innerHTML = tipoApontamento === 'manual' ? 'Confirmando...' : previousManualText;
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
            throw new Error(payload.message || 'Falha ao confirmar transferencia.');
        }

        modalConfirmarApontamentoInstance?.hide();
        const transferencia = payload.transferencia || {};
        const transferenciaIgnorada = String(transferencia.status || '').toLowerCase() === 'ignorada';
        const chaveTransferencia = transferencia.chave_transferencia || '';
        updateRowTransferencia(apontamentoSelecionado.id, transferencia);
        if (window.Swal) {
            Swal.fire({
                icon: transferenciaIgnorada ? 'info' : 'success',
                title: transferenciaIgnorada ? 'Sem alteracao de ficha tecnica' : 'Transferido',
                text: transferenciaIgnorada
                    ? (payload.message || transferencia.motivo || 'Sem divergencia entre a chapa cadastrada e a chapa usada na ordem.')
                    : (chaveTransferencia
                        ? `Chave gerada: ${chaveTransferencia}`
                        : (tipoApontamento === 'api' ? 'Transferencia enviada via API.' : 'Transferencia registrada manualmente.')),
                timer: chaveTransferencia ? 2200 : 1600,
                showConfirmButton: false,
            });
        }
    } catch (error) {
        console.error(error);
        if (window.Swal) {
            Swal.fire({
                icon: 'error',
                title: 'Erro ao transferir',
                text: error.message || 'Nao foi possivel concluir a transferencia.',
            });
        }
    } finally {
        if (btnConfirmarApontamentoERP) {
            btnConfirmarApontamentoERP.disabled = false;
            btnConfirmarApontamentoERP.innerHTML = previousManualText || 'Transferir manualmente';
        }
        if (btnApontarViaApiERP) {
            btnApontarViaApiERP.disabled = false;
            btnApontarViaApiERP.innerHTML = previousApiText || 'Transferir via API';
        }
    }
}

async function confirmarApontamentoSelecionado(tipoApontamento = 'api') {
    if (!apontamentoSelecionado?.id || !apontarUrlTemplate) return;

    const url = apontarUrlTemplate.replace('/0/apontar/', `/${apontamentoSelecionado.id}/apontar/`);
    const previousManualText = btnConfirmarApontamentoCorteERP?.innerHTML;
    const previousApiText = btnApontarCorteViaApiERP?.innerHTML;

    if (btnConfirmarApontamentoCorteERP) {
        btnConfirmarApontamentoCorteERP.disabled = true;
        btnConfirmarApontamentoCorteERP.innerHTML = tipoApontamento === 'manual' ? 'Confirmando...' : previousManualText;
    }
    if (btnApontarCorteViaApiERP) {
        btnApontarCorteViaApiERP.disabled = true;
        btnApontarCorteViaApiERP.innerHTML = tipoApontamento === 'api' ? 'Confirmando...' : previousApiText;
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
            throw new Error(payload.description || payload.message || 'Falha ao confirmar apontamento.');
        }

        modalConfirmarApontamentoCorteInstance?.hide();
        updateRowApontamento(apontamentoSelecionado.id, payload);
        if (window.Swal) {
            Swal.fire({
                icon: 'success',
                title: 'Apontado',
                text: payload.chave_apontamento
                    ? `Chave gerada: ${payload.chave_apontamento}`
                    : 'Apontamento registrado com sucesso.',
                timer: 2200,
                showConfirmButton: false,
            });
        }
    } catch (error) {
        console.error(error);
        if (window.Swal) {
            Swal.fire({
                icon: 'error',
                title: 'Erro ao apontar',
                text: error.message || 'Nao foi possivel concluir o apontamento.',
            });
        }
    } finally {
        if (btnConfirmarApontamentoCorteERP) {
            btnConfirmarApontamentoCorteERP.disabled = false;
            btnConfirmarApontamentoCorteERP.innerHTML = previousManualText || 'Apontar manualmente';
        }
        if (btnApontarCorteViaApiERP) {
            btnApontarCorteViaApiERP.disabled = false;
            btnApontarCorteViaApiERP.innerHTML = previousApiText || 'Apontar via API';
        }
    }
}

async function confirmarApontamentoEmBloco(tipoApontamento = 'api') {
    const itens = Array.from(apontamentosSelecionados.values());
    if (!itens.length || !apontarBlocoUrl) return;

    const previousManualText = btnConfirmarApontamentoBlocoERP?.innerHTML;
    const previousApiText = btnApontarBlocoViaApiERP?.innerHTML;

    setBulkButtonsLoading(true, tipoApontamento, previousManualText, previousApiText);

    try {
        const response = await fetch(apontarBlocoUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({
                tipo_apontamento: tipoApontamento,
                ids: itens.map((row) => row.id),
            }),
        });

        const payload = await response.json();
        const sucessos = payload.sucessos || [];
        const erros = payload.erros || [];
        if (!response.ok && !sucessos.length) {
            throw new Error(payload.message || 'Falha ao confirmar apontamento em bloco.');
        }

        modalApontamentoEmBlocoInstance?.hide();
        if (window.Swal) {
            Swal.fire({
                icon: erros.length ? 'warning' : 'success',
                title: erros.length ? 'Apontamento em bloco concluido com alertas' : 'Apontamento em bloco concluido',
                html: `
                    <div class="text-start">
                        <div>Sucessos: ${sucessos.length}</div>
                        <div>Erros: ${erros.length}</div>
                        ${erros.length ? `<div class="mt-2 small text-danger">${escapeHtml(shortText(erros[0].erro || payload.message || '', 180))}</div>` : ''}
                    </div>
                `,
            });
        }

        apontamentosSelecionados.clear();
        updateBulkButton();
        await loadPage(state.page || 1);
    } catch (error) {
        console.error(error);
        if (window.Swal) {
            Swal.fire({
                icon: 'error',
                title: 'Erro ao apontar em bloco',
                text: error.message || 'Nao foi possivel concluir o apontamento em bloco.',
            });
        }
    } finally {
        setBulkButtonsLoading(false, tipoApontamento, previousManualText, previousApiText);
    }
}

function setBulkButtonsLoading(isLoading, tipoApontamento, previousManualText, previousApiText) {
    if (btnConfirmarApontamentoBlocoERP) {
        btnConfirmarApontamentoBlocoERP.disabled = isLoading;
        btnConfirmarApontamentoBlocoERP.innerHTML = isLoading && tipoApontamento === 'manual'
            ? 'Confirmando...'
            : (previousManualText || 'Apontar manualmente');
    }
    if (btnApontarBlocoViaApiERP) {
        btnApontarBlocoViaApiERP.disabled = isLoading;
        btnApontarBlocoViaApiERP.innerHTML = isLoading && tipoApontamento === 'api'
            ? 'Confirmando...'
            : (previousApiText || 'Apontar via API');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (!form || !tbody || !apiUrl) return;
    const modalConfirmarEl = document.getElementById('modalConfirmarApontamentoERP');
    const modalConfirmarApontamentoCorteEl = document.getElementById('modalConfirmarApontamentoCorte');
    const modalApontamentoEmBlocoEl = document.getElementById('modalApontamentoEmBlocoCorte');
    const modalErroApontamentoCorteEl = document.getElementById('modalErroApontamentoCorte');
    const modalDetalhesEl = document.getElementById('modalDetalhesApontamentoERP');
    if (modalConfirmarEl && window.bootstrap?.Modal) {
        modalConfirmarApontamentoInstance = new window.bootstrap.Modal(modalConfirmarEl);
    }
    if (modalDetalhesEl && window.bootstrap?.Modal) {
        modalDetalhesApontamentoInstance = new window.bootstrap.Modal(modalDetalhesEl);
    }
    if (modalConfirmarApontamentoCorteEl && window.bootstrap?.Modal) {
        modalConfirmarApontamentoCorteInstance = new window.bootstrap.Modal(modalConfirmarApontamentoCorteEl);
    }
    if (modalApontamentoEmBlocoEl && window.bootstrap?.Modal) {
        modalApontamentoEmBlocoInstance = new window.bootstrap.Modal(modalApontamentoEmBlocoEl);
    }
    if (modalErroApontamentoCorteEl && window.bootstrap?.Modal) {
        modalErroApontamentoCorteInstance = new window.bootstrap.Modal(modalErroApontamentoCorteEl);
    }
    bindEvents();
    loadPage(1);
});
