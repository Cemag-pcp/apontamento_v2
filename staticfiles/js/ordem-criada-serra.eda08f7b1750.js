import { fetchStatusMaquinas } from './status-maquina.js';
import { fetchUltimasPecasProduzidas } from './status-maquina.js';
import { fetchContagemStatusOrdens } from './status-maquina.js';

export const loadOrdens = (container, page = 1, limit = 10, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => { // Retorna uma Promise
        if (isLoading) return resolve({ ordens: [] }); // Evita chamadas duplicadas
        isLoading = true;

        fetch(`api/ordens-criadas/?page=${page}&limit=${limit}&ordem=${filtros.ordem || ''}&status=${filtros.status || ''}&mp=${filtros.mp || ''}&peca=${filtros.peca || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;
                if (ordens.length > 0) {
                    console.log(ordens);
                    ordens.forEach(ordem => {
                        const card = document.createElement('div');
                        card.classList.add('col-md-4'); // Adiciona a classe de coluna

                        card.dataset.ordemId = ordem.ordem; // Adiciona o ID da ordem para referência
                        card.dataset.grupoMaquina = ordem.grupo_maquina || ''; // Adiciona o grupo máquina
                        card.dataset.obs = ordem.obs || ''; // Adiciona observações
                    
                        let statusBadge = ''; // Variável para armazenar o HTML do badge

                        switch (ordem.status_atual) {
                            case 'aguardando_iniciar':
                                statusBadge = '<span class="badge rounded-pill bg-warning badge-small ms-2">Aguardando Iniciar</span>';
                                break;
                            case 'iniciada':
                                statusBadge = '<span class="badge rounded-pill bg-info badge-small ms-2">Iniciada</span>';
                                break;
                            case 'finalizada':
                                statusBadge = '<span class="badge rounded-pill bg-success badge-small ms-2">Finalizada</span>';
                                break;
                            case 'interrompida':
                                statusBadge = '<span class="badge rounded-pill bg-danger badge-small ms-2">Interrompida</span>';
                                break;
                            default:
                                statusBadge = '<span class="badge rounded-pill bg-dark badge-small ms-2">Desconhecido</span>';
                        }

                        // Defina os botões dinamicamente com base no status
                        let botaoAcao = '';

                        if (ordem.status_atual === 'iniciada') {
                            botaoAcao = `
                                <button class="btn btn-danger btn-sm btn-interromper me-2" title="Interromper">
                                    <i class="fa fa-stop"></i>
                                </button>
                                <button class="btn btn-success btn-sm btn-finalizar" title="Finalizar">
                                    <i class="fa fa-check"></i>
                                </button>
                            `;
                        } else if (ordem.status_atual === 'aguardando_iniciar') {
                            botaoAcao = `
                                <button class="btn btn-warning btn-sm btn-iniciar" title="Iniciar">
                                    <i class="fa fa-play"></i>
                                </button>
                                <button class="btn btn-danger btn-sm btn-excluir" title="Excluir">
                                    <i class="fa fa-trash"></i>
                                </button>
                            `;
                        } else if (ordem.status_atual === 'interrompida') {
                            botaoAcao = `
                                <button class="btn btn-warning btn-sm btn-retornar" title="Retornar">
                                    <i class="fa fa-redo"></i>
                                </button>
                            `;
                        }

                        // Monta o card com os botões dinâmicos
                        card.innerHTML = `
                        <div class="card shadow-sm bg-light text-dark">
                            <div class="card-body">
                                <h5 class="card-title d-flex justify-content-between align-items-center">
                                    #${ordem.ordem}
                                    ${statusBadge}
                                </h5>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">Criado em: ${ordem.data_criacao}</p>
                                <p class="mb-2">${ordem.obs || '<span class="text-muted">Sem observações</span>'}</p>
                                <ul class="list-unstyled mb-0" style="font-size: 0.85rem;">
                                    <li><strong>MP:</strong> ${ordem.propriedade?.descricao_mp || 'N/A'}</li>
                                    <li><strong>Quantidade:</strong> ${ordem.propriedade?.quantidade || 'N/A'}</li>
                                    <li><strong>Retalho:</strong> ${ordem.propriedade?.retalho || 'Não'}</li>
                                    <li style="font-size: 0.75rem;">
                                        <strong>Peças:</strong> 
                                        ${ordem.pecas.map(peca => {
                                            const descricao = peca.peca_nome || 'Sem descrição'; // Usa "Sem descrição" se a descrição estiver ausente
                                            const descricaoTruncada = descricao.length > 10 
                                                ? descricao.substring(0, 10) + '...' 
                                                : descricao;
                                            return `
                                                <span title="${descricao}">
                                                    <a href="https://drive.google.com/drive/u/0/search?q=${peca.peca_codigo}" target="_blank" rel="noopener noreferrer">
                                                        ${peca.peca_codigo} - ${descricaoTruncada}
                                                    </a>
                                                </span>
                                            `;
                                        }).join(', ')}
                                    </li>
                                </ul>
                            </div>
                            <div class="card-footer text-end" style="background-color: #f8f9fa; border-top: 1px solid #dee2e6;">
                                <button class="btn btn-primary btn-sm btn-ver-peca me-2" title="Ver Peças">
                                    <i class="fa fa-eye"></i>
                                </button>
                                ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                            </div>
                        </div>`;
                        
                        // Seleciona os botões dinamicamente
                        const buttonVerPeca = card.querySelector('.btn-ver-peca');
                        const buttonIniciar = card.querySelector('.btn-iniciar');
                        const buttonInterromper = card.querySelector('.btn-interromper');
                        const buttonFinalizar = card.querySelector('.btn-finalizar');
                        const buttonRetornar = card.querySelector('.btn-retornar');
                        const buttonExcluir= card.querySelector('.btn-excluir');

                        // Adiciona evento ao botão "Ver Peças", se existir
                        if (buttonVerPeca) {
                            buttonVerPeca.addEventListener('click', () => {
                                mostrarPecas(ordem.ordem, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Iniciar", se existir
                        if (buttonIniciar) {
                            buttonIniciar.addEventListener('click', () => {
                                mostrarModalIniciar(ordem.ordem, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Interromper", se existir
                        if (buttonInterromper) {
                            buttonInterromper.addEventListener('click', () => {
                                mostrarModalInterromper(ordem.ordem, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Finalizar", se existir
                        if (buttonFinalizar) {
                            buttonFinalizar.addEventListener('click', () => {
                                mostrarModalFinalizar(ordem.ordem, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Retornar", se existir
                        if (buttonRetornar) {
                            buttonRetornar.addEventListener('click', () => {
                                mostrarModalRetornar(ordem.ordem, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Excluir", se existir
                        if (buttonExcluir) {
                            buttonExcluir.addEventListener('click', () => {
                                mostrarModalExcluir(ordem.ordem, 'serra');
                            });
                        }

                        // Adiciona o card ao container
                        container.appendChild(card);
                    });

                    // Esconde o botão "Carregar Mais" caso `has_next` seja false
                    const loadMoreButton = document.getElementById('loadMore');
                    if (!data.has_next) {
                        loadMoreButton.style.display = 'none'; // Esconde o botão
                    } else {
                        loadMoreButton.style.display = 'block'; // Mostra o botão caso ainda haja dados
                    }

                    resolve(data); // Retorna os dados carregados
                } else {
                    resolve(data); // Retorna mesmo se não houver dados
                }
            })
            .catch(error => {
                console.error('Erro ao buscar ordens:', error);
                container.insertAdjacentHTML('beforeend', '<p class="text-danger">Erro ao carregar as ordens.</p>');
                reject(error);
            })
            .finally(() => {
                isLoading = false; // Libera a flag em qualquer caso
            });
    });
};

function iniciarContador(ordemId, dataCriacao) {
    const contador = document.getElementById(`contador-${ordemId}`);
    const dataInicial = new Date(dataCriacao); // Converte a data de criação para objeto Date

    function atualizarContador() {
        const agora = new Date();
        const diferenca = Math.floor((agora - dataInicial) / 1000); // Diferença em segundos

        const dias = Math.floor(diferenca / 86400);
        const horas = Math.floor((diferenca % 86400) / 3600);
        const minutos = Math.floor((diferenca % 3600) / 60);
        const segundos = diferenca % 60;

        contador.textContent = `${dias}d ${horas}h ${minutos}m ${segundos}s`;
    }

    // Atualiza o contador a cada segundo
    atualizarContador();
    setInterval(atualizarContador, 1000);
}

export function carregarOrdensIniciadas(container, filtros={}) {
    fetch(`api/ordens-iniciadas/?page=1&limit=10&ordem=${filtros.ordem || ''}&mp=${filtros.mp || ''}&peca=${filtros.peca || ''}`)

        .then(response => response.json())
        .then(data => {
            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {

                const card = document.createElement('div');
                card.dataset.ordemId = ordem.ordem;

                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

                if (ordem.status_atual === 'iniciada') {
                    botaoAcao = `
                        <button class="btn btn-danger btn-sm btn-interromper me-2" title="Interromper">
                            <i class="fa fa-stop"></i>
                        </button>
                        <button class="btn btn-success btn-sm btn-finalizar" title="Finalizar">
                            <i class="fa fa-check"></i>
                        </button>
                    `;
                } else if (ordem.status_atual === 'aguardando_iniciar') {
                    botaoAcao = `
                        <button class="btn btn-warning btn-sm btn-iniciar" title="Iniciar">
                            <i class="fa fa-play"></i>
                        </button>
                    `;
                } else if (ordem.status_atual === 'interrompida') {
                    botaoAcao = `
                        <button class="btn btn-warning btn-sm btn-retornar" title="Retornar">
                            <i class="fa fa-redo"></i>
                        </button>
                    `;
                }

                card.innerHTML = `
                <div class="card shadow-sm border-0" style="border-radius: 10px; overflow: hidden;">
                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                        <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                        <span class="badge badge-pill badge-warning" id="contador-${ordem.ordem}" style="font-size: 0.65rem;">Carregando...</span>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Observação:</strong> ${ordem.obs || 'Sem observações'}
                        </p>
                        <p class="card-text mb-0 small">
                            <strong>Descrição MP:</strong> ${ordem.propriedade?.descricao_mp || 'Sem descrição'}
                        </p>
                        <p class="card-text mb-0 small" style="font-size: 0.75rem;">
                            <strong>Peças:</strong> 
                            ${ordem.pecas.map(peca => {
                                const descricao = peca.peca_nome || 'Sem descrição'; // Usa "Sem descrição" se a descrição estiver ausente
                                const descricaoTruncada = descricao.length > 10 
                                    ? descricao.substring(0, 10) + '...' 
                                    : descricao;
                                return `
                                    <span title="${descricao}">
                                        <a href="https://drive.google.com/drive/u/0/search?q=${peca.peca_codigo}" target="_blank" rel="noopener noreferrer">
                                            ${peca.peca_codigo} - ${descricaoTruncada}
                                        </a>
                                    </span>
                                `;
                            }).join(', ')}
                        </p>
                    </div>
                    <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                        <button class="btn btn-outline-primary btn-sm btn-ver-peca" title="Ver Peças">
                            <i class="fa fa-eye"></i> Ver Peças
                        </button>
                        <div class="d-flex gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;
            
                const buttonVerPeca = card.querySelector('.btn-ver-peca');
                const buttonInterromper = card.querySelector('.btn-interromper');
                const buttonFinalizar = card.querySelector('.btn-finalizar');

                // Adiciona evento ao botão "Ver Peças", se existir
                if (buttonVerPeca) {
                    buttonVerPeca.addEventListener('click', () => {
                        mostrarPecas(ordem.ordem, ordem.grupo_maquina);
                    });
                }

                // Adiciona evento ao botão "Interromper", se existir
                if (buttonInterromper) {
                    buttonInterromper.addEventListener('click', () => {
                        mostrarModalInterromper(ordem.ordem, ordem.grupo_maquina);
                    });
                }

                // Adiciona evento ao botão "Finalizar", se existir
                if (buttonFinalizar) {
                    buttonFinalizar.addEventListener('click', () => {
                        atualizarStatusOrdem(ordem.ordem, ordem.grupo_maquina, 'finalizada');
                    });
                }

                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao);

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
}

export function carregarOrdensInterrompidas(container, filtros={}) {
    // Fetch para buscar ordens interrompidas
    fetch(`api/ordens-interrompidas/?page=1&limit=10&ordem=${filtros.ordem || ''}&mp=${filtros.mp || ''}&peca=${filtros.peca || ''}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao buscar as ordens interrompidas.');
            }
            return response.json();
        })
        .then(data => {
            container.innerHTML = ''; // Limpa o container

            data.ordens.forEach(ordem => {
                // Cria o card de forma dinâmica
                const card = document.createElement('div');
                card.dataset.ordemId = ordem.ordem;
                
                // Define os botões dinamicamente
                const botaoAcao = `
                    <button class="btn btn-warning btn-sm btn-retornar me-2" title="Retornar">
                        <i class="fa fa-undo"></i>
                    </button>
                `;

                card.innerHTML = `
                <div class="card shadow-sm border-0" style="border-radius: 10px; overflow: hidden;">
                    <div class="card-header bg-danger text-white d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                            <small class="text-white">Motivo: ${ordem.motivo_interrupcao || 'Sem motivo'}</small>
                        </div>
                        <span class="badge badge-pill badge-warning" id="contador-${ordem.ordem}" style="font-size: 0.65rem;">Carregando...</span>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Observação:</strong> ${ordem.obs || 'N/A'}
                        </p>
                        <p class="card-text mb-2 small">
                            <strong>Descrição MP:</strong> ${ordem.propriedade?.descricao_mp || 'Sem descrição'}
                        </p>
                        <p class="card-text mb-0 small" style="font-size: 0.75rem;">
                            <strong>Peças:</strong> 
                            ${ordem.pecas.map(peca => {
                                const descricao = peca.peca_nome || 'Sem descrição'; // Usa "Sem descrição" se a descrição estiver ausente
                                const descricaoTruncada = descricao.length > 10 
                                    ? descricao.substring(0, 10) + '...' 
                                    : descricao;
                                return `
                                    <span title="${descricao}">
                                        <a href="https://drive.google.com/drive/u/0/search?q=${peca.peca_codigo}" target="_blank" rel="noopener noreferrer">
                                            ${peca.peca_codigo} - ${descricaoTruncada}
                                        </a>
                                    </span>
                                `;
                            }).join(', ')}
                        </p>
                    </div>
                    <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                        <button class="btn btn-outline-primary btn-sm btn-ver-peca" title="Ver Peças">
                            <i class="fa fa-eye"></i> Ver Peças
                        </button>
                        <div class="d-flex gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;
            

                // Adiciona eventos aos botões
                const buttonVerPeca = card.querySelector('.btn-ver-peca');
                const buttonRetornar = card.querySelector('.btn-retornar');

                // Evento para "Ver Peças"
                if (buttonVerPeca) {
                    buttonVerPeca.addEventListener('click', () => {
                        mostrarPecas(ordem.ordem, ordem.grupo_maquina);
                    });
                }

                // Evento para "Retornar"
                if (buttonRetornar) {
                    buttonRetornar.addEventListener('click', () => {
                        mostrarModalRetornar(ordem.ordem, ordem.grupo_maquina);
                    });
                }

                container.appendChild(card); // Adiciona o card ao container

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao);

            });
        })
        .catch(error => {
            console.error('Erro ao buscar ordens interrompidas:', error);
            container.innerHTML = '<p class="text-danger">Erro ao carregar ordens interrompidas.</p>';
        });
}

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function resetarCardsInicial(filtros = {}) {
    const container = document.getElementById('ordens-container');
    const loadMoreButton = document.getElementById('loadMore');
    let page = 1; // Página inicial
    const limit = 10; // Quantidade de ordens por página
    let isLoading = false; // Flag para evitar chamadas simultâneas
    let hasMoreData = true; // Flag para interromper chamadas quando não houver mais dados

    // Atualiza os filtros com os valores enviados
    const filtroOrdem = document.getElementById('filtro-ordem');
    const filtroMp = document.getElementById('filtro-mp');
    const filtroStatus = document.getElementById('filtro-status');
    const filtroPeca = document.getElementById('filtro-peca');

    const currentFiltros = {
        ordem: filtros.ordem || filtroOrdem.value.trim(),
        mp: filtros.mp || filtroMp.value.trim(),
        status: filtros.status || filtroStatus.value.trim(),
        peca: filtros.status || filtroPeca.value.trim(),
    };

    // Função principal para buscar e renderizar ordens
    const fetchOrdens = () => {
        if (isLoading || !hasMoreData) return;
        isLoading = true;

        loadOrdens(container, page, limit, currentFiltros)
            .then((data) => {
                if (data.ordens.length === 0) {
                    hasMoreData = false;
                    loadMoreButton.style.display = 'none'; // Esconde o botão quando não há mais dados
                    if (page === 1) {
                        container.innerHTML = '<p class="text-muted">Nenhuma ordem encontrada.</p>';
                    } else {
                        container.insertAdjacentHTML('beforeend', '<p class="text-muted">Nenhuma ordem adicional encontrada.</p>');
                    }
                } else {
                    loadMoreButton.style.display = 'block'; // Garante que o botão seja exibido quando houver mais dados
                    page++; // Incrementa a página para o próximo carregamento
                }
            })
            .catch((error) => {
                console.error('Erro ao carregar ordens:', error);
            })
            .finally(() => {
                isLoading = false;
            });
    };

    // Carrega a primeira página automaticamente
    container.innerHTML = ''; // Limpa o container antes de carregar novos resultados
    fetchOrdens();

    // Configurar o botão "Carregar Mais"
    loadMoreButton.onclick = () => {
        fetchOrdens(); // Carrega a próxima página ao clicar no botão
    };
}

