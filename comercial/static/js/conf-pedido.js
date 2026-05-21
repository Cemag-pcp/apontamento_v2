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

function formatDateOnlyInput(date) {
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

function getPedidoKey(row) {
    return [
        row.chave_pedido ?? '',
        row.deal_id ?? '',
        row.quote_id ?? '',
    ].join('|');
}

function getCorStyle(cor) {
    const colorMap = {
        AMARELO: '#facc15',
        AMARELA: '#facc15',
        AZUL: '#2563eb',
        AZUL_CLARO: '#38bdf8',
        BEGE: '#d6b88d',
        BRANCO: '#f8fafc',
        BRANCA: '#f8fafc',
        CINZA: '#6b7280',
        CINZA_CLARO: '#94a3b8',
        LARANJA: '#f97316',
        MARROM: '#92400e',
        PRETO: '#111827',
        PRETA: '#111827',
        ROSA: '#ec4899',
        ROXO: '#7c3aed',
        VERDE: '#16a34a',
        VERMELHO: '#dc2626',
        VERMELHA: '#dc2626',
    };

    const normalized = String(cor ?? '')
        .trim()
        .toUpperCase()
        .replaceAll(' ', '_');

    const background = colorMap[normalized] || '#cbd5e1';
    const border = normalized === 'BRANCO' || normalized === 'BRANCA' ? '#cbd5e1' : background;

    return { background, border };
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

function agruparPedidos(rows) {
    const grouped = new Map();

    rows.forEach((row) => {
        const key = getPedidoKey(row);
        if (!grouped.has(key)) {
            grouped.set(key, {
                chave_pedido: row.chave_pedido,
                deal_id: row.deal_id,
                data_criacao: row.data_criacao,
                quote_id: row.quote_id,
                contato: row.contato,
                observacao: row.observacao,
                itens: [],
            });
        }

        grouped.get(key).itens.push({
            codigo_produto: row.codigo_produto,
            cor: row.cor,
        });
    });

    return Array.from(grouped.values());
}

function getConferenciaInfo(pedido) {
    return conferidosCache.find((item) => getPedidoKey(item) === getPedidoKey(pedido))?.conferencia || null;
}

function isConferido(pedido) {
    return Boolean(getConferenciaInfo(pedido));
}

function mergeConferenciaInfo(pedido) {
    const info = getConferenciaInfo(pedido);
    return info ? { ...pedido, conferencia: info } : pedido;
}

function updateTabCounts() {
    document.getElementById('countAguardando').textContent = aguardandoCache.filter((pedido) => !isConferido(pedido)).length;
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

function renderCorCell(cor) {
    const safeCor = escapeHtml(cor ?? 'N/D');
    const styles = getCorStyle(cor);
    return `
        <span class="comercial-color-cell">
            <span
                class="comercial-color-flag"
                style="background:${styles.background};border-color:${styles.border};"
            ></span>
            <span>${safeCor}</span>
        </span>
    `;
}

function renderCorResumo(itens) {
    if (!itens.length) {
        return 'N/D';
    }

    const cores = [...new Set(itens.map((item) => item.cor || 'N/D'))];
    if (cores.length === 1) {
        return renderCorCell(cores[0]);
    }

    return `
        <span class="comercial-color-cell">
            <span class="comercial-color-flag comercial-color-flag-multi"></span>
            <span>Múltiplas</span>
        </span>
    `;
}

function renderItensResumo(itens) {
    if (!itens.length) {
        return 'N/D';
    }

    if (itens.length === 1) {
        return escapeHtml(itens[0].codigo_produto ?? 'N/D');
    }

    const primeiro = escapeHtml(itens[0].codigo_produto ?? 'N/D');
    return `
        <div class="comercial-item-summary">
            <strong>${itens.length} itens</strong>
            <span>${primeiro} +${itens.length - 1}</span>
        </div>
    `;
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

    return aguardandoCache.filter((pedido) => !isConferido(pedido)).map(mergeConferenciaInfo);
}

function renderRows(rows) {
    const tbody = document.getElementById('confPedidoTableBody');

    if (!rows.length) {
        const emptyText = activeTab === 'conferidos'
            ? 'Nenhum pedido conferido encontrado.'
            : 'Nenhum pedido aguardando conferência neste período.';
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">${emptyText}</td></tr>`;
        return;
    }

    tbody.innerHTML = rows.map((pedido) => `
        <tr>
            <td>${escapeHtml(pedido.chave_pedido ?? 'N/D')}</td>
            <td>${escapeHtml(pedido.deal_id ?? 'N/D')}</td>
            <td>${escapeHtml(pedido.data_criacao ?? '')}</td>
            <td>${escapeHtml(pedido.quote_id ?? 'N/D')}</td>
            <td>${escapeHtml(pedido.contato ?? 'N/D')}</td>
            <td>${renderItensResumo(pedido.itens || [])}</td>
            <td>${renderCorResumo(pedido.itens || [])}</td>
            <td>
                <button
                    type="button"
                    class="btn btn-sm btn-outline-primary btn-conferir-pedido"
                    data-pedido="${escapeHtml(JSON.stringify(pedido))}"
                >
                    Conferir
                </button>
            </td>
        </tr>
    `).join('');

    tbody.querySelectorAll('.btn-conferir-pedido').forEach((button) => {
        button.addEventListener('click', () => {
            const pedido = JSON.parse(button.dataset.pedido);
            abrirModalConferencia(pedido);
        });
    });
}

function abrirModalConferencia(pedido) {
    const detalhes = document.getElementById('confPedidoDetalhes');
    const itensBody = document.getElementById('confPedidoItens');
    const conferenciaSection = document.getElementById('confPedidoConferenciaSection');
    const conferenciaDetalhes = document.getElementById('confPedidoConferenciaDetalhes');
    const titulo = document.getElementById('modalConferirPedidoLabel');
    const btnMarcar = document.getElementById('btnMarcarConferido');
    const btnDesfazer = document.getElementById('btnDesfazerConferencia');
    const conferenciaInfo = pedido.conferencia || getConferenciaInfo(pedido);
    currentModalPedido = pedido;

    titulo.textContent = `Conferir pedido ${pedido.chave_pedido ?? 'N/D'}`;

    detalhes.innerHTML = [
        { label: 'Chave do Pedido', value: pedido.chave_pedido },
        { label: 'Deal ID', value: pedido.deal_id },
        { label: 'Data Criação', value: pedido.data_criacao },
        { label: 'Quote ID', value: pedido.quote_id },
        { label: 'Contato', value: pedido.contato },
        { label: 'Quantidade de Itens', value: pedido.itens?.length ?? 0 },
        { label: 'Observação', value: pedido.observacao || 'Sem observação' },
    ].map((item) => `
        <div class="comercial-detail-row">
            <div class="comercial-detail-label">${escapeHtml(item.label)}</div>
            <div class="comercial-detail-value">${escapeHtml(item.value ?? 'N/D')}</div>
        </div>
    `).join('');

    itensBody.innerHTML = (pedido.itens || []).map((item, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(item.codigo_produto ?? 'N/D')}</td>
            <td>${renderCorCell(item.cor)}</td>
        </tr>
    `).join('');

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

        conferidosCache = data.results || [];
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
    const botao = document.getElementById('btnBuscarConfPedido');

    if (!dataInicio || !dataFim) {
        setStatus('Preencha a data início e a data fim.', 'warning');
        return;
    }

    botao.disabled = true;
    botao.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Buscando';
    setStatus('Consultando pedidos na Ploomes...', 'info');

    try {
        const params = new URLSearchParams({
            data_inicio: dataInicio,
            data_fim: dataFim,
        });
        const response = await fetch(`/comercial/api/conf-pedido/?${params.toString()}`);
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || 'Falha ao consultar pedidos.');
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
    } finally {
        botao.disabled = false;
        botao.innerHTML = '<i class="bi bi-search me-1"></i> Buscar';
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
        conferidosCache = [data.result, ...conferidosCache.filter((item) => getPedidoKey(item) !== getPedidoKey(data.result))];
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

    document.getElementById('btnBuscarConfPedido').addEventListener('click', buscarConfPedido);
    document.getElementById('tabAguardando').addEventListener('click', () => handleTabChange('aguardando'));
    document.getElementById('tabConferidos').addEventListener('click', () => handleTabChange('conferidos'));
    document.getElementById('btnFiltrarConferidos').addEventListener('click', () => handleTabChange('conferidos'));
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
