import { carregarOrdensIniciadas, carregarOrdensInterrompidas, mostrarPecas, mostrarModalIniciar, resetarCardsInicial} from './ordem-criada.js';

document.addEventListener('DOMContentLoaded', function () {
    // Atualiza automaticamente ao carregar a página
    fetchStatusMaquinas();
    fetchOrdensSequenciadasLaser();
    fetchOrdensSequenciadasPlasma();

    // Adiciona eventos de clique para atualizar manualmente
    document.getElementById('refresh-status-maquinas').addEventListener('click', function () {
        fetchStatusMaquinas(); // Chama a função existente
    });

    document.getElementById('refresh-ordens-sequenciadas-laser').addEventListener('click', function () {
        const tabAtiva = document.querySelector('#laserTabs .nav-link.active');
        const grupo = tabAtiva ? tabAtiva.dataset.group : '';

        fetchOrdensSequenciadasLaser(grupo); // Chama a função existente
    });

    document.getElementById('refresh-ordens-sequenciadas-plasma').addEventListener('click', function () {
        fetchOrdensSequenciadasPlasma(); // Chama a função existente
    });

    document.getElementById('btnPararMaquina').addEventListener('click', () => {
        mostrarModalPararMaquina(); // Chama a função já existente
    });

    inicializarTabsLaser(function(grupo) {
        console.log("Tab clicada:", grupo);
        fetchOrdensSequenciadasLaser(grupo);
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
    fetch('/core/api/status_maquinas/?setor=corte')
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

function inicializarTabsLaser(callback) {
  const tabs = document.querySelectorAll("#laserTabs .nav-link");

  tabs.forEach((tab) => {
    tab.addEventListener("click", function (event) {
      event.preventDefault();

      // Atualiza visual da tab ativa
      tabs.forEach((t) => t.classList.remove("active"));
      this.classList.add("active");

      // Recupera o grupo selecionado
      const grupo = this.dataset.group;

      // Executa o callback passado, se existir
      if (typeof callback === "function") {
        callback(grupo);
      }
    });
  });
}

export function fetchOrdensSequenciadasLaser(grupo = 'laser_1') {
    // Seleciona o container onde os cards serão adicionados
    const container = document.getElementById('ordens-sequenciadas-laser-container');
    const btnFiltrarOrdemSequenciadaLaser = document.getElementById('btnPesquisarOrdemSequenciadaLaser');
    const ordemLaser = document.getElementById('pesquisarOrdemSequenciadaLaser');

    // Função que realiza a requisição, dado um URL
    function carregarOrdens(url) {
        container.innerHTML = `
        <div class="spinner-border text-dark" role="status">
            <span class="sr-only">Loading...</span>
        </div>`;
    
        // Limpa o conteúdo imediatamente antes de iniciar a requisição
        
        fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {

            console.log(data);

            container.innerHTML = '';
            // Se a resposta não tiver ordens, exibe mensagem
            if (data.ordens_sequenciadas && data.ordens_sequenciadas.length > 0) {
                data.ordens_sequenciadas.forEach(ordem => {
                    // Mapeamento de cores para o badge de status
                    const statusColors = {
                        'aguardando_iniciar': 'warning',
                        'iniciada': 'info',
                        'interrompida': 'danger',
                        'finalizada': 'success',
                    };

                    const statusLabels = {
                        'aguardando_iniciar': 'Aguardando iniciar',
                        'iniciada': 'Iniciada',
                        'interrompida': 'Interrompida',
                        'finalizada': 'Finalizada',
                    };

                    const badgeColor = statusColors[ordem.status_atual] || 'secondary';
                    const statusLabel = statusLabels[ordem.status_atual] || ordem.status_atual;

                    const statusColorsMaquina = {
                        'laser_1': 'primary',
                        'laser_2': 'success',
                        'laser_3': 'info',
                    };
                    const badgeColorMaquina = statusColorsMaquina[ordem.grupo_maquina] || 'secondary';

                    let botoesAcao = '';

                    if (ordem.status_atual === 'aguardando_iniciar'){
                        botoesAcao = `
                        <div>
                            <button class="btn btn-warning btn-sm btn-iniciar" title="Iniciar">
                                <i class="fa fa-play"></i>
                            </button>
                            <button class="btn btn-primary btn-sm btn-ver-peca me-2" title="Ver Peças">
                                <i class="fa fa-eye"></i>
                            </button>
                        </div>
                        <div>
                            <button class="btn btn-danger btn-sm btn-retirar-sequenciamento" data-index="${ordem.id}">
                                🗑
                            </button>
                        </div>
                        `
                    } else {
                        botoesAcao = `
                        <div>
                            <button class="btn btn-primary btn-sm btn-ver-peca me-2" title="Ver Peças">
                                <i class="fa fa-eye"></i>
                            </button>
                        </div>
                        `
                    }

                    // Cria um card para cada ordem
                    const card = document.createElement('div');
                    card.classList.add('card', 'mb-3');
                    card.innerHTML = `
                    <div class="card-header d-flex align-items-center">
                        <h5 class="card-title mb-0">
                            #${ordem.ordem ? ordem.ordem : ordem.ordem_duplicada}
                            <span class="badge bg-${badgeColor}">${statusLabel}</span>
                            <small><span class="badge bg-${badgeColorMaquina}">${ordem.grupo_maquina_display}</span></small>
                        </h5>
                        <div class="ms-auto">
                            <span class="badge bg-primary text-white prioridade-badge" 
                                data-order-id="${ordem.id}" 
                                style="cursor: pointer;" 
                                title="Definir prioridade">
                                ${ordem.ordem_prioridade || '-'}
                            </span>
                        </div>                    
                    </div>
                    <div class="card-body">
                        <small><p class="card-text mb-1">
                            <strong>Observação:</strong> ${ordem.obs ? ordem.obs : 'Sem observação'}
                        </p></small>
                        <small><p class="card-text mb-1">
                            <strong>Programação:</strong> ${ordem.data_programacao}
                        <small></p></small>
                        <small><p class="card-text mb-1">
                            <strong>Chapa:</strong> ${ordem.descricao_mp} ${ordem.tipo_chapa}
                        </p></small>
                        <small><p class="card-text mb-1">
                            <strong>Qt. chapa:</strong> ${ordem.quantidade} | <strong>Tempo estimado:</strong> ${ordem.tempo_estimado}
                        </p></small>
                    </div>
                    <div class="card-footer d-flex justify-content-between align-items-center">
                        ${botoesAcao}
                    </div>
                    `;
                    container.appendChild(card);

                    const buttonVerPeca = card.querySelector('.btn-ver-peca');
                    const buttonIniciar = card.querySelector('.btn-iniciar');
                    const buttonRetirarSequenciamento = card.querySelector('.btn-retirar-sequenciamento');

                    if (buttonVerPeca) {
                        buttonVerPeca.addEventListener('click', () => {
                            mostrarPecas(ordem.id);
                        });
                    }
                    
                    if (buttonIniciar) {
                        buttonIniciar.addEventListener('click', () => {
                            mostrarModalIniciar(ordem.id, ordem.grupo_maquina);
                        });
                    }
                    
                    if (buttonRetirarSequenciamento) {
                        buttonRetirarSequenciamento.addEventListener('click', () => {
                            mostrarModalExcluir(ordem.id, ordem.grupo_maquina);
                        });
                    }

                });
            } else {
                container.innerHTML = '<p class="text-center text-muted">Nenhuma ordem sequenciada encontrada.</p>';
            }
        
            container.querySelectorAll('.prioridade-badge').forEach(badge => {
                badge.addEventListener('click', () => {
                    const orderId = badge.dataset.orderId;
                    document.getElementById('prioridadeOrderId').value = orderId;
                    document.getElementById('inputPrioridade').value = badge.textContent !== '-' ? badge.textContent : '';
                    const modal = new bootstrap.Modal(document.getElementById('modalPrioridade'));
                    modal.show();
                });
            });

            const btnSalvarPrioridade = document.getElementById('btnSalvarPrioridade');
            if (btnSalvarPrioridade && !btnSalvarPrioridade.dataset.listenerAdded) {
                btnSalvarPrioridade.addEventListener('click', salvarPrioridade);
                btnSalvarPrioridade.dataset.listenerAdded = 'true';
            }
    
            somarTemposEstimados('ordens-sequenciadas-laser-container','tempo-estimado-total-laser');

        })
        .catch(error => {
            console.error('Erro ao buscar ordens sequenciadas:', error);
            container.innerHTML = '<p class="text-center text-danger">Erro ao carregar os dados.</p>';
        });
    }
    
    // Busca inicial sem filtro de ordem
    carregarOrdens(`api/ordens-sequenciadas/?maquina=${grupo}`);
    
    // Verifica se o listener já foi adicionado para evitar duplicação
    if (!btnFiltrarOrdemSequenciadaLaser.dataset.listenerAdded) {
        btnFiltrarOrdemSequenciadaLaser.addEventListener('click', () => {
            const ordemDigitada = ordemLaser.value.trim();

            // Descobre qual tab está ativa
            const tabAtiva = document.querySelector('#laserTabs .nav-link.active');
            const grupo = tabAtiva ? tabAtiva.dataset.group : '';

            const url = `api/ordens-sequenciadas/?maquina=${grupo}${ordemDigitada ? `&ordem=${encodeURIComponent(ordemDigitada)}` : ''}`;
            carregarOrdens(url);
        });

        btnFiltrarOrdemSequenciadaLaser.dataset.listenerAdded = 'true';
    }
    
}

export function fetchOrdensSequenciadasPlasma() {
    const container = document.getElementById('ordens-sequenciadas-plasma-container');
    const btnFiltrarOrdemSequenciadaPlasma = document.getElementById('btnPesquisarOrdemSequenciadaPlasma');
    const ordemPlasma = document.getElementById('pesquisarOrdemSequenciadaPlasma');
    
    function carregarOrdens(url) {
        container.innerHTML = `
        <div class="spinner-border text-dark" role="status">
            <span class="sr-only">Loading...</span>
        </div>`;
        fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            container.innerHTML = '';
            if (data.ordens_sequenciadas && data.ordens_sequenciadas.length > 0) {
                data.ordens_sequenciadas.forEach(ordem => {
                    // Mapeamento de cores para o badge de status
                    const statusColors = {
                        'aguardando_iniciar': 'warning',
                        'iniciada': 'info',
                        'interrompida': 'danger',
                        'finalizada': 'success',
                    };

                    const statusLabels = {
                        'aguardando_iniciar': 'Aguardando iniciar',
                        'iniciada': 'Iniciada',
                        'interrompida': 'Interrompida',
                        'finalizada': 'Finalizada',
                    };

                    const badgeColor = statusColors[ordem.status_atual] || 'secondary';
                    const statusLabel = statusLabels[ordem.status_atual] || ordem.status_atual;

                    let botoesAcao = '';
                    
                    if (ordem.status_atual === 'aguardando_iniciar'){
                        botoesAcao = `
                        <div>
                            <button class="btn btn-warning btn-sm btn-iniciar" title="Iniciar">
                                <i class="fa fa-play"></i>
                            </button>
                            <button class="btn btn-primary btn-sm btn-ver-peca me-2" title="Ver Peças">
                                <i class="fa fa-eye"></i>
                            </button>
                        </div>
                        <div>
                            <button class="btn btn-danger btn-sm btn-retirar-sequenciamento" data-index="${ordem.id}">
                                🗑
                            </button>
                        </div>
                        `;
                    } else {
                        botoesAcao = `
                        <div>
                            <button class="btn btn-primary btn-sm btn-ver-peca me-2" title="Ver Peças">
                                <i class="fa fa-eye"></i>
                            </button>
                        </div>
                        `;
                    }

                    const card = document.createElement('div');
                    card.classList.add('card', 'mb-3');
                    card.innerHTML = `
                    <div class="card-header d-flex align-items-center">
                        <h5 class="card-title mb-0">
                            #${ordem.ordem ? ordem.ordem : ordem.ordem_duplicada}
                            <span class="badge bg-${badgeColor}">${statusLabel}</span>
                        </h5>
                        <div class="ms-auto">
                            <span class="badge bg-primary text-white prioridade-badge" 
                                data-order-id="${ordem.id}" 
                                style="cursor: pointer;" 
                                title="Definir prioridade">
                                ${ordem.ordem_prioridade || '-'}
                            </span>
                        </div>                    
                    </div>
                    <div class="card-body">
                        <small><p class="card-text mb-1">
                            <strong>Observação:</strong> ${ordem.obs ? ordem.obs : 'Sem observação'}
                        </p></small>
                        <small><p class="card-text mb-1">
                            <strong>Programação:</strong> ${ordem.data_programacao}
                        <small></p></small>
                        <small><p class="card-text mb-1">
                            <strong>Chapa:</strong> ${ordem.descricao_mp} ${ordem.tipo_chapa}
                        </p></small>
                        <small><p class="card-text mb-1">
                            <strong>Qt. chapa:</strong> ${ordem.quantidade} | <strong>Tempo estimado:</strong> ${ordem.tempo_estimado}
                        </p></small>
                    </div>
                    <div class="card-footer d-flex justify-content-between align-items-center">
                        ${botoesAcao}
                    </div>
                    `;
                    container.appendChild(card);

                    const buttonVerPeca = card.querySelector('.btn-ver-peca');
                    const buttonIniciar = card.querySelector('.btn-iniciar');
                    const buttonRetirarSequenciamento = card.querySelector('.btn-retirar-sequenciamento');

                    if (buttonIniciar){
                        buttonIniciar.addEventListener('click', () => {
                            mostrarModalIniciar(ordem.id, ordem.grupo_maquina);
                        });
                    }

                    buttonVerPeca.addEventListener('click', () => {
                        mostrarPecas(ordem.id);
                    });
                    
                    if (buttonRetirarSequenciamento){
                        buttonRetirarSequenciamento.addEventListener('click', () => {
                            mostrarModalExcluir(ordem.id, ordem.grupo_maquina);
                        });
                    }
                });
            } else {
                container.innerHTML = '<p class="text-center text-muted">Nenhuma ordem sequenciada encontrada.</p>';
            }
            container.querySelectorAll('.prioridade-badge').forEach(badge => {
                badge.addEventListener('click', () => {
                    const orderId = badge.dataset.orderId;
                    document.getElementById('prioridadeOrderId').value = orderId;
                    document.getElementById('inputPrioridade').value = badge.textContent !== '-' ? badge.textContent : '';
                    const modal = new bootstrap.Modal(document.getElementById('modalPrioridade'));
                    modal.show();
                });
            });

            const btnSalvarPrioridade = document.getElementById('btnSalvarPrioridade');
            if (btnSalvarPrioridade && !btnSalvarPrioridade.dataset.listenerAdded) {
                btnSalvarPrioridade.addEventListener('click', salvarPrioridade);
                btnSalvarPrioridade.dataset.listenerAdded = 'true';
            }

            somarTemposEstimados('ordens-sequenciadas-plasma-container','tempo-estimado-total-plasma');

        })
        .catch(error => {
            console.error('Erro ao buscar ordens sequenciadas:', error);
            container.innerHTML = '<p class="text-center text-danger">Erro ao carregar os dados.</p>';
        });
    }
    
    // Busca inicial sem filtro de ordem
    carregarOrdens(`api/ordens-sequenciadas/?maquina=plasma`);
    
    // Verifica se o listener já foi adicionado para evitar duplicação
    if (!btnFiltrarOrdemSequenciadaPlasma.dataset.listenerAdded) {
        btnFiltrarOrdemSequenciadaPlasma.addEventListener('click', () => {
            const ordemDigitada = ordemPlasma.value.trim();
            const url = `api/ordens-sequenciadas/?maquina=plasma${ordemDigitada ? `&ordem=${encodeURIComponent(ordemDigitada)}` : ''}`;
            carregarOrdens(url);
        });
        btnFiltrarOrdemSequenciadaPlasma.dataset.listenerAdded = 'true';
    }
}

function salvarPrioridade() {
    const orderId = document.getElementById('prioridadeOrderId').value;
    const prioridade = document.getElementById('inputPrioridade').value.trim();
    const btnSalvarPrioridade = document.getElementById('btnSalvarPrioridade');

    if (prioridade === '' || isNaN(prioridade) || Number(prioridade) < 1) {
        alert('Informe uma prioridade válida');
        return;
    }
    
    btnSalvarPrioridade.innerHTML = `
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span class="visually-hidden">Salvando...</span>
    `;

    btnSalvarPrioridade.disabled = true;

    fetch('api/salvar-prioridade/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ordemId: orderId, prioridade: Number(prioridade) })
    })
    .then(response => response.json().then(data => ({ status: response.status, body: data })))
    .then(({ status, body }) => {
        if (status === 201) {
            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: body.success,
            });

            // Recarrega os dados chamando a função de carregamento
            document.getElementById('ordens-container').innerHTML = '';
            fetchOrdensSequenciadasLaser();
            fetchOrdensSequenciadasPlasma();
            resetarCardsInicial();
            btnSalvarPrioridade.innerHTML = `Salvar`;
            btnSalvarPrioridade.disabled = false;

            // Fecha o modal
            bootstrap.Modal.getInstance(document.getElementById('modalPrioridade')).hide(); 

        } else {
            // Exibe o erro vindo do backend
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: body.error || 'Erro ao salvar prioridade',
            });
        }
    })
    .catch(err => console.error('Erro ao salvar prioridade:', err));
}

