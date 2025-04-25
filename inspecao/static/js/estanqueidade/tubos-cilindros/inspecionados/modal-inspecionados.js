document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('historico-inspecao')) {

            const buttonSeeDetails = document.querySelectorAll(".historico-inspecao");
            const button = event.target;
            buttonSeeDetails.forEach((detailsButton) => {
                detailsButton.disabled = true;
            })
            button.querySelector(".spinner-border").style.display = "flex";
            let listaTimeline = document.querySelector(".timeline");
            const id = event.target.getAttribute("data-id");

            listaTimeline.innerHTML = "";
            
            fetch(`/inspecao/api/${id}/historico-tubos-cilindros/`, {
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
                    let nao_conformidade = element.nao_conformidade + element.nao_conformidade_refugo;
                    listaTimeline.innerHTML += `
                    <li class="timeline-item" style="cursor:pointer;" 
                            data-id="${element.id_tubos_cilindros}" 
                            data-nao-conformidade="${nao_conformidade}" 
                            data-data="${element.data_execucao}">
                        <span class="timeline-icon ${nao_conformidade == 0 ? 'success' : 'danger'}">
                            <i class="bi ${nao_conformidade == 0 ? 'bi-check-circle-fill' : 'bi-x-circle-fill'}"></i>
                        </span>
                        <div class="timeline-content">
                            <div class="d-flex justify-content-between">
                                <h5>Execução #${element.num_execucao}</h5>
                                <i class="bi bi-exclamation-circle exclamation-history" data-bs-toggle="tooltip" data-bs-placement="top"
                                    data-bs-custom-class="custom-tooltip"
                                    data-bs-title="Deseja excluir a última execução inspecionada?">
                                </i>
                            </div>
                            <p class="date">${element.data_execucao}</p>
                            <p><strong>Inspetor:</strong> ${element.inspetor}</p>
                            <p class="text-muted"><strong>Conformidade:</strong> ${element.qtd_inspecionada - nao_conformidade}</p>
                            <p class="${nao_conformidade == 0 ? 'text-success' : 'text-danger'}">
                                <strong>Não Conformidade:</strong> ${nao_conformidade}
                            </p>
                        </div>
                    </li>`;
                });
                
                const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
                tooltips.forEach(t => new bootstrap.Tooltip(t));
                const modal = new bootstrap.Modal(document.getElementById("modal-historico-tubos-cilindros"));
                modal.show();
            })
            .catch(error => {
                console.error(error);
            })
            .finally(d => {
                buttonSeeDetails.forEach((detailsButton) => {
                    detailsButton.disabled = false;
                })
                button.querySelector(".spinner-border").style.display = "none";
            })
        }
    });

    document.addEventListener("click", function(event) {
        if (event.target.closest(".timeline-item")) { 

            const naoConformidade = event.target.closest(".timeline-item").getAttribute("data-nao-conformidade");
            if(parseFloat(naoConformidade) > 0) {
    
                const modalHistorico = document.getElementById("modal-historico-tubos-cilindros");
                const listaCausas = document.getElementById("causas-tubos-cilindros");
                const confirmModal = bootstrap.Modal.getInstance(modalHistorico);
                const id = event.target.closest(".timeline-item").getAttribute("data-id");
                const dataExecucao = event.target.closest(".timeline-item").getAttribute("data-data");
                confirmModal.hide();

                listaCausas.innerHTML = `<div class="card" aria-hidden="true">
                                            <img src="/static/img/fundo cinza.png" class="card-img-top" alt="Tela cinza">
                                            <div class="card-body">
                                                <h5 class="card-title placeholder-glow">
                                                <span class="placeholder col-6"></span>
                                                </h5>
                                                <p class="card-text placeholder-glow">
                                                    <span class="placeholder col-12"></span>
                                                </p>
                                                <p class="card-text placeholder-glow">
                                                    <span class="placeholder col-4"></span>
                                                </p>
                                            </div>
                                        </div>` 
                                
                const modalCausas = new bootstrap.Modal(document.getElementById("modal-causas-historico-tubos-cilindros"));
                modalCausas.show();

                fetch(`/inspecao/api/${id}/historico-causas-tubos-cilindros/`, {
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
                    listaCausas.innerHTML = "";
                    data.causas.forEach((causa, index) => {
                        let causaHTML = 
                        `<div class="row mb-3" style="border: 1px solid; border-radius: 10px; padding: 5px; border-color: #ced4da;">
                            <div class="d-flex justify-content-between">
                                <span class="label-modal text-end mb-3 mt-3">Quantidade: ${causa.quantidade}</span>
                                <span class="label-modal text-end mb-3 mt-3">${index + 1}ª Causa</span>
                            </div>`;
                        
                        if(causa.imagens.length > 0) {
                            causa.imagens.forEach(imagem => {
                                causaHTML += `<div class="card mb-3 p-0">
                                                <img src="${imagem.url}" class="card-img-top" alt="...">
                                                <div class="card-body">
                                                    <h5 class="card-title">${causa.nomes.join(", ")}</h5>
                                                    <p class="card-text label-modal"><small class="text-muted">${dataExecucao}</small></p>
                                                </div>
                                            </div>`;
                            });                            
                        } else {
                            causaHTML += `<div class="card mb-3 p-0">
                                            <div class="card-body">
                                                <h5 class="card-title">${causa.nomes.join(", ")}</h5>
                                                <p class="card-text label-modal"><small class="text-muted">${dataExecucao}</small></p>
                                            </div>
                                        </div>`;
                        }
                        causaHTML += `</div>`;
                
                        listaCausas.innerHTML += causaHTML;
                    });
                })
                .catch(error => {
                    console.error(error);
                })
            } else {
                const Toast = Swal.mixin({
                    toast: true,
                    position: "top-end",
                    showConfirmButton: false,
                    timer: 3000,
                    timerProgressBar: true,
                    didOpen: (toast) => {
                      toast.onmouseenter = Swal.stopTimer;
                      toast.onmouseleave = Swal.resumeTimer;
                    }
                  });
                  Toast.fire({
                    icon: "info",
                    title: "Não possui não conformidade"
                  });
            }
        }
    });
});