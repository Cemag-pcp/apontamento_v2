document.addEventListener("DOMContentLoaded", () => {
    buscarItensInspecionados(); // Chama a função quando a página carrega
});

document.getElementById("btn-filtrar-inspecionados").addEventListener("click", () => {
    buscarItensInspecionados(); // Chama a função quando o botão de filtro é clicado
});


function buscarItensInspecionados() {

    let cardsInspecao = document.getElementById("cards-inspecionados");
    let qtdPendenteInspecao = document.getElementById("qtd-inspecionados");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-inspecionados");
    let itensInspecionar = document.getElementById("itens-inspecionados");

    let itensFiltradosCor = document.getElementById("itens-filtrados-inspecionados-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-inspecionados-data");
    let itensFiltradosInspetor = document.getElementById("itens-filtrados-inspecionados-inspetor");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-inspecionados-pesquisa");

    cardsInspecao.innerHTML = "";

    // Coletar os filtros aplicados
    let coresSelecionadas = [];
    document.querySelectorAll('.form-check-input-inspecionados:checked').forEach(checkbox => {
        coresSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });
    let inspetorSelecionado = [];
    document.querySelectorAll('.form-check-input-inspecionados-inspetores:checked').forEach(checkbox => {
        inspetorSelecionado.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-inspecionados').value;
    let pesquisarInspecao = document.getElementById('pesquisar-peca-inspecionados').value;
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

    fetch(`/inspecao/api/itens-inspecionados-pintura/?${params.toString()}`, {
        methot: 'GET',
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
        console.log(items)
        cardsInspecao.innerHTML = "";

        const quantidadeInspecoes = items.total;
        const quantidadeFiltradaInspecoes = items.total_filtrado;

        qtdPendenteInspecao.textContent = `${quantidadeInspecoes} itens pendentes`;

        if (params.size > 0) {
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
            }

            let iconeNaoConformidade;

            if (item.possui_nao_conformidade) {
                iconeNaoConformidade = '<i class="bi bi-check-circle-fill" style="color:green"></i>'
            } else {
                iconeNaoConformidade = '<i class="bi bi-x-circle-fill" style="color:red"></i>'
            }

            let color = borderColors[item.cor]

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
                    <div class="d-flex justify-content-between">
                        <div class="d-flex align-items-baseline gap-2">
                            ${iconeNaoConformidade}
                            <h4 style="font-size: 0.875rem; color:#71717a;">Possui nao conformidade?</h4>
                        </div>
                        <button class="btn btn-white w-50" data-bs-toggle="modal" data-bs-target="#modal-historico-pintura">Ver detalhes</button>
                    </div>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards
        });

        itensInspecionar.textContent = "Itens Inspecionados";

    }).catch((error) => {
        console.error(error)
    })

}