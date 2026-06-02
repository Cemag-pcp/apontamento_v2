/* compras.js - Analise de Compras */
'use strict';

const API_BASE = window.COMPRAS_API_BASE || '/compras/';

const URGENCY_ROW_CLASS = {
    PEDIDO_ATRASADO:   'urg-pedido',
    URGENTE:           'urg-critico',
    URGENTE_COM_PEDIDO:'urg-pedido',
    PRAZO_CURTO:       'urg-curto',
    PRAZO_OK:          'urg-ok',
    SEM_DADOS:         '',
};

const URGENCY_BADGE = {
    PEDIDO_ATRASADO:   '<span class="compras-badge pedido-pendente"><i class="fas fa-triangle-exclamation"></i> Ped. Atrasado</span>',
    URGENTE:           '<span class="compras-badge urgente"><i class="fas fa-arrow-down"></i> Urgente</span>',
    URGENTE_COM_PEDIDO:'<span class="compras-badge pedido-pendente"><i class="fas fa-truck"></i> Ped. Pendente</span>',
    PRAZO_CURTO:       '<span class="compras-badge curto"><i class="fas fa-clock"></i> Prazo curto</span>',
    PRAZO_OK:          '<span class="compras-badge ok"><i class="fas fa-check"></i> Em dia</span>',
    SEM_DADOS:         '<span class="compras-badge sem-dado">—</span>',
};

const SUGESTAO_COLORS = {
    critico: 'danger',
    urgente: 'warning',
    alerta: 'warning',
    info: 'info',
    ok: 'success',
    erro: 'secondary',
};

const DOLAR_REFRESH_INTERVAL_MS = 60 * 1000;
let produtoSelect2Inicializado = false;
let materiaisCache = [];
let sortDataCompraAsc = true;

function fmt(n, decimais = 2) {
    if (n === null || n === undefined || n === 9999) return '-';
    return Number(n).toLocaleString('pt-BR', {
        minimumFractionDigits: decimais,
        maximumFractionDigits: decimais,
    });
}

function fmtDolar(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '--';
    return Number(n).toLocaleString('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 4,
        maximumFractionDigits: 4,
    });
}

function extrairHoraCotacao(texto) {
    if (!texto) return '--:--';

    const match = String(texto).match(/(\d{2}):(\d{2})/);
    if (match) return `${match[1]}:${match[2]}`;

    return '--:--';
}

async function carregarCotacaoDolar(forceRefresh = false) {
    const widget = document.getElementById('cotacaoDolarWidget');
    const valor = document.getElementById('cotacaoDolarValor');
    const horario = document.getElementById('cotacaoDolarHorario');

    try {
        const qs = new URLSearchParams(forceRefresh ? { refresh: '1' } : {});
        const resp = await fetch(`${API_BASE}api/dolar/${qs.toString() ? `?${qs.toString()}` : ''}`);
        const data = await resp.json();
        if (!resp.ok || data.error) throw new Error(data.error || 'Falha ao consultar cotacao.');

        widget.classList.remove('is-error');
        valor.textContent = fmtDolar(data.cotacao_venda);
        horario.textContent = extrairHoraCotacao(data.data_hora_formatada || data.data_hora_cotacao);
    } catch (e) {
        widget.classList.add('is-error');
        valor.textContent = '--';
        horario.textContent = '--:--';
    }
}

function getParams() {
    return {
        codigo: document.getElementById('filtroCodigo').value,
        grupo: document.getElementById('filtroGrupo').value,
        urgencia: document.getElementById('filtroUrgencia').value,
        busca: document.getElementById('campoBusca').value,
    };
}

function inicializarFiltroProduto() {
    if (produtoSelect2Inicializado) return;

    $('#filtroCodigo').select2({
        theme: 'bootstrap-5',
        width: '100%',
        placeholder: 'Todos os produtos',
        allowClear: true,
    });

    produtoSelect2Inicializado = true;
}

