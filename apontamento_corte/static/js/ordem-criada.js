import { fetchStatusMaquinas, fetchOrdensSequenciadasLaser, fetchOrdensSequenciadasPlasma } from './status-maquina-corte.js';

export const loadOrdens = (container, page = 1, limit = 10, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => { // Retorna uma Promise
        if (isLoading) return resolve({ ordens: [] }); // Evita chamadas duplicadas
        isLoading = true;


        fetch(`api/ordens-criadas/?page=${page}&limit=${limit}&ordem=${encodeURIComponent(filtros.ordem || '')}&maquina=${filtros.maquina || ''}&peca=${filtros.peca || ''}&status=${filtros.status || ''}&turno=${filtros.turno || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;
                if (ordens.length > 0) {

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
                        let botaoAcao = `
                        `;

                        if (ordem.status_atual === 'iniciada') {
                            botaoAcao += `
                                <button class="btn btn-danger btn-sm btn-interromper me-2" title="Interromper">
                                    <i class="fa fa-stop"></i>
                                </button>
                                <button class="btn btn-success btn-sm btn-finalizar" title="Finalizar">
                                    <i class="fa fa-check"></i>
                                </button>
                                <button class="btn btn-danger btn-sm btn-excluir" title="Excluir">
                                    <i class="fa fa-trash"></i>
                                </button>
                            `;
                        } else if (ordem.status_atual === 'aguardando_iniciar') {
                            botaoAcao += `
                                <button class="btn btn-warning btn-sm btn-iniciar" title="Iniciar">
                                    <i class="fa fa-play"></i>
                                </button>
                                <button class="btn btn-danger btn-sm btn-excluir" title="Excluir">
                                    <i class="fa fa-trash"></i>
                                </button>
                            `;
                        
                            if (!ordem.sequenciada) {
                                botaoAcao += `
                                    <button class="btn btn-dark btn-sm btn-sequenciar me-2" title="Sequenciar">
                                        <i class="fa fa-step-forward"></i>
                                    </button>
                                `;
                            }
                        } else if (ordem.status_atual === 'interrompida') {
                            botaoAcao += `
                                <button class="btn btn-warning btn-sm btn-retornar" title="Retornar">
                                    <i class="fa fa-redo"></i>
                                </button>
                                <button class="btn btn-danger btn-sm btn-excluir" title="Excluir">
                                    <i class="fa fa-trash"></i>
                                </button>
                            `;
                        }

                        //verificar se a ordem está finalizada
                        let dataFinalizacao = '';
                        if (ordem.status_atual === 'finalizada') {
                            dataFinalizacao = `<p class="text-success fw-semibold mb-2" style="font-size: 0.85rem;">Finalizada em: ${ordem.ultima_atualizacao}</p>`
                        }
                        // Monta o card com os botões dinâmicos
                        card.innerHTML = `
                        <div class="card shadow-sm bg-light text-dark">
                            <div class="card-body">
                                <h5 class="card-title d-flex justify-content-between align-items-center">
                                    ${ordem.ordem} - ${ordem.grupo_maquina}
                                    ${statusBadge}
                                </h5>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">Criado em: ${ordem.data_criacao}</p>
                                ${dataFinalizacao}
                                <p class="mb-2">${ordem.obs || '<span class="text-muted">Sem observações</span>'}</p>
                                <ul class="list-unstyled mb-0" style="font-size: 0.85rem;">
                                    <li><strong>MP:</strong> ${ordem.propriedade.descricao_mp || 'N/A'}</li>
                                    <li><strong>Quantidade:</strong> ${ordem.propriedade.quantidade || 'N/A'}</li>
                                    <li><strong>Tipo Chapa:</strong> ${ordem.propriedade.tipo_chapa || 'N/A'}</li>
                                    <li><strong>Aproveitamento:</strong> ${ordem.propriedade.aproveitamento || 'N/A'}</li>
                                    <li><strong>Retalho:</strong> ${ordem.propriedade.retalho || 'Não'}</li>
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
                        const buttonSequenciar = card.querySelector('.btn-sequenciar');
                        const buttonExcluir= card.querySelector('.btn-excluir');

                        // Adiciona evento ao botão "Ver Peças", se existir
                        if (buttonVerPeca) {
                            buttonVerPeca.addEventListener('click', () => {
                                mostrarPecas(ordem.id);
                            });
                        }

                        // Adiciona evento ao botão "Iniciar", se existir
                        if (buttonIniciar) {
                            buttonIniciar.addEventListener('click', () => {
                                mostrarModalIniciar(ordem.id, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Interromper", se existir
                        if (buttonInterromper) {
                            buttonInterromper.addEventListener('click', () => {
                                mostrarModalInterromper(ordem.id);
                            });
                        }

                        // Adiciona evento ao botão "Finalizar", se existir
                        if (buttonFinalizar) {
                            buttonFinalizar.addEventListener('click', () => {
                                mostrarModalFinalizar(ordem.id);
                            });
                        }

                        // Adiciona evento ao botão "Retornar", se existir
                        if (buttonRetornar) {
                            buttonRetornar.addEventListener('click', () => {
                                mostrarModalRetornar(ordem.id, ordem.maquina_id);
                            });
                        }

                        // Adiciona evento ao botão "Resequenciar", se existir
                        if (buttonSequenciar) {
                            buttonSequenciar.addEventListener('click', () => {
                                mostrarModalResequenciar(ordem.id);
                            });
                        }

                        // Adiciona evento ao botão "Excluir", se existir
                        if (buttonExcluir) {
                            buttonExcluir.addEventListener('click', () => {
                                mostrarModalExcluir(ordem.id);
                            });
                        }

                        // Adiciona o card ao container
                        container.appendChild(card);
                    });

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

export function carregarOrdensIniciadas(container) {
    container.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;

    fetch('api/ordens-iniciadas/?page=1&limit=10')
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
                        ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor'
                        ? `<button class="btn btn-danger btn-sm btn-deletar m-2" data-ordem="${ordem.id}" title="Desfazer">
                            <i class="bi bi-arrow-left-right"></i>
                        </button>`: ""}
                        <button class="btn btn-warning btn-sm btn-interromper m-2" title="Interromper">
                            <i class="fa fa-stop"></i>
                        </button>
                        <button class="btn btn-success btn-sm btn-finalizar m-2" title="Finalizar">
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
                <div class="card shadow-lg border-0 rounded-3 mb-3 position-relative">
                    <!-- Contador fixado no topo direito -->
                    <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                        id="contador-${ordem.ordem}" 
                        style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                        Carregando...
                    </span>

                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title fw-bold mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                    </div>

                    <div class="card-body bg-light p-3">
                        <p class="card-text mb-3">
                            <strong>Observação:</strong> ${ordem.obs || 'Sem observações'}
                        </p>
                        <p class="card-text mb-3">
                            <strong>Descrição MP:</strong> ${ordem.propriedade.descricao_mp || 'Sem descrição'}
                        </p>
                    </div>

                    <div class="card-footer d-flex justify-content-between align-items-center bg-white p-3 border-top">
                        <button class="btn btn-outline-primary btn-sm btn-ver-peca">
                            Ver Peças
                        </button>
                        <div class="d-flex flex-wrap justify-content-center gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                const buttonVerPeca = card.querySelector('.btn-ver-peca');
                const buttonDeletar = card.querySelector('.btn-deletar');
                const buttonInterromper = card.querySelector('.btn-interromper');
                const buttonFinalizar = card.querySelector('.btn-finalizar');

                // Adiciona evento ao botão "Ver Peças", se existir
                if (buttonVerPeca) {
                    buttonVerPeca.addEventListener('click', () => {
                        mostrarPecas(ordem.id);
                    });
                }

                // Adiciona evento ao botão "Interromper", se existir
                if (buttonInterromper) {
                    buttonInterromper.addEventListener('click', () => {
                        mostrarModalInterromper(ordem.id);
                    });
                }

                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', () => {
                        mostrarModalRetornarOrdemIniciada(ordem.id);
                    });
                }

                // Adiciona evento ao botão "Finalizar", se existir
                if (buttonFinalizar) {
                    buttonFinalizar.addEventListener('click', () => {
                        mostrarModalFinalizar(ordem.id);
                    });
                }

                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)
            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
}