// Função para exibir as peças no modal
function mostrarPecas(ordemId, maquinaName) {
    const modalContent = document.getElementById('modalPecasContent');

    // Exibe SweetAlert de carregamento
    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das peças...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Converte o nome da máquina para minúsculas
    const maquinaNameLower = maquinaName.toLowerCase();

    // Fetch para buscar peças
    fetch(`api/ordens-criadas/${ordemId}/${maquinaNameLower}/pecas/`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro na resposta da API');
            }
            return response.json();
        })
        .then(data => {
            Swal.close(); // Fecha o SweetAlert de carregamento

            if (data.pecas.length === 0) {
                modalContent.innerHTML = `<p class="text-center text-muted">Não há peças cadastradas para esta ordem.</p>`;
            } else {
                modalContent.innerHTML = `
                    <h5 class="text-center">Peças da Ordem ${ordemId}</h5>
                    <table class="table table-bordered table-sm text-center">
                        <thead>
                            <tr class="table-light">
                                <th>Peça</th>
                                <th>Quantidade</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.pecas.map(peca => `
                                <tr>
                                    <td>
                                    <a href="https://drive.google.com/drive/u/0/search?q=${peca.peca_codigo}" target="_blank" rel="noopener noreferrer">
                                        ${peca.peca_nome}
                                    </a>
                                    </td>
                                    <td>${peca.quantidade}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            }

            // Exibe o modal
            const modal = new bootstrap.Modal(document.getElementById('modalPecas'));
            modal.show();
        })
        .catch(error => {
            Swal.close(); // Fecha o SweetAlert de carregamento
            console.error('Erro ao buscar peças:', error);
            
            // Exibe mensagem de erro no SweetAlert
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: 'Erro ao carregar as peças. Por favor, tente novamente.',
            });
        });
}

