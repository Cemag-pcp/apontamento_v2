import { renderCallendar } from './full-calendar.js';

function obterElementos() {
    return {
        btnPesquisar: document.getElementById('pesquisarLiberacao'),
        btnLiberar: document.getElementById('confirmarLiberacao'),
        btnMarcarTodosSemNumeroSerie: document.getElementById('marcarTodosSemNumeroSerie'),
        btnDesmarcarTodosSemNumeroSerie: document.getElementById('desmarcarTodosSemNumeroSerie'),
        dataInicio: document.getElementById('liberacao-data-inicio'),
        dataFim: document.getElementById('liberacao-data-fim'),
        tabela: document.getElementById('tabelaLiberacao'),
        tabelaSemNumeroSerie: document.getElementById('tabelaItensSemNumeroSerie'),
        secaoSemNumeroSerie: document.getElementById('secaoItensSemNumeroSerie'),
        resumo: document.getElementById('resumoLiberacao'),
        containerLiberar: document.getElementById('containerBotaoLiberar'),
    };
}

function validarDatas(dataInicio, dataFim) {
    if (!dataInicio || !dataFim) {
        return 'Preencha data inÃ­cio e data fim.';
    }

    if (dataInicio > dataFim) {
        return 'A data inÃ­cio deve ser menor ou igual Ã  data fim.';
    }

    return null;
}

function limparResultados() {
    const { tabela, tabelaSemNumeroSerie, secaoSemNumeroSerie, resumo, containerLiberar } = obterElementos();
    tabela.innerHTML = "<tr><td colspan='4'>Nenhum dado disponível</td></tr>";
    tabelaSemNumeroSerie.innerHTML = "<tr><td colspan='7'>Nenhum item sem PED_NUMEROSERIE no período.</td></tr>";
    secaoSemNumeroSerie.classList.add('d-none');
    resumo.classList.add('d-none');
    resumo.textContent = '';
    containerLiberar.classList.add('d-none');
}

function renderizarTabela(cargas, itensSemNumeroSerie = []) {
    const { tabela, tabelaSemNumeroSerie, secaoSemNumeroSerie, resumo, containerLiberar } = obterElementos();

    const possuiCargas = Array.isArray(cargas) && cargas.length > 0;
    const possuiItensSemNumeroSerie = Array.isArray(itensSemNumeroSerie) && itensSemNumeroSerie.length > 0;

    if (!possuiCargas && !possuiItensSemNumeroSerie) {
        limparResultados();
        return;
    }

    if (possuiCargas) {
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
    } else {
        tabela.innerHTML = "<tr><td colspan='4'>Nenhum item com PED_NUMEROSERIE no período.</td></tr>";
    }

    if (possuiItensSemNumeroSerie) {
        tabelaSemNumeroSerie.innerHTML = '';
        itensSemNumeroSerie.forEach((item) => {
            const linha = document.createElement('tr');
            linha.innerHTML = `
                <td class="text-center">
                    <input
                        type="checkbox"
                        class="form-check-input js-item-sem-numero-serie"
                        value="${item.sheet_row_index}"
                    >
                </td>
                <td>${item.data_carga}</td>
                <td>${item.carga}</td>
                <td>${item.cliente || ''}</td>
                <td>${item.codigo_recurso}</td>
                <td>${item.quantidade}</td>
                <td>${item.presente_no_carreta}</td>
            `;
            tabelaSemNumeroSerie.appendChild(linha);
        });
        secaoSemNumeroSerie.classList.remove('d-none');
    } else {
        tabelaSemNumeroSerie.innerHTML = "<tr><td colspan='7'>Nenhum item sem PED_NUMEROSERIE no período.</td></tr>";
        secaoSemNumeroSerie.classList.add('d-none');
    }

    const grupos = new Set((cargas || []).map((item) => `${item.data_carga}|${item.carga}`));
    const totalSemNumeroSerie = possuiItensSemNumeroSerie ? itensSemNumeroSerie.length : 0;
    resumo.textContent = `${grupos.size} carga(s) encontradas no período. ${totalSemNumeroSerie} item(ns) sem PED_NUMEROSERIE disponível(is) para seleção.`;
    resumo.classList.remove('d-none');
    containerLiberar.classList.remove('d-none');
}

function obterItensSemNumeroSerieSelecionados() {
    return Array.from(document.querySelectorAll('.js-item-sem-numero-serie:checked'))
        .map((input) => Number.parseInt(input.value, 10))
        .filter((value) => Number.isInteger(value));
}

function marcarItensSemNumeroSerie(marcado) {
    document.querySelectorAll('.js-item-sem-numero-serie').forEach((input) => {
        input.checked = marcado;
    });
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

        renderizarTabela(
            payload?.cargas?.cargas || [],
            payload?.cargas?.itens_sem_numero_serie || [],
        );
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
                itens_sem_numero_serie_selecionados: obterItensSemNumeroSerieSelecionados(),
            }),
        });

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Erro ao liberar cargas.');
        }

        const totalInativadas = payload.total_cargas_inativadas_automaticamente || 0;
        const mensagemExclusao = totalInativadas
            ? ` ${totalInativadas} carga(s) antiga(s) foram inativada(s) automaticamente por não existirem mais na consulta atual.`
            : '';
        alert(
            `${payload.total_cargas_liberadas} carga(s) liberadas e ${payload.total_versoes_criadas} versões criadas.${mensagemExclusao}`
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
    const {
        btnPesquisar,
        btnLiberar,
        btnMarcarTodosSemNumeroSerie,
        btnDesmarcarTodosSemNumeroSerie,
    } = obterElementos();
    if (!btnPesquisar || !btnLiberar) {
        return;
    }

    limparResultados();
    btnPesquisar.addEventListener('click', pesquisarLiberacoes);
    btnLiberar.addEventListener('click', liberarCargas);

    if (btnMarcarTodosSemNumeroSerie) {
        btnMarcarTodosSemNumeroSerie.addEventListener('click', () => marcarItensSemNumeroSerie(true));
    }

    if (btnDesmarcarTodosSemNumeroSerie) {
        btnDesmarcarTodosSemNumeroSerie.addEventListener('click', () => marcarItensSemNumeroSerie(false));
    }
});
