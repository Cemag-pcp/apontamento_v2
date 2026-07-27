const config = document.getElementById('ocupacaoConfig');
const API_URL = config.dataset.apiUrl;
const MAQUINAS_URL = config.dataset.maquinasUrl;

const form = document.getElementById('ocupacaoFiltrosForm');
const selectCelula = document.getElementById('filtroCelula');
const inputData = document.getElementById('filtroData');
const loadingState = document.getElementById('ocupacaoLoadingState');
const vazioEl = document.getElementById('ocupacaoVazio');
const resultadoEl = document.getElementById('ocupacaoResultado');

function escapeHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

async function carregarCelulas() {
    try {
        const resp = await fetch(MAQUINAS_URL);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const payload = await resp.json();
        const maquinas = payload.maquinas || [];
        maquinas.sort((a, b) => (a.nome || '').localeCompare(b.nome || ''));

        selectCelula.innerHTML = '<option value="">Selecione...</option>' +
            maquinas.map((m) => `<option value="${m.id}">${escapeHtml(m.nome)}</option>`).join('');
    } catch (err) {
        selectCelula.innerHTML = '<option value="">Falha ao carregar celulas</option>';
    }
}

function preencherDataPadrao() {
    const hoje = new Date();
    inputData.value = hoje.toISOString().slice(0, 10);
}

function renderTabelaProduzindo(segmentos) {
    const tbody = document.getElementById('tabelaProduzindo');
    if (!segmentos.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Nenhum periodo de producao nesse dia.</td></tr>';
        return;
    }
    tbody.innerHTML = segmentos.map((s) => `
        <tr>
            <td>${escapeHtml(s.inicio)}</td>
            <td>${escapeHtml(s.fim)}</td>
            <td>${escapeHtml(s.duracao)}</td>
            <td>${escapeHtml(s.ordem || '-')}</td>
        </tr>
    `).join('');
}

function renderTabelaParado(segmentos) {
    const tbody = document.getElementById('tabelaParado');
    if (!segmentos.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Sem periodos parada nesse dia.</td></tr>';
        return;
    }
    tbody.innerHTML = segmentos.map((s) => `
        <tr>
            <td>${escapeHtml(s.inicio)}</td>
            <td>${escapeHtml(s.fim)}</td>
            <td>${escapeHtml(s.duracao)}</td>
            <td>${escapeHtml(s.motivo)}</td>
        </tr>
    `).join('');
}

async function carregar() {
    const maquinaId = selectCelula.value;
    const dia = inputData.value;

    if (!maquinaId) {
        resultadoEl.classList.add('d-none');
        vazioEl.classList.remove('d-none');
        vazioEl.textContent = 'Selecione uma celula e clique em "Buscar".';
        return;
    }

    loadingState.classList.remove('d-none');
    vazioEl.classList.add('d-none');
    resultadoEl.classList.add('d-none');

    try {
        const params = new URLSearchParams({ maquina_id: maquinaId, data: dia });
        const resp = await fetch(`${API_URL}?${params.toString()}`);
        const payload = await resp.json();
        if (!resp.ok) throw new Error(payload.erro || `HTTP ${resp.status}`);

        document.getElementById('resPeriodoTotal').textContent = payload.periodo_total;
        document.getElementById('resTempoProduzindo').textContent = payload.tempo_produzindo;
        document.getElementById('resTempoParado').textContent = payload.tempo_parado;
        document.getElementById('resPercentual').textContent = `${payload.percentual_produzindo}%`;

        const barraProduzindo = document.getElementById('barraProduzindo');
        const barraParado = document.getElementById('barraParado');
        barraProduzindo.style.width = `${payload.percentual_produzindo}%`;
        barraProduzindo.textContent = payload.percentual_produzindo > 8 ? `${payload.percentual_produzindo}%` : '';
        const percentualParado = Math.max(0, 100 - payload.percentual_produzindo);
        barraParado.style.width = `${percentualParado}%`;
        barraParado.textContent = percentualParado > 8 ? `${percentualParado.toFixed(1)}%` : '';

        renderTabelaProduzindo(payload.segmentos_produzindo || []);
        renderTabelaParado(payload.segmentos_parado || []);

        resultadoEl.classList.remove('d-none');
    } catch (err) {
        vazioEl.classList.remove('d-none');
        vazioEl.textContent = `Falha ao carregar: ${err.message}`;
    } finally {
        loadingState.classList.add('d-none');
    }
}

form.addEventListener('submit', (e) => {
    e.preventDefault();
    carregar();
});

document.getElementById('btnAtualizar').addEventListener('click', () => {
    carregar();
});

preencherDataPadrao();
carregarCelulas();