export function carregarOrdensInterrompidas(container) {
    container.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;
    
    // Fetch para buscar ordens interrompidas
    fetch('api/ordens-interrompidas/?page=1&limit=10')
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
                card.dataset.ordemId = ordem.id;
                console.log(data.usuario_tipo_acesso)
                
                // Define os botões dinamicamente
                const botaoAcao = `
                    ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor'
                    ? `<button class="btn btn-danger btn-sm btn-deletar m-2" data-ordem="${ordem.id}" title="Deletar">
                            <i class="bi bi-arrow-left-right"></i>
                    </button>`: ""} 
                    <button class="btn btn-warning btn-sm btn-retornar m-2" title="Retornar">
                        <i class="fa fa-undo"></i>
                    </button>
                `;

                card.innerHTML = `
                <div class="card shadow-lg border-0 rounded-3 mb-3">
                    <div class="card-header bg-danger text-white d-flex justify-content-between align-items-center p-3">
                        <div>
                            <h6 class="card-title fw-bold mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                            <small class="text-white d-block mt-1">Motivo: ${ordem.motivo_interrupcao || 'Sem motivo'}</small>
                        </div>
                        <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                            id="contador-${ordem.ordem}" 
                            style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                            Carregando...
                        </span>
                    </div>
                    
                    <div class="card-body bg-light p-3">
                        <p class="card-text mb-3">
                            <strong>Observação:</strong> ${ordem.obs || 'N/A'}
                        </p>
                        <p class="card-text mb-3">
                            <strong>Descrição MP:</strong> ${ordem.propriedade.descricao_mp || 'Sem descrição'}
                        </p>
                    </div>
                    
                    <div class="card-footer d-flex justify-content-between align-items-center bg-white p-3 border-top">
                        <button class="btn btn-outline-primary btn-sm btn-ver-peca">
                            Ver Peças
                        </button>
                        <div class="d-flex gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                // Adiciona eventos aos botões
                const buttonVerPeca = card.querySelector('.btn-ver-peca');
                const buttonRetornar = card.querySelector('.btn-retornar');
                const buttonDeletar = card.querySelector('.btn-deletar');

                // Evento para "Ver Peças"
                if (buttonVerPeca) {
                    buttonVerPeca.addEventListener('click', () => {
                        mostrarPecas(ordem.id);
                    });
                }

                // Evento para "Retornar"
                if (buttonRetornar) {
                    buttonRetornar.addEventListener('click', () => {
                        mostrarModalRetornar(ordem.id, ordem.maquina_id);
                    });
                }

                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', function() {
                        mostrarModalRetornarOrdemIniciada(ordem.id);
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

// Função para exibir as peças no modal
export function mostrarPecas(ordemId) {
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

    // Fetch para buscar peças
    fetch(`api/ordens-criadas/${ordemId}/pecas/`)
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
                                        <a href="https://drive.google.com/drive/u/0/search?q=${peca.peca}" target="_blank" rel="noopener noreferrer">
                                            ${peca.peca}
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

// Modal para "Interromper"
function mostrarModalInterromper(ordemId) {
    const modal = new bootstrap.Modal(document.getElementById('modalInterromper'));
    const modalTitle = document.getElementById('modalInterromperLabel');
    const formInterromper = document.getElementById('formInterromperOrdemCorte');

    modalTitle.innerHTML = `Interromper Ordem`;
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
                // grupo_maquina: grupoMaquina,
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
            resetarCardsInicial();

            fetchStatusMaquinas();
            fetchOrdensSequenciadasPlasma();

        })
        .catch((error) => {
            console.error('Erro:', error);
            alert('Erro ao interromper a ordem.');
        });
    });
}

// Modal para "Iniciar"
export function mostrarModalIniciar(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalIniciar'));
    const modalTitle = document.getElementById('modalIniciarLabel');
    const escolhaMaquina = document.getElementById('escolhaMaquinaIniciarOrdem');

    modalTitle.innerHTML = `Iniciar Ordem ${ordemId}`;
    modal.show();

    grupoMaquina = grupoMaquina.toLowerCase().replace(" ","_").replace(" (jfy)","");

    // Limpa opções antigas no select
    escolhaMaquina.innerHTML = ``;

    // Define as máquinas para cada grupo
    const maquinasPorGrupo = {
        laser_1: [
            { value: '16', label: 'Laser 1' },
            { value: '17', label: 'Laser 2 (JFY)' },
        ],
        laser_2: [
            { value: '17', label: 'Laser 2 (JFY)' },
            { value: '16', label: 'Laser 1' },
        ],
        plasma: [
            { value: '19', label: 'Plasma 1' },
            { value: '54', label: 'Plasma 2' },
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
                maquina: maquinaName,
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

                resetarCardsInicial(); 

                fetchStatusMaquinas();
                fetchOrdensSequenciadasPlasma();

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

function mostrarModalRetornarOrdemIniciada(ordemId) {
    const modalRetornarProcessoIniciado = new bootstrap.Modal(document.getElementById('modalRetornarProcessoIniciado'));
    const textRetorno = document.getElementById('text-confirm');
    const modalTitle = document.getElementById("modalExcluirRetorno");
    const form = document.getElementById('formRetornarProcessoIniciado');
    
    modalTitle.textContent = `#${ordemId}`;
    textRetorno.textContent = `Você tem certeza que deseja retornar a Ordem #${ordemId} para o status "Aguardando Iniciar"?`;
    
    // Remove todos os listeners de submit existentes
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);
    
    // Adiciona o novo listener
    newForm.addEventListener('submit', async function handleSubmit(event) {
        event.preventDefault();
        
        try {
            const submitButton = document.getElementById('retornar-aguardando-iniciar');
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processando...';
            
            const response = await fetch('/core/api/retornar-processo/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ ordemId: ordemId })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                modalRetornarProcessoIniciado.hide();
                carregarOrdensIniciadas(document.querySelector('.containerProcesso'));
                carregarOrdensInterrompidas(document.querySelector('.containerInterrompido'));
                resetarCardsInicial();
            } else {
                throw new Error(data.message || 'Erro ao retornar a ordem');
            }
        } catch (error) {
            console.error('Erro:', error);
            alert(error.message || 'Ocorreu um erro ao processar sua solicitação');
        } finally {
            const submitButton = document.getElementById('retornar-aguardando-iniciar');
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = 'Retornar';
            }
        }
    });
    
    modalRetornarProcessoIniciado.show();
}

