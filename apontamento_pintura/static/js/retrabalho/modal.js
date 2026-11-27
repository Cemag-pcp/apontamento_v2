document.addEventListener("click", function(event) {
    if (event.target.closest(".iniciar-retrabalho")) { 

        const id = event.target.getAttribute("data-id");
        const peca = event.target.getAttribute("data-peca");

        document.getElementById("retrabalho-id").value = id;
        document.getElementById("desc-peca").textContent = `Deseja confirmar o retrabalho do conjunto ${peca}?`;

        const modal = new bootstrap.Modal(document.getElementById("modal-confirmar-retrabalho-pintura"));
        modal.show();

    }
})

document.addEventListener("click", function(event) {
    if (event.target.closest(".finalizar-em-processo")) { 

        const botao = event.target.closest(".finalizar-em-processo");

        // Finalizar = registrar o consumo do retrabalho (finalizar-retrabalho.js)
        abrirConsumoRetrabalho([{
            id: botao.getAttribute("data-id"),
            peca: botao.getAttribute("data-peca"),
            cor: botao.getAttribute("data-cor"),
        }]);

    }
})