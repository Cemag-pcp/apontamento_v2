document.addEventListener("DOMContentLoaded", () => {

    let cardsInspecao = document.getElementById("cards-inspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-inspecao");
    
    fetch("/inspecao/itens-inspecao-pintura", {
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

        const quantidade = items.dados.length;

        qtdPendenteInspecao.textContent = `${quantidade} itens pendentes`
        
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
                    <button class="btn btn-dark w-100" data-bs-toggle="modal" data-bs-target="#modal-inspecionar-pintura">Iniciar Inspeção</button>
                </div>
            </div>`; 

            cardsInspecao.innerHTML += cards
        });

    }).catch((error) => {
        console.error(error)
    })

})