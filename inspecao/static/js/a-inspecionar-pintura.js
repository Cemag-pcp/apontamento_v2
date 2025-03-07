document.addEventListener("DOMContentLoaded", () => {
    buscarItensInspecao(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-inspecao").addEventListener("click", () => {
    buscarItensInspecao(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

function buscarItensInspecao(pagina) {
    let cardsInspecao = document.getElementById("cards-inspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-inspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-inspecao");
    let itensInspecionar = document.getElementById("itens-inspecionar");
    let itensFiltradosCor = document.getElementById("itens-filtrados-inspecao-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-inspecao-data");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-inspecao-pesquisa");
    let paginacao = document.getElementById("paginacao-inspecao-pintura");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let coresSelecionadas = [];
    document.querySelectorAll('.form-check-input-inspecao:checked').forEach(checkbox => {
        coresSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-inspecao').value;
    let pesquisarInspecao = document.getElementById('pesquisar-peca-inspecao').value;

    // Monta os parâmetros de busca
    let params = new URLSearchParams();
    if (coresSelecionadas.length > 0) {
        params.append("cores", coresSelecionadas.join(","));
        itensFiltradosCor.style.display = "block";
        itensFiltradosCor.textContent = "Cores: " + coresSelecionadas.join(", ");
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

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/inspecao/api/itens-inspecao-pintura/?${params.toString()}`, {
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
        console.log(items);
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
                    <p>
                        <strong>📅 Due:</strong> ${item.data}<br>
                        <strong>📍 Tipo:</strong> ${item.tipo}<br>
                        <strong>🎨 Cor:</strong> ${item.cor}<br>
                        <strong>🧑🏻‍🏭 Operador:</strong> ${item.operador}
                    </p>
                    <hr>
                    <button class="btn btn-dark w-100" data-bs-toggle="modal" data-bs-target="#modal-inspecionar-pintura">Iniciar Inspeção</button>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;
        });

        itensInspecionar.textContent = "Itens a Inspecionar";

        // Adiciona a paginação
        if (items.total_paginas > 1) {
            let paginacaoHTML = `<nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">`;
            for (let i = 1; i <= items.total_paginas; i++) {
                paginacaoHTML += `
                    <li class="page-item ${i === items.pagina_atual ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="buscarItensInspecao(${i})">${i}</a>
                    </li>`;
            }
            paginacaoHTML += `</ul></nav>`;
            paginacao.innerHTML = paginacaoHTML;
        }
    }).catch((error) => {
        console.error(error);
    });
}