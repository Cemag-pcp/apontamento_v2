'use strict';

const COLUMNS = [
    { id: 'regiao', label: 'Região' },
    { id: 'uf', label: 'UF' },
    { id: 'observacao', label: 'Observação' },
    { id: 'localidade', label: 'Localidade' },
    { id: 'chcriacao', label: 'Ch Criação' },
    { id: 'emissao', label: 'Emissão' },
    { id: 'prev_emissao', label: 'Prev. Emissão Doc' },
    { id: 'programacao', label: 'Programação' },
    { id: 'classe', label: 'Classe' },
    { id: 'pessoa', label: 'Pessoa' },
    { id: 'recurso_codigo', label: 'Recurso Código' },
    { id: 'recurso_nome', label: 'Recurso Nome' },
    { id: 'recurso_classe', label: 'Recurso Classe' },
    { id: 'numero_serie', label: 'Número Série' },
    { id: 'nucleo', label: 'Núcleo' },
    { id: 'quantidade', label: 'Quantidade' },
    { id: 'unitario', label: 'Unitário' },
    { id: 'total', label: 'Total' },
    { id: 'descricao', label: 'Descrição Genérica' },
    { id: 'representante', label: 'Representante' },
    { id: 'id_negociacao', label: 'ID Negociação' },
    { id: 'acao', label: 'Ação', locked: true },
];

const COL_STORAGE_KEY = 'confPedidoVisibleColumns';

let aguardandoCache = [];
let conferidosCache = [];
let activeTab = 'aguardando';
let currentModalPedido = null;
let currentPage = 1;
let totalAguardando = 0;
let totalPagesAguardando = 1;

function formatDateInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function getCsrfToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
}

function formatDateTime(value) {
    if (!value) {
        return 'N/D';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return date.toLocaleString('pt-BR');
}

function formatDecimal(value) {
    if (value === null || value === undefined || value === '') {
        return 'N/D';
    }

    const numeric = Number(String(value).replace(',', '.'));
    if (Number.isNaN(numeric)) {
        return escapeHtml(value);
    }

    return numeric.toLocaleString('pt-BR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 4,
    });
}

const DEFAULT_VISIBLE_COLUMNS = new Set([
    'chcriacao', 'emissao', 'prev_emissao', 'pessoa',
    'recurso_codigo', 'numero_serie', 'total', 'id_negociacao', 'acao',
]);

function loadColumnVisibility() {
    try {
        const stored = localStorage.getItem(COL_STORAGE_KEY);
        const parsed = stored ? JSON.parse(stored) : null;
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            return parsed;
        }
    } catch {}
    return Object.fromEntries(COLUMNS.map((col) => [col.id, DEFAULT_VISIBLE_COLUMNS.has(col.id)]));
}

function saveColumnVisibility(visibility) {
    localStorage.setItem(COL_STORAGE_KEY, JSON.stringify(visibility));
}

function getVisibleColCount() {
    const visibility = loadColumnVisibility();
    return COLUMNS.filter((col) => visibility[col.id] !== false).length;
}

function applyColumnVisibility(visibility) {
    let styleEl = document.getElementById('confPedidoColStyle');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'confPedidoColStyle';
        document.head.appendChild(styleEl);
    }
    const rules = COLUMNS
        .filter((col) => visibility[col.id] === false)
        .map((col) => `[data-col="${col.id}"] { display: none; }`)
        .join('\n');
    styleEl.textContent = rules;

    const colCount = COLUMNS.filter((col) => visibility[col.id] !== false).length;
    document.querySelectorAll('#confPedidoTableBody td[colspan]').forEach((td) => {
        td.setAttribute('colspan', colCount);
    });
}

