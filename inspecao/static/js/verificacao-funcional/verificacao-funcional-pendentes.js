// Sample data for different inspection categories
document.addEventListener("DOMContentLoaded", () => {
    buscarItensPendentes(1); // Chama a função quando a página carrega, começando na página 1
});

document.getElementById("btn-filtrar-verificacao-pendentes").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário
    buscarItensPendentes(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-verificacao-pendentes").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-verificacao-pendentes");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensPendentes(1);
});


function buscarItensPendentes(pagina) {
    let cardsVerificacao = document.getElementById("cards-verificacao-pendentes");
    let qtdPendenteVerificacao = document.getElementById("qtd-pendente-verificacao-pendentes");
    let qtdFiltradaVerificacao = document.getElementById("qtd-filtrada-verificacao-pendentes");
    let itensTestar = document.getElementById("itens-testar");
    let itensFiltradosCor = document.getElementById("itens-filtrados-verificacao-pendentes-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-verificacao-pendentes-data");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-verificacao-pendentes-pesquisa");
    let paginacao = document.getElementById("paginacao-verificacao-pendentes-pintura");

    // Limpa os cards antes de buscar novos
    cardsVerificacao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let coresSelecionadas = [];
    document.querySelectorAll('.form-check-input-verificacao-pendentes:checked').forEach(checkbox => {
        coresSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-verificacao-pendentes').value;
    let pesquisarVerificacao = document.getElementById('pesquisar-peca-verificacao-pendentes').value;

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

    if (pesquisarVerificacao) {
        params.append("pesquisar", pesquisarVerificacao);
        itensFiltradosPesquisa.style.display = "block";
        itensFiltradosPesquisa.textContent = "Pesquisa: " + pesquisarVerificacao;
    } else {
        itensFiltradosPesquisa.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/inspecao/api/testes-funcionais-pintura-pendentes/?${params.toString()}`, {
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
        cardsVerificacao.innerHTML = "";

        const quantidadeInspecoes = items.total;
        const quantidadeFiltradaInspecoes = items.total_filtrado;

        qtdPendenteVerificacao.textContent = `${quantidadeInspecoes} itens pendentes`;

        if (params.size > 1) {
            qtdFiltradaVerificacao.style.display = 'block';
        } else {
            qtdFiltradaVerificacao.style.display = 'none';
        }

        qtdFiltradaVerificacao.textContent = `${quantidadeFiltradaInspecoes} itens filtrados`;

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
                    <p>Registro #${item.id}</p>
                    <p>
                        <strong>📅 Dt. Carga:</strong> ${item.data_carga}<br>
                        <strong>📍 Tipo:</strong> ${item.tipo_pintura}<br>
                        <strong>🎨 Cor:</strong> ${item.cor}<br>
                    </p>
                    <hr>
                    <button 
                        data-id="${item.id}"
                        data-data="${item.data_carga}"
                        data-tipo="${item.tipo_pintura}"
                        data-cor="${item.cor}"
                        data-peca="${item.peca}"
                    class="btn btn-dark w-100 iniciar-verificacao-pendentes">
                    Iniciar Teste</button>
                </div>
            </div>`;

            cardsVerificacao.innerHTML += cards;
        });

        itensTestar.textContent = "Itens Pendentes";

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
                        <a class="page-link" href="#" onclick="buscarItensPendentes(${i})">${i}</a>
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

async function itemsPendentes(){
    try {
        const response = await fetch('/inspecao/api/testes-funcionais-pintura-pendentes/');
        const data = await response.json();
        console.log(data);
        console.log(data.length);
        return data.testes; // agora sim retorna para quem chamou
    } catch (error) {
        console.error('Erro:', error);
        return []; // retorna lista vazia em caso de erro
    }
}

