export const loadOrdens = (container, page = 1, limit = 10, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => { // Retorna uma Promise
        if (isLoading) return resolve({ ordens: [] }); // Evita chamadas duplicadas
        isLoading = true;

        fetch(`api/ordens-criadas/?page=${page}&limit=${limit}&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&status=${filtros.status || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;

                if (ordens.length > 0) {

                    ordens.forEach(ordem => {
                        const card = document.createElement('div');
                        card.classList.add('col-md-4'); // Adiciona a classe de coluna

                        card.dataset.ordemId = ordem.ordem; // Adiciona o ID da ordem para referência
                        card.dataset.grupoPeca = ordem.grupo_peca || ''; // Adiciona o grupo máquina
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
                                    <a href="https://drive.google.com/drive/u/0/search?q=${ordem.peca.codigo}" target="_blank" rel="noopener noreferrer">
                                        ${ordem.peca.codigo} - ${truncateText(ordem.peca.descricao, 10)}
                                    </a>
                                    ${statusBadge}
                                </h5>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">#${ordem.ordem} Criado em: ${ordem.data_criacao}</p>
                                <p class="mb-2">${ordem.obs || '<span class="text-muted">Sem observações</span>'}</p>
                            </div>
                            <div class="card-footer text-end" style="background-color: #f8f9fa; border-top: 1px solid #dee2e6;">
                                ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                            </div>
                        </div>`;
                        
                        // Seleciona os botões dinamicamente
                        const buttonIniciar = card.querySelector('.btn-iniciar');
                        const buttonInterromper = card.querySelector('.btn-interromper');
                        const buttonFinalizar = card.querySelector('.btn-finalizar');
                        const buttonRetornar = card.querySelector('.btn-retornar');

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

function truncateText(text, maxLength) {
    if (text.length > maxLength) {
        return text.substring(0, maxLength) + '...';
    }
    return text;
}

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
                        <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Observação:</strong> ${ordem.obs || 'Sem observações'}
                        </p>
                        <p class="card-text mb-0 small">
                            <a href="https://drive.google.com/drive/u/0/search?q=${ordem.peca.codigo}" target="_blank" rel="noopener noreferrer">
                                ${ordem.peca.codigo} - ${ordem.peca.descricao}
                            </a>
                        </p>
                    </div>

                    <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                        <div class="d-flex gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                const buttonInterromper = card.querySelector('.btn-interromper');
                const buttonFinalizar = card.querySelector('.btn-finalizar');

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
                // Cria o card
                const card = document.createElement('div');
                card.dataset.ordemId = ordem.ordem;
            
                // Cria a lista de peças em formato simplificado
                const pecasHTML = ordem.pecas.map(peca => `
                    <a href="https://drive.google.com/drive/u/0/search?q=${peca.codigo}" target="_blank" rel="noopener noreferrer">
                        ${peca.codigo} - ${peca.descricao}
                    </a>
                `).join('<br>');
            
                // Botões de ação
                const botaoAcao = `
                    <button class="btn btn-warning btn-sm btn-retornar me-2" title="Retornar">
                        <i class="fa fa-undo"></i>
                    </button>
                `;
            
                // Estrutura do card com fonte menor
                card.innerHTML = `
                    <div class="card shadow-sm border-0" style="border-radius: 10px; overflow: hidden;">
                        <div class="card-header bg-danger text-white">
                            <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                            <small class="text-white">Motivo: ${ordem.motivo_interrupcao || 'Sem motivo'}</small>
                        </div>
                        <div class="card-body bg-light">
                            <p class="card-text mb-2 small">
                                <strong>Observação:</strong> ${ordem.obs || 'N/A'}
                            </p>
                            <p class="card-text mb-2 small">
                                ${pecasHTML}
                            </p>
                        </div>
                        <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                            <div class="d-flex gap-2">
                                ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                            </div>
                        </div>
                    </div>`;
            
                // Adiciona eventos aos botões
                const buttonRetornar = card.querySelector('.btn-retornar');
                if (buttonRetornar) {
                    buttonRetornar.addEventListener('click', () => {
                        mostrarModalRetornar(ordem.ordem, ordem.grupo_maquina);
                    });
                }
            
                // Adiciona o card ao container
                container.appendChild(card);
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

    // Limpa opções antigas no select
    escolhaMaquina.innerHTML = `<option value="">------</option>`;

    // Define as máquinas para cada grupo
    const maquinasPorGrupo = {
        usinagem: [
            { value: 'furadeira_1', label: 'Furadeira 1'},
            { value: 'furadeira_2', label: 'Furadeira 2'},
            { value: 'furadeira_3', label: 'Furadeira 3'},
            { value: 'furadeira_4', label: 'Furadeira 4'},
            { value: 'furadeira_5', label: 'Furadeira 5'},
            { value: 'furadeira_6', label: 'Furadeira 6'},
            { value: 'furadeira_7', label: 'Furadeira 7'},
            { value: 'centro_de_usinagem', label: 'Centro de usinagem' },
            { value: 'torno_1', label: 'Torno 1' },
            { value: 'torno_2', label: 'Torno 2' },
            { value: 'chanfradeira', label: 'Chanfradeira' },
        ]
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

function mostrarModalFinalizar(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalFinalizar'));
    const modalTitle = document.getElementById('modalFinalizarLabel');
    const formFinalizar = document.getElementById('formFinalizarOrdemUsinagem');

    // Remove event listeners antigos para evitar duplicidade
    const clonedForm = formFinalizar.cloneNode(true);
    formFinalizar.parentNode.replaceChild(clonedForm, formFinalizar);

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

    // Fetch para buscar informações da ordem
    fetch(`api/ordens-criadas/${ordemId}/${grupoMaquina.toLowerCase()}/pecas/`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao buscar informações da API');
            }
            return response.json();
        })
        .then(data => {
            Swal.close(); // Fecha o SweetAlert de carregamento
            document.getElementById('bodyPecasFinalizar').innerHTML = `
            <div class="row mb-3">
                <div class="col-sm-6">
                    <label for="qtRealizada">Qt. peças boas</label>
                    <input type="number" id="qtRealizada" name="qtRealizada" min=1 class="form-control" required>
                </div>    
                <div class="col-sm-6">
                    <label for="qtMortas">Qt. mortas</label>
                    <input type="number" id="qtMortas" name="qtMortas" min=0 class="form-control">
                </div>    
            </div> 
            `;

            // Exibe o modal
            modal.show();

            // Adiciona o evento de submissão no formulário clonado
            clonedForm.addEventListener('submit', (event) => {
                event.preventDefault();

                // Validação do formulário
                if (!clonedForm.checkValidity()) {
                    clonedForm.reportValidity(); // Exibe mensagens de erro padrão
                    return;
                }

                Swal.fire({
                    title: 'Finalizando...',
                    text: 'Por favor, aguarde...',
                    allowOutsideClick: false,
                    didOpen: () => {
                        Swal.showLoading();
                    }
                });

                const qtRealizada = document.getElementById('qtRealizada').value;
                const qtMortas = document.getElementById('qtMortas').value || 0;
                const operadorFinal = document.getElementById('operadorFinalizar').value;
                const obsFinalizar = document.getElementById('obsFinalizar').value;

                // Faz o fetch para finalizar a ordem
                fetch(`api/ordens/atualizar-status/`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        ordem_id: ordemId,
                        grupo_maquina: grupoMaquina,
                        status: 'finalizada',
                        qt_realizada: qtRealizada,
                        qt_mortas: qtMortas,
                        operador_final: operadorFinal,
                        obs_finalizar: obsFinalizar
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
        })
        .catch(error => {
            Swal.close(); // Fecha o SweetAlert de carregamento
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: 'Erro ao buscar as informações da ordem.',
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

function configurarFormulario() {
    const form = document.getElementById('opUsinagemForm');

    if (form) {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const formData = new FormData(form);

            Swal.fire({
                title: 'Enviando...',
                text: 'Aguarde enquanto processamos sua solicitação.',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                },
            });

            try {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
                const response = await fetch('api/criar-ordem-usinagem/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                    },
                    body: formData,
                });

                const data = await response.json();

                Swal.close();

                if (response.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Sucesso!',
                        text: 'Ordem de Produção criada com sucesso.',
                        confirmButtonText: 'OK',
                    });

                    form.reset();

                    // Recarrega os cards
                    document.getElementById('ordens-container').innerHTML = '';
                    resetarCardsInicial();

                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Erro!',
                        text: data.error || 'Erro ao criar a Ordem de Produção.',
                        confirmButtonText: 'OK',
                    });
                }
            } catch (error) {
                Swal.close();
                Swal.fire({
                    icon: 'error',
                    title: 'Erro inesperado!',
                    text: 'Ocorreu um erro ao processar sua solicitação. Tente novamente.',
                    confirmButtonText: 'OK',
                });
                console.error('Erro:', error);
            }
        });
    }
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
    const filtroPeca = document.getElementById('filtro-peca');
    const filtroStatus = document.getElementById('filtro-status');

    const currentFiltros = {
        ordem: filtros.ordem || filtroOrdem.value.trim(),
        peca: filtros.peca || filtroPeca.value.trim(),
        status: filtros.status || filtroStatus.value.trim(),
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

function filtro() {
    const form = document.getElementById('filtro-form');

    form.addEventListener('submit', (event) => {
        event.preventDefault(); // Evita comportamento padrão do formulário

        // Captura os valores atualizados dos filtros
        const filtros = {
            ordem: document.getElementById('filtro-ordem').value.trim(),
            peca: document.getElementById('filtro-peca').value.trim(),
            status: document.getElementById('filtro-status').value.trim(),
        };

        // Recarrega os resultados com os novos filtros
        resetarCardsInicial(filtros);
    });
}

document.addEventListener('DOMContentLoaded', () => {

    resetarCardsInicial();
    configurarFormulario();
    
    $('#pecaSelect').select2({
        placeholder: 'Selecione a peça',
        ajax: {
            url: 'api/get-pecas/',
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
        dropdownParent: $('#modalUsinagem'),
    });

    const containerIniciado = document.querySelector('.containerProcesso');
    carregarOrdensIniciadas(containerIniciado);

    const containerInterrompido = document.querySelector('.containerInterrompido');
    carregarOrdensInterrompidas(containerInterrompido);

    filtro();

});