function buildColunasDropdown(visibility) {
    const menu = document.getElementById('colunasMenu');
    if (!menu) { console.error('[colunas] #colunasMenu não encontrado'); return; }

    const cols = (typeof COLUMNS !== 'undefined' ? COLUMNS : []).filter((col) => !col.locked);
    console.log('[colunas] populando', cols.length, 'colunas');

    if (!cols.length) {
        menu.innerHTML = '<p class="px-2 mb-0 text-muted small">Nenhuma coluna disponível.</p>';
        return;
    }

    menu.innerHTML = cols
        .map((col) => `
            <div class="form-check mb-1">
                <input
                    class="form-check-input col-toggle-check"
                    type="checkbox"
                    id="colCheck_${col.id}"
                    data-col-id="${col.id}"
                    ${visibility[col.id] !== false ? 'checked' : ''}
                >
                <label class="form-check-label user-select-none" for="colCheck_${col.id}">
                    ${col.label}
                </label>
            </div>
        `).join('');

    menu.querySelectorAll('.col-toggle-check').forEach((checkbox) => {
        checkbox.addEventListener('change', () => {
            const vis = loadColumnVisibility();
            vis[checkbox.dataset.colId] = checkbox.checked;
            saveColumnVisibility(vis);
            applyColumnVisibility(vis);
        });
    });
}

function getPloomesKey(item) {
    return String(item.codigo_produto ?? '').trim().toUpperCase();
}

function getPedidoKey(row) {
    return [
        row.id_negociacao ?? '',
        row.chcriacao ?? '',
    ].join('|');
}

function agruparPedidos(rows) {
    const grouped = new Map();

    (rows || []).forEach((row) => {
        const key = getPedidoKey(row);
        if (!grouped.has(key)) {
            grouped.set(key, {
                regiao_nome: row.regiao_nome,
                uf_codigo: row.uf_codigo,
                observacao: row.observacao,
                localidade_codigo: row.localidade_codigo,
                chcriacao: row.chcriacao,
                emissao: row.emissao,
                previsaoemissaodoc: row.previsaoemissaodoc,
                programaca: row.programaca,
                classe_nome: row.classe_nome,
                pessoa_codigo: row.pessoa_codigo,
                nucleo_codigo: row.nucleo_codigo,
                representa_codigo: row.representa_codigo,
                id_negociacao: row.id_negociacao,
                quantidade_total: 0,
                total_geral: 0,
                itens: [],
                conferencia: row.conferencia || null,
            });
        }

        const pedido = grouped.get(key);
        pedido.itens.push({
            recurso_codigo: row.recurso_codigo,
            recurso_nome: row.recurso_nome,
            recurso_classe_nome: row.recurso_classe_nome,
            numero_serie: row.numero_serie,
            quantidade: row.quantidade,
            unitario: row.unitario,
            total: row.total,
            descricaogenerica: row.descricaogenerica,
        });
        pedido.quantidade_total += Number(String(row.quantidade ?? 0).replace(',', '.')) || 0;
        pedido.total_geral += Number(String(row.total ?? 0).replace(',', '.')) || 0;
    });

    return Array.from(grouped.values());
}

function renderItensResumo(itens) {
    if (!itens?.length) {
        return 'N/D';
    }

    if (itens.length === 1) {
        return escapeHtml(itens[0].recurso_codigo ?? 'N/D');
    }

    return `
        <div class="comercial-item-summary">
            <strong>${itens.length} itens</strong>
            <span>${escapeHtml(itens[0].recurso_codigo ?? 'N/D')} +${itens.length - 1}</span>
        </div>
    `;
}

function renderSerieResumo(itens) {
    if (!itens?.length) {
        return 'N/D';
    }

    const series = itens
        .map((item) => item.numero_serie || '')
        .filter(Boolean);

    if (!series.length) {
        return 'Sem série';
    }

    if (series.length === 1) {
        return escapeHtml(series[0]);
    }

    return `${escapeHtml(series[0])} +${series.length - 1}`;
}


function setStatus(message, type = 'info') {
    const status = document.getElementById('confPedidoStatus');
    status.className = `alert alert-${type} mt-3 mb-0`;
    status.textContent = message;
}

function setTotal(total) {
    document.getElementById('confPedidoTotal').textContent = `${total} pedido${total === 1 ? '' : 's'}`;
}

function getConferenciaInfo(row) {
    return conferidosCache.find((item) => getPedidoKey(item) === getPedidoKey(row))?.conferencia || null;
}

function isConferido(row) {
    return Boolean(getConferenciaInfo(row));
}

