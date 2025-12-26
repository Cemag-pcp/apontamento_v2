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
                
                data.history.forEach((element, index) => {

                    const isFirstItem = index === 0; 

                    listaTimeline.innerHTML += `
                    <li class="timeline-item" style="cursor:pointer;" 
                            data-id="${element.id}" 
                            data-nao-conformidade="${element.nao_conformidade}" 
                            data-data="${element.data_execucao}"
                            data-execucao="${element.num_execucao}">
                        <span class="timeline-icon ${element.nao_conformidade == 0 ? 'success' : 'danger'}">
                            <i class="bi ${element.nao_conformidade == 0 ? 'bi-check-circle-fill' : 'bi-x-circle-fill'}"></i>
                        </span>
                        <div class="timeline-content">
                            <div class="d-flex justify-content-between">
                                <h5>${element.num_execucao === 0? `Inspeção`: `Reinspeção`} #${element.num_execucao}</h5>
                                ${isFirstItem ? `
                                    <i class="bi bi-trash trash-history-last-execution" 
                                        data-id="${element.id}" 
                                        data-id-inspecao="${element.id_inspecao}"
                                        data-nao-conformidade="${element.nao_conformidade}"
                                        data-conformidade="${element.conformidade}" 
                                        data-data="${element.data_execucao}"
                                        data-primeira-execucao="${data.history.length - 1}"
                                        data-bs-toggle="tooltip" 
                                        data-bs-placement="top"
                                        data-bs-custom-class="custom-tooltip"
                                        data-bs-title="Deseja excluir esta execução?">
                                    </i>
                                ` : `<i class="bi bi-trash trash-history-others-execution" 
                                        data-bs-toggle="tooltip" 
                                        data-bs-placement="top"
                                        data-bs-custom-class="custom-tooltip"
                                        data-bs-title="Exclua a última execução para conseguir excluir a execução #${element.num_execucao}">
                                    </i>`}
                            </div>
                            <p class="date">${element.data_execucao}</p>
                            <p><strong>Inspetor:</strong> ${element.inspetor}</p>
                            <p class="text-muted"><strong>Conformidade:</strong> ${element.conformidade}</p>
                            <p class="${element.nao_conformidade == 0 ? 'text-success' : 'text-danger'}">
                                <strong>Não Conformidade:</strong> ${element.nao_conformidade}
                            </p>
                        </div>
                    </li>`;
                });
                
                const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
                tooltips.forEach(t => new bootstrap.Tooltip(t));
                const modal = new bootstrap.Modal(document.getElementById("modal-historico-pintura"));
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
        if (event.target.closest('.bi-trash')) {
            if(event.target.classList.contains('trash-history-last-execution')) {
                const confirmModal = bootstrap.Modal.getInstance(document.getElementById("modal-historico-pintura"));
                confirmModal.hide();

                const id = event.target.getAttribute('data-id');
                const idInspecao = event.target.getAttribute('data-id-inspecao');
                const conformidade = event.target.getAttribute('data-conformidade');
                const naoConformidade = event.target.getAttribute('data-nao-conformidade');
                const dataExecucao = event.target.getAttribute('data-data');
                const indexItem = event.target.getAttribute('data-primeira-execucao');

                let textDescricao;
                if (parseInt(indexItem) !== 0) {
                    textDescricao = "Tem certeza que deseja excluir esta execução? Ao excluir o item será retornado para 'Itens a Reinspecionar'";
                } else {
                    textDescricao = "Tem certeza que deseja excluir esta execução? Ao excluir o item será retornado para 'Itens a Inspecionar'";
                }
                
                // Preenche o modal com os dados
                document.getElementById('modal-execucao-conformidade').textContent = conformidade;
                document.getElementById('modal-execucao-nao-conformidade').textContent = naoConformidade;
                document.getElementById('modal-execucao-data').textContent = dataExecucao;
                document.getElementById('descricao-exclusao').textContent = textDescricao;

                document.getElementById('confirmar-exclusao').setAttribute('data-execucao-id', id);
                document.getElementById('confirmar-exclusao').setAttribute('data-inspecao-id', idInspecao);
                document.getElementById('confirmar-exclusao').setAttribute('primeira-execucao', parseInt(indexItem) === 0);
                
                const modalExcluirExecution = new bootstrap.Modal(document.getElementById("modal-excluir-execucao"));
                modalExcluirExecution.show();
            }
            return;
        }
        if (event.target.closest(".timeline-item")) { 

            const naoConformidade = event.target.closest(".timeline-item").getAttribute("data-nao-conformidade");
            const id = event.target.closest(".timeline-item").getAttribute("data-id");
            const dataExecucao = event.target.closest(".timeline-item").getAttribute("data-data");
            const numExecucao = event.target.closest(".timeline-item").getAttribute("data-execucao");

            if(parseFloat(naoConformidade) > 0) {
    
                const modalHistorico = document.getElementById("modal-historico-pintura");
                const listaCausas = document.getElementById("causas-pintura");
                const confirmModal = bootstrap.Modal.getInstance(modalHistorico);
                confirmModal.hide();
                console.log(listaCausas);

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
                                
                const modalCausas = new bootstrap.Modal(document.getElementById("modal-causas-historico-pintura"));
                modalCausas.show();

                fetch(`/inspecao/api/historico-causas-pintura/${id}`, {
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
                // 1. Pega os elementos do modal e esconde o modal pai
                const modalHistorico = document.getElementById("modal-historico-pintura");
                const listaConteudo = document.getElementById("causas-pintura"); // Alvo mais específico
                const confirmModal = bootstrap.Modal.getInstance(modalHistorico);
                if (confirmModal) {
                    confirmModal.hide();
                }

                // 2. Mostra o placeholder de carregamento
                listaConteudo.innerHTML = `<div class="card" aria-hidden="true">
                                                <img src="/static/img/fundo cinza.png" class="card-img-top" alt="Carregando...">
                                                <div class="card-body">
                                                    <h5 class="card-title placeholder-glow"><span class="placeholder col-6"></span></h5>
                                                    <p class="card-text placeholder-glow"><span class="placeholder col-12"></span></p>
                                                </div>
                                            </div>`;
                
                // Abre o modal que exibirá o conteúdo
                const modalCausas = new bootstrap.Modal(document.getElementById("modal-causas-historico-pintura"));
                modalCausas.show();

                // 3. Faz a requisição para a nova API de conformidades
                fetch(`/inspecao/api/imagens-causas-conformidades-pintura/${id}/${numExecucao}`, {
                    method: "GET",
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
                    listaConteudo.innerHTML = ""; // Limpa o placeholder

                    if (data.imagens && data.imagens.length > 0) {
                        let conformidadeHTML = '';
                        data.imagens.forEach(imagem => {
                            conformidadeHTML += `
                                <div class="card mb-3 p-0">
                                    <img src="${imagem.url}" class="card-img-top" alt="Evidência de Conformidade">
                                    <div class="card-body">
                                        <h5 class="card-title">Inspeção Conforme ✅</h5>
                                        <p class="card-text label-modal">
                                            <small class="text-muted">Evidência registrada em: ${dataExecucao}</small>
                                        </p>
                                    </div>
                                </div>`;
                        });
                        listaConteudo.innerHTML = conformidadeHTML;
                    } else {
                        // Caso não haja imagens, exibe uma mensagem
                        listaConteudo.innerHTML = `<p class="text-center">Esta inspeção foi marcada como conforme, mas não possui imagens de evidência.</p>`;
                    }
                })
                .catch(error => {
                    console.error("Erro ao buscar imagens de conformidade:", error);
                    listaConteudo.innerHTML = `<p class="text-center text-danger">Ocorreu um erro ao carregar as imagens.</p>`;
                });
            }
        }
    });
});
