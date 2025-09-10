document.addEventListener("DOMContentLoaded", function () {

    const formFinalizarRetrabalho = document.getElementById("form-finalizar-retrabalho")

    formFinalizarRetrabalho.addEventListener("submit", function (event) {
        event.preventDefault();
        const buttonConfirm = this.querySelector("button");

        const formData = new FormData(formFinalizarRetrabalho);
        
        const id = document.getElementById("em-processo-id").value;

        buttonConfirm.disabled = true;
        buttonConfirm.querySelector(".spinner-border").style.display = "block";

        const modal = bootstrap.Modal.getInstance(document.getElementById("modal-finalizar-retrabalho-pintura"));
        
        formData.append('id', id);

        fetch(`/pintura/api/finalizar-retrabalho-pintura/`, {
            method:"POST",
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: formData,
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro na requisição HTTP. Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            buscarItensRetrabalho(1);
            buscarItensEmProcesso(1);
            buscarItensInspecionadosRetrabalho(1);
            modal.hide();
        })
        .catch(error => {
            console.error(error);
        }).finally(d => {
            buttonConfirm.disabled = false;
            buttonConfirm.querySelector(".spinner-border").style.display = "none";
        })
    })
})
