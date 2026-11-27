document.addEventListener("DOMContentLoaded", () => {
    buscarItensInspecao(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-inspecao-serra-usinagem").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensInspecao(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-inspecao-serra-usinagem").addEventListener("click", (event) => {
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
    let itensFiltradosStatus = document.getElementById("itens-filtrados-inspecao-status");
    let itensFiltradosDataInicio = document.getElementById("itens-filtrados-inspecao-data-inicio");
    let itensFiltradosDataFim = document.getElementById("itens-filtrados-inspecao-data-fim");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-inspecao-pesquisa");
    let paginacao = document.getElementById("paginacao-inspecao-serra-usinagem");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let maquinasSelecionadas = [];
    document.querySelectorAll('.form-check-input-inspecao-serra-usinagem:checked').forEach(checkbox => {
        maquinasSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let statusSelecionados = [];
    document.querySelectorAll('.form-check-status-input-inspecao-serra-usinagem:checked').forEach(checkbox => {
        statusSelecionados.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionadaInicio = document.getElementById('data-filtro-inspecao-inicio').value;
    let dataSelecionadaFim = document.getElementById('data-filtro-inspecao-fim').value;

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

    if (statusSelecionados.length > 0) {
        console.log(statusSelecionados);
        params.append("status", statusSelecionados.join(","));
        itensFiltradosStatus.style.display = "block";
        itensFiltradosStatus.textContent = "Status: " + statusSelecionados.join(", ");
    } else {
        itensFiltradosStatus.style.display = "none";
    }

    if (dataSelecionadaInicio) {
        params.append("data_inicio", dataSelecionadaInicio);
        itensFiltradosDataInicio.style.display = "block";
        itensFiltradosDataInicio.textContent = "Data: " + dataSelecionadaInicio;
    } else {
        itensFiltradosDataInicio.style.display = "none";
    }

    if (dataSelecionadaFim) {
        params.append("data_fim", dataSelecionadaFim);
        itensFiltradosDataFim.style.display = "block";
        itensFiltradosDataFim.textContent = "Data: " + dataSelecionadaFim;
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

    fetch(`/inspecao/api/itens-inspecao-serra-usinagem/?${params.toString()}`, {
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

        const quantidadeInspecoes = items.total_inspecoes_sem_filtros;
        const quantidadeFiltradaInspecoes = items.paginacao.total_filtrado;
        const status = {
            "Não iniciado":"devolvido",
            "Em andamento": "pendente"
        }

        qtdPendenteInspecao.textContent = `${quantidadeInspecoes} itens pendentes`;

        if (params.size > 1) {
            qtdFiltradaInspecao.style.display = 'block';
        } else {
            qtdFiltradaInspecao.style.display = 'none';
        }

        qtdFiltradaInspecao.textContent = `${quantidadeFiltradaInspecoes} itens filtrados`;

        items.dados.forEach(item => {
            const emAndamento = item.status === "Em andamento";
            const statusTexto = emAndamento
                ? `Parcial (${item.amostras_feitas}/${item.amostras_exigidas} amostras)`
                : item.status;
            const badge100 = item.inspecao_completa
                ? '<p class="status-badge status-aprovado mt-1" style="font-size:13px" title="Inspeção 100% marcada">100%</p>'
                : '';
            // inspeção aberta no início da ordem: operador ainda produzindo (inspeção em tempo real)
            const badgeProducao = item.em_producao
                ? '<p class="status-badge status-entregue mt-1" style="font-size:13px" title="Ordem iniciada pelo operador, ainda não finalizada">Em produção</p>'
                : '';
            let linhaQuantidade = item.em_producao
                ? `<strong>🔢 Quantidade Planejada:</strong> ${item.qtd_planejada} <small class="text-muted">(em produção)</small>`
                : `<strong>🔢 Quantidade Produzida:</strong> ${item.qtd_apontada}`;
            if (item.em_producao && item.qtd_inspecionar) {
                linhaQuantidade += `<br><strong>🔍 Quantidade a Inspecionar:</strong> ${item.qtd_inspecionar}`;
            }
            const qtdReferencia = item.qtd_apontada || item.qtd_inspecionar || item.qtd_planejada;

            const cards = `
            <div class="col-md-4 mb-4">
                <div class="card p-3" style="min-height: 300px; display: flex; flex-direction: column; justify-content: space-between">
                    <div class="d-flex justify-content-between">
                        <h5 style="width:70%;"> <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(item.peca)}" target="_blank" rel="noopener noreferrer">${item.peca}</a></h5>
                        <div class="text-center">
                            <p class="status-badge status-${status[item.status]}" style="font-size:13px">${statusTexto}</p>
                            ${badge100}
                            ${badgeProducao}
                        </div>
                    </div>
                    <p>Inspecao #${item.id}</p>
                    <p>
                        <strong>📅 Data:</strong> ${item.data}<br>
                        <strong>⚙️ Máquina:</strong> ${item.maquina}<br>
                        ${linhaQuantidade}<br>
                        <strong>🧑🏻‍🏭 Operador:</strong> ${item.operador || '-'}
                    </p>
                    <hr>
                    <button
                        data-id="${item.id}"
                        data-data="${item.data}"
                        data-qtd="${qtdReferencia}"
                        data-em-producao="${item.em_producao ? 'true' : 'false'}"
                        data-peca="${item.peca}"
                        data-maquina="${item.maquina}"
                    class="btn btn-dark w-100 iniciar-inspecao" id="openModalButton">
                    ${emAndamento ? 'Continuar Inspeção' : 'Iniciar Inspeção'}</button>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;

        });

        // Chamar modal ao clicar em "Iniciar Inspecao"
        document.querySelectorAll('.iniciar-inspecao').forEach(button => {
            button.addEventListener('click', function () {
                abrirModalInspecaoSerraUsinagem({
                    id: this.getAttribute('data-id'),
                    qtd: this.getAttribute('data-qtd'),
                    peca: this.getAttribute('data-peca'),
                    maquina: this.getAttribute('data-maquina'),
                    em_producao: this.getAttribute('data-em-producao') === 'true',
                });
            });
        });

        itensInspecionar.textContent = "Itens a Inspecionar";
        if (items.paginacao.total_paginas > 1) {
            let paginacaoHTML = `<nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">`;

            const paginaAtual = items.paginacao.pagina_atual;
            const totalPaginas = items.paginacao.total_paginas;

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
