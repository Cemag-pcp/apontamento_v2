document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('historico-inspecao')) {

            let listaTimeline = document.querySelector(".timeline");
            const id = event.target.getAttribute("data-id");

            listaTimeline.innerHTML = "";
            
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
                
                console.log(data)

                data.history.forEach(element => {
                    listaTimeline.innerHTML += `
                    <li class="timeline-item">
                        <span class="timeline-icon ${element.nao_conformidade == 0 ? 'success' : 'danger'}">
                            <i class="bi ${element.nao_conformidade == 0 ? 'bi-check-circle-fill' : 'bi-x-circle-fill'}"></i>
                        </span>
                        <div class="timeline-content">
                            <h5>Execução #${element.num_execucao}</h5>
                            <p class="date">${element.data_execucao}</p>
                            <p><strong>Inspetor:</strong> ${element.inspetor}</p>
                            <p class="text-muted"><strong>Conformidade:</strong> ${element.conformidade}</p>
                            <p class="${element.nao_conformidade == 0 ? 'text-success' : 'text-danger'}">
                                <strong>Não Conformidade:</strong> ${element.nao_conformidade}
                            </p>
                        </div>
                    </li>`;
                });
                

                console.log(listaTimeline)
                
                const modal = new bootstrap.Modal(document.getElementById("modal-historico-pintura"));
                modal.show();
            })
            .catch(error => {
                console.error(error);
            })
        }
    });
});