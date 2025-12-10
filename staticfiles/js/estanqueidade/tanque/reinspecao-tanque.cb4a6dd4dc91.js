document.addEventListener("DOMContentLoaded", () => {
    buscarItensReinspecaoEstanqueidadeTanque(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-reinspecao").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensReinspecaoEstanqueidadeTanque(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
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
    buscarItensReinspecaoEstanqueidadeTanque(1);
});

function buscarItensReinspecaoEstanqueidadeTanque(pagina) {
    let cardsInspecao = document.getElementById("cards-reinspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-reinspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-reinspecao");
    let itensInspecionar = document.getElementById("itens-reinspecao");
    let itensFiltradosCor = document.getElementById("itens-filtrados-reinspecao-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-reinspecao-data");
    let itensFiltradosInspetor = document.getElementById("itens-filtrados-reinspecao-inspetor");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-reinspecao-pesquisa");
    let paginacao = document.getElementById("paginacao-reinspecao-tanque");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let maquinasSelecionadas = [];
    document.querySelectorAll('.form-check-input-reinspecao-tanque:checked').forEach(checkbox => {
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

    fetch(`/inspecao/api/itens-reinspecao-tanque/?${params.toString()}`, {
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

        console.log(items)


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
                <div class="card p-3" style="min-height: 400px; display: flex; flex-direction: column; justify-content: space-between">
                    <div>
                        <h5 class="card-title">${item.peca}</h5>
                        <h6 class="card-subtitle mb-2 text-muted">Inspeção #${item.id}</h6>
                        <p class="card-text">
                            <strong>📅 Data da última inspeção:</strong> ${item.data}<br>
                            <strong>📍 Tipo da Inspeção:</strong> ${item.tipo_inspecao}<br>
                            <strong>🧑🏻‍🏭 Inspetor:</strong> ${item.inspetor}
                        </p>
                    </div>

                    <div id="carousel-${item.id}" class="carousel slide mb-3" data-bs-ride="carousel" style="background: #f8f9fa; border-radius: 8px; padding: 10px;">
                        <div class="carousel-inner">
                            <div class="carousel-item active">
                                <p class="text-center">
                                    <strong>📊 Pressão Inicial:</strong> ${item.pressao_inicial_1}<br>
                                    <strong>📊 Pressão Final:</strong> ${item.pressao_final_1}<br>
                                    <strong>📝 Tipo de Teste:</strong> ${mapearTipoTeste(item.tipo_teste_1)}<br>
                                    <strong>⏱️ Tempo de Execução:</strong> ${item.tempo_execucao_1}
                                </p>
                            </div>

                            <div class="carousel-item">
                                <p class="text-center">
                                    <strong>📊 Pressão Inicial:</strong> ${item.pressao_inicial_2}<br>
                                    <strong>📊 Pressão Final:</strong> ${item.pressao_final_2}<br>
                                    <strong>📝 Tipo de Teste:</strong> ${mapearTipoTeste(item.tipo_teste_2)}<br>
                                    <strong>⏱️ Tempo de Execução:</strong> ${item.tempo_execucao_2}
                                </p>
                            </div>
                        </div>
                        <button class="carousel-control-prev" type="button" data-bs-target="#carousel-${item.id}" data-bs-slide="prev">
                            <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                            <span class="visually-hidden">Anterior</span>
                        </button>
                        <button class="carousel-control-next" type="button" data-bs-target="#carousel-${item.id}" data-bs-slide="next">
                            <span class="carousel-control-next-icon" aria-hidden="true"></span>
                            <span class="visually-hidden">Próximo</span>
                        </button>
                    </div>

                    <div>
                        <hr>
                        <button 
                            data-id="${item.id}"
                            data-id-dados-execucao="${item.id_dados_execucao}"
                            data-data="${item.data}"
                            data-data-carga="${item.data_carga}"
                            data-tipo="${item.tipo_inspecao}"
                            data-peca="${item.peca}"

                            data-pressao-inicial-1="${item.pressao_inicial_1}"
                            data-pressao-final-1="${item.pressao_final_1}"
                            data-nao-conformidade-1="${item.nao_conformidade_1}"
                            data-tipo-teste-1="${mapearTipoTeste(item.tipo_teste_1)}"
                            data-tempo-execucao-1="${item.tempo_execucao_1}"

                            data-pressao-inicial-2="${item.pressao_inicial_2}"
                            data-pressao-final-2="${item.pressao_final_2}"
                            data-nao-conformidade-2="${item.nao_conformidade_2}"
                            data-tipo-teste-2="${mapearTipoTeste(item.tipo_teste_2)}"
                            data-tempo-execucao-2="${item.tempo_execucao_2}"
                            
                            class="btn btn-dark w-100 iniciar-reinspecao-tanque">
                            Iniciar Reinspeção
                        </button>
                    </div>
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
                        <a class="page-link" href="#" onclick="buscarItensReinspecaoEstanqueidade(${i})">${i}</a>
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

function mapearTipoTeste(codigo) {
    const tiposTeste = {
        "ctpi": "Corpo do tanque parte inferior",
        "ctl": "Corpo do tanque + longarinas",
        "ct": "Corpo do tanque",
        "ctc": "Corpo do tanque + chassi"
    };
    return tiposTeste[codigo] || codigo; // Retorna o código original se não encontrar no mapeamento
}