async function fetchMaquinasDisponiveis() {
    
    try {
        const response = await fetch('/core/api/buscar-maquinas-disponiveis/?setor=corte');
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
        const response = await fetch(`/core/api/parar-maquina/?setor=corte`, {
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
        fetchOrdensSequenciadasPlasma();
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

// Modal para "Excluir"
function mostrarModalExcluir(ordemId, setor) {
    const modal = new bootstrap.Modal(document.getElementById('modalExcluir'));
    const modalTitle = document.getElementById('modalExcluirLabel');
    const formExcluir = document.getElementById('formExcluir');

    modalTitle.innerHTML = `Excluir Ordem ${ordemId}`;
    modal.show();

    // Remove listeners antigos e adiciona novo
    const clonedForm = formExcluir.cloneNode(true);
    formExcluir.parentNode.replaceChild(clonedForm, formExcluir);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const motivoExclusao = formData.get('motivoExclusao');

        Swal.fire({
            title: 'Excluindo...',
            text: 'Por favor, aguarde enquanto a ordem está sendo excluída.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch(`/core/api/excluir-ordem/`, {
            method: 'POST',
            body: JSON.stringify({
                ordem_id: ordemId,
                setor: setor,
                motivo: motivoExclusao
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() // Inclui o CSRF Token no cabeçalho
            }
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (status === 201) {
                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso',
                    text: body.success,
                });

                modal.hide();

                // Recarrega os dados chamando a função de carregamento
                document.getElementById('ordens-container').innerHTML = '';
                fetchOrdensSequenciadasLaser();
                fetchOrdensSequenciadasPlasma();
                resetarCardsInicial();

            } else {
                // Exibe o erro vindo do backend
                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: body.error || 'Erro ao excluir a ordem.',
                });
            }
        })
        .catch((error) => {
            console.error('Erro:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: 'Ocorreu um erro inesperado. Tente novamente mais tarde.',
            });
        });
    });
}

