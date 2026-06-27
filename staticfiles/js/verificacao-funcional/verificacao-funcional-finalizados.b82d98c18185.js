document.addEventListener("DOMContentLoaded", () => {
    buscarItensFinalizados(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-verificacao-finalizados").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensFinalizados(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-verificacao-finalizados").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-verificacao-finalizados");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensFinalizados(1);
});

function buscarItensFinalizados(pagina) {
    let cardsInspecao = document.getElementById("cards-verificacao-finalizados");
    let qtdPendenteInspecao = document.getElementById("qtd-verificacao-finalizados");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-verificacao-finalizados");
    let itensInspecionar = document.getElementById("itens-testados");
    let itensFiltradosCor = document.getElementById("itens-filtrados-verificacao-finalizados-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-verificacao-finalizados-data");
    let itensFiltradosDataFinalizacao = document.getElementById("itens-filtrados-verificacao-finalizados-data-final");
    // let itensFiltradosInspetor = document.getElementById("itens-filtrados-verificacao-finalizados-inspetor");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-verificacao-finalizados-pesquisa");
    let itensFiltradosStatusConformidade = document.getElementById("itens-filtrados-verificacao-finalizados-status");
    let paginacao = document.getElementById("paginacao-verificacao-finalizados-pintura");
    let itensFiltradosTipoPintura = document.getElementById("itens-filtrados-verificacao-finalizados-tipo-pintura");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let coresSelecionadas = [];
    document.querySelectorAll('.form-check-input-verificacao-finalizados:checked').forEach(checkbox => {
        coresSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    // let inspetorSelecionado = [];
    // document.querySelectorAll('.form-check-input-verificacao-finalizados-inspetores:checked').forEach(checkbox => {
    //     inspetorSelecionado.push(checkbox.nextElementSibling.textContent.trim());
    // });

    let statusConformidade = [];    
    if (document.getElementById('filter-itens-verificacao-aprovados-pintura').checked) {
        statusConformidade.push('aprovado');
    }

    let tipoPinturaSelecionadas = [];
    if (document.getElementById('pintura-po-verificacao-finalizados').checked){
        tipoPinturaSelecionadas.push('po');
    }

    if (document.getElementById('pintura-pu-verificacao-finalizados').checked){
        tipoPinturaSelecionadas.push('pu');
    }
    
    // Verifica se o checkbox de itens não conformes está marcado
    if (document.getElementById('filter-itens-verificacao-reprovados-pintura').checked) {
        statusConformidade.push('reprovado');
    }

    let dataCriacaoInicialSelecionada = document.getElementById('data-criacao-inicial-filtro-verificacao-finalizadas').value;
    let dataCriacaoFinalSelecionada = document.getElementById('data-criacao-final-filtro-verificacao-finalizadas').value;
    let dataFinalizacaoInicioSelecionada = document.getElementById('data-finalizacao-inicial-filtro-verificacao-finalizadas').value;
    let dataFinalizacaoFinalSelecionada = document.getElementById('data-finalizacao-final-filtro-verificacao-finalizadas').value;

    let pesquisarInspecao = document.getElementById('pesquisar-peca-verificacao-finalizados').value;

    // Datas em formato BR para exibição do filtro aplicado
    let formatadaCriacaoInicio, formatadaCriacaoFim;
    let formatadaFinalizacaoInicio, formatadaFinalizacaoFinal;

    if (dataCriacaoInicialSelecionada){
        formatadaCriacaoInicio = dataPTBR(dataCriacaoInicialSelecionada);
    }

    if (dataCriacaoFinalSelecionada){
        formatadaCriacaoFim = dataPTBR(dataCriacaoFinalSelecionada);
    }

    if (dataFinalizacaoInicioSelecionada){
        formatadaFinalizacaoInicio = dataPTBR(dataFinalizacaoInicioSelecionada);
    }

    if (dataFinalizacaoFinalSelecionada){
        formatadaFinalizacaoFinal = dataPTBR(dataFinalizacaoFinalSelecionada);
    }

    // Monta os parâmetros de busca
    let params = new URLSearchParams();
    if (coresSelecionadas.length > 0) {
        params.append("cores", coresSelecionadas.join(","));
        itensFiltradosCor.style.display = "block";
        itensFiltradosCor.textContent = "Cores: " + coresSelecionadas.join(", ");
    } else {
        itensFiltradosCor.style.display = "none";
    }

    // Data Criação
    if (dataCriacaoInicialSelecionada) {
        params.append("dataCriacaoInicio", dataCriacaoInicialSelecionada);
        itensFiltradosData.style.display = "block";
        itensFiltradosData.textContent = `Data Criação: ${formatadaCriacaoInicio} até hoje`;
    } else {
        itensFiltradosData.style.display = "none";
    }
    
    if (dataCriacaoFinalSelecionada){
        params.append("dataCriacaoFinal", dataCriacaoFinalSelecionada);
        if (dataCriacaoInicialSelecionada){
            itensFiltradosData.textContent = `Data Criação: ${formatadaCriacaoInicio} até ${formatadaCriacaoFim}`;
        } else{
            itensFiltradosData.textContent = `Data Criação: até ${formatadaCriacaoFim}`;
        }
    } else if (!dataCriacaoInicialSelecionada){
        itensFiltradosData.style.display = "none";
    }

    // Data Finalização

    if (dataFinalizacaoInicioSelecionada) {
        params.append("dataFinalizacaoInicial", dataFinalizacaoInicioSelecionada);
        itensFiltradosDataFinalizacao.style.display = "block";
        itensFiltradosDataFinalizacao.textContent = `Data Finalização: ${formatadaFinalizacaoInicio} até hoje`;
    } else {
        itensFiltradosDataFinalizacao.style.display = "none";
    }

    if (dataFinalizacaoFinalSelecionada){
        params.append("dataFinalizacaoFinal", dataFinalizacaoFinalSelecionada);
        if (dataFinalizacaoFinalSelecionada){
            itensFiltradosDataFinalizacao.textContent = `Data Finalização: ${formatadaFinalizacaoInicio} até ${formatadaFinalizacaoFinal}`;
        } else{
            itensFiltradosDataFinalizacao.textContent = `Data Finalização: até ${formatadaFinalizacaoFinal}`;
        }
    } else if (!dataFinalizacaoInicioSelecionada){
        itensFiltradosDataFinalizacao.style.display = "none";
    }

    if (pesquisarInspecao) {
        params.append("pesquisar", pesquisarInspecao);
        itensFiltradosPesquisa.style.display = "block";
        itensFiltradosPesquisa.textContent = "Pesquisa: " + pesquisarInspecao;
    } else {
        itensFiltradosPesquisa.style.display = "none";
    }

    if (statusConformidade.length > 0) {
        params.append("statusTeste", statusConformidade.join(","));
        itensFiltradosStatusConformidade.style.display = "block";
        itensFiltradosStatusConformidade.textContent = "Status: " + 
            statusConformidade.map(s => s === 'aprovado' ? 'Itens Aprovados' : 'Itens Reprovados').join(", ");
    } else {
        itensFiltradosStatusConformidade.style.display = "none";
    }

    if (tipoPinturaSelecionadas.length > 0) {
        params.append("tipoPintura", tipoPinturaSelecionadas.join(","));
        itensFiltradosTipoPintura.style.display = "block";
        itensFiltradosTipoPintura.textContent = "Tipo Pintura: " + 
            tipoPinturaSelecionadas.map(s => s === 'pu' ? 'Itens PU' : 'Itens PÓ').join(", ");
    } else {
        itensFiltradosTipoPintura.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros
    params.append("status", "finalizado"); // Garante apenas os itens pendentes

    fetch(`/inspecao/api/testes-funcionais-pintura/?${params.toString()}`, {
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

        qtdPendenteInspecao.textContent = `${quantidadeInspecoes} itens finalizados`;

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

            let iconeAprovado;

            if (item.status === 'aprovado') {
                iconeAprovado = '<i class="bi bi-check-circle-fill" style="color:green"></i>';
            } else {
                iconeAprovado = '<i class="bi bi-x-circle-fill" style="color:red"></i>';
            }
            let textoStatus = item.status === "aprovado" ? "Aprovado" : "Reprovado";
            let color = borderColors[item.cor];

            let causasReprovacao = [];
            let textoCausasReprovacao = '';
            // 'aderencia': 'Aprovado' if data['aderencia'] else ('Reprovado' if data['aderencia'] is False else 'Não verificado'),
            //     'tonalidade': 'Aprovado' if data['tonalidade'] else ('Reprovado' if data['tonalidade'] is False else 'Não verificado'),
            //     'polimerizacao': 'Aprovado' if data['polimerizacao'] else ('Reprovado' if data['polimerizacao'] is False else 'Somente para PÓ'),
            //     'resultado_espessura': espessura_camada_resultado if espessura_camada_resultado else 'Não verificado',
            if (item.status === 'reprovado'){
                if (item.aderencia === 'Reprovado') causasReprovacao.push('Aderência');
                if (item.tonalidade === 'Reprovado') causasReprovacao.push('Tonalidade');
                if (item.resultado_espessura === 'Reprovado') causasReprovacao.push('Espessura de Camada');
                if (item.polimerizacao != null){
                    if (item.polimerizacao === 'Reprovado') causasReprovacao.push('Polimerização');
                }
                textoCausasReprovacao = `<strong>❌ Motivo Reprovação:</strong> ${causasReprovacao.length > 0 ? causasReprovacao.join(', '): 'Aprovado'}<br></br>`
            }
            const cards = `
            <div class="col-md-4 mb-4">
                <div class="card p-3 border-${color}" style="min-height: 300px; display: flex; flex-direction: column; justify-content: space-between">
                    <h5> ${item.peca}</h5>
                    <p>Ordem #${item.ordem}</p>
                    <p>
                        <strong>📅 Data de Criação:</strong> ${item.data_inicial}<br>
                        <strong>📅 Data de Finalização:</strong> ${item.data_atualizacao}<br>
                        <strong>📍 Tipo:</strong> ${item.tipo_pintura}<br>
                        <strong>🎨 Cor:</strong> ${item.cor}<br>
                        <strong>👷‍♂️ Inspetor:</strong> ${item.inspetor}<br>
                        ${textoCausasReprovacao}              
                    </p>
                    <hr>
                    <div class="d-flex justify-content-between">
                        <div class="d-flex align-items-baseline gap-2">
                            ${iconeAprovado}
                            <h4 style="font-size: 0.875rem; color:#71717a;">${textoStatus}</h4>
                        </div>
                        <button 
                            data-id="${item.id}"
                            data-data-inicial="${item.data_inicial}"
                            data-data-atualizacao="${item.data_atualizacao}"
                            data-peca="${item.peca}"
                            data-tipo="${item.tipo_pintura}"
                            data-aprovado="${item.status}"
                            data-reprovado="${item.status}"
                            data-cor="${item.cor}"
                        class="btn btn-white historico-verificacao-funcional w-50 d-flex justify-content-center align-items-center gap-2">              
                            <span class="spinner-border spinner-border-sm" style="display:none"></span>
                            Ver detalhes
                        </button>
                    </div>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;
        });

        itensInspecionar.textContent = "Itens Finalizados";
        
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
                        <a class="page-link" href="#" onclick="buscarItensFinalizados(${i})">${i}</a>
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
    }).finally(() => {
        atribuirDadosModalVerDetalhes(); // Reatribui os eventos de clique aos novos botões
    });
}