function atualizarFiltroProduto(produtos, valorAtual = '') {
    const sel = document.getElementById('filtroCodigo');
    if (!sel) return;

    sel.innerHTML = '<option value="">Todos os produtos</option>';
    (produtos || []).forEach(produto => {
        const option = new Option(
            produto.rotulo || produto.codigo,
            produto.codigo,
            false,
            produto.codigo === valorAtual
        );
        sel.appendChild(option);
    });

    if (produtoSelect2Inicializado) {
        $('#filtroCodigo').trigger('change.select2');
    }
}

async function carregarMateriais(params = {}, forceRefresh = false) {
    document.getElementById('loadingTabela').style.display = 'block';
    document.getElementById('tabelaWrapper').style.display = 'none';
    document.getElementById('semResultados').style.display = 'none';
    document.getElementById('contadores').style.display = 'none !important';

    const qs = new URLSearchParams(
        Object.fromEntries(
            Object.entries({ ...params, refresh: forceRefresh ? '1' : undefined }).filter(([, v]) => v)
        )
    ).toString();

    let data;
    try {
        const resp = await fetch(`${API_BASE}api/material-direto/?${qs}`);
        data = await resp.json();
        if (data.error) throw new Error(data.error);
    } catch (e) {
        document.getElementById('loadingTabela').style.display = 'none';
        document.getElementById('tabelaWrapper').style.display = 'block';
        document.getElementById('bodyMateriais').innerHTML =
            `<tr><td colspan="14" class="text-center text-danger">Erro ao carregar dados: ${e.message}</td></tr>`;
        return;
    }

    if (!params.codigo && data.produtos && data.produtos.length) {
        const atual = document.getElementById('filtroCodigo').value;
        atualizarFiltroProduto(data.produtos, atual);
    }

    if (!params.grupo && data.grupos && data.grupos.length) {
        const sel = document.getElementById('filtroGrupo');
        const atual = sel.value;
        sel.innerHTML = '<option value="">Todos os grupos</option>';
        data.grupos.forEach(g => sel.appendChild(new Option(g, g, false, g === atual)));
    }

    materiaisCache = data.materiais;
    renderTabela(materiaisCache);
    atualizarContadores(materiaisCache);

    document.getElementById('ultimaAtualizacao').textContent =
        'Atualizado: ' + new Date().toLocaleTimeString('pt-BR');
    document.getElementById('loadingTabela').style.display = 'none';
}

function renderTabela(materiais) {
    const tbody = document.getElementById('bodyMateriais');
    tbody.innerHTML = '';

    if (!materiais.length) {
        document.getElementById('semResultados').style.display = 'block';
        return;
    }

    const fragment = document.createDocumentFragment();
    materiais.forEach(m => {
        const tr = document.createElement('tr');
        tr.className = URGENCY_ROW_CLASS[m.flag_urgencia] || '';
        tr.innerHTML = `
            <td class="col-codigo">${m.codigo}</td>
            <td>${m.descricao}</td>
            <td style="color:#888;font-size:12px;">${m.grupo || '-'}</td>
            <td class="num">${fmt(m.media_3m)}</td>
            <td class="num">${fmt(m.cons_mes_anterior)}</td>
            <td class="num">${fmt(m.simulado_pend_vendas)}</td>
            <td class="num">${fmt(m.dee_dias_em_est, 1)}</td>
            <td class="num">${fmt(m.estoque_almox_central ?? m.estoque_almox)}</td>
            <td class="num">${fmt(m.consumo_diario, 3)}</td>
            <td class="num">${m.dias_ate_zero === 9999 ? '∞' : fmt(m.dias_ate_zero, 1)}</td>
            <td class="num">${fmt(m.ped_compras)}</td>
            <td class="num">${fmt(m.estoque_minimo)}</td>
            <td style="font-size:12px;">${m.data_compra || '-'}</td>
            <td class="center">${URGENCY_BADGE[m.flag_urgencia] || ''}</td>
            <td class="center">
                <button class="btn btn-xs btn-outline-primary btn-grafico"
                    data-codigo="${m.codigo}" data-descricao="${m.descricao}" title="Ver gráfico">
                    <i class="fas fa-chart-line"></i>
                </button>
            </td>`;
        fragment.appendChild(tr);
    });

    tbody.appendChild(fragment);
    document.getElementById('tabelaWrapper').style.display = 'block';

    tbody.querySelectorAll('.btn-grafico').forEach(btn => {
        btn.addEventListener('click', () => carregarProjecao(btn.dataset.codigo, btn.dataset.descricao));
    });
}

