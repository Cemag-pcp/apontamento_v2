import { renderCallendar } from './full-calendar.js';

function carregarBaseCarretas() {
    const dataInicio = document.getElementById('data-inicio').value;
    const dataFim = document.getElementById('data-fim').value;

    return fetch(`api/buscar-carretas-base/?data_inicio=${dataInicio}&data_fim=${dataFim}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        popularTabelaResumo(data.cargas.cargas); // Chama a função para popular a tabela
    })
    .catch(error => {
        console.error('Erro ao carregar os dados:', error);
    });
}

function popularTabelaResumo(cargas) {
    const tabelaResumo = document.getElementById('tabelaResumo');

    if (cargas.length === 0) {
        tabelaResumo.innerHTML = "<tr><td colspan='4'>Nenhum dado disponível</td></tr>";
        return;
    }

    tabelaResumo.innerHTML = ""; // Limpa a tabela antes de popular os novos dados

    cargas.forEach(item => {
        const linha = document.createElement('tr');
        linha.innerHTML = `
            <td>${item.data_carga}</td>
            <td>${item.codigo_recurso}</td>
            <td>${item.quantidade}</td>
            <td>${item.presente_no_carreta}</td>
        `;
        tabelaResumo.appendChild(linha);
    });
}

function gerarArquivos(){
    const dataInicio = document.getElementById("data-inicio").value;
    const dataFim = document.getElementById("data-fim").value;
    const setor = document.getElementById("setorSelect").value;

    if (!dataInicio || !dataFim || !setor) {
        alert("Preencha todos os campos!");
        return;
    }

    const url = `api/gerar-arquivos/?data_inicio=${dataInicio}&data_fim=${dataFim}&setor=${setor}`;

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao gerar sequenciamento.");
            }
            return response.blob();
        })
        .then(blob => {
            const urlBlob = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = urlBlob;
            a.download = "sequenciamento.zip";
            document.body.appendChild(a);
            a.click();
            a.remove();
        })
        .catch(error => console.error("Erro:", error));
}

function gerarPlanejamento() {
    const btngerarPlanejamento = document.getElementById("gerarPlanejamento");
    const dataInicio = document.getElementById("data-inicio").value;
    const dataFim = document.getElementById("data-fim").value;
    const setor = document.getElementById("setorSelect").value;

    btngerarPlanejamento.disabled = true;
    btngerarPlanejamento.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando...';

    const url = `api/gerar-dados-ordem/?data_inicio=${dataInicio}&data_fim=${dataFim}&setor=${setor}`;

    fetch(url, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
    })
    .then(response => {
        return response.json().then(data => {
            if (!response.ok) {
                throw data; // Lança o erro para ser tratado no catch
            }
            return data;
        });
    })
    .then(data => {
        alert("Planejamento gerado com sucesso!");
        renderCallendar();
    })
    .catch(error => {
        console.error("Erro ao criar ordens:", error);
        if (error && error.error) {
            alert("Erro ao gerar planejamento: " + error.error);
        } else {
            alert("Erro inesperado ao processar a solicitação.");
        }
    })
    .finally(() => {
        btngerarPlanejamento.innerHTML = '<i class="fas fa-save"></i> Gerar Planejamento';
        btngerarPlanejamento.disabled = false;
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const btPesquisar = document.getElementById('pesquisarDados');
    const btngerarSequenciamento = document.getElementById('gerarSequenciamento');
    const btngerarPlanejamento = document.getElementById('gerarPlanejamento');

    btPesquisar.addEventListener('click', () => {
        btPesquisar.disabled = true; // Desabilita o botão antes de carregar os dados
        btPesquisar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pesquisando...';
    
        carregarBaseCarretas().finally(() => {
            btPesquisar.disabled = false; // Reabilita o botão após a execução
            btngerarSequenciamento.disabled = false;
            btngerarPlanejamento.disabled = false;
            btPesquisar.innerHTML = '<i class="fas fa-search"></i> Pesquisar';

        });
    });

    btngerarSequenciamento.addEventListener('click', () => {
        btngerarSequenciamento.disabled = true; // Desabilita o botão antes de carregar os dados
        
        gerarArquivos().finally(() => {
            btngerarSequenciamento.disabled = false; // Reabilita o botão após a execução
        });
    });

    btngerarPlanejamento.addEventListener("click", gerarPlanejamento);

});