function updateTabCounts() {
    document.getElementById('countAguardando').textContent = totalAguardando;
    document.getElementById('countConferidos').textContent = conferidosCache.length;
}

function updateTabsUI() {
    const filtros = document.getElementById('confPedidoFiltros');
    const filtrosConferidos = document.getElementById('confPedidoFiltrosConferidos');

    document.querySelectorAll('.comercial-tab').forEach((button) => {
        const isActive = button.dataset.tab === activeTab;
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    if (filtros) {
        filtros.style.display = activeTab === 'aguardando' ? '' : 'none';
    }

    if (filtrosConferidos) {
        filtrosConferidos.style.display = activeTab === 'conferidos' ? '' : 'none';
    }
}

function getConferidosFiltros() {
    return {
        conferido_por: document.getElementById('filtroConferidoPor')?.value || '',
        data_conferencia_inicio: document.getElementById('dataConferenciaInicio')?.value || '',
        data_conferencia_fim: document.getElementById('dataConferenciaFim')?.value || '',
    };
}

function getAguardandoFiltros() {
    return {
        data_inicio: document.getElementById('dataInicio')?.value || '',
        data_fim: document.getElementById('dataFim')?.value || '',
        classe: document.getElementById('filtroClasse')?.value || '',
        pessoa: document.getElementById('filtroPessoa')?.value || '',
        numero_serie: document.getElementById('filtroNumeroSerie')?.value || '',
        id_negociacao: document.getElementById('filtroIdNegociacao')?.value || '',
        chcriacao: document.getElementById('filtroChCriacao')?.value || '',
    };
}

function renderPaginacao(page, totalPages) {
    const nav = document.getElementById('confPedidoPaginacao');
    const lista = document.getElementById('confPedidoPaginacaoLista');

    if (activeTab !== 'aguardando' || totalPages <= 1) {
        nav.style.display = 'none';
        return;
    }

    nav.style.display = '';

    const maxVisible = 5;
    let startPage = Math.max(1, page - Math.floor(maxVisible / 2));
    const endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    const items = [];

    items.push(`<li class="page-item ${page === 1 ? 'disabled' : ''}">
        <button class="page-link" data-page="${page - 1}" aria-label="Anterior">&laquo;</button>
    </li>`);

    if (startPage > 1) {
        items.push(`<li class="page-item"><button class="page-link" data-page="1">1</button></li>`);
        if (startPage > 2) {
            items.push(`<li class="page-item disabled"><span class="page-link">&hellip;</span></li>`);
        }
    }

    for (let p = startPage; p <= endPage; p++) {
        items.push(`<li class="page-item ${p === page ? 'active' : ''}">
            <button class="page-link" data-page="${p}">${p}</button>
        </li>`);
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            items.push(`<li class="page-item disabled"><span class="page-link">&hellip;</span></li>`);
        }
        items.push(`<li class="page-item"><button class="page-link" data-page="${totalPages}">${totalPages}</button></li>`);
    }

    items.push(`<li class="page-item ${page === totalPages ? 'disabled' : ''}">
        <button class="page-link" data-page="${page + 1}" aria-label="Próximo">&raquo;</button>
    </li>`);

    lista.innerHTML = items.join('');

    lista.querySelectorAll('button[data-page]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const p = parseInt(btn.dataset.page, 10);
            if (p >= 1 && p <= totalPages && p !== currentPage) {
                buscarConfPedido(p);
            }
        });
    });
}