// Modal para "Finalizar"
function mostrarModalFinalizar(ordemId) {
    const modal = new bootstrap.Modal(document.getElementById('modalFinalizar'));
    const modalTitle = document.getElementById('modalFinalizarLabel');
    const formFinalizar = document.getElementById('formFinalizarOrdemCorte');

    // Configura título do modal
    modalTitle.innerHTML = `Finalizar Ordem`;
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
    fetch(`api/ordens-criadas/${ordemId}/pecas/`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao buscar informações da API');
            }
            return response.json();
        })
        .then(data => {
            Swal.close(); // Fecha o SweetAlert de carregamento
            document.getElementById('bodyPecasFinalizar').innerHTML = '';

            // Renderiza propriedades
            const propriedadesHTML = `
                <h6 class="text-center mt-3">Informações da Chapa</h6>
                <table class="table table-bordered table-sm text-center">
                    <thead>
                        <tr class="table-light">
                            <th>Descrição</th>
                            <th>Espessura</th>
                            <th>Quantidade de Chapas</th>
                            <th>Tipo Chapa</th>
                            <th>Aproveitamento</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${data.propriedades.descricao_mp || 'N/A'}</td>
                            <td>${data.propriedades.espessura || 'N/A'}</td>
                            <td style='display: flex; justify-content: center; align-items: center;'>
                                <input 
                                    type="number" 
                                    min="1" 
                                    max="100" 
                                    class="form-control form-control-sm" 
                                    id="propQtd" 
                                    data-qtd-chapa="${data.propriedades.quantidade}" 
                                    value="${data.propriedades.quantidade}" 
                                    style="width: 100px; text-align: center;">
                            </td>
                            <td>
                                <select name="tipo_chapa" class="form-select form-select-sm">
                                    <option value="aco_carbono" ${data.propriedades.tipo_chapa === 'Aço carbono' ? 'selected' : ''}>Aço carbono</option>
                                    <option value="anti_derrapante" ${data.propriedades.tipo_chapa === 'Anti derrapante' ? 'selected' : ''}>Anti derrapante</option>
                                    <option value="inox" ${data.propriedades.tipo_chapa === 'Inox' ? 'selected' : ''}>Inox</option>
                                    <option value="alta_resistencia" ${data.propriedades.tipo_chapa === 'Alta resistência' ? 'selected' : ''}>Alta resistência</option>
                                </select>
                            </td>
                            <td>${data.propriedades.aproveitamento || 'N/A'}</td>
                        </tr>
                    </tbody>
                </table>
            `;
            document.getElementById('bodyPecasFinalizar').insertAdjacentHTML('beforeend', propriedadesHTML);

            // Renderiza peças
            if (data.pecas && data.pecas.length > 0) {
                const pecasHTML = `
                    <h6 class="text-center mt-3">Peças da Ordem</h6>
                    <table class="table table-bordered table-sm text-center">
                        <thead>
                            <tr class="table-light">
                                <th>Peça</th>
                                <th>Quantidade Inicial</th>
                                <th>Mortas</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.pecas.map((peca, index) => `
                                <tr>
                                    <td>${peca.peca}</td>
                                    <td class="peca-quantidade" data-peca-id="${peca.peca}"  data-peca-index="${index}" data-quantidade-inicial="${peca.quantidade}">
                                        ${peca.quantidade}
                                    </td>
                                    <td>
                                        <input 
                                            type="number" 
                                            class="form-control form-control-sm input-mortas" 
                                            data-peca-id="${peca.peca}" 
                                            min="0" 
                                            max="${peca.quantidade}" 
                                            placeholder="Mortas"
                                            style="width: 100px; text-align: center;">
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('bodyPecasFinalizar').insertAdjacentHTML('beforeend', pecasHTML);

                // Atualiza as quantidades de peças ao alterar a quantidade de chapas
                const propQtdInput = document.getElementById('propQtd');
                propQtdInput.addEventListener('change', () => {
                    const novaQtdChapas = parseInt(propQtdInput.value, 10);
                    const qtdInicialChapas = parseInt(propQtdInput.dataset.qtdChapa, 10);

                    if (novaQtdChapas && novaQtdChapas > 0) {
                        document.querySelectorAll('.peca-quantidade').forEach(cell => {
                            const qtdInicial = parseInt(cell.dataset.quantidadeInicial, 10); // Quantidade inicial de peças
                            const novaQtdPecas = (qtdInicial / qtdInicialChapas) * novaQtdChapas; // Recalcula a nova quantidade de peças
                    
                            cell.textContent = Math.floor(novaQtdPecas); // Atualiza o texto na célula
                    
                            // Atualiza o atributo 'max' do input correspondente
                            const pecaId = cell.dataset.pecaId; // Obtém o identificador único da peça
                            const mortasInput = document.querySelector(`input[data-peca-id="${pecaId}"]`); // Seleciona o input correto
                    
                            if (mortasInput) {
                                mortasInput.setAttribute('max', Math.floor(novaQtdPecas)); // Define o novo valor máximo
                            }
                        });
                    }
                });
            } else {
                document.getElementById('bodyPecasFinalizar').innerHTML += '<p class="text-center text-muted">Não há peças cadastradas para esta ordem.</p>';
            }

            modal.show();
        
            if (!formFinalizar.checkValidity()) {
                formFinalizar.reportValidity(); // Exibe as mensagens de erro padrão do navegador
                return;
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

        const tipoChapa = document.querySelector('[name="tipo_chapa"]').value;
        const obsFinal = document.getElementById('obsFinalizarCorte').value;
        const operadorFinal=document.getElementById('operadorFinal').value;
        const inputsMortas = document.querySelectorAll('.input-mortas');
        const pecasMortas = Array.from(inputsMortas).map(input => {
            const pecaId = input.dataset.pecaId;
            const mortas = parseInt(input.value) || 0;
        
            // Captura a quantidade planejada usando um atributo ou elemento relacionado
            const quantidadePlanejada = parseInt(
                document.querySelector(`[data-peca-id="${pecaId}"]`).closest('tr')
                    .querySelector('.peca-quantidade').textContent
            ) || 0;
        
            return {
                peca: pecaId,
                mortas: mortas,
                planejadas: quantidadePlanejada // Adiciona a quantidade planejada
            };
        });

        const qtdChapas = document.getElementById('propQtd').value;

        // Faz o fetch para finalizar a ordem
        fetch(`api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify({
                ordem_id: ordemId,
                // grupo_maquina: grupoMaquina,
                status: 'finalizada',
                pecas_mortas: pecasMortas,
                qtdChapas: qtdChapas,
                operadorFinal: operadorFinal,
                obsFinal: obsFinal,
                tipoChapa: tipoChapa,
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
            
            resetarCardsInicial();
                        
            modal.hide();

            fetchStatusMaquinas();
            fetchOrdensSequenciadasPlasma();
            fetchOrdensSequenciadasLaser();

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
function mostrarModalRetornar(ordemId, maquina) {
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
                // grupo_maquina: grupoMaquina,
                status: 'iniciada',
                maquina: maquina,
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

            resetarCardsInicial();

            fetchStatusMaquinas();
            fetchOrdensSequenciadasPlasma();

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

// Modal para "Resequenciar"
function mostrarModalResequenciar(ordemId, setor) {
    const modal = new bootstrap.Modal(document.getElementById('modalResequenciar'));
    const modalTitle = document.getElementById('modalResequenciarLabel');
    const formResequenciar = document.getElementById('formResequenciar');

    modalTitle.innerHTML = `Sequenciar Ordem ${ordemId}`;
    modal.show();

    // Remove listeners antigos e adiciona novo
    const clonedForm = formResequenciar.cloneNode(true);
    formResequenciar.parentNode.replaceChild(clonedForm, formResequenciar);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const motivoExclusao = formData.get('motivoExclusao');

        Swal.fire({
            title: 'Sequenciando...',
            text: 'Por favor, aguarde enquanto a ordem está sendo sequenciada.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch(`api/resequenciar-ordem/`, {
            method: 'POST',
            body: JSON.stringify({
                ordem_id: ordemId,
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
                    text: body.error || 'Erro ao sequenciar a ordem.',
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

        fetch(`api/excluir-ordem/`, {
            method: 'POST',
            body: JSON.stringify({
                ordem_id: ordemId,
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

                const containerIniciado = document.querySelector('.containerProcesso');
                carregarOrdensIniciadas(containerIniciado);
                
                const containerInterrompido = document.querySelector('.containerInterrompido');
                carregarOrdensInterrompidas(containerInterrompido);

                fetchStatusMaquinas();
                fetchOrdensSequenciadasLaser();
                fetchOrdensSequenciadasPlasma();
    
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

export function resetarCardsInicial(filtros = {}) {
    const container = document.getElementById('ordens-container');
    const loadMoreButton = document.getElementById('loadMore');
    let page = 1; // Página inicial
    const limit = 10; // Quantidade de ordens por página
    let isLoading = false; // Flag para evitar chamadas simultâneas
    let hasMoreData = true; // Flag para interromper chamadas quando não houver mais dados

    // Atualiza os filtros com os valores enviados
    const filtroOrdem = document.getElementById('filtro-ordem');
    const filtroMaquina = document.getElementById('filtro-maquina');
    const filtroStatus = document.getElementById('filtro-status');
    const filtroPeca = document.getElementById('filtro-peca');
    const filtroTurno = document.getElementById('filtro-turno');

    const currentFiltros = {
        ordem: filtros.ordem || filtroOrdem.value.trim(),
        maquina: filtros.maquina || filtroMaquina.value,
        status: filtros.status || filtroStatus.value,
        peca: filtros.peca || filtroPeca.value,
        turno: filtros.turno || filtroTurno.value
    };

    console.log(currentFiltros)

    // Função principal para buscar e renderizar ordens
    const fetchOrdens = () => {
        if (isLoading || !hasMoreData) return;
        isLoading = true;

        loadOrdens(container, page, limit, currentFiltros)
            .then((data) => {
                loadMoreButton.disabled = false;
                loadMoreButton.innerHTML = `Carregar mais`; 

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

        // Atualiza os filtros com os valores enviados
        const filtroOrdem = document.getElementById('filtro-ordem');
        const filtroMaquina = document.getElementById('filtro-maquina');
        const filtroStatus = document.getElementById('filtro-status');
        const filtroPeca = document.getElementById('filtro-peca');
        const filtroTurno = document.getElementById('filtro-turno');

        currentFiltros.ordem = filtroOrdem.value.trim();
        currentFiltros.maquina = filtroMaquina.value;
        currentFiltros.status = filtroStatus.value;
        currentFiltros.peca = filtroPeca.value;
        currentFiltros.turno = filtroTurno.value;
    
        loadMoreButton.disabled = true;
        loadMoreButton.innerHTML = `                    
            <div class="spinner-border text-dark" role="status">
                <span class="sr-only">Loading...</span>
            </div>
        `;
        fetchOrdens(currentFiltros); // Carrega a próxima página ao clicar no botão
    };
}

function carregarPecasDuplicar() {
    fetch('api/pecas/') // Substitua pela URL correta da API para obter as peças
        .then(response => response.json())
        .then(data => {
            const filtroPecas = document.getElementById('filtroPecas');
            filtroPecas.innerHTML = ''; // Limpa as opções anteriores

            data.forEach(peca => {
                const option = document.createElement('option');
                option.value = peca.id;
                option.textContent = `${peca.codigo} - ${peca.descricao}`;
                filtroPecas.appendChild(option);
            });
        })
        .catch(error => console.error('Erro ao carregar peças:', error));
}

function filtro() {
    const form = document.getElementById('formFiltrarOrdem');

    if (form){
        form.addEventListener('submit', (event) => {
            event.preventDefault(); // Evita comportamento padrão do formulário
    
            // Captura os valores atualizados dos filtros
            const filtroPecas= document.getElementById('filtroPecas')
            const filtroMaquina= document.getElementById('filtroMaquina').value
    
            const pecasSelecionadas = Array.from(filtroPecas.selectedOptions).map((opt) => opt.value);
    
            fetch(`api/duplicador-ordem/filtrar/?pecas=${pecasSelecionadas.join(",")}&maquina=${filtroMaquina}`)
            .then((response) => response.json())
            .then((data) => {
    
                resultadoFiltro.innerHTML = "";
                data.ordens.forEach((ordem) => {
                    const row = document.createElement("tr");
                    row.innerHTML = `
                        <td>${ordem.id}</td>
                        <td>${ordem.peca}</td>
                        <td>${ordem.quantidade}</td>
                        <td>
                            <button class="btn btn-primary btn-sm btn-duplicar" data-id="${ordem.id}">Duplicar</button>
                        </td>
                    `;
                    resultadoFiltro.appendChild(row);
                });
            })
            .catch((error) => console.error("Erro ao filtrar ordens:", error));
    
        });
    }


}

document.addEventListener('DOMContentLoaded', () => {

    resetarCardsInicial(); 

    const containerIniciado = document.querySelector('.containerProcesso');
    carregarOrdensIniciadas(containerIniciado);

    const containerInterrompido = document.querySelector('.containerInterrompido');
    carregarOrdensInterrompidas(containerInterrompido);

    filtro();

});