function atualizarStatusOrdem(ordemId, grupoMaquina, status) {
    switch (status) {
        case 'iniciada':
            mostrarModalIniciar(ordemId, grupoMaquina);
            break;
        case 'interrompida':
            mostrarModalInterromper(ordemId, grupoMaquina);
            break;
        case 'finalizada':
            mostrarModalFinalizar(ordemId, grupoMaquina);
            break;
        default:
            alert('Status desconhecido.');
    }
}

// Modal para "Interromper"
function mostrarModalInterromper(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalInterromper'));
    const modalTitle = document.getElementById('modalInterromperLabel');
    const formInterromper = document.getElementById('formInterromperOrdemCorte');

    modalTitle.innerHTML = `Interromper Ordem ${ordemId}`;
    modal.show();

    // Remove listeners antigos e adiciona novo
    const clonedForm = formInterromper.cloneNode(true);
    formInterromper.parentNode.replaceChild(clonedForm, formInterromper);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const motivoInterrupcao = formData.get('motivoInterrupcao');

        Swal.fire({
            title: 'Interrompendo...',
            text: 'Por favor, aguarde enquanto a ordem está sendo interrompida.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch(`api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify({
                ordem_id: ordemId,
                grupo_maquina: grupoMaquina,
                status: 'interrompida',
                motivo: motivoInterrupcao
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() // Inclui o CSRF Token no cabeçalho
            }
        })
        .then(response => response.json())
        .then(data => {

            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: 'Ordem interrompida com sucesso.',
            });

            modal.hide();

            // Atualiza a interface
            const containerIniciado = document.querySelector('.containerProcesso');
            carregarOrdensIniciadas(containerIniciado);
            
            const containerInterrompido = document.querySelector('.containerInterrompido');
            carregarOrdensInterrompidas(containerInterrompido);

            // Recarrega os dados chamando a função de carregamento
            document.getElementById('ordens-container').innerHTML = '';
            resetarCardsInicial();
            
            fetchContagemStatusOrdens();
            fetchStatusMaquinas();

        })
        .catch((error) => {
            console.error('Erro:', error);
            alert('Erro ao interromper a ordem.');
        });
    });
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