function renderRows(rows) {
    const tbody = document.getElementById('confPedidoTableBody');

    if (!rows.length) {
        const emptyText = activeTab === 'conferidos'
            ? 'Nenhum pedido conferido encontrado.'
            : 'Nenhum pedido aguardando conferência neste período.';
        tbody.innerHTML = `<tr><td colspan="${getVisibleColCount()}" class="text-center text-muted py-4">${emptyText}</td></tr>`;
        return;
    }

    tbody.innerHTML = rows.map((row) => `
        <tr>
            <td data-col="regiao">${escapeHtml(row.regiao_nome ?? 'N/D')}</td>
            <td data-col="uf">${escapeHtml(row.uf_codigo ?? 'N/D')}</td>
            <td data-col="observacao">${escapeHtml(row.observacao ?? '')}</td>
            <td data-col="localidade">${escapeHtml(row.localidade_codigo ?? 'N/D')}</td>
            <td data-col="chcriacao">${escapeHtml(row.chcriacao ?? 'N/D')}</td>
            <td data-col="emissao">${escapeHtml(row.emissao ?? '')}</td>
            <td data-col="prev_emissao">${escapeHtml(row.previsaoemissaodoc ?? '')}</td>
            <td data-col="programacao">${escapeHtml(row.programaca ?? '')}</td>
            <td data-col="classe">${escapeHtml(row.classe_nome ?? 'N/D')}</td>
            <td data-col="pessoa">${escapeHtml(row.pessoa_codigo ?? 'N/D')}</td>
            <td data-col="recurso_codigo">${renderItensResumo(row.itens || [])}</td>
            <td data-col="recurso_nome">${escapeHtml(row.itens?.length === 1 ? (row.itens[0].recurso_nome ?? 'N/D') : `${row.itens?.length || 0} itens no pedido`)}</td>
            <td data-col="recurso_classe">${escapeHtml(row.itens?.length === 1 ? (row.itens[0].recurso_classe_nome ?? 'N/D') : 'Múltiplas linhas')}</td>
            <td data-col="numero_serie">${renderSerieResumo(row.itens || [])}</td>
            <td data-col="nucleo">${escapeHtml(row.nucleo_codigo ?? 'N/D')}</td>
            <td data-col="quantidade">${formatDecimal(row.quantidade_total)}</td>
            <td data-col="unitario">${escapeHtml(row.itens?.length === 1 ? formatDecimal(row.itens[0].unitario) : 'Múltiplos')}</td>
            <td data-col="total">${formatDecimal(row.total_geral)}</td>
            <td data-col="descricao">${escapeHtml(row.itens?.length === 1 ? (row.itens[0].descricaogenerica ?? 'N/D') : 'Múltiplos')}</td>
            <td data-col="representante">${escapeHtml(row.representa_codigo ?? 'N/D')}</td>
            <td data-col="id_negociacao">${escapeHtml(row.id_negociacao ?? 'N/D')}</td>
            <td data-col="acao">
                <button
                    type="button"
                    class="btn btn-sm btn-outline-primary btn-conferir-pedido"
                    data-pedido="${escapeHtml(JSON.stringify(row))}"
                >
                    Conferir
                </button>
            </td>
        </tr>
    `).join('');

    tbody.querySelectorAll('.btn-conferir-pedido').forEach((button) => {
        button.addEventListener('click', () => {
            const row = JSON.parse(button.dataset.pedido);
            abrirModalConferencia(row);
        });
    });
}

function renderItensPloomes(rows) {
    const tbody = document.getElementById('confPedidoItensPloomes');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Nenhum item retornado pela Ploomes.</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map((item, index) => {
        const qtd = item.quantidade != null
            ? formatDecimal(item.quantidade)
            : 'N/D';
        return `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(item.codigo_produto ?? 'N/D')}</td>
            <td>${escapeHtml(item.cor ?? 'N/D')}</td>
            <td>${qtd}</td>
        </tr>`;
    }).join('');
}

function renderObsPloomes(rows) {
    const container = document.getElementById('confPedidoObsPloomes');
    const observacoes = [...new Set((rows || []).map((item) => String(item.observacao ?? '').trim()).filter(Boolean))];

    if (!observacoes.length) {
        container.innerHTML = `
            <div class="comercial-detail-row">
                <div class="comercial-detail-label">Observação</div>
                <div class="comercial-detail-value">Sem observação</div>
            </div>
        `;
        return;
    }

    container.innerHTML = observacoes.map((observacao, index) => `
        <div class="comercial-detail-row">
            <div class="comercial-detail-label">Observação ${index + 1}</div>
            <div class="comercial-detail-value">${escapeHtml(observacao)}</div>
        </div>
    `).join('');
}

