document.addEventListener("DOMContentLoaded", () => {
    buscarItensInspecao(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-inspecao-montagem").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensInspecao(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-inspecao-montagem").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-inspecao");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensInspecao(1);
});

function buscarItensInspecao(pagina) {
    let cardsInspecao = document.getElementById("cards-inspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-inspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-inspecao");
    let itensInspecionar = document.getElementById("itens-inspecionar");
    let itensFiltradosMaquina = document.getElementById("itens-filtrados-inspecao-maquina");
    let itensFiltradosDataInicio = document.getElementById("itens-filtrados-inspecao-data-inicio");
    let itensFiltradosDataFim = document.getElementById("itens-filtrados-inspecao-data-fim");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-inspecao-pesquisa");
    let paginacao = document.getElementById("paginacao-inspecao-montagem");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let maquinasSelecionadas = [];
    document.querySelectorAll('.form-check-input-inspecao-montagem:checked').forEach(checkbox => {
        maquinasSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionadaInicio = document.getElementById('data-inicio-inspecao').value;
    let dataSelecionadaFim = document.getElementById('data-fim-inspecao').value;
    let pesquisarInspecao = document.getElementById('pesquisar-peca-inspecao').value;

    // Monta os parâmetros de busca
    let params = new URLSearchParams();
    if (maquinasSelecionadas.length > 0) {
        params.append("maquinas", maquinasSelecionadas.join(","));
        itensFiltradosMaquina.style.display = "block";
        itensFiltradosMaquina.textContent = "Máquinas: " + maquinasSelecionadas.join(", ");
    } else {
        itensFiltradosMaquina.style.display = "none";
    }

    if (dataSelecionadaInicio) {
        params.append("data_inicio", dataSelecionadaInicio);
        itensFiltradosDataInicio.style.display = "block";
        itensFiltradosDataInicio.textContent = "De: " + dataSelecionadaInicio;
    } else {
        itensFiltradosDataInicio.style.display = "none";
    }

    if (dataSelecionadaFim) {
        params.append("data_fim", dataSelecionadaFim);
        itensFiltradosDataFim.style.display = "block";
        itensFiltradosDataFim.textContent = "Até: " + dataSelecionadaFim;
    } else {
        itensFiltradosDataFim.style.display = "none";
    }

    if (pesquisarInspecao) {
        params.append("pesquisar", pesquisarInspecao);
        itensFiltradosPesquisa.style.display = "block";
        itensFiltradosPesquisa.textContent = "Pesquisa: " + pesquisarInspecao;
    } else {
        itensFiltradosPesquisa.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/inspecao/api/itens-inspecao-montagem/?${params.toString()}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
    }).then(response => {
        if (!response.ok) {
            throw new Error(`Erro HTTP! Status: ${response.status}`);
        }
        return response.json();
    }).then(items => {
        cardsInspecao.innerHTML = "";

        const quantidadeInspecoes = items.total;
        const quantidadeFiltradaInspecoes = items.total_filtrado;

        qtdPendenteInspecao.textContent = `${quantidadeInspecoes} itens pendentes`;

        if (params.size > 1) {
            qtdFiltradaInspecao.style.display = 'block';
        } else {
            qtdFiltradaInspecao.style.display = 'none';
        }

        qtdFiltradaInspecao.textContent = `${quantidadeFiltradaInspecoes} itens filtrados`;

        items.dados.forEach(item => {

            const cards = `
            <div class="col-md-4 mb-4">
                <div class="card p-3" style="min-height: 300px; display: flex; flex-direction: column; justify-content: space-between">
                    <h5> <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(item.peca)}" target="_blank" rel="noopener noreferrer">${item.peca}</a></h5>
                    <p>Inspecao #${item.id}</p>
                    <p>
                        <strong>📅 Data:</strong> ${item.data}<br>
                        <strong>📅 Data da carga:</strong> ${item.data_carga || "-"}<br>
                        <strong>⚙️ Máquina:</strong> ${item.maquina}<br>
                        <strong>🔢 Quantidade Produzida:</strong> ${item.qtd_apontada}<br>
                        <strong>🧑🏻‍🏭 Operador:</strong> ${item.operador}
                    </p>
                    <hr>
                    <button 
                        data-id="${item.id}"
                        data-data="${item.data}"
                        data-qtd="${item.qtd_apontada}"
                        data-peca="${item.peca}"
                    class="btn btn-dark w-100 iniciar-inspecao">
                    Iniciar Inspeção</button>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;
        });

        itensInspecionar.textContent = "Itens a Inspecionar";

        if (items.total_paginas > 1) {
            let paginacaoHTML = `<nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">`;

            const paginaAtual = items.pagina_atual;
            const totalPaginas = items.total_paginas;

            // Função para adicionar um link de página
            const adicionarLinkPagina = (i) => {
                paginacaoHTML += `
                    <li class="page-item ${i === paginaAtual ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="buscarItensInspecao(${i})">${i}</a>
                    </li>`;
            };

            // Mostrar a primeira página
            adicionarLinkPagina(1);

            // Mostrar reticências antes da página atual, se necessário
            if (paginaAtual > 3) {
                paginacaoHTML += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }

            // Mostrar páginas ao redor da página atual
            for (let i = Math.max(2, paginaAtual - 1); i <= Math.min(totalPaginas - 1, paginaAtual + 1); i++) {
                adicionarLinkPagina(i);
            }

            // Mostrar reticências após a página atual, se necessário
            if (paginaAtual < totalPaginas - 2) {
                paginacaoHTML += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }

            // Mostrar a última página
            if (totalPaginas > 1) {
                adicionarLinkPagina(totalPaginas);
            }

            paginacaoHTML += `</ul></nav>`;
            paginacao.innerHTML = paginacaoHTML;
        }
    }).catch((error) => {
        console.error(error);
    });
}
