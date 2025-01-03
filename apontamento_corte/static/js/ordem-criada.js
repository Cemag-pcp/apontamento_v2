export const loadOrdens = (container, page = 1, limit = 10, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    const spinner = document.getElementById('loading'); // Referência ao spinner

    const showSpinner = () => {
        if (spinner) {
            spinner.style.display = 'flex'; // Exibe o spinner
        } else {
            console.warn('Spinner não encontrado no DOM.');
        }
    };

    const hideSpinner = () => {
        if (spinner) {
            spinner.style.display = 'none'; // Oculta o spinner
        } else {
            console.warn('Spinner não encontrado no DOM.');
        }
    };

    return new Promise((resolve, reject) => { // Retorna uma Promise
        if (isLoading) return resolve({ ordens: [] }); // Evita chamadas duplicadas
        isLoading = true;

        fetch(`api/ordens-criadas/?page=${page}&limit=${limit}&ordem=${filtros.ordem || ''}&maquina=${filtros.maquina || ''}`)
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

                        // Monta o card com os botões dinâmicos
                        card.innerHTML = `
                        <div class="card shadow-sm bg-light text-dark">
                            <div class="card-body">
                                <h5 class="card-title d-flex justify-content-between align-items-center">
                                    ${ordem.ordem} - ${ordem.grupo_maquina}
                                    ${statusBadge}
                                </h5>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">Criado em: ${ordem.data_criacao}</p>
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
                hideSpinner(); // Oculta o spinner após o carregamento
            });
    });
};

function carregarOrdensIniciadas(container) {
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
                    <div class="card-header bg-primary text-white">
                        <h6 class="card-title mb-0">${ordem.ordem} - ${ordem.maquina}</h6>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Observação:</strong> ${ordem.obs || 'Sem observações'}
                        </p>
                        <p class="card-text mb-0 small">
                            <strong>Descrição MP:</strong> ${ordem.propriedade.descricao_mp || 'Sem descrição'}
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
            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
}

function carregarOrdensInterrompidas(container) {
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
                card.dataset.ordemId = ordem.ordem;
                
                // Define os botões dinamicamente
                const botaoAcao = `
                    <button class="btn btn-warning btn-sm btn-retornar me-2" title="Retornar">
                        <i class="fa fa-undo"></i>
                    </button>
                `;

                card.innerHTML = `
                <div class="card shadow-sm border-0" style="border-radius: 10px; overflow: hidden;">
                    <div class="card-header bg-danger text-white">
                        <h6 class="card-title mb-0">${ordem.ordem} - ${ordem.maquina}</h6>
                        <small class="text-white">Motivo: ${ordem.motivo_interrupcao || 'Sem motivo'}</small>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Observação:</strong> ${ordem.obs || 'N/A'}
                        </p>
                        <p class="card-text mb-2 small">
                            <strong>Descrição MP:</strong> ${ordem.propriedade.descricao_mp || 'Sem descrição'}
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
    const maquinaNameLower = maquinaName.toLowerCase().replace(" ","_").replace(" (jfy)","");
    document.getElementById('modalPecas').removeAttribute('inert');

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
                                    <td>${peca.peca}</td>
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
            document.getElementById('ordens-container')='';
            resetarCardsInicial();

        })
        .catch((error) => {
            console.error('Erro:', error);
            alert('Erro ao interromper a ordem.');
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

    grupoMaquina = grupoMaquina.toLowerCase().replace(" ","_").replace(" (jfy)","");

    // Limpa opções antigas no select
    escolhaMaquina.innerHTML = ``;

    // Define as máquinas para cada grupo
    const maquinasPorGrupo = {
        laser_1: [
            { value: 'laser_1', label: 'Laser 1' },
        ],
        laser_2: [
            {value: 'laser_2', label: 'Laser 2 (JFY)'},
        ],
        plasma: [
            { value: 'plasma_1', label: 'Plasma 1' },
            { value: 'plasma_2', label: 'Plasma 2' },
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
                            <td>
                                <input 
                                    type="number" 
                                    min="1" 
                                    max="20" 
                                    class="form-control form-control-sm" 
                                    id="propQtd" 
                                    data-qtd-chapa="${data.propriedades.quantidade}" 
                                    value="${data.propriedades.quantidade}" 
                                    style="width: 100px; text-align: center;">
                            </td>
                            <td>${data.propriedades.tipo_chapa || 'N/A'}</td>
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
                grupo_maquina: grupoMaquina,
                status: 'finalizada',
                pecas_mortas: pecasMortas,
                qtdChapas: qtdChapas,
                operadorFinal: operadorFinal,
                obsFinal: obsFinal
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
            
            document.getElementById('ordens-container')='';
            resetarCardsInicial();
                        
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

            document.getElementById('ordens-container')='';
            resetarCardsInicial();

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

function resetarCardsInicial(filtros = {}) {
    const container = document.getElementById('ordens-container');
    const loadMoreButton = document.getElementById('loadMore');
    let page = 1; // Página inicial
    const limit = 10; // Quantidade de ordens por página
    let isLoading = false; // Flag para evitar chamadas simultâneas
    let hasMoreData = true; // Flag para interromper chamadas quando não houver mais dados

    // Atualiza os filtros com os valores enviados
    const filtroOrdem = document.getElementById('filtro-ordem');
    const filtroMaquina = document.getElementById('filtro-maquina');

    const currentFiltros = {
        ordem: filtros.ordem || filtroOrdem.value.trim(),
        maquina: filtros.maquina || filtroMaquina.value.trim(),
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

document.addEventListener('DOMContentLoaded', () => {

    resetarCardsInicial(); 

    const containerIniciado = document.querySelector('.containerProcesso');
    carregarOrdensIniciadas(containerIniciado);

    const containerInterrompido = document.querySelector('.containerInterrompido');
    carregarOrdensInterrompidas(containerInterrompido);

});