async function carregarPloomesParaPedido(row) {
    const params = new URLSearchParams();
    if (row.id_negociacao) {
        params.set('id_negociacao', row.id_negociacao);
    }
    if (row.chcriacao) {
        params.set('chcriacao', row.chcriacao);
    }

    const response = await fetch(`/comercial/api/conf-pedido/ploomes/?${params.toString()}`);
    const data = await response.json();

    if (!response.ok || data.error) {
        throw new Error(data.error || 'Falha ao consultar Ploomes.');
    }

    return data.results || [];
}

async function abrirModalConferencia(row) {
    const detalhes = document.getElementById('confPedidoDetalhes');
    const itensBody = document.getElementById('confPedidoItens');
    const obsPloomes = document.getElementById('confPedidoObsPloomes');
    const conferenciaSection = document.getElementById('confPedidoConferenciaSection');
    const conferenciaDetalhes = document.getElementById('confPedidoConferenciaDetalhes');
    const titulo = document.getElementById('modalConferirPedidoLabel');
    const btnMarcar = document.getElementById('btnMarcarConferido');
    const btnDesfazer = document.getElementById('btnDesfazerConferencia');
    const conferenciaInfo = row.conferencia || getConferenciaInfo(row);
    currentModalPedido = row;

    titulo.textContent = `Conferir pedido ${row.chcriacao ?? 'N/D'}`;

    detalhes.innerHTML = [
        { label: 'ID Negociação', value: row.id_negociacao },
        { label: 'Ch Criação', value: row.chcriacao },
        { label: 'Pessoa', value: row.pessoa_codigo },
        { label: 'Localidade', value: row.localidade_codigo },
        { label: 'UF', value: row.uf_codigo },
        { label: 'Região', value: row.regiao_nome },
        { label: 'Emissão', value: row.emissao },
        { label: 'Programação', value: row.programaca },
        { label: 'Prev. Emissão Doc', value: row.previsaoemissaodoc },
        { label: 'Observação', value: row.observacao || 'Sem observação' },
        { label: 'Núcleo', value: row.nucleo_codigo },
        { label: 'Representante', value: row.representa_codigo },
        { label: 'Quantidade de itens', value: String(row.itens?.length || 0) },
    ].map((item) => `
        <div class="comercial-detail-row">
            <div class="comercial-detail-label">${escapeHtml(item.label)}</div>
            <div class="comercial-detail-value">${escapeHtml(item.value ?? 'N/D')}</div>
        </div>
    `).join('');

    itensBody.innerHTML = (row.itens || []).map((item, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(item.recurso_codigo ?? 'N/D')}</td>
            <td>${escapeHtml(item.recurso_nome ?? 'N/D')}</td>
            <td>${escapeHtml(item.numero_serie ?? '')}</td>
        </tr>
    `).join('');

    currentPloomesRows = [];
    renderItensPloomes([]);
    obsPloomes.innerHTML = `
        <div class="comercial-detail-row">
            <div class="comercial-detail-label">Observação</div>
            <div class="comercial-detail-value">Carregando...</div>
        </div>
    `;

    document.getElementById('confPedidoAgenteSection').style.display = 'none';
    document.getElementById('confPedidoAgenteResultado').textContent = '';

    if (conferenciaInfo) {
        conferenciaSection.style.display = '';
        conferenciaDetalhes.innerHTML = [
            { label: 'Conferido por', value: conferenciaInfo.conferido_por || 'N/D' },
            { label: 'Quando conferiu', value: formatDateTime(conferenciaInfo.conferido_em) },
        ].map((item) => `
            <div class="comercial-detail-row">
                <div class="comercial-detail-label">${escapeHtml(item.label)}</div>
                <div class="comercial-detail-value">${escapeHtml(item.value ?? 'N/D')}</div>
            </div>
        `).join('');
    } else {
        conferenciaSection.style.display = 'none';
        conferenciaDetalhes.innerHTML = '';
    }

    btnMarcar.disabled = Boolean(conferenciaInfo);
    btnMarcar.textContent = conferenciaInfo ? 'Já conferido' : 'Marcar como conferido';
    btnDesfazer.style.display = conferenciaInfo ? '' : 'none';

    const modalEl = document.getElementById('modalConferirPedido');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    try {
        const ploomesRows = await carregarPloomesParaPedido(row);
        if (currentModalPedido && getPedidoKey(currentModalPedido) === getPedidoKey(row)) {
            currentPloomesRows = ploomesRows;
            renderItensPloomes(ploomesRows);
            renderObsPloomes(ploomesRows);
        }
    } catch (error) {
        if (currentModalPedido && getPedidoKey(currentModalPedido) === getPedidoKey(row)) {
            const errorRows = [{
                chave_pedido: '',
                deal_id: '',
                data_criacao: '',
                quote_id: '',
                contato: '',
                codigo_produto: '',
                cor: '',
                observacao: error.message,
            }];
            renderItensPloomes(errorRows);
            renderObsPloomes(errorRows);
        }
    }
}

async function carregarConferidos({ silent = false } = {}) {
    const params = new URLSearchParams(
        Object.entries(getConferidosFiltros()).filter(([, value]) => value)
    );

    try {
        const response = await fetch(`/comercial/api/conferidos/?${params.toString()}`);
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || 'Falha ao carregar conferidos.');
        }

        conferidosCache = agruparPedidos(data.results || []);
        updateTabCounts();

        if (activeTab === 'conferidos') {
            renderRows(conferidosCache);
            setTotal(conferidosCache.length);
        }
    } catch (error) {
        if (!silent) {
            setStatus(error.message, 'danger');
        }
    }
}

async function buscarConfPedido(page = 1) {
    const filtros = getAguardandoFiltros();

    setStatus('Consultando itens da pendência comercial...', 'info');

    try {
        const params = new URLSearchParams(
            Object.entries({ ...filtros, page: String(page) }).filter(([, value]) => value),
        );
        const response = await fetch(`/comercial/api/conf-pedido/?${params.toString()}`);
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || 'Falha ao consultar registros.');
        }

        currentPage = data.page ?? page;
        totalAguardando = data.total ?? 0;
        totalPagesAguardando = data.total_pages ?? 1;

        aguardandoCache = agruparPedidos(data.results || []);
        updateTabCounts();

        if (activeTab === 'aguardando') {
            renderRows(aguardandoCache);
            setTotal(totalAguardando);
            renderPaginacao(currentPage, totalPagesAguardando);
        }

        document.getElementById('confPedidoStatus').style.display = 'none';
    } catch (error) {
        aguardandoCache = [];
        totalAguardando = 0;
        totalPagesAguardando = 1;
        currentPage = 1;
        updateTabCounts();
        renderRows([]);
        renderPaginacao(1, 1);
        setTotal(0);
        setStatus(error.message, 'danger');
    }
}

async function marcarPedidoComoConferido() {
    if (!currentModalPedido || isConferido(currentModalPedido)) {
        return;
    }

    const response = await fetch('/comercial/api/conf-pedido/conferir/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(currentModalPedido),
    });
    const data = await response.json();

    if (!response.ok || data.error) {
        throw new Error(data.error || 'Falha ao conferir pedido.');
    }

    if (data.result) {
        const grouped = agruparPedidos([data.result])[0];
        conferidosCache = [grouped, ...conferidosCache.filter((item) => getPedidoKey(item) !== getPedidoKey(grouped))];
    }
}

let currentPloomesRows = [];


function renderMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text.trim());
    html = html.replace(/^## (.+)$/gm, '<h6 class="fw-bold mt-2 mb-1">$1</h6>');
    html = html.replace(/^### (.+)$/gm, '<strong class="d-block mt-2 mb-1">$1</strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`([^`\n]+)`/g, '<code class="px-1 rounded" style="background:#e9ecef;font-size:.85em">$1</code>');
    html = html.replace(/^[\-\*] (.+)$/gm, '<li class="mb-1">$1</li>');
    html = html.replace(/(<li[\s\S]*?<\/li>\n?)+/g, (m) => `<ul class="mb-1 ps-3">${m}</ul>`);
    html = html.replace(/\n{2,}/g, '</p><p class="mb-1">');
    html = html.replace(/\n/g, '<br>');
    return `<p class="mb-1">${html}</p>`;
}

function renderAgenteResultado(data) {
    const resultado = document.getElementById('confPedidoAgenteResultado');

    // fallback: raw text (parse error or old format)
    if (!data || !Array.isArray(data.itens)) {
        const raw = typeof data === 'string' ? data : (data?.analise ?? JSON.stringify(data));
        const texto = typeof raw === 'string' ? raw : JSON.stringify(raw);
        resultado.innerHTML = renderMarkdown(texto);
        return;
    }

    const statusConsistente = (data.status || '').toUpperCase() === 'CONSISTENTE';
    const statusIcon = statusConsistente ? '✅' : '⚠️';
    const statusClass = statusConsistente ? 'text-success' : 'text-warning';

    const rows = data.itens.map((item) => {
        // divergencia = ERP está errado; crm_divergencia = CRM está errado (independente)
        const erpErrado = !!item.divergencia;
        const crmErrado = !!item.crm_divergencia;
        const rowClass = erpErrado ? 'table-danger' : (crmErrado ? 'table-warning' : '');
        const iaClass = erpErrado ? 'fw-bold text-danger' : 'fw-bold text-success';
        const crmBadge = crmErrado ? ' <span class="badge bg-warning text-dark ms-1" title="CRM precisa ser atualizado">CRM ⚠</span>' : '';
        const motivo = item.motivo && item.motivo !== '—' ? escapeHtml(item.motivo) : '';
        return `
            <tr class="${rowClass}">
                <td class="font-monospace small">${escapeHtml(item.erp || '—')}</td>
                <td class="font-monospace small">${escapeHtml(item.crm || '—')}${crmBadge}</td>
                <td class="font-monospace small ${iaClass}">${escapeHtml(item.ia || '—')}</td>
                <td class="small text-muted fst-italic">${motivo}</td>
            </tr>`;
    }).join('');

    resultado.innerHTML = `
        <div class="table-responsive mb-2">
            <table class="table table-sm table-bordered mb-0">
                <thead class="table-light">
                    <tr>
                        <th>ERP</th>
                        <th>CRM</th>
                        <th>Código sugerido</th>
                        <th>O que a IA detectou</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
        <div class="small ${statusClass} fw-semibold mt-1">
            ${statusIcon} ${escapeHtml(data.status || '')}${data.resumo ? ' — ' + escapeHtml(data.resumo) : ''}
        </div>`;
}

function agregarItensPorCodigo(itens) {
    const mapa = new Map();
    for (const item of itens) {
        const cod = String(item.recurso_codigo || 'N/D').trim();
        if (!mapa.has(cod)) {
            mapa.set(cod, { ...item, quantidade: 0 });
        }
        mapa.get(cod).quantidade += parseFloat(item.quantidade ?? 0) || 0;
    }
    return [...mapa.values()];
}

async function analisarComAgente() {
    const btnAnalisar = document.getElementById('btnAnalisarAgente');
    const section = document.getElementById('confPedidoAgenteSection');
    const resultado = document.getElementById('confPedidoAgenteResultado');

    if (!currentModalPedido) {
        return;
    }

    btnAnalisar.disabled = true;
    btnAnalisar.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Analisando...';
    section.style.display = '';
    resultado.textContent = 'Aguarde, o agente está analisando o pedido...';

    const observacoes = [...new Set(
        currentPloomesRows.map((r) => String(r.observacao ?? '').trim()).filter(Boolean),
    )];

    try {
        const response = await fetch('/comercial/api/conf-pedido/agente/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                itens_innovaro: agregarItensPorCodigo(currentModalPedido.itens || []),
                itens_ploomes: currentPloomesRows,
                observacoes,
            }),
        });
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || 'Falha ao executar análise.');
        }

        renderAgenteResultado(data);
    } catch (error) {
        resultado.textContent = `Erro: ${error.message}`;
    } finally {
        btnAnalisar.disabled = false;
        btnAnalisar.innerHTML = '<i class="bi bi-robot me-1"></i> Analisar com IA';
    }
}

