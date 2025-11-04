document.addEventListener("DOMContentLoaded", () => {
    buscarItensReinspecao(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-reinspecao").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensReinspecao(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-reinspecao").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-reinspecao");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensReinspecao(1);
});

function buscarItensReinspecao(pagina) {
    let cardsInspecao = document.getElementById("cards-reinspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-reinspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-reinspecao");
    let itensInspecionar = document.getElementById("itens-reinspecao");
    let itensFiltradosCor = document.getElementById("itens-filtrados-reinspecao-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-reinspecao-data");
    let itensFiltradosInspetor = document.getElementById("itens-filtrados-reinspecao-inspetor");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-reinspecao-pesquisa");
    let paginacao = document.getElementById("paginacao-reinspecao-montagem");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let maquinasSelecionadas = [];
    document.querySelectorAll('.form-check-input-reinspecao-montagem:checked').forEach(checkbox => {
        maquinasSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let inspetorSelecionado = [];
    document.querySelectorAll('.form-check-input-reinspecao-inspetores:checked').forEach(checkbox => {
        inspetorSelecionado.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-reinspecao').value;
    let pesquisarInspecao = document.getElementById('pesquisar-peca-reinspecao').value;

    // Monta os parâmetros de busca
    let params = new URLSearchParams();
    if (maquinasSelecionadas.length > 0) {
        params.append("maquinas", maquinasSelecionadas.join(","));
        itensFiltradosCor.style.display = "block";
        itensFiltradosCor.textContent = "maquinas: " + maquinasSelecionadas.join(", ");
    } else {
        itensFiltradosCor.style.display = "none";
    }

    if (dataSelecionada) {
        params.append("data", dataSelecionada);
        itensFiltradosData.style.display = "block";
        itensFiltradosData.textContent = "Data: " + dataSelecionada;
    } else {
        itensFiltradosData.style.display = "none";
    }

    if (pesquisarInspecao) {
        params.append("pesquisar", pesquisarInspecao);
        itensFiltradosPesquisa.style.display = "block";
        itensFiltradosPesquisa.textContent = "Pesquisa: " + pesquisarInspecao;
    } else {
        itensFiltradosPesquisa.style.display = "none";
    }

    if (inspetorSelecionado.length > 0) {
        params.append("inspetores", inspetorSelecionado.join(","));
        itensFiltradosInspetor.style.display = "block";
        itensFiltradosInspetor.textContent = "Inspetores: " + inspetorSelecionado.join(", ");
    } else {
        itensFiltradosInspetor.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/inspecao/api/itens-reinspecao-montagem/?${params.toString()}`, {
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
            let borderColors = {
                "Laranja": "orange", "Verde": "green",
                "Vermelho": "red", "Azul": "blue",
                "Amarelo": "yellow", "Cinza": "gray"
            };

            let color = borderColors[item.cor];

            const cards = `
            <div class="col-md-4 mb-4">
                <div class="card p-3 border-${color}" style="min-height: 300px; display: flex; flex-direction: column; justify-content: space-between">
                    <h5> ${item.peca}</h5>
                    <p>Inspecao #${item.id}</p>
                    <p>
                        <strong>📅 Data da última inspeção:</strong> ${item.data}<br>
                        <strong>🧮 Conformidade:</strong> ${item.conformidade}<br>
                        <strong>🔢 Não conformidade:</strong> ${item.nao_conformidade}<br>
                    </p>
                    <hr>
                    <button 
                        data-id="${item.id}"
                        data-data="${item.data}"
                        data-nao-conformidade="${item.nao_conformidade}"
                        data-conformidade="${item.conformidade}"
                        data-cor="${item.cor}"
                        data-peca="${item.peca}"
                    class="btn btn-dark w-100 iniciar-reinspecao">
                    Iniciar Reinspeção</button>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;
        });

        itensInspecionar.textContent = "Itens a Reinspecionar";

        // Adiciona a paginação
        if (items.total_paginas > 1) {
            let paginacaoHTML = `<nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">`;

            const paginaAtual = items.pagina_atual;
            const totalPaginas = items.total_paginas;

            // Função para adicionar um link de página
            const adicionarLinkPagina = (i) => {
                paginacaoHTML += `
                    <li class="page-item ${i === paginaAtual ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="buscarItensReinspecao(${i})">${i}</a>
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