function parseDateBR(str) {
    if (!str) return Infinity;
    const [d, m, y] = str.split('/');
    return new Date(`${y}-${m}-${d}`).getTime();
}

function ordenarPorDataCompra() {
    const sorted = [...materiaisCache].sort((a, b) => {
        const diff = parseDateBR(a.data_compra) - parseDateBR(b.data_compra);
        return sortDataCompraAsc ? diff : -diff;
    });
    const th = document.getElementById('thDataCompra');
    th.querySelector('.sort-icon').textContent = sortDataCompraAsc ? ' ↑' : ' ↓';
    sortDataCompraAsc = !sortDataCompraAsc;
    renderTabela(sorted);
}

function atualizarContadores(materiais) {
    const pedidoAtrasado = materiais.filter(m => m.flag_urgencia === 'PEDIDO_ATRASADO').length;
    const urgente = materiais.filter(m => m.flag_urgencia === 'URGENTE').length;
    const urgentePedido = materiais.filter(m => m.flag_urgencia === 'URGENTE_COM_PEDIDO').length;
    const curto = materiais.filter(m => m.flag_urgencia === 'PRAZO_CURTO').length;
    const ok = materiais.filter(m => m.flag_urgencia === 'PRAZO_OK').length;
    const semDados = materiais.filter(m => m.flag_urgencia === 'SEM_DADOS').length;

    document.getElementById('ctPedidoAtrasado').textContent = `${pedidoAtrasado} pedido atrasado`;
    document.getElementById('ctUrgente').textContent = `${urgente} urgentes`;
    document.getElementById('ctUrgentePedido').textContent = `${urgentePedido} c/ ped. pendente`;
    document.getElementById('ctPrazoCurto').textContent = `${curto} prazo curto`;
    document.getElementById('ctPrazoOk').textContent = `${ok} OK`;
    document.getElementById('ctSemDados').textContent = `${semDados} sem dados`;
    document.getElementById('ctTotal').textContent = `Total: ${materiais.length} materiais`;

    const el = document.getElementById('contadores');
    el.removeAttribute('style');
    el.style.display = 'flex';
}

let modalProjecao = null;
let modalSugestoes = null;
let codigoAtualProjecao = null;

function getModalProjecao() {
    if (!modalProjecao) {
        modalProjecao = new bootstrap.Modal(document.getElementById('modalProjecao'), {
            backdrop: true,
        });
    }
    return modalProjecao;
}

function getModalSugestoes() {
    if (!modalSugestoes) {
        modalSugestoes = new bootstrap.Modal(document.getElementById('modalSugestoesCompra'), {
            backdrop: false,
            focus: false,
        });
    }
    return modalSugestoes;
}

