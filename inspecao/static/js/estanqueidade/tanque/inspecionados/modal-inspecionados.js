document.addEventListener("DOMContentLoaded", () => {
    
    const dataInspecao = document.getElementById('data-inspecao-solda-tanque');
    const hoje = new Date().toISOString().split('T')[0];
    dataInspecao.value = hoje;
    
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
                console.log(data);
            
                // Primeiro, limpamos a timeline
                listaTimeline.innerHTML = "";
            
                // Agrupar por número de execução
                const execucoes = {};
            
                data.history.forEach(element => {
                    if (!execucoes[element.num_execucao]) {
                        execucoes[element.num_execucao] = [];
                    }
                    execucoes[element.num_execucao].push(element);
                });
            
                // Obter as execuções em ordem decrescente
                const execucaoKeys = Object.keys(execucoes).sort((a, b) => b - a);
            
                // Para cada execução, criar um carrossel
                execucaoKeys.forEach(num_execucao => {
                    const elementos = execucoes[num_execucao];
            
                    const carrosselId = `carouselExecucao${num_execucao}`;
                    let carrosselInnerHTML = `
                        <h5 class="text-center mb-3">Execução #${num_execucao}</h5>
                        <div id="${carrosselId}" class="carousel slide" data-bs-ride="carousel">
                            <div class="carousel-inner">
                    `;
            
                    elementos.forEach((element, index) => {
                        const isLastItem = parseInt(num_execucao) === parseInt(execucaoKeys[0]);
                        carrosselInnerHTML += `
                            <div class="carousel-item ${index === 0 ? 'active' : ''}">
                                <li class="timeline-item" style="cursor:pointer;">
                                    <div class="timeline-content">
                                        <p class="date">${element.data_execucao}</p>
                                        <p><strong>Inspetor:</strong> ${element.inspetor || 'N/A'}</p>
                                        <p><strong>Pressão Inicial:</strong> ${element.pressao_inicial || 'N/A'}</p>
                                        <p><strong>Pressão Final:</strong> ${element.pressao_final || 'N/A'}</p>
                                        <p><strong>Tipo de Teste:</strong> ${element.tipo_teste || 'N/A'}</p>
                                        <p><strong>Tempo de Execução:</strong> ${element.tempo_execucao || 'N/A'}</p>
                                        <p class="${element.nao_conformidade === true ? 'text-danger' : 'text-success'}">
                                            <strong>Não Conformidade:</strong> ${element.nao_conformidade === true ? 'Sim' : 'Não'}
                                        </p>
                                    </div>
                                </li>
                            </div>
                        `;
                    });
            
                    carrosselInnerHTML += `
                            </div>
                            <button class="carousel-control-prev" type="button" data-bs-target="#${carrosselId}" data-bs-slide="prev">
                                <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                                <span class="visually-hidden">Anterior</span>
                            </button>
                            <button class="carousel-control-next" type="button" data-bs-target="#${carrosselId}" data-bs-slide="next">
                                <span class="carousel-control-next-icon" aria-hidden="true"></span>
                                <span class="visually-hidden">Próximo</span>
                            </button>
                        </div>
                        <hr>
                    `;
            
                    listaTimeline.innerHTML += carrosselInnerHTML;
                });
            
                const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
                tooltips.forEach(t => new bootstrap.Tooltip(t));
            
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
});