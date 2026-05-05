/* compras.js - Analise de Compras */
'use strict';

const URGENCY_ROW_CLASS = {
    URGENTE: 'table-danger',
    PRAZO_CURTO: 'table-warning',
    PRAZO_OK: 'table-success',
    SEM_DADOS: '',
};

const URGENCY_BADGE = {
    URGENTE: '<span class="badge bg-danger">Urgente</span>',
    PRAZO_CURTO: '<span class="badge bg-warning text-dark">Prazo Curto</span>',
    PRAZO_OK: '<span class="badge bg-success">Prazo OK</span>',
    SEM_DADOS: '<span class="badge bg-secondary">-</span>',
};

const SUGESTAO_COLORS = {
    critico: 'danger',
    urgente: 'warning',
    alerta: 'warning',
    info: 'info',
    ok: 'success',
    erro: 'secondary',
};

function fmt(n, decimais = 2) {
    if (n === null || n === undefined || n === 9999) return '-';
    return Number(n).toLocaleString('pt-BR', {
        minimumFractionDigits: decimais,
        maximumFractionDigits: decimais,
    });
}

function getParams() {
    return {
        codigo: document.getElementById('filtroCodigo').value,
        grupo: document.getElementById('filtroGrupo').value,
        urgencia: document.getElementById('filtroUrgencia').value,
        busca: document.getElementById('campoBusca').value,
    };
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
        const resp = await fetch(`/compras/api/material-direto/?${qs}`);
        data = await resp.json();
        if (data.error) throw new Error(data.error);
    } catch (e) {
        document.getElementById('loadingTabela').style.display = 'none';
        document.getElementById('tabelaWrapper').style.display = 'block';
        document.getElementById('bodyMateriais').innerHTML =
            `<tr><td colspan="11" class="text-center text-danger">Erro ao carregar dados: ${e.message}</td></tr>`;
        return;
    }

    if (!params.codigo && data.codigos && data.codigos.length) {
        const sel = document.getElementById('filtroCodigo');
        const atual = sel.value;
        sel.innerHTML = '<option value="">Todos os produtos</option>';
        data.codigos.forEach(c => sel.appendChild(new Option(c, c, false, c === atual)));
    }

    if (!params.grupo && data.grupos && data.grupos.length) {
        const sel = document.getElementById('filtroGrupo');
        const atual = sel.value;
        sel.innerHTML = '<option value="">Todos os grupos</option>';
        data.grupos.forEach(g => sel.appendChild(new Option(g, g, false, g === atual)));
    }

    renderTabela(data.materiais);
    atualizarContadores(data.materiais);

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
            <td class="font-monospace">${m.codigo}</td>
            <td>${m.descricao}</td>
            <td><small class="text-muted">${m.grupo || '-'}</small></td>
            <td class="text-end">${fmt(m.media_3m)}</td>
            <td class="text-end">${fmt(m.estoque_almox)}</td>
            <td class="text-end">${fmt(m.consumo_diario, 3)}</td>
            <td class="text-end">${m.dias_ate_zero === 9999 ? '∞' : fmt(m.dias_ate_zero, 1)}</td>
            <td class="text-end">${fmt(m.ped_compras)}</td>
            <td class="text-end">${fmt(m.estoque_minimo)}</td>
            <td><small>${m.data_compra || '-'}</small></td>
            <td>${URGENCY_BADGE[m.flag_urgencia] || ''}</td>
            <td class="text-center">
                <button class="btn btn-xs btn-outline-primary btn-grafico"
                    data-codigo="${m.codigo}" data-descricao="${m.descricao}" title="Ver grafico">
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

function atualizarContadores(materiais) {
    const urgente = materiais.filter(m => m.flag_urgencia === 'URGENTE').length;
    const curto = materiais.filter(m => m.flag_urgencia === 'PRAZO_CURTO').length;
    const ok = materiais.filter(m => m.flag_urgencia === 'PRAZO_OK').length;

    document.getElementById('ctUrgente').textContent = `${urgente} urgentes`;
    document.getElementById('ctPrazoCurto').textContent = `${curto} prazo curto`;
    document.getElementById('ctPrazoOk').textContent = `${ok} OK`;
    document.getElementById('ctTotal').textContent = `Total: ${materiais.length} materiais`;

    const el = document.getElementById('contadores');
    el.removeAttribute('style');
    el.style.display = 'flex';
}

let modalProjecao = null;
let modalSugestoes = null;

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
    document.getElementById('tituloGrafico').textContent = `Projeção - ${codigo}: ${descricao}`;
    document.getElementById('tituloSugestoesCompra').textContent = `Sugestoes - ${codigo}`;
    document.getElementById('loadingGrafico').style.display = 'block';
    document.getElementById('loadingSugestoes').style.display = 'block';
    document.getElementById('conteudoGrafico').style.display = 'none';
    document.getElementById('conteudoSugestoes').style.display = 'none';
    document.getElementById('plotlyDiv').innerHTML = '';
    document.getElementById('painelSugestoes').innerHTML = '';

    getModalProjecao().show();
    getModalSugestoes().show();

    let data;
    try {
        const resp = await fetch(`/compras/api/projecao/?codigo=${encodeURIComponent(codigo)}`);
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
    return mensagem.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
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

document.addEventListener('DOMContentLoaded', () => {
    carregarMateriais();

    document.getElementById('btnFiltrar').addEventListener('click', () => {
        carregarMateriais(getParams());
    });

    document.getElementById('campoBusca').addEventListener('keydown', e => {
        if (e.key === 'Enter') carregarMateriais(getParams());
    });

    document.getElementById('btnRefresh').addEventListener('click', () => {
        carregarMateriais(getParams(), true);
    });

    document.getElementById('modalProjecao').addEventListener('hidden.bs.modal', () => {
        Plotly.purge('plotlyDiv');
        if (modalSugestoes) modalSugestoes.hide();
    });
});
