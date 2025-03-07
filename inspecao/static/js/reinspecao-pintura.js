document.addEventListener("DOMContentLoaded", () => {
    buscarItensReinspecao(); // Chama a função quando a página carrega
});

document.getElementById("btn-filtrar-reinspecao").addEventListener("click", () => {
    buscarItensReinspecao(); // Chama a função quando o botão de filtro é clicado
});

function buscarItensReinspecao() {

    let cardsInspecao = document.getElementById("cards-reinspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-reinspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-reinspecao");

    let itensInspecionar = document.getElementById("itens-reinspecao");

    let itensFiltradosCor = document.getElementById("itens-filtrados-reinspecao-cor");
    let itensFiltradosData = document.getElementById("itens-filtrados-reinspecao-data");
    let itensFiltradosInspetor = document.getElementById("itens-filtrados-reinspecao-inspetor");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-reinspecao-pesquisa");

    cardsInspecao.innerHTML = "";

    // Coletar os filtros aplicados
    let coresSelecionadas = [];
    document.querySelectorAll('.form-check-input-reinspecao:checked').forEach(checkbox => {
        coresSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });
    let inspetorSelecionado = [];
    document.querySelectorAll('.form-check-input-reinspecao-inspetores:checked').forEach(checkbox => {
        inspetorSelecionado.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-reinspecao').value;
    let pesquisarInspecao = document.getElementById('pesquisar-peca-reinspecao').value;
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

    fetch(`/inspecao/api/itens-reinspecao-pintura/?${params.toString()}`, {
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
                    "Laranja": "orange","Verde": "green", 
                    "Vermelho":"red","Azul":"blue",
                    "Amarelo":"yellow","Cinza":"gray"
                }
    
                let color =  borderColors[item.cor]
    
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
                        <button class="btn btn-dark w-100" data-bs-toggle="modal" data-bs-target="#modal-reinspecionar-pintura">Iniciar Reinspeção</button>
                    </div>
                </div>`; 
    
                cardsInspecao.innerHTML += cards
            });

        itensInspecionar.textContent = "Itens a Reinspecionar";

    }).catch((error) => {
        console.error(error)
    })
}