document.addEventListener("DOMContentLoaded", () => {
    buscarItensEmProcesso(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-em-processo").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensEmProcesso(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-em-processo").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-em-processo");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensEmProcesso(1);
});

function buscarItensEmProcesso(pagina) {
    let cardsInspecao = document.getElementById("cards-em-processo");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-em-processo");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-em-processo");
    let itensInspecionar = document.getElementById("titulo-itens-em-processo");
    let itensFiltradosCor = document.getElementById("itens-filtrados-em-processo-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-em-processo-data");
    let itensFiltradosInspetor = document.getElementById("itens-filtrados-em-processo-inspetor");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-em-processo-pesquisa");
    let paginacao = document.getElementById("paginacao-em-processo-pintura");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let coresSelecionadas = [];
    document.querySelectorAll('.form-check-input-em-processo:checked').forEach(checkbox => {
        coresSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let inspetorSelecionado = [];
    document.querySelectorAll('.form-check-input-em-processo-inspetores:checked').forEach(checkbox => {
        inspetorSelecionado.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-em-processo').value;
    let pesquisarInspecao = document.getElementById('pesquisar-peca-em-processo').value;

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

    if (inspetorSelecionado.length > 0) {
        params.append("inspetores", inspetorSelecionado.join(","));
        itensFiltradosInspetor.style.display = "block";
        itensFiltradosInspetor.textContent = "Inspetores: " + inspetorSelecionado.join(", ");
    } else {
        itensFiltradosInspetor.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/pintura/api/itens-em-processo-pintura/?${params.toString()}`, {
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

        // qtdPendenteInspecao.textContent = `${quantidadeInspecoes} itens pendentes`;

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
                    <div class="d-flex justify-content-between align-items-start">
                        <h5 class="mb-0">${item.peca}</h5>
                        <input
                            type="checkbox"
                            class="form-check-input selecionar-finalizar-lote"
                            data-id="${item.id}"
                            aria-label="Selecionar retrabalho para finalizar"
                        >
                    </div>
                    <p>Inspecao #${item.id}</p>
                    <p>
                        <strong>📅 Data da última inspeção:</strong> ${item.data}<br>
                        <strong>📍 Tipo:</strong> ${item.tipo}<br>
                        <strong>🧮 Conformidade:</strong> ${item.conformidade}<br>
                        <strong>🔢 Não conformidade:</strong> ${item.nao_conformidade}<br>
                        <strong>🎨 Cor:</strong> ${item.cor}<br>
                        <strong>🧑🏻‍🏭 Inspetor:</strong> ${item.inspetor}
                    </p>
                    <hr>
                    <button 
                        data-id="${item.id}"
                        data-data="${item.data}"
                        data-tipo="${item.tipo}"
                        data-nao-conformidade="${item.nao_conformidade}"
                        data-conformidade="${item.conformidade}"
                        data-cor="${item.cor}"
                        data-peca="${item.peca}"
                    class="btn btn-dark w-100 finalizar-em-processo">
                    Finalizar Retrabalho</button>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;
        });
        atualizarBotaoFinalizarLote();

        itensInspecionar.textContent = "Em processo de retrabalho";
        document.getElementById('badge-em-processo').innerText = quantidadeInspecoes;
        document.querySelector('#itens-em-processo .spinner-border').style.display = 'none';

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
                        <a class="page-link" href="#" onclick="buscarItensEmProcesso(${i})">${i}</a>
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

function atualizarBotaoFinalizarLote() {
    const botaoLote = document.getElementById("btn-finalizar-retrabalho-lote");
    if (!botaoLote) {
        return;
    }
    const selecionados = document.querySelectorAll(".selecionar-finalizar-lote:checked");
    botaoLote.disabled = selecionados.length === 0;
    botaoLote.textContent = selecionados.length > 0
        ? `Finalizar selecionados (${selecionados.length})`
        : "Finalizar selecionados";
}

document.addEventListener("change", function(event) {
    if (event.target.classList.contains("selecionar-finalizar-lote")) {
        atualizarBotaoFinalizarLote();
    }
});

const botaoFinalizarLote = document.getElementById("btn-finalizar-retrabalho-lote");
if (botaoFinalizarLote) {
    botaoFinalizarLote.addEventListener("click", async () => {
        const selecionados = Array.from(document.querySelectorAll(".selecionar-finalizar-lote:checked"));
        if (!selecionados.length) {
            return;
        }
        if (!window.confirm(`Deseja finalizar o retrabalho de ${selecionados.length} item(ns)?`)) {
            return;
        }

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        const textoOriginal = botaoFinalizarLote.textContent;
        botaoFinalizarLote.disabled = true;
        botaoFinalizarLote.textContent = "Finalizando...";

        const requisicoes = selecionados.map((checkbox) => {
            const formData = new FormData();
            formData.append("id", checkbox.dataset.id);
            return fetch(`/pintura/api/finalizar-retrabalho-pintura/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                },
                body: formData,
            }).then((response) => {
                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                return response.json();
            });
        });

        const resultados = await Promise.allSettled(requisicoes);
        const quantidadeSucesso = resultados.filter((resultado) => resultado.status === "fulfilled").length;
        const quantidadeErro = resultados.length - quantidadeSucesso;

        if (quantidadeErro > 0) {
            console.error(`Falha ao finalizar ${quantidadeErro} item(ns) de retrabalho.`);
        }

        buscarItensEmProcesso(1);
        buscarItensInspecionadosRetrabalho(1);

        botaoFinalizarLote.disabled = false;
        botaoFinalizarLote.textContent = textoOriginal;
    });
}
