document.addEventListener("DOMContentLoaded", () => {
    buscarItensInspecionados(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-inspecionados").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensInspecionados(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-inspecionados").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-inspecionados");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensInspecionados(1);
});

function buscarItensInspecionados(pagina) {
    let cardsInspecao = document.getElementById("cards-inspecionados");
    let qtdPendenteInspecao = document.getElementById("qtd-inspecionados");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-inspecionados");
    let itensInspecionar = document.getElementById("itens-inspecionados");
    let itensFiltradosCor = document.getElementById("itens-filtrados-inspecionados-cor");
    let itensFiltradosDataInicio = document.getElementById("itens-filtrados-inspecionados-data-inicio");
    let itensFiltradosDataFim = document.getElementById("itens-filtrados-inspecionados-data-fim");
    let itensFiltradosInspetor = document.getElementById("itens-filtrados-inspecionados-inspetor");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-inspecionados-pesquisa");
    let itensFiltradosStatusConformidade = document.getElementById("itens-filtrados-inspecionados-status");
    let paginacao = document.getElementById("paginacao-inspecionados-montagem");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let maquinasSelecionadas = [];
    document.querySelectorAll('.form-check-input-inspecionados-montagem:checked').forEach(checkbox => {
        maquinasSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let inspetorSelecionado = [];
    document.querySelectorAll('.form-check-input-inspecionados-inspetores:checked').forEach(checkbox => {
        inspetorSelecionado.push(checkbox.nextElementSibling.textContent.trim());
    });

    let statusConformidade = [];
    if (document.getElementById('filter-itens-conformes-montagem').checked) {
        statusConformidade.push('conforme');
    }
    
    // Verifica se o checkbox de itens não conformes está marcado
    if (document.getElementById('filter-itens-nao-conformes-montagem').checked) {
        statusConformidade.push('nao_conforme');
    }

    let dataSelecionadaInicio = document.getElementById('data-inicio-inspecionados').value;
    let dataSelecionadaFim = document.getElementById('data-fim-inspecionados').value;
    let pesquisarInspecao = document.getElementById('pesquisar-peca-inspecionados').value;

    // Monta os parâmetros de busca
    let params = new URLSearchParams();
    if (maquinasSelecionadas.length > 0) {
        params.append("maquinas", maquinasSelecionadas.join(","));
        itensFiltradosCor.style.display = "block";
        itensFiltradosCor.textContent = "Máquinas: " + maquinasSelecionadas.join(", ");
    } else {
        itensFiltradosCor.style.display = "none";
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

    if (statusConformidade.length > 0) {
        params.append("status-conformidade", statusConformidade.join(","));
        itensFiltradosStatusConformidade.style.display = "block";
        itensFiltradosStatusConformidade.textContent = "Status: " + 
            statusConformidade.map(s => s === 'conforme' ? 'Itens Conformes' : 'Itens Não Conformes').join(", ");
    } else {
        itensFiltradosStatusConformidade.style.display = "none";
    }

    if (inspetorSelecionado.length > 0) {
        params.append("inspetores", inspetorSelecionado.join(","));
        itensFiltradosInspetor.style.display = "block";
        itensFiltradosInspetor.textContent = "Inspetores: " + inspetorSelecionado.join(", ");
    } else {
        itensFiltradosInspetor.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/inspecao/api/itens-inspecionados-montagem/?${params.toString()}`, {
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

        console.log(items)

        qtdPendenteInspecao.textContent = `${quantidadeInspecoes} itens inspecionados`;

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

            let iconeNaoConformidade;

            if (item.possui_nao_conformidade) {
            iconeNaoConformidade = `
                <span class="badge rounded-pill bg-danger">
                <i class="bi bi-exclamation-triangle-fill me-1"></i>
                Não conformidade
                </span>
            `;
            } else {
            iconeNaoConformidade = `
                <span class="badge rounded-pill bg-success">
                <i class="bi bi-check-circle-fill me-1"></i>
                Conforme
                </span>
            `;
            }

            let color = borderColors[item.cor];

            const cards = `
            <div class="col-md-4 mb-4">
                <div class="card p-3 border-${color}" style="min-height: 300px; display: flex; flex-direction: column; justify-content: space-between">
                    <h5> <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(item.peca)}" target="_blank" rel="noopener noreferrer">${item.peca}</a></h5>
                    <p>Inspeção #${item.id}</p>
                    <p>
                        <strong>📅 Data da última inspeção:</strong> ${item.data}<br>
                        <strong>⚙️ Máquina:</strong> ${item.maquina}<br>
                        <strong>🔢 Qtd Produzida:</strong> ${item.qtd_produzida}<br>
                        <strong>🔍 Qtd Inspecionada:</strong> ${item.qtd_inspecionada}<br>
                        <strong>🧑🏻‍🏭 Inspetor:</strong> ${item.inspetor}
                    </p>
                    <hr>
                    <div class="d-flex justify-content-between">
                        <div class="d-flex align-items-baseline gap-2">
                            ${iconeNaoConformidade}
                        </div>
                        <button 
                            data-id="${item.id}"
                            data-data="${item.data}"
                            data-peca="${item.peca}"
                            data-tipo="${item.tipo}"
                            data-nao-conformidade="${item.nao_conformidade}"
                            data-conformidade="${item.conformidade}"
                            data-cor="${item.cor}"
                            data-id-dados-execucao="${item.id_dados_execucao}"
                        class="btn btn-white historico-inspecao w-50 d-flex justify-content-center align-items-center gap-2">              
                            <span class="spinner-border spinner-border-sm" style="display:none"></span>
                            Ver detalhes
                        </button>
                    </div>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;
        });

        itensInspecionar.textContent = "Itens Inspecionados";
        
        // Adiciona a paginação com reticências
        if (items.total_paginas > 1) {
            let paginacaoHTML = `<nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">`;

            const paginaAtual = items.pagina_atual;
            const totalPaginas = items.total_paginas;

            // Função para adicionar um link de página
            const adicionarLinkPagina = (i) => {
                paginacaoHTML += `
                    <li class="page-item ${i === paginaAtual ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="buscarItensInspecionados(${i})">${i}</a>
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

function pegarCodigoPeca(peca){
    if (peca.includes("-")) {
        // Se a peça contém um hífen, divide a string e retorna a parte antes do hífen
        const partes = peca.split("-");
        return partes[0].trim(); // Retorna a parte antes do hífen
    }
    return peca; // Se não houver hífen, retorna a peça completa
}