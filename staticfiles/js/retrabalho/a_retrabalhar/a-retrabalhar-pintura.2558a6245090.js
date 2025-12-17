document.addEventListener("DOMContentLoaded", () => {
    buscarItensRetrabalho(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-retrabalho").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário
    buscarItensRetrabalho(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-retrabalho").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-retrabalho");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensRetrabalho(1);
});


function buscarItensRetrabalho(pagina) {
    let cardsretrabalho = document.getElementById("cards-retrabalho");
    let qtdPendenteretrabalho = document.getElementById("qtd-pendente-retrabalho");
    let qtdFiltradaretrabalho = document.getElementById("qtd-filtrada-retrabalho");
    let itensInspecionar = document.getElementById("titulo-itens-inspecionar");
    let itensFiltradosCor = document.getElementById("itens-filtrados-retrabalho-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-retrabalho-data");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-retrabalho-pesquisa");
    let paginacao = document.getElementById("paginacao-retrabalho-pintura");

    // Limpa os cards antes de buscar novos
    cardsretrabalho.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let coresSelecionadas = [];
    document.querySelectorAll('.form-check-input-retrabalho:checked').forEach(checkbox => {
        coresSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-retrabalho').value;
    let pesquisarretrabalho = document.getElementById('pesquisar-peca-retrabalho').value;

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

    if (pesquisarretrabalho) {
        params.append("pesquisar", pesquisarretrabalho);
        itensFiltradosPesquisa.style.display = "block";
        itensFiltradosPesquisa.textContent = "Pesquisa: " + pesquisarretrabalho;
    } else {
        itensFiltradosPesquisa.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/pintura/api/itens-retrabalho-pintura/?${params.toString()}`, {
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
        cardsretrabalho.innerHTML = "";

        const quantidadeInspecoes = items.total;
        const quantidadeFiltradaInspecoes = items.total_filtrado;

        if (params.size > 1) {
            qtdFiltradaretrabalho.style.display = 'block';
        } else {
            qtdFiltradaretrabalho.style.display = 'none';
        }

        qtdFiltradaretrabalho.textContent = `${quantidadeFiltradaInspecoes} itens filtrados`;

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
                    <p>Dados Execucao #${item.id}</p>
                    <p>
                        <strong>📅 Dt. Produzida:</strong> ${item.data}<br>
                        <strong>📍 Tipo:</strong> ${item.tipo}<br>
                        <strong>🎨 Cor:</strong> ${item.cor}<br>
                        <strong>🔢 Não conformidade:</strong> ${item.nao_conformidade}<br>
                        <strong>🧑🏻‍🏭 Inspetor:</strong> ${item.inspetor}
                    </p>
                    <hr>
                    <div class="d-flex justify-content-between">
                        <button data-dados-execucao="${item.id_dados_execucao}"
                            data-data="${item.data}"
                            class="btn btn-white motivo" style="width:30%">
                        Motivo</button>
                        <button 
                            data-id="${item.id}"
                            data-dados-execucao="${item.id_dados_execucao}"
                            data-data="${item.data}"
                            data-qtd="${item.nao_conformidade}"
                            data-tipo="${item.tipo}"
                            data-cor="${item.cor}"
                            data-peca="${item.peca}"
                        class="btn btn-dark iniciar-retrabalho" style="width:50%">
                        Iniciar Retrabalho</button>
                    </div>
                </div>
            </div>`;

            cardsretrabalho.innerHTML += cards;
        });

        itensInspecionar.textContent = "Pendente";
        document.getElementById('badge-inspecionar').innerText = quantidadeInspecoes;
        document.querySelector('#itens-inspecionar .spinner-border').style.display = 'none';
        
        // Adiciona a paginação
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
                        <a class="page-link" href="#" onclick="buscarItensRetrabalho(${i})">${i}</a>
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

document.addEventListener("click", function(event) {
    if (event.target.closest(".motivo")) { 

        const listaCausas = document.getElementById("causas-retrabalho-pintura");
        const id = event.target.closest(".motivo").getAttribute("data-dados-execucao");
        const dataExecucao = event.target.closest(".motivo").getAttribute("data-data");

        listaCausas.innerHTML = `<div class="card" aria-hidden="true">
                                    <img src="/static/img/fundo cinza.png" class="card-img-top" alt="Tela cinza">
                                    <div class="card-body">
                                        <h5 class="card-title placeholder-glow">
                                        <span class="placeholder col-6"></span>
                                        </h5>
                                        <p class="card-text placeholder-glow">
                                            <span class="placeholder col-12"></span>
                                        </p>
                                        <p class="card-text placeholder-glow">
                                            <span class="placeholder col-4"></span>
                                        </p>
                                    </div>
                                </div>` 
                        
        const modalCausas = new bootstrap.Modal(document.getElementById("modal-causas-historico-retrabalho-pintura"));
        modalCausas.show();

        fetch(`/inspecao/api/historico-causas-pintura/${id}`, {
            method:"GET",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro na requisição HTTP. Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            listaCausas.innerHTML = "";
            data.causas.forEach((causa, index) => {
                let causaHTML = 
                `<div class="row mb-3" style="border: 1px solid; border-radius: 10px; padding: 5px; border-color: #ced4da;">
                    <div class="d-flex justify-content-between">
                        <span class="label-modal text-end mb-3 mt-3">Quantidade: ${causa.quantidade}</span>
                        <span class="label-modal text-end mb-3 mt-3">${index + 1}ª Causa</span>
                    </div>`;
                
                if(causa.imagens.length > 0) {
                    causa.imagens.forEach(imagem => {
                        causaHTML += `<div class="card mb-3 p-0">
                                        <img src="${imagem.url}" class="card-img-top" alt="...">
                                        <div class="card-body">
                                            <h5 class="card-title">${causa.nomes.join(", ")}</h5>
                                            <p class="card-text label-modal"><small class="text-muted">${dataExecucao}</small></p>
                                        </div>
                                    </div>`;
                    });                            
                } else {
                    causaHTML += `<div class="card mb-3 p-0">
                                    <div class="card-body">
                                        <h5 class="card-title">${causa.nomes.join(", ")}</h5>
                                        <p class="card-text label-modal"><small class="text-muted">${dataExecucao}</small></p>
                                    </div>
                                </div>`;
                }
                causaHTML += `</div>`;
        
                listaCausas.innerHTML += causaHTML;
            });
        })
        .catch(error => {
            console.error(error);
        })
    
    }
});