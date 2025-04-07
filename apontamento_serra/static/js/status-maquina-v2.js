import { carregarOrdensIniciadas, carregarOrdensInterrompidas} from './ordem-criada-serra-v2.js';

document.addEventListener('DOMContentLoaded', function () {
    // Atualiza automaticamente ao carregar a página
    fetchStatusMaquinas();
    fetchUltimasPecasProduzidas();
    fetchContagemStatusOrdens();

    // Adiciona eventos de clique para atualizar manualmente
    document.getElementById('refresh-status-maquinas').addEventListener('click', function () {
        fetchStatusMaquinas(); // Chama a função existente
    });

    document.getElementById('refresh-pecas').addEventListener('click', function () {
        fetchUltimasPecasProduzidas(); // Chama a função existente
    });

    document.getElementById('refresh-ordens').addEventListener('click', function () {
        fetchContagemStatusOrdens(); // Chama a função existente
    });

    document.getElementById('btnPararMaquina').addEventListener('click', () => {
        mostrarModalPararMaquina(); // Chama a função já existente
    });
});

export function fetchStatusMaquinas() {
    // Seleciona os elementos do container
    const indicador = document.querySelector('.text-center.mb-3 .display-4');
    const descricao = document.querySelector('.text-center.mb-3 p');
    const listaStatus = document.querySelector('#machine-status-list');

    indicador.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;
    
    listaStatus.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;

    // Faz a requisição para a API
    fetch('/core/api/status_maquinas/?setor=serra')
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
                        maquina.status === 'Em produção' ? 'bg-success' : 
                        maquina.status === 'Parada' ? 'bg-danger' : 
                        'bg-warning';

                    const statusItem = document.createElement('li');
                    statusItem.classList.add('list-group-item', 'd-flex', 'align-items-center', 'justify-content-between', 'border-0');

                    const motivoParada = maquina.status === 'Parada' ? 
                        ` - <span class="text-danger">${maquina.motivo_parada || 'Sem motivo especificado'}</span>` : '';

                    // Criar botão de retorno se a máquina estiver parada
                    let botaoRetorno = '';
                    if (maquina.status === 'Parada') {
                        botaoRetorno = `
                            <button class="btn btn-sm btn-outline-success retornar-maquina-btn" data-maquina="${maquina.maquina_id}">
                                Retomar
                            </button>
                        `;
                    }

                    statusItem.innerHTML = `
                        <div class="d-flex align-items-center gap-2">
                            <span class="fw-bold">${maquina.maquina}</span>
                            <div class="status-circle ${statusColor}" style="
                                width: 15px;
                                height: 15px;
                                border-radius: 50%;
                            "></div>
                            ${motivoParada}
                        </div>
                        ${botaoRetorno}
                    `;

                    listaStatus.appendChild(statusItem);
                });

                // Adicionar eventos de clique aos botões de retorno
                document.querySelectorAll('.retornar-maquina-btn').forEach(button => {
                    button.addEventListener('click', function () {
                        const maquinaId = this.getAttribute('data-maquina');
                        retornarMaquina(maquinaId);
                    });
                });

            } else {
                // Caso não haja máquinas registradas
                listaStatus.innerHTML = '<li class="list-group-item text-muted">Nenhuma máquina registrada no momento.</li>';
            }
        })
        .catch(error => {
            console.error('Erro ao buscar status das máquinas:', error);
            indicador.textContent = '0%';
            descricao.textContent = 'Erro ao carregar dados';
            listaStatus.innerHTML = '<li class="list-group-item text-danger">Erro ao carregar os dados.</li>';
        });
}

export function fetchUltimasPecasProduzidas() {
    // Seleciona o elemento da lista onde as peças serão adicionadas
    const listaPecas = document.querySelector('#ultimas-pecas-list');
    
    listaPecas.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;

    // Faz a requisição para a API
    fetch(`/core/api/ultimas_pecas_produzidas/?setor=serra`)
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

export function fetchContagemStatusOrdens() {
    // Seleciona o elemento da lista onde os status serão adicionados
    const listaStatus = document.getElementById('status-ordens-list');

    listaStatus.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;

    // Faz a requisição para a API
    fetch('/core/api/status_ordem/?setor=serra')
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
        const response = await fetch('/core/api/buscar-maquinas-disponiveis/?setor=serra');
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

// Função para obter o token CSRF
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function retornarMaquina(maquina) {
    Swal.fire({
        title: 'Retornar máquina',
        text: `Deseja retornar a máquina ${maquina} à produção?`,
        showCancelButton: true,
        confirmButtonText: 'Sim',
        cancelButtonText: 'Cancelar',
        showLoaderOnConfirm: true,
        preConfirm: () => {
            return fetch(`/core/api/retornar-maquina/`, {
                method: 'PATCH',
                body: JSON.stringify({ maquina }),  // Envia no corpo como JSON
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()  // Certifique-se de que está obtendo o CSRF token corretamente
                }
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || `Erro na requisição: ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                fetchStatusMaquinas();  // Atualiza a lista de máquinas após a ação
                return data;
            })
            .catch(error => {
                console.error('Erro:', error);
                Swal.showValidationMessage(`Erro: ${error.message}`);
            });
        }
    })
    .then(result => {
        if (result.isConfirmed) {
            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: 'Máquina retornada à produção.',
            });
        }
    });
}

async function mostrarModalPararMaquina() {
    const formPararMaquina = document.getElementById('formPararMaquina');

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
    Swal.close(); // Fecha o SweetAlert de carregamento

    //  Remove event listener antigo antes de adicionar um novo
    formPararMaquina.removeEventListener('submit', handleFormSubmit);
    formPararMaquina.addEventListener('submit', handleFormSubmit, { once: true });
}

//  Função separada para submissão do formulário de parar maquina
async function handleFormSubmit(event) {
    event.preventDefault();

    Swal.fire({
        title: 'Parando...',
        text: 'Por favor, aguarde enquanto a máquina está sendo parada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    try {
        const response = await fetch(`/core/api/parar-maquina/?setor=serra`, {
            method: 'PATCH',
            body: JSON.stringify({
                maquina: document.getElementById('escolhaMaquinaParada').value,
                motivo: document.getElementById('motivoParadaMaquina').value
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() // Inclui o CSRF Token no cabeçalho
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `Erro na requisição: ${response.status}`);
        }

        Swal.fire({
            icon: 'success',
            title: 'Sucesso',
            text: 'Ordem interrompida com sucesso.',
        });

        // Atualiza a interface
        fetchContagemStatusOrdens();
        fetchStatusMaquinas();
    
        const containerIniciado = document.querySelector('.containerProcesso');
        carregarOrdensIniciadas(containerIniciado);
    
        const containerInterrompido = document.querySelector('.containerInterrompido');
        carregarOrdensInterrompidas(containerInterrompido);

    } catch (error) {
        console.error('Erro:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message,
        });
    }
}