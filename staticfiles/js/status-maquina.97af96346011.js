document.addEventListener('DOMContentLoaded', function () {

    // Atualiza a cada 10 segundos
    fetchStatusMaquinas();
    setInterval(fetchStatusMaquinas, 10000);

    fetchUltimasPecasProduzidas();
    setInterval(fetchUltimasPecasProduzidas, 10000);

    fetchContagemStatusOrdens();
    setInterval(fetchContagemStatusOrdens, 10000);

    document.getElementById('btnPararMaquina').addEventListener('click', () => {
        mostrarModalPararMaquina(); // Chama a função ao clicar no botão
    });

});

function fetchStatusMaquinas() {
    // Seleciona os elementos do container
    const indicador = document.querySelector('.col-md-6.text-center .display-4');
    const descricao = document.querySelector('.col-md-6.text-center p');
    const listaStatus = document.querySelector('.col-md-6 ul');

    // Faz a requisição para a API
    fetch('api/status_maquinas/')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Atualiza o indicador de percentual
            const totalMaquinas = data.status.length;
            const maquinasOperando = data.status.filter(maquina => maquina.status === 'Em produção').length;
            const percentualOperando = totalMaquinas > 0 ? Math.round((maquinasOperando / totalMaquinas) * 100) : 0;

            indicador.textContent = `${percentualOperando}%`;
            descricao.textContent = 'Máquinas em operação';

            // Atualiza a lista de status das máquinas
            listaStatus.innerHTML = ''; // Limpa os itens antigos
            if (data.status.length > 0) {
                data.status.forEach(maquina => {
                    const statusColor = 
                        maquina.status === 'Em produção' ? 'bg-warning' : 
                        maquina.status === 'Parada' ? 'bg-danger' : 
                        'bg-success';

                    const statusItem = document.createElement('li');
                    statusItem.classList.add('mb-2', 'd-flex', 'align-items-center', 'gap-2');
                    statusItem.innerHTML = `
                        <span class="fw-bold">${maquina.maquina}</span>
                        <div class="status-circle ${statusColor}" style="
                            width: 15px;
                            height: 15px;
                            border-radius: 50%;
                        "></div>
                    `;
                    listaStatus.appendChild(statusItem);
                });
            } else {
                // Caso não haja máquinas registradas
                listaStatus.innerHTML = '<li class="text-muted">Nenhuma máquina registrada no momento.</li>';
            }
        })
        .catch(error => {
            console.error('Erro ao buscar status das máquinas:', error);
            indicador.textContent = '0%';
            descricao.textContent = 'Erro ao carregar dados';
            listaStatus.innerHTML = '<li class="text-danger">Erro ao carregar os dados.</li>';
        });
}

function fetchUltimasPecasProduzidas() {
    // Seleciona o elemento da lista onde as peças serão adicionadas
    const listaPecas = document.querySelector('.col-md-4 .list-group');

    // Faz a requisição para a API
    fetch('api/ultimas_pecas_produzidas/')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Limpa o conteúdo anterior da lista
            listaPecas.innerHTML = '';

            // Adiciona os itens retornados pela API
            if (data.pecas && data.pecas.length > 0) {
                data.pecas.forEach(peca => {
                    const listItem = document.createElement('li');
                    listItem.classList.add('list-group-item', 'd-flex', 'justify-content-between', 'align-items-center');
                    listItem.innerHTML = `
                        <span><i class="fa fa-cube text-primary me-2"></i>${peca.nome}</span>
                        <span class="badge bg-primary rounded-pill">${peca.quantidade}</span>
                    `;
                    listaPecas.appendChild(listItem);
                });
            } else {
                // Caso não haja peças retornadas
                listaPecas.innerHTML = '<li class="list-group-item text-muted text-center">Nenhuma peça produzida recentemente.</li>';
            }
        })
        .catch(error => {
            console.error('Erro ao buscar as últimas peças produzidas:', error);
            listaPecas.innerHTML = '<li class="list-group-item text-danger text-center">Erro ao carregar os dados.</li>';
        });
}

