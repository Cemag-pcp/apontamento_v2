import { renderCallendar } from './full-calendar.js';

function obterElementos() {
    return {
        btnPesquisar: document.getElementById('pesquisarLiberacao'),
        btnLiberar: document.getElementById('confirmarLiberacao'),
        dataInicio: document.getElementById('liberacao-data-inicio'),
        dataFim: document.getElementById('liberacao-data-fim'),
        tabela: document.getElementById('tabelaLiberacao'),
        resumo: document.getElementById('resumoLiberacao'),
        containerLiberar: document.getElementById('containerBotaoLiberar'),
    };
}

function validarDatas(dataInicio, dataFim) {
    if (!dataInicio || !dataFim) {
        return 'Preencha data início e data fim.';
    }

    if (dataInicio > dataFim) {
        return 'A data início deve ser menor ou igual à data fim.';
    }

    return null;
}

function limparResultados() {
    const { tabela, resumo, containerLiberar } = obterElementos();
    tabela.innerHTML = "<tr><td colspan='4'>Nenhum dado disponível</td></tr>";
    resumo.classList.add('d-none');
    resumo.textContent = '';
    containerLiberar.classList.add('d-none');
}

function renderizarTabela(cargas) {
    const { tabela, resumo, containerLiberar } = obterElementos();

    if (!Array.isArray(cargas) || cargas.length === 0) {
        limparResultados();
        return;
    }

    tabela.innerHTML = '';
    cargas.forEach((item) => {
        const linha = document.createElement('tr');
        linha.innerHTML = `
            <td>${item.data_carga}</td>
            <td>${item.carga}</td>
            <td>${item.codigo_recurso}</td>
            <td>${item.quantidade}</td>
        `;
        tabela.appendChild(linha);
    });

    const grupos = new Set(cargas.map((item) => `${item.data_carga}|${item.carga}`));
    resumo.textContent = `${grupos.size} carga(s) encontradas no período.`;
    resumo.classList.remove('d-none');
    containerLiberar.classList.remove('d-none');
}

async function pesquisarLiberacoes() {
    const { btnPesquisar, dataInicio, dataFim } = obterElementos();
    const erro = validarDatas(dataInicio.value, dataFim.value);
    if (erro) {
        alert(erro);
        return;
    }

    btnPesquisar.disabled = true;
    btnPesquisar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pesquisando...';

    try {
        const response = await fetch(
            `/cargas/api/buscar-carretas-base/?data_inicio=${encodeURIComponent(dataInicio.value)}&data_fim=${encodeURIComponent(dataFim.value)}`
        );
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Erro ao pesquisar cargas.');
        }

        renderizarTabela(payload?.cargas?.cargas || []);
    } catch (error) {
        console.error(error);
        limparResultados();
        alert(error.message || 'Erro ao pesquisar cargas.');
    } finally {
        btnPesquisar.disabled = false;
        btnPesquisar.innerHTML = '<i class="fas fa-search"></i> Pesquisar';
    }
}

async function liberarCargas() {
    const { btnLiberar, dataInicio, dataFim } = obterElementos();
    const erro = validarDatas(dataInicio.value, dataFim.value);
    if (erro) {
        alert(erro);
        return;
    }

    btnLiberar.disabled = true;
    btnLiberar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Liberando...';

    try {
        const response = await fetch('/cargas/api/liberacoes/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                data_inicio: dataInicio.value,
                data_fim: dataFim.value,
            }),
        });

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Erro ao liberar cargas.');
        }

        alert(
            `${payload.total_cargas_liberadas} carga(s) liberadas e ${payload.total_versoes_criadas} versão(ões) criadas.`
        );

        const modalElement = document.getElementById('modalLiberacao');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) {
            modal.hide();
        }

        limparResultados();
        renderCallendar();
    } catch (error) {
        console.error(error);
        alert(error.message || 'Erro ao liberar cargas.');
    } finally {
        btnLiberar.disabled = false;
        btnLiberar.innerHTML = '<i class="fas fa-check"></i> Liberar';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btnPesquisar = document.getElementById('pesquisarLiberacao');
    const btnLiberar = document.getElementById('confirmarLiberacao');
    if (!btnPesquisar || !btnLiberar) {
        return;
    }

    limparResultados();
    btnPesquisar.addEventListener('click', pesquisarLiberacoes);
    btnLiberar.addEventListener('click', liberarCargas);
});
