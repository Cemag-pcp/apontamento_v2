document.addEventListener("DOMContentLoaded", function () {

    const formConfirmarRetrabalho = document.getElementById("form-confirmar-retrabalho")

    formConfirmarRetrabalho.addEventListener("submit", function (event) {
        event.preventDefault();
        const buttonConfirm = this.querySelector("button");

        const formData = new FormData(formConfirmarRetrabalho);
        
        const id = document.getElementById("retrabalho-id").value;

        buttonConfirm.disabled = true;
        buttonConfirm.querySelector(".spinner-border").style.display = "block";

        const modal = bootstrap.Modal.getInstance(document.getElementById("modal-confirmar-retrabalho-pintura"));
        
        formData.append('id', id);

        fetch(`/pintura/api/confirmar-retrabalho-pintura/`, {
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