async function carregarProjecao(codigo, descricao) {
    codigoAtualProjecao = codigo;
    document.getElementById('tituloGrafico').textContent = `Projeção - ${codigo}: ${descricao}`;
    document.getElementById('tituloSugestoesCompra').textContent = `Sugestões - ${codigo}`;
    document.getElementById('loadingGrafico').style.display = 'block';
    document.getElementById('loadingSugestoes').style.display = 'block';
    document.getElementById('conteudoGrafico').style.display = 'none';
    document.getElementById('conteudoSugestoes').style.display = 'none';
    document.getElementById('plotlyDiv').innerHTML = '';
    document.getElementById('painelSugestoes').innerHTML = '';
    _resetAnaliseIA();

    getModalProjecao().show();
    getModalSugestoes().show();

    let data;
    try {
        const resp = await fetch(`${API_BASE}api/projecao/?codigo=${encodeURIComponent(codigo)}`);
        data = await resp.json();
        if (data.error) throw new Error(data.error);
    } catch (e) {
        document.getElementById('loadingGrafico').style.display = 'none';
        document.getElementById('loadingSugestoes').style.display = 'none';
        document.getElementById('conteudoGrafico').style.display = 'block';
        document.getElementById('conteudoSugestoes').style.display = 'block';
        document.getElementById('plotlyDiv').innerHTML = `<div class="alert alert-danger">Erro: ${e.message}</div>`;
        document.getElementById('painelSugestoes').innerHTML =
            `<div class="alert alert-danger mb-0">Erro: ${e.message}</div>`;
        return;
    }

    document.getElementById('loadingGrafico').style.display = 'none';
    document.getElementById('loadingSugestoes').style.display = 'none';
    document.getElementById('conteudoGrafico').style.display = 'block';
    document.getElementById('conteudoSugestoes').style.display = 'block';

    requestAnimationFrame(() => {
        renderPlotly(data);
        renderSugestoes(data.sugestoes || []);
    });

    // Verifica silenciosamente se já existe análise em cache
    _verificarCacheAnaliseIA(codigo);
}

function renderPlotly(data) {
    const real = data.serie_real || { datas: [], estoques: [] };
    const ideal = data.serie_ideal || { datas: [], estoques: [] };
    const min = data.estoque_minimo || 0;
    const chegadasPrevistas = data.chegadas_previstas || [];

    const allDatas = [...new Set([...real.datas, ...ideal.datas])].sort();
    const xMin = allDatas[0];
    const xMax = allDatas[allDatas.length - 1];

    const traces = [
        {
            x: real.datas, y: real.estoques,
            type: 'scatter', mode: 'lines',
            name: 'Consumo Real',
            line: { color: '#0d6efd', width: 2 },
        },
        {
            x: ideal.datas, y: ideal.estoques,
            type: 'scatter', mode: 'lines',
            name: 'Consumo Ideal',
            line: { color: '#198754', width: 2, dash: 'dot' },
        },
        {
            x: [xMin, xMax], y: [min, min],
            type: 'scatter', mode: 'lines',
            name: 'Estoque Minimo',
            line: { color: '#dc3545', width: 2, dash: 'dash' },
        },
        {
            x: [xMin, xMax], y: [0, 0],
            type: 'scatter', mode: 'lines',
            name: 'Estoque Zero',
            line: { color: '#6c757d', width: 1 },
        },
    ];

    if (chegadasPrevistas.length) {
        traces.push({
            x: chegadasPrevistas.map(item => item.data),
            y: chegadasPrevistas.map(item => item.estoque_apos_chegada),
            type: 'scatter',
            mode: 'markers',
            name: 'Chegada prevista',
            marker: {
                color: '#dc3545',
                size: 14,
                symbol: 'diamond',
                line: { color: '#ffffff', width: 2 },
            },
            text: chegadasPrevistas.map(item =>
                `Chegada prevista<br>Data: ${item.data}<br>Qtd: ${fmt(item.quantidade)}<br>Estoque após chegada: ${fmt(item.estoque_apos_chegada)}`
            ),
            hovertemplate: '%{text}<extra></extra>',
        });
    }

    const layout = {
        margin: { t: 20, b: 60, l: 60, r: 20 },
        xaxis: { title: 'Data', type: 'date', tickangle: -45 },
        yaxis: { title: 'Quantidade em Estoque' },
        legend: { orientation: 'h', y: -0.25 },
        hovermode: 'x unified',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        shapes: chegadasPrevistas.map(item => ({
            type: 'line',
            xref: 'x',
            yref: 'paper',
            x0: item.data,
            x1: item.data,
            y0: 0,
            y1: 1,
            line: {
                color: '#dc3545',
                width: 2,
                dash: 'dot',
            },
        })),
        annotations: chegadasPrevistas.map(item => ({
            x: item.data,
            y: 0.94,
            xref: 'x',
            yref: 'paper',
            text: 'Bandeira chegada',
            showarrow: true,
            arrowhead: 2,
            ax: 0,
            ay: -18,
            bgcolor: '#dc3545',
            bordercolor: '#dc3545',
            font: {
                color: '#ffffff',
                size: 10,
            },
            opacity: 0.95,
        })),
    };

    Plotly.newPlot('plotlyDiv', traces, layout, {
        responsive: true,
        displayModeBar: false,
    });
}

