'use strict';

let aguardandoCache = [];
let conferidosCache = [];
let activeTab = 'aguardando';
let currentModalPedido = null;

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

function setPeriodoPadrao() {
    const hoje = new Date();
    const primeiroDia = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
    document.getElementById('dataInicio').value = formatDateInput(primeiroDia);
    document.getElementById('dataFim').value = formatDateInput(hoje);
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

function mergeConferenciaInfo(row) {
    const info = getConferenciaInfo(row);
    return info ? { ...row, conferencia: info } : row;
}

function updateTabCounts() {
    document.getElementById('countAguardando').textContent = aguardandoCache.filter((row) => !isConferido(row)).length;
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

function getResultadosFiltrados() {
    if (activeTab === 'conferidos') {
        return conferidosCache;
    }

    return aguardandoCache.filter((row) => !isConferido(row)).map(mergeConferenciaInfo);
}

function renderRows(rows) {
    const tbody = document.getElementById('confPedidoTableBody');

    if (!rows.length) {
        const emptyText = activeTab === 'conferidos'
            ? 'Nenhum pedido conferido encontrado.'
            : 'Nenhum pedido aguardando conferência neste período.';
        tbody.innerHTML = `<tr><td colspan="22" class="text-center text-muted py-4">${emptyText}</td></tr>`;
        return;
    }

    tbody.innerHTML = rows.map((row) => `
        <tr>
            <td>${escapeHtml(row.regiao_nome ?? 'N/D')}</td>
            <td>${escapeHtml(row.uf_codigo ?? 'N/D')}</td>
            <td>${escapeHtml(row.observacao ?? '')}</td>
            <td>${escapeHtml(row.localidade_codigo ?? 'N/D')}</td>
            <td>${escapeHtml(row.chcriacao ?? 'N/D')}</td>
            <td>${escapeHtml(row.emissao ?? '')}</td>
            <td>${escapeHtml(row.previsaoemissaodoc ?? '')}</td>
            <td>${escapeHtml(row.programaca ?? '')}</td>
            <td>${escapeHtml(row.classe_nome ?? 'N/D')}</td>
            <td>${escapeHtml(row.pessoa_codigo ?? 'N/D')}</td>
            <td>${renderItensResumo(row.itens || [])}</td>
            <td>${escapeHtml(row.itens?.length === 1 ? (row.itens[0].recurso_nome ?? 'N/D') : `${row.itens?.length || 0} itens no pedido`)}</td>
            <td>${escapeHtml(row.itens?.length === 1 ? (row.itens[0].recurso_classe_nome ?? 'N/D') : 'Múltiplas linhas')}</td>
            <td>${renderSerieResumo(row.itens || [])}</td>
            <td>${escapeHtml(row.nucleo_codigo ?? 'N/D')}</td>
            <td>${formatDecimal(row.quantidade_total)}</td>
            <td>${escapeHtml(row.itens?.length === 1 ? formatDecimal(row.itens[0].unitario) : 'Múltiplos')}</td>
            <td>${formatDecimal(row.total_geral)}</td>
            <td>${escapeHtml(row.itens?.length === 1 ? (row.itens[0].descricaogenerica ?? 'N/D') : 'Múltiplos')}</td>
            <td>${escapeHtml(row.representa_codigo ?? 'N/D')}</td>
            <td>${escapeHtml(row.id_negociacao ?? 'N/D')}</td>
            <td>
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
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-3">Nenhum item retornado pela Ploomes.</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map((item, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(item.codigo_produto ?? 'N/D')}</td>
            <td>${escapeHtml(item.cor ?? 'N/D')}</td>
        </tr>
    `).join('');
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

async function buscarConfPedido() {
    const dataInicio = document.getElementById('dataInicio').value;
    const dataFim = document.getElementById('dataFim').value;

    if (!dataInicio || !dataFim) {
        setStatus('Preencha a data emissão início e a data emissão fim.', 'warning');
        return;
    }

    setStatus('Consultando itens da pendência comercial...', 'info');

    try {
        const params = new URLSearchParams({
            data_inicio: dataInicio,
            data_fim: dataFim,
        });
        const response = await fetch(`/comercial/api/conf-pedido/?${params.toString()}`);
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || 'Falha ao consultar registros.');
        }

        aguardandoCache = agruparPedidos(data.results || []);
        updateTabCounts();
        renderRows(getResultadosFiltrados());
        setTotal(getResultadosFiltrados().length);
        setStatus(`Consulta concluída. ${aguardandoCache.length} pedido(s) encontrado(s).`, 'success');
    } catch (error) {
        aguardandoCache = [];
        renderRows([]);
        updateTabCounts();
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

    const observacoes = [
        ...(currentModalPedido.observacao ? [currentModalPedido.observacao] : []),
        ...currentPloomesRows.map((r) => r.observacao).filter(Boolean),
    ];

    try {
        const response = await fetch('/comercial/api/conf-pedido/agente/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                itens_innovaro: currentModalPedido.itens || [],
                itens_ploomes: currentPloomesRows,
                observacoes,
            }),
        });
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || 'Falha ao executar análise.');
        }

        resultado.textContent = data.analise;
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
        return;
    }

    const filtrados = getResultadosFiltrados();
    renderRows(filtrados);
    setTotal(filtrados.length);
}

document.addEventListener('DOMContentLoaded', async () => {
    setPeriodoPadrao();
    updateTabsUI();
    await carregarConferidos({ silent: true });
    await buscarConfPedido();

    document.getElementById('tabAguardando').addEventListener('click', () => handleTabChange('aguardando'));
    document.getElementById('tabConferidos').addEventListener('click', () => handleTabChange('conferidos'));
    document.getElementById('btnFiltrarConferidos').addEventListener('click', () => handleTabChange('conferidos'));
    document.getElementById('dataInicio').addEventListener('change', () => {
        if (activeTab === 'aguardando') {
            buscarConfPedido();
        }
    });
    document.getElementById('dataFim').addEventListener('change', () => {
        if (activeTab === 'aguardando') {
            buscarConfPedido();
        }
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
            updateTabCounts();
            await handleTabChange(activeTab);

            const modalEl = document.getElementById('modalConferirPedido');
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.hide();
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
            updateTabCounts();
            activeTab = 'aguardando';
            await handleTabChange('aguardando');

            const modalEl = document.getElementById('modalConferirPedido');
            bootstrap.Modal.getOrCreateInstance(modalEl).hide();

            const confirmModalEl = document.getElementById('modalConfirmarDesfazerConferencia');
            bootstrap.Modal.getOrCreateInstance(confirmModalEl).hide();

            setStatus('Conferência desfeita. O pedido voltou para Aguardando conferência.', 'warning');
        } catch (error) {
            setStatus(error.message, 'danger');
        }
    });
});
