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

        const id = event.target.getAttribute("data-id");
        const peca = event.target.getAttribute("data-peca");

        document.getElementById("em-processo-id").value = id;
        document.getElementById("desc-peca-em-processo").textContent = `Deseja finalizar o retrabalho do conjunto ${peca}?`;

        const modal = new bootstrap.Modal(document.getElementById("modal-finalizar-retrabalho-pintura"));
        modal.show();

    }
})