const SUGESTAO_CONFIG = {
    critico: {
        icon: 'fas fa-circle-exclamation',
        accentColor: '#dc3545',
        bgColor: '#fff5f5',
        borderColor: '#f5c2c7',
        labelColor: '#b02a37',
        label: 'SITUAÇÃO CRÍTICA',
    },
    urgente: {
        icon: 'fas fa-triangle-exclamation',
        accentColor: '#d97706',
        bgColor: '#fffbeb',
        borderColor: '#fde68a',
        labelColor: '#92400e',
        label: 'AÇÃO URGENTE',
    },
    alerta: {
        icon: 'fas fa-clock',
        accentColor: '#ca8a04',
        bgColor: '#fefce8',
        borderColor: '#fef08a',
        labelColor: '#713f12',
        label: 'ALERTA PREVENTIVO',
    },
    info: {
        icon: 'fas fa-box-open',
        accentColor: '#0284c7',
        bgColor: '#f0f9ff',
        borderColor: '#bae6fd',
        labelColor: '#075985',
        label: 'PEDIDO PENDENTE',
    },
    ok: {
        icon: 'fas fa-circle-check',
        accentColor: '#16a34a',
        bgColor: '#f0fdf4',
        borderColor: '#bbf7d0',
        labelColor: '#15803d',
        label: 'SITUAÇÃO CONTROLADA',
    },
    erro: {
        icon: 'fas fa-ban',
        accentColor: '#6b7280',
        bgColor: '#f9fafb',
        borderColor: '#e5e7eb',
        labelColor: '#374151',
        label: 'AVISO',
    },
};