function somarTemposEstimados(containerId, spanId) {

    const container = document.getElementById(containerId);
    if (!container) return;

    const tempoElements = container.querySelectorAll('.card .card-body p');
    let totalMilissegundos = 0;

    tempoElements.forEach(p => {
        if (p.innerText.includes('Tempo estimado:')) {
            const tempoStr = p.innerText.split('Tempo estimado:')[1].trim();

            // Formato 1: 00:23:56.831000
            if (tempoStr.includes(':')) {
                const partes = tempoStr.split(':');
                if (partes.length === 3) {
                    const horas = parseInt(partes[0], 10);
                    const minutos = parseInt(partes[1], 10);
                    const [segundos, micros] = partes[2].split('.');
                    const milissegundos = parseInt(segundos, 10) * 1000 + parseInt(micros?.slice(0, 3) || 0, 10);
                    totalMilissegundos += (horas * 3600000) + (minutos * 60000) + milissegundos;
                    return;
                }
            }

            // Formato 2 e 3: ex: 1hours4min17,5s ou 22min26,6s
            const horasMatch = tempoStr.match(/(\d+)\s*hours?/i);
            const minMatch = tempoStr.match(/(\d+)\s*min/i);
            const secMatch = tempoStr.match(/(\d+[.,]?\d*)\s*s/i);

            const horas = horasMatch ? parseInt(horasMatch[1], 10) : 0;
            const minutos = minMatch ? parseInt(minMatch[1], 10) : 0;

            let segundos = 0;
            if (secMatch) {
                segundos = parseFloat(secMatch[1].replace(',', '.'));
            }

            totalMilissegundos += (horas * 3600000) + (minutos * 60000) + (segundos * 1000);
        }
    });

    const horas = Math.floor(totalMilissegundos / 3600000);
    const minutos = Math.floor((totalMilissegundos % 3600000) / 60000);
    const segundos = Math.floor((totalMilissegundos % 60000) / 1000);

    const tempoFinal = 
        String(horas).padStart(2, '0') + ':' +
        String(minutos).padStart(2, '0') + ':' +
        String(segundos).padStart(2, '0');

    document.getElementById(spanId).innerHTML = `Tempo estimado: ${tempoFinal}`;

}