function fetchContagemStatusOrdens() {
    // Seleciona o elemento da lista onde os status serão adicionados
    const listaStatus = document.getElementById('status-ordens-list');

    // Faz a requisição para a API
    fetch('api/status_ordem/')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Limpa o conteúdo anterior da lista
            listaStatus.innerHTML = '';

            // Adiciona os itens retornados pela API
            if (data.status_contagem && data.status_contagem.length > 0) {
                data.status_contagem.forEach(status => {
                    const statusColor = {
                        'aguardando_iniciar': 'primary',
                        'iniciada': 'success',
                        'interrompida': 'warning',
                        'finalizada': 'secondary',
                    }[status.status] || 'secondary';

                    const listItem = document.createElement('li');
                    listItem.classList.add('mb-3');
                    listItem.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <span class="text-${statusColor} fw-bold">${status.status.replace('_', ' ')}:</span>
                            <span class="fw-bold text-${statusColor}">${status.total}</span>
                        </div>
                        <div class="progress" style="height: 10px;">
                            <div class="progress-bar bg-${statusColor}" role="progressbar" style="width: ${status.porcentagem}%;" aria-valuenow="${status.porcentagem}" aria-valuemin="0" aria-valuemax="100"></div>
                        </div>
                    `;
                    listaStatus.appendChild(listItem);
                });
            } else {
                // Caso não haja status retornados
                listaStatus.innerHTML = '<li class="text-muted text-center">Nenhuma ordem encontrada.</li>';
            }
        })
        .catch(error => {
            console.error('Erro ao buscar contagem de status das ordens:', error);
            listaStatus.innerHTML = '<li class="text-danger text-center">Erro ao carregar os dados.</li>';
        });
}

async function fetchMaquinasDisponiveis() {
    try {
        const response = await fetch('api/buscar-maquinas-disponiveis/');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        // Exemplo de manipulação dos dados retornados
        const selectMaquina = document.getElementById('escolhaMaquinaParada');
        selectMaquina.innerHTML = ''; // Limpa as opções anteriores

        if (data.maquinas_disponiveis.length > 0) {
            data.maquinas_disponiveis.forEach(maquina => {
                const option = document.createElement('option');
                option.value = maquina.alias; // Usa o alias como valor
                option.textContent = maquina.nome; // Usa o nome como texto visível
                selectMaquina.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.textContent = 'Nenhuma máquina disponível';
            option.disabled = true;
            selectMaquina.appendChild(option);
        }
    } catch (error) {
        console.error('Erro ao buscar máquinas disponíveis:', error);
    }
}

async function mostrarModalPararMaquina() {
    const modal = new bootstrap.Modal(document.getElementById('modalPararMaquina'));
    const modalTitle = document.getElementById('modalPararMaquinaLabel');
    const formInterromper = document.getElementById('formPararMaquina');

    modalTitle.innerHTML = `Escolha a máquina e o motivo`;
    
    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações da ordem...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Atualiza as máquinas disponíveis no modal
    await fetchMaquinasDisponiveis();

    modal.show();
    Swal.close();

    // Remove event listeners antigos para evitar múltiplas submissões
    const clonedForm = formInterromper.cloneNode(true);
    formInterromper.parentNode.replaceChild(clonedForm, formInterromper);

    // Adiciona o novo event listener para o formulário
    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const motivoInterrupcao = formData.get('motivoParadaMaquina');
        const maquina = formData.get('escolhaMaquinaParada');

        // Validação básica dos campos
        if (!maquina || !motivoInterrupcao) {
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: 'Por favor, selecione uma máquina e informe o motivo.',
            });
            return;
        }

        Swal.fire({
            title: 'Parando...',
            text: 'Por favor, aguarde enquanto a máquina está sendo parada.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        // Envia a requisição ao backend
        fetch(`api/parar-maquina/`, {
            method: 'PATCH',
            body: JSON.stringify({
                maquina: maquina,
                motivo: motivoInterrupcao
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() // Inclui o CSRF Token no cabeçalho
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errorData => {
                    throw new Error(errorData.error || `Erro na requisição: ${response.status}`);
                });
            }
            fetchStatusMaquinas();

            return response.json();
        })
        .then(data => {
            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: 'Ordem interrompida com sucesso.',
            });

            modal.hide();
        })
        .catch((error) => {
            console.error('Erro:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: error.message,
            });
        });
    });
}

// Função para obter o token CSRF
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}
