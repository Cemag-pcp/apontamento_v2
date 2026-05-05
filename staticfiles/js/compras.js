/* compras.js — Análise de Compras */
'use strict';

const URGENCY_ROW_CLASS = {
    URGENTE: 'table-danger',
    PRAZO_CURTO: 'table-warning',
    PRAZO_OK: 'table-success',
    SEM_DADOS: '',
};

const URGENCY_BADGE = {
    URGENTE: '<span class="badge bg-danger">🔴 Urgente</span>',
    PRAZO_CURTO: '<span class="badge bg-warning text-dark">🟡 Prazo Curto</span>',
    PRAZO_OK: '<span class="badge bg-success">🟢 Prazo OK</span>',
    SEM_DADOS: '<span class="badge bg-secondary">—</span>',
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
    if (n === null || n === undefined || n === 9999) return '—';
    return Number(n).toLocaleString('pt-BR', { minimumFractionDigits: decimais, maximumFractionDigits: decimais });
}

function getParams() {
    return {
        codigo: document.getElementById('filtroCodigo').value,
        grupo: document.getElementById('filtroGrupo').value,
        urgencia: document.getElementById('filtroUrgencia').value,
        busca: document.getElementById('campoBusca').value,
    };
}

// ---- Carregamento principal ----
async function carregarMateriais(params = {}, forceRefresh = false) {
    document.getElementById('loadingTabela').style.display = 'block';
    document.getElementById('tabelaWrapper').style.display = 'none';
    document.getElementById('semResultados').style.display = 'none';
    document.getElementById('contadores').style.display = 'none !important';

    const qs = new URLSearchParams(
        Object.fromEntries(Object.entries({ ...params, refresh: forceRefresh ? '1' : undefined })
            .filter(([, v]) => v))
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

    // Dropdowns (apenas no primeiro load)
    if (!params.codigo && data.codigos && data.codigos.length) {
        const sel = document.getElementById('filtroCodigo');
        const atual = sel.value;
        sel.innerHTML = '<option value="">Todos os produtos</option>';
        data.codigos.forEach(c => {
            const opt = new Option(c, c, false, c === atual);
            sel.appendChild(opt);
        });
    }
    if (!params.grupo && data.grupos && data.grupos.length) {
        const sel = document.getElementById('filtroGrupo');
        const atual = sel.value;
        sel.innerHTML = '<option value="">Todos os grupos</option>';
        data.grupos.forEach(g => {
            const opt = new Option(g, g, false, g === atual);
            sel.appendChild(opt);
        });
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
            <td><small class="text-muted">${m.grupo || '—'}</small></td>
            <td class="text-end">${fmt(m.media_3m)}</td>
            <td class="text-end">${fmt(m.estoque_almox)}</td>
            <td class="text-end">${fmt(m.consumo_diario, 3)}</td>
            <td class="text-end">${m.dias_ate_zero === 9999 ? '∞' : fmt(m.dias_ate_zero, 1)}</td>
            <td class="text-end">${fmt(m.ped_compras)}</td>
            <td class="text-end">${fmt(m.estoque_minimo)}</td>
            <td><small>${m.data_compra || '—'}</small></td>
            <td>${URGENCY_BADGE[m.flag_urgencia] || ''}</td>
            <td class="text-center">
                <button class="btn btn-xs btn-outline-primary btn-grafico"
                    data-codigo="${m.codigo}" data-descricao="${m.descricao}" title="Ver gráfico">
                    <i class="fas fa-chart-line"></i>
                </button>
            </td>`;
        fragment.appendChild(tr);
    });

    tbody.appendChild(fragment);
    document.getElementById('tabelaWrapper').style.display = 'block';

    // Handlers de gráfico
    tbody.querySelectorAll('.btn-grafico').forEach(btn => {
        btn.addEventListener('click', () =>
            carregarProjecao(btn.dataset.codigo, btn.dataset.descricao));
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

    // exibir contadores usando style direto (evita conflito com !important inline)
    const el = document.getElementById('contadores');
    el.removeAttribute('style');
    el.style.display = 'flex';
}

// ---- Modal de Projeção ----
let _modalProjecao = null;

function getModal() {
    if (!_modalProjecao) {
        _modalProjecao = new bootstrap.Modal(document.getElementById('modalProjecao'), { backdrop: true });
    }
    return _modalProjecao;
}

async function carregarProjecao(codigo, descricao) {
    document.getElementById('tituloGrafico').textContent = `Projeção — ${codigo}: ${descricao}`;
    document.getElementById('loadingGrafico').style.display = 'block';
    document.getElementById('conteudoGrafico').style.display = 'none';
    document.getElementById('plotlyDiv').innerHTML = '';
    document.getElementById('painelSugestoes').innerHTML = '';

    getModal().show();

    let data;
    try {
        const resp = await fetch(`/compras/api/projecao/?codigo=${encodeURIComponent(codigo)}`);
        data = await resp.json();
        if (data.error) throw new Error(data.error);
    } catch (e) {
        document.getElementById('loadingGrafico').style.display = 'none';
        document.getElementById('conteudoGrafico').style.display = 'block';
        document.getElementById('plotlyDiv').innerHTML =
            `<div class="alert alert-danger">Erro: ${e.message}</div>`;
        return;
    }

    document.getElementById('loadingGrafico').style.display = 'none';
    document.getElementById('conteudoGrafico').style.display = 'block';

    // Plotly precisa que o div esteja visível antes de renderizar
    requestAnimationFrame(() => {
        renderPlotly(data);
        renderSugestoes(data.sugestoes || []);
    });
}

function renderPlotly(data) {
    const real = data.serie_real || { datas: [], estoques: [] };
    const ideal = data.serie_ideal || { datas: [], estoques: [] };
    const min = data.estoque_minimo || 0;

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
            name: 'Estoque Mínimo',
            line: { color: '#dc3545', width: 2, dash: 'dash' },
        },
        {
            x: [xMin, xMax], y: [0, 0],
            type: 'scatter', mode: 'lines',
            name: 'Estoque Zero',
            line: { color: '#6c757d', width: 1 },
        },
    ];

    const layout = {
        margin: { t: 20, b: 60, l: 60, r: 20 },
        xaxis: { title: 'Data', type: 'date', tickangle: -45 },
        yaxis: { title: 'Quantidade em Estoque' },
        legend: { orientation: 'h', y: -0.25 },
        hovermode: 'x unified',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
    };

    Plotly.newPlot('plotlyDiv', traces, layout, { responsive: true, displayModeBar: false });
}

function renderSugestoes(sugestoes) {
    const painel = document.getElementById('painelSugestoes');
    if (!sugestoes.length) {
        painel.innerHTML = '<p class="text-muted mb-0">Sem sugestões disponíveis.</p>';
        return;
    }

    painel.innerHTML = sugestoes.map(s => {
        const cor = SUGESTAO_COLORS[s.tipo] || 'secondary';
        const qtdHtml = s.qtd_sugerida !== null && s.qtd_sugerida !== undefined
            ? `<div class="mt-1"><span class="badge bg-primary fs-6">Qtd sugerida: ${fmt(s.qtd_sugerida)}</span></div>`
            : '';
        return `
        <div class="alert alert-${cor} mb-2 py-2">
            <strong>${s.titulo}</strong><br>
            <small style="white-space:pre-line">${s.mensagem}</small>
            ${qtdHtml}
        </div>`;
    }).join('');
}

// ---- Event Listeners ----
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

    // Limpa o gráfico Plotly ao fechar o modal para liberar memória
    document.getElementById('modalProjecao').addEventListener('hidden.bs.modal', () => {
        Plotly.purge('plotlyDiv');
    });
});