// Modal para "Iniciar"
function mostrarModalIniciar(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalIniciar'));
    const modalTitle = document.getElementById('modalIniciarLabel');
    const escolhaMaquina = document.getElementById('escolhaMaquinaIniciarOrdem');

    modalTitle.innerHTML = `Iniciar Ordem ${ordemId}`;
    modal.show();

    // Limpa opções antigas no select
    escolhaMaquina.innerHTML = `<option value="">------</option>`;

    // Define as máquinas para cada grupo
    const maquinasPorGrupo = {
        serra: [
            { value: 'serra_1', label: 'Serra 1' },
            { value: 'serra_2', label: 'Serra 2' },
            { value: 'serra_3', label: 'Serra 3' },
        ],
    };

    // Preenche o select com base no grupo de máquinas
    if (maquinasPorGrupo[grupoMaquina.toLowerCase()]) {
        maquinasPorGrupo[grupoMaquina.toLowerCase()].forEach((maquina) => {
            const option = document.createElement('option');
            option.value = maquina.value;
            option.textContent = maquina.label;
            escolhaMaquina.appendChild(option);
        });
    } else {
        console.warn(`Grupo de máquina "${grupoMaquina}" não encontrado.`);
    }

    // Remove listeners antigos e adiciona novo no formulário
    const formIniciar = document.getElementById('formIniciarOrdemCorte');
    const clonedForm = formIniciar.cloneNode(true);
    formIniciar.parentNode.replaceChild(clonedForm, formIniciar);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const maquinaName = formData.get('escolhaMaquinaIniciarOrdem');

        // Exibe SweetAlert de carregamento
        Swal.fire({
            title: 'Iniciando Ordem...',
            text: 'Por favor, aguarde.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            },
        });

        fetch(`api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify({
                ordem_id: ordemId,
                grupo_maquina: grupoMaquina,
                status: 'iniciada',
                maquina_nome: maquinaName,
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(), // Inclui o CSRF Token no cabeçalho
            },
        })
            .then(async (response) => {
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Erro ao iniciar a ordem.');
                }

                return data; // Retorna os dados para o próximo `.then`
            })
            .then(() => {
                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso',
                    text: 'Ordem iniciada com sucesso.',
                });

                modal.hide();

                // Atualiza a interface
                const containerIniciado = document.querySelector('.containerProcesso');
                carregarOrdensIniciadas(containerIniciado);
                
                // Recarrega os dados chamando a função de carregamento
                document.getElementById('ordens-container').innerHTML = '';
                resetarCardsInicial();

                fetchStatusMaquinas();
                fetchContagemStatusOrdens();

            })
            .catch((error) => {
                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: error.message,
                });
            });
    });
}

// Modal para "Finalizar"
function mostrarModalFinalizar(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalFinalizar'));
    const modalTitle = document.getElementById('modalFinalizarLabel');
    const formFinalizar = document.getElementById('formFinalizarOrdemCorte');

    // Configura título do modal
    modalTitle.innerHTML = `Finalizar Ordem ${ordemId}`;
    document.getElementById('bodyPecasFinalizar').innerHTML = '<p class="text-center text-muted">Carregando informações...</p>';

    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações da ordem...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Remove listeners antigos do formulário
    const clonedForm = formFinalizar.cloneNode(true);
    formFinalizar.parentNode.replaceChild(clonedForm, formFinalizar);

    // Fetch para buscar peças e propriedades
    fetch(`api/ordens-criadas/${ordemId}/${grupoMaquina.toLowerCase()}/pecas/`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao buscar informações da API');
            }
            return response.json();
        })
        .then(data => {
            Swal.close(); // Fecha o SweetAlert de carregamento
            document.getElementById('bodyPecasFinalizar').innerHTML = '';
            const tamanho = parseFloat(data.propriedades.tamanho) || 0; // Garante que `tamanho` será numérico ou `0`

            // Renderiza propriedades
            const propriedadesHTML = `
                <h6 class="text-center mt-3">Informações da matéria-prima</h6>
                <table class="table table-bordered table-sm text-center">
                    <thead>
                        <tr class="table-light">
                            <th>Descrição</th>
                            <th>Tamanho</th>
                            <th>Quantidade</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="text-align: center; padding: 5px;">
                                <select 
                                    id="selectMpSerraAlterar"
                                    class="form-select form-select-sm select2-materia-prima"
                                    style="width: 100%; max-width: 150px; font-size: 0.85rem; padding: 0.2rem 0.5rem; height: auto;"
                                    required>
                                    <option value="${data.propriedades.id_mp}" selected>${data.propriedades.descricao_mp || 'Selecione'}</option>
                                </select>
                            </td>
                            <td>
                                <input 
                                    type="number" 
                                    min="1" 
                                    step="0.01" 
                                    class="form-control form-control-sm" 
                                    id="tamanhoVaraInput" 
                                    name="tamanhoVaraInput"
                                    value=${tamanho}
                                    style="width: 100px; text-align: center;" required>
                            </td>
                            <td>
                                <input 
                                    type="number" 
                                    min="1" 
                                    step="0.01" 
                                    class="form-control form-control-sm" 
                                    id="propQtd" 
                                    name="propQtd"
                                    data-qtd-vara="${data.propriedades.quantidade}" 
                                    value="${data.propriedades.quantidade}" 
                                    style="width: 100px; text-align: center;" required>
                            </td>
                        </tr>
                    </tbody>
                </table>
            `;
            document.getElementById('bodyPecasFinalizar').insertAdjacentHTML('beforeend', propriedadesHTML);

            $('#selectMpSerraAlterar').select2({
                theme: 'bootstrap-5', // Tema específico para Bootstrap 5
                ajax: {
                    url: 'api/get-mp/',
                    dataType: 'json',
                    delay: 250,
                    data: function (params) {
                        return {
                            search: params.term || '',
                            page: params.page || 1,
                            per_page: 10
                        };
                    },
                    processResults: function (data, params) {
                        params.page = params.page || 1;
                        return {
                            results: data.results.map(item => ({
                                id: item.id,
                                text: item.text
                            })),
                            pagination: {
                                more: data.pagination.more
                            }
                        };
                    },
                    cache: true
                },
                minimumInputLength: 0,
                dropdownParent: $('#modalFinalizar'),
            });

            // Renderiza peças
            if (data.pecas && data.pecas.length > 0) {
                const pecasHTML = `
                    <h6 class="text-center mt-3">Peças da Ordem</h6>
                    <table class="table table-bordered table-sm text-center">
                        <thead>
                            <tr class="table-light">
                                <th>Peça</th>
                                <th>Qt. peças boas</th>
                                <th>Mortas</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.pecas.map((peca, index) => `
                                <tr>
                                    <td>${peca.peca_nome}</td>
                                    <td>
                                        <input 
                                            type="number" 
                                            id="qtdRealizada_${peca.peca_id}"
                                            data-peca-index="${index}"
                                            data-peca-id="${peca.peca_id}"
                                            class="form-control form-control-sm peca-quantidade" 
                                            value="${peca.quantidade}" 
                                            style="width: 100px; text-align: center;" required>
                                    </td>
                                    <td>
                                        <input 
                                            type="number" 
                                            class="form-control form-control-sm input-mortas" 
                                            data-peca-id="${peca.peca_id}" 
                                            min="0" 
                                            placeholder="Mortas"
                                            style="width: 100px; text-align: center;">
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('bodyPecasFinalizar').insertAdjacentHTML('beforeend', pecasHTML);

            } else {
                document.getElementById('bodyPecasFinalizar').innerHTML += '<p class="text-center text-muted">Não há peças cadastradas para esta ordem.</p>';
            }

            modal.show();

            if (!formFinalizar.checkValidity()) {
                formFinalizar.reportValidity(); // Exibe as mensagens de erro nativas do navegador
                return; // Interrompe a submissão se o formulário for inválido
            }
        
        })
        .catch(error => {
            Swal.close(); // Fecha o SweetAlert de carregamento
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: 'Erro ao buscar as informações da ordem.',
            });
        });

    // Listener para submissão do formulário
    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        Swal.fire({
            title: 'Finalizando...',
            text: 'Por favor, aguarde...',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        const inputsMortas = document.querySelectorAll('.input-mortas');
        const pecasMortas = Array.from(inputsMortas).map(input => {
            const pecaId = input.dataset.pecaId;
            const mortas = parseInt(input.value) || 0;
        
            const qtdRealizadaElement = document.querySelector(`[data-peca-id="${pecaId}"]`).closest('tr')
                .querySelector('.peca-quantidade');
        
            const qtdRealizada = parseInt(qtdRealizadaElement.value) || 0;
        
            return {
                peca: pecaId,
                mortas: mortas,
                planejadas: qtdRealizada
            };
        });
                
        const qtdVaras = document.getElementById('propQtd').value;
        const tamanhoVara = document.getElementById('tamanhoVaraInput').value;
        const operadorFinal = document.getElementById('operadorFinalizar').value;
        const obsFinalizar = document.getElementById('obsFinalizar').value;
        const mp_final = document.getElementById('selectMpSerraAlterar').value;
        
        // Faz o fetch para finalizar a ordem
        fetch(`api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify({
                ordem_id: ordemId,
                grupo_maquina: grupoMaquina,
                status: 'finalizada',
                pecas_mortas: pecasMortas,
                qtd_vara: qtdVaras,
                tamanho_vara: tamanhoVara,
                operador_final: operadorFinal,
                obs_finalizar: obsFinalizar,
                mp_final: mp_final
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(async (response) => {
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Erro ao finalizar a ordem.');
            }
            return data;
        })
        .then(() => {
            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: 'Ordem finalizada com sucesso.',
            });
            
            // Atualiza a interface
            const containerIniciado = document.querySelector('.containerProcesso');
            carregarOrdensIniciadas(containerIniciado);
            
            // Recarrega os dados chamando a função de carregamento
            document.getElementById('ordens-container').innerHTML = '';
            resetarCardsInicial();

            fetchStatusMaquinas();
            fetchUltimasPecasProduzidas();
            fetchContagemStatusOrdens();

            modal.hide();
        })
        .catch((error) => {
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: error.message,
            });
        });
    });
}

