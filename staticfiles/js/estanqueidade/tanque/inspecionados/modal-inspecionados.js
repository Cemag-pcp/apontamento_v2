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
            
            fetch(`/inspecao/api/${id}/historico-tanque/`, {
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
                            <li class="timeline-item" style="cursor:pointer;">
                            <span class="timeline-icon ${element.vazamento === true ? 'success' : 'danger'}">
                                <i class="bi ${element.vazamento === true ? 'bi-check-circle-fill' : 'bi-x-circle-fill'}"></i>
                            </span>
                            <div class="timeline-content">
                                <h5>Execução #${element.num_execucao}</h5>
                                <p class="date">${element.data_execucao}</p>
                                <p><strong>Inspetor:</strong> ${element.inspetor || 'N/A'}</p>
                                <p><strong>Pressão Inicial:</strong> ${element.pressao_inicial || 'N/A'}</p>
                                <p><strong>Pressão Final:</strong> ${element.pressao_final || 'N/A'}</p>
                                <p><strong>Tipo de Teste:</strong> ${element.tipo_teste || 'N/A'}</p>
                                <p><strong>Tempo de Execução:</strong> ${element.tempo_execucao || 'N/A'}</p>
                                <p class="${element.vazamento === true ? 'text-success' : 'text-danger'}">
                                    <strong>Não Conformidade:</strong> ${element.vazamento === true ? 'Não' : 'Sim'}
                                </p>
                            </div>
                        </li>`;
                });
                
                
                const modal = new bootstrap.Modal(document.getElementById("modal-historico-tanque"));
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