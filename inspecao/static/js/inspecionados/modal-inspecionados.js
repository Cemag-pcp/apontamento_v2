document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('historico-inspecao')) {

            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const tipo = event.target.getAttribute("data-tipo");
            const naoConformidade = event.target.getAttribute("data-nao-conformidade");
            const conformidade = event.target.getAttribute("data-conformidade");
            const cor = event.target.getAttribute("data-cor");
            const idDadosExecucao = event.target.getAttribute("data-id-dados-execucao");
            
            fetch(`/inspecao/api/historico-pintura/${id}`, {
                method:"GET",
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erro na requisição HTTP. Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(data);

                const modal = new bootstrap.Modal(document.getElementById("modal-historico-pintura"));
                modal.show();
            })
            .catch(error => {
                console.error(error);
            })
        }
    });
});