// Modal para "Retornar"
function mostrarModalRetornar(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalRetornar'));
    const modalTitle = document.getElementById('modalRetornarLabel');
    const formRetornar = document.getElementById('formRetornarProducao');

    modalTitle.innerHTML = `Retornar Ordem ${ordemId}`;
    modal.show();

    // Remove listeners antigos e adiciona novo
    const clonedForm = formRetornar.cloneNode(true);
    formRetornar.parentNode.replaceChild(clonedForm, formRetornar);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        Swal.fire({
            title: 'Retornando Ordem...',
            text: 'Por favor, aguarde.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        const formData = new FormData(clonedForm);

        fetch(`api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify({
                ordem_id: ordemId,
                grupo_maquina: grupoMaquina,
                status: 'iniciada',
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() // Inclui o CSRF Token no cabeçalho
            }
        })
        .then(async (response) => {
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Erro ao retornar a ordem.');
            }

            return data; // Retorna os dados para o próximo `.then`
        })
        .then((data) => {
            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: 'Ordem retornada com sucesso.',
            });

            modal.hide();

            // Atualiza a interface
            const containerIniciado = document.querySelector('.containerProcesso');
            carregarOrdensIniciadas(containerIniciado);

            const containerInterrompido = document.querySelector('.containerInterrompido');
            carregarOrdensInterrompidas(containerInterrompido);

            // Recarrega os dados chamando a função de carregamento
            document.getElementById('ordens-container').innerHTML = '';
            resetarCardsInicial();

            fetchContagemStatusOrdens();
            fetchStatusMaquinas();

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

function addPeca() {
    const containerPecas = document.getElementById('containerPecas');
    const indexInput = document.getElementById('indexCont'); // Input escondido que mantém o índice
    const index = parseInt(indexInput.value, 10); // Obtém o índice atual como número inteiro

    // Cria um novo grupo de inputs
    const newPecaRow = document.createElement('div');
    newPecaRow.classList.add('row');

    // Define o conteúdo HTML para o novo grupo de inputs
    newPecaRow.innerHTML = `
        <div class="col-sm-6">
            <label for="pecaEscolhida_${index}" class="form-label">Peça:</label>
            <select id="pecaEscolhida_${index}" class="form-select" name="pecaEscolhida_${index}" required>
                <option value="" disabled selected>Selecione a Peça</option>
            </select>
        </div>
        <div class="col-sm-4">
            <label for="quantidade_${index}" class="form-label">Quantidade</label>
            <input class="form-control" type="number" id="quantidade_${index}" name="quantidade_${index}" required>
        </div>
        <div class="col-auto d-flex align-items-center">
            <button class="btn btn-danger btn-sm btn-delete" type="button">
                <i class="fa fa-trash"></i>
            </button>
        </div>
    `;

    // Adiciona a nova linha ao final do contêiner
    containerPecas.appendChild(newPecaRow);

    // Incrementa o índice e atualiza o valor no input escondido
    indexInput.value = index + 1;

    // Inicializa o Select2 para o select recém-criado
    $(`#pecaEscolhida_${index}`).select2({
        placeholder: 'Selecione a Peça',
        width: '100%',
        theme: 'bootstrap-5', // Tema específico para Bootstrap 5
        ajax: {
            url: 'api/get-peca/',
            dataType: 'json',
            delay: 250,
            data: function (params) {
                return {
                    search: params.term || '',
                    page: params.page || 1,
                    per_page: 10
                };
            },
            processResults: function (data, params) {
                params.page = params.page || 1;
                return {
                    results: data.results.map(item => ({
                        id: item.id,
                        text: item.text
                    })),
                    pagination: {
                        more: data.pagination.more
                    }
                };
            },
            cache: true
        },
        minimumInputLength: 0,
        dropdownParent: $('#containerPecas'), // Use o contêiner correto como pai do dropdown
    });

    // Adiciona o evento de exclusão à linha
    const deleteButton = newPecaRow.querySelector('.btn-delete');
    deleteButton.addEventListener('click', function () {
        // Remove a linha correspondente
        newPecaRow.remove();
    });
}

function criarOrdem() {
    const form = document.getElementById('opSerraForm');

    if (!form.dataset.listenerAdded) {  // Verifica se o listener já foi adicionado
        form.dataset.listenerAdded = "true"; // Marca como adicionado

        form.addEventListener('submit', (event) => {
            event.preventDefault(); // Impede o envio padrão do formulário

            const formData = new FormData(form); // Captura os dados do formulário

            // Inicializa os dados principais do formulário
            const data = {
                mp: formData.get('mpEscolhida'),
                retalho: formData.get('retalho') === 'on', // Checkbox retorna 'on', converte para booleano
                descricao: formData.get('descricao') || '',
                tamanhoVara: formData.get('tamanhoVara') || '',
                quantidade: parseInt(formData.get('quantidade'), 10) || 0,
                pecas: [], // Array para armazenar peças e quantidades
                dataProgramacao: formData.get('dataProgramacao')
            };

            // Exibe SweetAlert de carregamento
            Swal.fire({
                title: 'Criando Ordem...',
                text: 'Por favor, aguarde.',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                },
            });

            // Itera sobre o FormData para capturar as peças e quantidades
            for (let [key, value] of formData.entries()) {
                if (key.startsWith('pecaEscolhida_')) {
                    const index = key.split('_')[1]; // Extrai o índice do campo
                    const quantidade = formData.get(`quantidade_${index}`); // Busca a quantidade correspondente

                    if (quantidade) {
                        data.pecas.push({
                            peca: value, // ID da peça
                            quantidade: parseInt(quantidade, 10) // Quantidade como número
                        });
                    }
                }
            }

            // Envia os dados usando fetch
            fetch('api/criar-ordem/', {
                method: 'POST',
                body: JSON.stringify(data),
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erro ao enviar o formulário');
                }
                return response.json();
            })
            .then(data => {
                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso',
                    text: 'Ordem criada com sucesso.',
                });

                document.getElementById('ordens-container').innerHTML = '';
                resetarCardsInicial();

                form.reset();
            })
            .catch(error => {
                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: error.message,
                });
            });
        });
    }
}