function _formatarMensagemSugestao(mensagem) {
    // Converte **texto** → <strong>texto</strong>
    return mensagem
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function renderSugestoes(sugestoes) {
    const painel = document.getElementById('painelSugestoes');
    if (!sugestoes || !sugestoes.length) {
        painel.innerHTML = `
            <div class="sugestao-vazia">
                <i class="fas fa-info-circle"></i>
                Sem sugestões disponíveis para este material.
            </div>`;
        return;
    }

    painel.innerHTML = sugestoes.map(s => {
        const cfg = SUGESTAO_CONFIG[s.tipo] || SUGESTAO_CONFIG.erro;

        const qtdBlock = (s.qtd_sugerida !== null && s.qtd_sugerida !== undefined)
            ? `<div class="sugestao-qtd-box" style="border-color:${cfg.accentColor}; color:${cfg.accentColor};">
                    <span class="sugestao-qtd-label">Quantidade sugerida para compra</span>
                    <span class="sugestao-qtd-valor">${fmt(s.qtd_sugerida)} <small>unidades</small></span>
               </div>`
            : '';

        const mensagemHtml = _formatarMensagemSugestao(s.mensagem || '');

        return `
        <div class="sugestao-card" style="background:${cfg.bgColor}; border-color:${cfg.borderColor}; border-left-color:${cfg.accentColor};">
            <div class="sugestao-card-header">
                <span class="sugestao-tipo-badge" style="background:${cfg.accentColor};">
                    <i class="${cfg.icon}"></i> ${cfg.label}
                </span>
            </div>
            <div class="sugestao-card-titulo" style="color:${cfg.labelColor};">
                ${s.titulo}
            </div>
            <p class="sugestao-mensagem">${mensagemHtml}</p>
            ${qtdBlock}
        </div>`;
    }).join('');
}

function _resetAnaliseIA() {
    document.getElementById('btnAnaliseIA').innerHTML = '<i class="fas fa-robot me-1"></i> Analisar com IA';
    document.getElementById('btnAnaliseIA').disabled = true;
    document.getElementById('textoAnaliseIA').style.display = 'none';
    document.getElementById('textoAnaliseIA').textContent = '';
    document.getElementById('dataAnaliseIA').style.display = 'none';
    document.getElementById('dataAnaliseIA').textContent = '';
    document.getElementById('loadingAnaliseIA').style.display = 'none';
}

function _mostrarAnalise(texto, criadoEm, fromCache) {
    document.getElementById('textoAnaliseIA').textContent = texto;
    document.getElementById('textoAnaliseIA').style.display = 'block';
    if (criadoEm) {
        const label = fromCache ? 'Análise salva em' : 'Análise gerada em';
        document.getElementById('dataAnaliseIA').textContent = `${label}: ${criadoEm}`;
        document.getElementById('dataAnaliseIA').style.display = 'block';
    }
    document.getElementById('btnAnaliseIA').innerHTML = '<i class="fas fa-rotate-right me-1"></i> Re-analisar com IA';
    document.getElementById('btnAnaliseIA').disabled = false;
    document.getElementById('loadingAnaliseIA').style.display = 'none';
}

async function _verificarCacheAnaliseIA(codigo) {
    try {
        const resp = await fetch(`${API_BASE}api/analise-ia/?codigo=${encodeURIComponent(codigo)}&check_only=1`);
        const data = await resp.json();
        if (data.analise) {
            _mostrarAnalise(data.analise, data.criado_em, true);
        } else {
            // Sem cache: habilita o botão para o usuário gerar
            document.getElementById('btnAnaliseIA').disabled = false;
        }
    } catch (_) {
        document.getElementById('btnAnaliseIA').disabled = false;
    }
}

async function carregarAnaliseIA(force = false) {
    if (!codigoAtualProjecao) return;
    document.getElementById('btnAnaliseIA').disabled = true;
    document.getElementById('loadingAnaliseIA').style.display = 'block';
    document.getElementById('textoAnaliseIA').style.display = 'none';
    document.getElementById('dataAnaliseIA').style.display = 'none';

    const qs = new URLSearchParams({ codigo: codigoAtualProjecao });
    if (force) qs.set('force', '1');

    try {
        const resp = await fetch(`${API_BASE}api/analise-ia/?${qs}`);
        const data = await resp.json();
        if (data.error) throw new Error(data.error);
        _mostrarAnalise(data.analise, data.criado_em, data.from_cache);
    } catch (e) {
        document.getElementById('textoAnaliseIA').textContent = `Erro: ${e.message}`;
        document.getElementById('textoAnaliseIA').style.display = 'block';
        document.getElementById('btnAnaliseIA').disabled = false;
        document.getElementById('loadingAnaliseIA').style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    inicializarFiltroProduto();
    carregarMateriais();
    carregarCotacaoDolar();
    window.setInterval(() => carregarCotacaoDolar(), DOLAR_REFRESH_INTERVAL_MS);

    document.getElementById('btnAnaliseIA').addEventListener('click', () => {
        const jaTemAnalise = document.getElementById('textoAnaliseIA').style.display !== 'none';
        carregarAnaliseIA(jaTemAnalise);
    });

    document.getElementById('btnFiltrar').addEventListener('click', () => {
        carregarMateriais(getParams());
    });

    document.getElementById('campoBusca').addEventListener('keydown', e => {
        if (e.key === 'Enter') carregarMateriais(getParams());
    });

    document.getElementById('btnRefresh').addEventListener('click', () => {
        carregarMateriais(getParams(), true);
        carregarCotacaoDolar(true);
    });

    document.getElementById('modalProjecao').addEventListener('hidden.bs.modal', () => {
        Plotly.purge('plotlyDiv');
        if (modalSugestoes) modalSugestoes.hide();
    });
});