async function desfazerConferenciaPedido() {
    if (!currentModalPedido || !isConferido(currentModalPedido)) {
        return;
    }

    const response = await fetch('/comercial/api/conf-pedido/desfazer/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(currentModalPedido),
    });
    const data = await response.json();

    if (!response.ok || data.error) {
        throw new Error(data.error || 'Falha ao desfazer conferência.');
    }

    conferidosCache = conferidosCache.filter((item) => getPedidoKey(item) !== getPedidoKey(currentModalPedido));
}

async function handleTabChange(tab) {
    activeTab = tab;
    updateTabsUI();

    if (tab === 'conferidos') {
        await carregarConferidos();
        renderRows(conferidosCache);
        setTotal(conferidosCache.length);
        renderPaginacao(1, 1);
        return;
    }

    renderRows(aguardandoCache);
    setTotal(totalAguardando);
    renderPaginacao(currentPage, totalPagesAguardando);
}

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('btnToggleColunas').addEventListener('show.bs.dropdown', () => {
        buildColunasDropdown(loadColumnVisibility());
    });

    applyColumnVisibility(loadColumnVisibility());
    buildColunasDropdown(loadColumnVisibility());

    updateTabsUI();
    await carregarConferidos({ silent: true });
    await buscarConfPedido(1);

    document.getElementById('tabAguardando').addEventListener('click', () => handleTabChange('aguardando'));
    document.getElementById('tabConferidos').addEventListener('click', () => handleTabChange('conferidos'));
    document.getElementById('btnFiltrarConferidos').addEventListener('click', () => handleTabChange('conferidos'));
    document.getElementById('btnBuscarAguardando').addEventListener('click', () => buscarConfPedido(1));

    document.getElementById('dataInicio').addEventListener('change', () => {
        if (activeTab === 'aguardando') {
            buscarConfPedido(1);
        }
    });
    document.getElementById('dataFim').addEventListener('change', () => {
        if (activeTab === 'aguardando') {
            buscarConfPedido(1);
        }
    });

    ['filtroClasse', 'filtroPessoa', 'filtroNumeroSerie', 'filtroIdNegociacao', 'filtroChCriacao'].forEach((id) => {
        document.getElementById(id)?.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && activeTab === 'aguardando') {
                buscarConfPedido(1);
            }
        });
    });

    document.getElementById('filtroConferidoPor').addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            handleTabChange('conferidos');
        }
    });
    document.getElementById('dataConferenciaInicio').addEventListener('change', () => {
        if (activeTab === 'conferidos') {
            handleTabChange('conferidos');
        }
    });
    document.getElementById('dataConferenciaFim').addEventListener('change', () => {
        if (activeTab === 'conferidos') {
            handleTabChange('conferidos');
        }
    });
    document.getElementById('btnMarcarConferido').addEventListener('click', async () => {
        try {
            await marcarPedidoComoConferido();

            const modalEl = document.getElementById('modalConferirPedido');
            bootstrap.Modal.getOrCreateInstance(modalEl).hide();

            await buscarConfPedido(currentPage);
            updateTabCounts();
            setStatus('Pedido marcado como conferido.', 'success');
        } catch (error) {
            setStatus(error.message, 'danger');
        }
    });
    document.getElementById('btnAnalisarAgente').addEventListener('click', () => {
        analisarComAgente();
    });
    document.getElementById('btnDesfazerConferencia').addEventListener('click', () => {
        if (!currentModalPedido || !isConferido(currentModalPedido)) {
            return;
        }

        const confirmModalEl = document.getElementById('modalConfirmarDesfazerConferencia');
        const confirmModal = bootstrap.Modal.getOrCreateInstance(confirmModalEl);
        confirmModal.show();
    });
    document.getElementById('btnConfirmarDesfazerConferencia').addEventListener('click', async () => {
        try {
            await desfazerConferenciaPedido();

            const modalEl = document.getElementById('modalConferirPedido');
            bootstrap.Modal.getOrCreateInstance(modalEl).hide();

            const confirmModalEl = document.getElementById('modalConfirmarDesfazerConferencia');
            bootstrap.Modal.getOrCreateInstance(confirmModalEl).hide();

            activeTab = 'aguardando';
            updateTabsUI();
            await buscarConfPedido(currentPage);
            updateTabCounts();
            setStatus('Conferência desfeita. O pedido voltou para Aguardando conferência.', 'warning');
        } catch (error) {
            setStatus(error.message, 'danger');
        }
    });
});