function filtro() {
    const form = document.getElementById('filtro-form');

    form.addEventListener('submit', (event) => {
        event.preventDefault(); // Evita comportamento padrão do formulário

        // Captura os valores atualizados dos filtros
        const filtros = {
            ordem: document.getElementById('filtro-ordem').value.trim(),
            mp: document.getElementById('filtro-mp').value.trim(),
            status: document.getElementById('filtro-status').value.trim(),
        };

        // Recarrega os resultados com os novos filtros
        resetarCardsInicial(filtros);

        // Filtrar ordens em andamento
        const containerIniciado = document.querySelector('.containerProcesso');
        carregarOrdensIniciadas(containerIniciado, filtros);

        // Filtrar ordens interrompidas
        const containerInterrompido = document.querySelector('.containerInterrompido');
        carregarOrdensInterrompidas(containerInterrompido, filtros);

    });
}

function importarOrdensSerra() {
    const form = document.getElementById('formImportarOrdemSerra');
    
    form.addEventListener('submit', (event) => {
        event.preventDefault(); // Evita o comportamento padrão do formulário

        const file = document.getElementById('arquivoOrdens').files[0]; // Captura o arquivo selecionado

        if (!file) {
            Swal.fire({
                icon: 'warning',
                title: 'Atenção!',
                text: 'Por favor, selecione um arquivo antes de enviar.',
            });
            return;
        }

        const formData = new FormData(); // Cria o objeto FormData
        formData.append('arquivoOrdens', file); // Adiciona o arquivo ao FormData

        // Inclui o token CSRF no cabeçalho (caso o Django esteja configurado para exigir CSRF)
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        // Exibe um SweetAlert de carregamento
        Swal.fire({
            title: 'Enviando...',
            text: 'Por favor, aguarde enquanto o arquivo é enviado.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        // Faz a requisição para o backend
        fetch('api/importar-ordens-serra/', {
            method: 'POST',
            body: formData, // Envia o FormData com o arquivo
            headers: {
                'X-CSRFToken': csrfToken // Adiciona o token CSRF
            }
        })
        .then(response => response.json())
        .then(data => {
            Swal.close(); // Fecha o SweetAlert de carregamento

            if (data.status === 'success') {
                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso!',
                    text: 'Arquivo importado com sucesso!',
                });

                // Atualiza a interface
                const containerIniciado = document.querySelector('.containerProcesso');
                carregarOrdensIniciadas(containerIniciado);
                
                // Recarrega os dados chamando a função de carregamento
                document.getElementById('ordens-container').innerHTML = '';
                resetarCardsInicial();

            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Erro!',
                    text: `Erro ao importar arquivo: ${data.message}`,
                });
            }
        })
        .catch(error => {
            Swal.close(); // Fecha o SweetAlert de carregamento
            console.error('Erro ao enviar o arquivo:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erro!',
                text: 'Ocorreu um erro ao enviar o arquivo.',
            });
        });
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        resetarCardsInicial();

        // // Inicializa carregamento de ordens simultaneamente
        // const containerIniciado = document.querySelector('.containerProcesso');
        // const containerInterrompido = document.querySelector('.containerInterrompido');

        // if (containerIniciado) carregarOrdensIniciadas(containerIniciado);
        // if (containerInterrompido) carregarOrdensInterrompidas(containerInterrompido);

        // // Adiciona evento ao botão "Add" se ele existir
        // const addPecaBtn = document.getElementById("addPeca");
        // if (addPecaBtn) {
        //     addPecaBtn.addEventListener("click", addPeca);
        // }

        // // Configuração do Select2 para diferentes campos
        // configurarSelect2('#mpEscolhida', 'api/get-mp/', '#modalSerra');
        // configurarSelect2('#pecaEscolhida_0', 'api/get-peca/', '#containerPecas');
        // configurarSelect2('#filtro-mp', 'api/get-mp/', null, true);
        // configurarSelect2('#filtro-peca', 'api/get-peca/', null, true);

        // // Executa outras funções de inicialização
        // criarOrdem();
        // // filtro();
        // importarOrdensSerra();
        
    } catch (error) {
        console.error("Erro ao carregar a página:", error);
    }
});

/**
 * Configura o Select2 de forma reutilizável
 * @param {string} selector - Seletor do elemento
 * @param {string} url - URL da API
 * @param {string|null} parent - Seletor do contêiner pai (se aplicável)
 * @param {boolean} [allowClear=false] - Habilitar botão de limpar
 */
function configurarSelect2(selector, url, parent = null, allowClear = false) {
    const element = document.querySelector(selector);
    if (!element) return; // Evita erros se o elemento não existir

    $(selector).select2({
        placeholder: 'Selecione uma opção',
        width: '100%',
        theme: 'bootstrap-5',
        allowClear: allowClear,
        ajax: {
            url: url,
            dataType: 'json',
            delay: 250,
            data: (params) => ({
                search: params.term || '',
                page: params.page || 1,
                per_page: 10
            }),
            processResults: (data, params) => ({
                results: data.results.map(item => ({
                    id: item.id,
                    text: item.text
                })),
                pagination: { more: data.pagination?.more || false }
            }),
            cache: true
        },
        minimumInputLength: 0,
        dropdownParent: parent ? $(parent) : undefined
    });
}

