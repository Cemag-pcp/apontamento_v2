export const loadOrdens = (container, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => {
        if (isLoading) return resolve({ ordens: [] });
        isLoading = true;

        document.getElementById('data-entrega-info').textContent = '[carregando...]';

        fetch(`api/ordens-criadas/?data_carga=${filtros.data_carga}&setor=${filtros.setor || ''}&data-programada=${filtros.data_programada || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;
                container.innerHTML = ""; // Limpa antes de inserir novas ordens

                const filtroSetorInput = document.getElementById("filtro-setor");
                const setorContainer = document.getElementById("setor-container");
                setorContainer.innerHTML = ""; // Limpa os botões antes de popular

                if (ordens.length > 0) {
                    // Criar cabeçalho da tabela
                    const tableWrapper = document.createElement("div");
                    tableWrapper.classList.add("table-container");
    
                    const table = document.createElement('table');
                    table.classList.add('table', 'table-bordered', 'table-striped', 'header-fixed', 'responsive-table');

                    table.innerHTML = `
                        <thead class="table-light">
                            <tr>
                                <th style="width: 15%;">Código Conjunto</th>
                                <th style="width: 10%;">Status</th>
                                <th style="width: 10%;">Qtd. a Fazer</th>
                                <th style="width: 10%;">Qtd. Feita</th>
                                <th style="width: 10%;">Ação</th>
                            </tr>
                        </thead>
                        <tbody id="tabela-ordens-corpo"></tbody>
                    `;

                    tableWrapper.appendChild(table);
                    container.appendChild(tableWrapper);

                    const tabelaCorpo = document.getElementById('tabela-ordens-corpo');
                    ordens.forEach(ordem => {
                        const linha = document.createElement('tr');
                        linha.dataset.ordemId = ordem.ordem;
                        
                        let badgeClass = "";
                        switch (ordem.ordem__status_atual) {
                            case "aguardando_iniciar":
                                badgeClass = "badge bg-warning text-dark"; // Amarelo
                                break;
                            case "finalizada":
                                badgeClass = "badge bg-success"; // Verde
                                break;
                            case "iniciada":
                                badgeClass = "badge bg-primary"; // Azul
                                break;
                            case "interrompida":
                                badgeClass = "badge bg-danger"; // Vermelho
                                break;
                            default:
                                badgeClass = "badge bg-secondary"; // Cinza para status desconhecidos
                        }

                        linha.innerHTML = `
                            <td data-label="Código Conjunto">
                                <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(ordem.peca[0])}" 
                                target="_blank" rel="noopener noreferrer">
                                ${truncateText(ordem.peca, 100)}
                                </a>
                            </td>
                            <td data-label="Status"><span class="${badgeClass}">${ordem.ordem__status_atual.replace("_", " ")}</span></td>
                            <td data-label="Qtd. a Fazer">${ordem.restante}</td>
                            <td data-label="Qtd. Feita">${ordem.total_boa}</td>
                            <td data-label="Ação"><button class="btn btn-sm btn-primary btn-start">Iniciar</button></td>
                        `;

                        tabelaCorpo.appendChild(linha);
                    });

                    resolve(data);
                } else {
                    container.innerHTML = '<p class="text-danger">Nenhuma ordem encontrada.</p>';
                    resolve(data);
                }

                if (data.maquinas.length === 0) {
                    setorContainer.innerHTML = '<p class="text-muted">Nenhuma máquina encontrada</p>';
                    return;
                }
    
                data.maquinas.forEach(maquina => {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.classList.add("btn", "btn-outline-primary", "setor-btn");
                    button.dataset.setor = maquina.maquina__id;
                    button.textContent = maquina.maquina__nome;
    
                    // Evento de clique para selecionar o setor
                    button.addEventListener("click", function () {
                        // Remover seleção de outros botões
                        document.querySelectorAll(".setor-btn").forEach(btn => {
                            btn.classList.remove("btn-primary");
                            btn.classList.add("btn-outline-primary");
                        });
    
                        // Adicionar a seleção ao botão clicado
                        this.classList.remove("btn-outline-primary");
                        this.classList.add("btn-primary");
    
                        // Definir valor do setor no campo oculto
                        filtroSetorInput.value = this.dataset.setor;
                    });
    
                    setorContainer.appendChild(button);
                });

                document.getElementById('data-entrega-info').textContent = data.data_programacao;
                document.getElementById('filtro-data-carga').textContent = data.data_carga;

            })
            .catch(error => {
                console.error('Erro ao buscar ordens:', error);
                container.innerHTML = '<p class="text-danger">Erro ao carregar as ordens.</p>';
                reject(error);
            })
            .finally(() => {
                isLoading = false; // Libera a flag em qualquer caso
            });
    });
};

let currentOrdemId = null;

function truncateText(text, maxLength) {
    return text.length > maxLength ? text.slice(0, maxLength) + '...' : text;
}

// Usando delegação de eventos para capturar o clique no botão "Iniciar"
document.addEventListener('click', function(e) {
    if (e.target && e.target.classList.contains('btn-start')) {
        const linha = e.target.closest('tr');

        if (!linha) {
            console.error("Linha da tabela não encontrada.");
            return;
        }

        currentOrdemId = linha.getAttribute('data-ordem-id');

        if (!currentOrdemId) {
            console.error("Ordem ID não encontrada na linha.");
            return;
        }

        console.log("Ordem selecionada:", currentOrdemId);

        // Obtém o modal corretamente
        const modalElement = document.getElementById('confirmModal');

        // Remove manualmente o aria-hidden antes de exibir o modal
        modalElement.removeAttribute("aria-hidden");

        // Exibe o modal corretamente
        const confirmModal = new bootstrap.Modal(modalElement);
        confirmModal.show();
    }
});

document.getElementById('confirmStartButton').addEventListener('click', function() {
    Swal.fire({
        title: 'Verificando quantidade pendente...',
        text: 'Aguarde enquanto verificamos se a ordem pode ser iniciada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        },
    });

    // Primeiro, verificar se a ordem tem quantidade pendente
    fetch(`api/verificar-qt-restante/?ordem_id=${currentOrdemId}`)
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        Swal.close(); // Fecha o loading

        if (data.ordens.length === 0) {
            throw new Error("Ordem não encontrada.");
        }

        const ordem = data.ordens[0]; // Pegamos a primeira ordem retornada
        if (ordem.restante === 0.0) {
            throw new Error("Essa ordem já foi totalmente produzida. Não é possível iniciá-la novamente.");
        }

        // Se chegou até aqui, pode iniciar a ordem
        iniciarOrdem(currentOrdemId);
    })
    .catch(error => {
        console.error('Erro ao verificar quantidade pendente:', error);

        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Não foi possível verificar a quantidade pendente. Tente novamente.',
        });
    });
});

function iniciarOrdem(ordemId) {
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };
    
    Swal.fire({
        title: 'Iniciando...',
        text: 'Por favor, aguarde enquanto a ordem está sendo iniciada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        },
    });

    fetch("api/ordens/atualizar-status/", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            status: "iniciada",
            ordem_id: ordemId
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        Swal.close(); // Fecha o loading

        // Fecha o modal de confirmação
        const modalElement = document.getElementById('confirmModal');
        const confirmModal = bootstrap.Modal.getInstance(modalElement);
        confirmModal.hide();

        // Mostra mensagem de sucesso
        Swal.fire({
            icon: 'success',
            title: 'Sucesso!',
            text: 'A ordem foi iniciada com sucesso.'
        }).then(() => {
            resetarCardsInicial(filtros);
            carregarOrdensIniciadas(filtros);
        });

    })
    .catch(error => {
        console.error('Erro ao iniciar a ordem:', error);

        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Ocorreu um erro ao tentar iniciar a ordem. Tente novamente.',
        });
    });
}

export function carregarOrdensIniciadas(filtros = {}) {
    const container = document.querySelector('.containerProcesso');
    container.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;

    fetch(`api/ordens-iniciadas/?setor=${filtros.setor || ''}`)
        .then(response => response.json())
        .then(data => {
            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {
                const card = document.createElement('div');
                card.dataset.ordemId = ordem.ordem_id;
                
                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

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

                card.innerHTML = `
                <div class="card shadow-lg border-0 rounded-3 mb-3 position-relative">
                    <!-- Contador fixado no topo direito -->
                    <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                        id="contador-${ordem.ordem_id}" 
                        style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                        Carregando...
                    </span>
    
                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title mb-0">#${ordem.ordem_id} - ${ordem.maquina}</h6>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Data da carga:</strong> ${ordem.data_carga}
                        </p>
                        <p class="card-text mb-2 small">
                            <strong>Qt. restante:</strong> ${ordem.qtd_restante}
                        </p>
                        <p class="card-text mb-0 small">
                            <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(ordem.pecas[0])}" target="_blank" rel="noopener noreferrer">
                                ${ordem.pecas}
                            </a>
                        </p>
                    </div>

                    <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                        <div class="d-flex flex-wrap justify-content-center gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                const buttonInterromper = card.querySelector('.btn-interromper');
                const buttonFinalizar = card.querySelector('.btn-finalizar');
                const buttonDeletar = card.querySelector('.btn-deletar');

                // Adiciona evento ao botão "Interromper", se existir
                if (buttonInterromper) {
                    buttonInterromper.addEventListener('click', () => {
                        mostrarModalInterromper(ordem.ordem_id, ordem.pecas, ordem.maquina_id, ordem.data_carga);
                    });
                }

                // Adiciona evento ao botão "Finalizar", se existir
                if (buttonFinalizar) {
                    buttonFinalizar.addEventListener('click', () => {
                        mostrarModalFinalizar(ordem.ordem_id, ordem.maquina, ordem.qtd_restante);
                    });
                }

                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', function() {
                        mostrarModalRetornarOrdemIniciada(ordem.ordem_id);
                    });
                }

                container.appendChild(card);

                iniciarContador(ordem.ordem_id, ordem.ultima_atualizacao)

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
};

export function carregarOrdensInterrompidas(filtros = {}) {
    const container = document.querySelector('.containerInterrompido');
    container.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;

    // Fetch para buscar ordens interrompidas
    fetch(`api/ordens-interrompidas/?setor=${filtros.setor || ''}`)
    .then(response => response.json())
    .then(data => {
        container.innerHTML = ''; // Limpa o container

        data.ordens.forEach(ordem => {
            const card = document.createElement('div');
            card.dataset.ordemId = ordem.ordem_id;

            // Defina os botões dinamicamente com base no status
            let botaoAcao = `
                ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor'
                ? `<button class="btn btn-danger btn-sm btn-deletar m-2" data-ordem="${ordem.id}" title="Desfazer">
                        <i class="bi bi-arrow-left-right"></i>
                    </button>`: ""}
                <button class="btn btn-warning btn-sm btn-retornar m-2" title="Retornar">
                    <i class="fa fa-undo"></i>
                </button>
            `;

            // Verifica se há processos e formata as informações
            let processosInfo = "<p class='text-muted small mb-0'>Nenhum processo registrado</p>";
            if (ordem.processos && ordem.processos.length > 0) {
                processosInfo = ordem.processos.map(processo => `
                    <div class="border p-2 rounded bg-white mb-2">
                        <p class="mb-1"><strong>Motivo:</strong> ${processo.motivo_interrupcao || 'N/A'}</p>
                    </div>
                `).join("");
            }

            // Formata as peças faltantes
            let pecasFaltantesInfo = "";
            if (ordem.pecas_faltantes && ordem.pecas_faltantes.length > 0) {
                pecasFaltantesInfo = `
                    <div class="mt-3 mb-2">
                        <h6 class="text-danger mb-2">
                            <i class="bi bi-exclamation-triangle-fill me-1"></i>
                            Peças Faltantes:
                        </h6>
                        <div class="list-group">
                            ${ordem.pecas_faltantes.map(peca => {
                                const pecaJsonString = JSON.stringify(peca).replace(/"/g, '&quot;');

                                return `
                                    <div 
                                        class="list-group-item list-group-item-danger p-2 mb-1 click-peca-faltante"
                                        data-peca-info="${pecaJsonString}" 
                                        style="cursor: pointer;"
                                    >
                                        <div class="d-flex flex-wrap justify-content-between align-items-center">
                                            <span class="fw-bold text-truncate" style="font-size:13px; max-width: 70%;">${peca.nome_peca}</span>
                                            <span class="badge bg-danger rounded-pill">Qtd: ${peca.quantidade}</span>
                                        </div>
                                        <small class="text-muted d-block mt-1">
                                            Registrado em: ${new Date(peca.data_registro).toLocaleDateString('pt-BR')}
                                        </small>
                                    </div>
                                `;
                            }).join("")}
                        </div>
                    </div>
                `;
            }

            card.innerHTML = `
            <div class="card shadow-lg border-0 rounded-3 mb-3 position-relative">
                <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                    id="contador-${ordem.ordem_id}" 
                    style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                    Carregando...
                </span>

                <div class="card-header bg-danger text-white d-flex justify-content-between align-items-center p-3">
                    <h6 class="card-title mb-0">#${ordem.ordem_id} - ${ordem.maquina}</h6>
                </div>
                <div class="card-body bg-light">
                    <p class="card-text mb-2 small">
                        <strong>Data da carga:</strong> ${ordem.data_carga}
                    </p>
                    <p class="card-text mb-2 small">
                        <strong>Qt. restante:</strong> ${ordem.qtd_restante}
                    </p>
                    <p class="card-text mb-2 small">
                        <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(ordem.pecas[0])}" target="_blank" rel="noopener noreferrer">
                            ${ordem.pecas}
                        </a>
                    </p>

                    ${pecasFaltantesInfo}

                    <div class="mt-3">
                        ${processosInfo}
                    </div>
                </div>

                <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                    <div class="d-flex flex-wrap justify-content-center gap-2">
                        ${botaoAcao} </div>
                </div>
            </div>`;

            const pecaCards = card.querySelectorAll('.click-peca-faltante');
            
            // 2. Adiciona o Event Listener para CADA item
            pecaCards.forEach(pecaCard => {
                pecaCard.addEventListener('click', () => {
                    const pecaDataString = pecaCard.dataset.pecaInfo.replace(/&quot;/g, '"');
                    try {
                        const peca = JSON.parse(pecaDataString);
                        mostrarDetalhesPeca(peca); 
                    } catch (e) {
                        console.error('Erro ao fazer parse dos dados da peça:', e);
                    }
                });
            });

            const buttonRetornar = card.querySelector('.btn-retornar');
            const buttonDeletar = card.querySelector('.btn-deletar');

            if (buttonRetornar) {
                buttonRetornar.addEventListener('click', () => {
                    mostrarModalRetornar(ordem.ordem_id);
                });
            }

            if (buttonDeletar) {
                buttonDeletar.addEventListener('click', function() {
                    mostrarModalRetornarOrdemIniciada(ordem.ordem_id);
                });
            }

            container.appendChild(card);

            iniciarContador(ordem.ordem_id, ordem.ultima_atualizacao);
        });
    })
    .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
};

function mostrarDetalhesPeca(peca) {
    // 1. Preenche os campos do Modal
    document.getElementById('modalPecaNome').textContent = peca.nome_peca || 'N/A';
    document.getElementById('modalPecaQuantidade').textContent = peca.quantidade || 0;
    document.getElementById('modalPecaDataRegistro').textContent = new Date(peca.data_registro).toLocaleString('pt-BR');

    // 2. Abre o Modal (Requer a biblioteca JS do Bootstrap)
    const modalElement = document.getElementById('modalDetalhesPeca');
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

// Modal para "Interromper"
function mostrarModalInterromper(ordemId, codigoConjunto, maquinaId, dataCarga) {
    const modal = new bootstrap.Modal(document.getElementById('modalInterromper'));
    const modalTitle = document.getElementById('modalInterromperLabel');
    const motivoInterrupcaoSelect = $('#motivoInterrupcao'); // AGORA É JQUERY
    const pecasDisponiveisSelect = $('#pecasDisponiveis'); // Usando jQuery para Select2
    const selectPecasContainer = $('#selectPecasContainer');
    const confirmInterromperButton = $('#confirmInterromper');

    // Define o título do modal
    modalTitle.innerHTML = `Interromper Ordem ${ordemId}`;
    modal.show();

    // Limpa e desativa o select antes de carregar os dados
    motivoInterrupcaoSelect.html(`<option value="" disabled selected>Carregando...</option>`).prop('disabled', true);
    selectPecasContainer.hide(); // Esconde o select de peças por padrão

    // Buscar motivos de interrupção
    fetch("api/listar-motivos-interrupcao/")
        .then(response => response.json())
        .then(data => {
            motivoInterrupcaoSelect.html(`<option value="" disabled selected>Selecione um motivo...</option>`);

            if (data.motivos.length === 0) {
                motivoInterrupcaoSelect.append(`<option value="" disabled>Nenhum motivo encontrado</option>`);
            } else {
                data.motivos.forEach(motivo => {
                    motivoInterrupcaoSelect.append(`<option value="${motivo.id}">${motivo.nome}</option>`);
                });
                motivoInterrupcaoSelect.prop('disabled', false); // Habilita o select após carregar os dados
            }
        })
        .catch(error => {
            console.error("Erro ao carregar motivos:", error);
            motivoInterrupcaoSelect.html(`<option value="" disabled>Erro ao carregar</option>`);
        });

    // **Correção: Remover eventos duplicados antes de adicionar**
    motivoInterrupcaoSelect.off("change").on("change", function () {
        const motivoSelecionado = motivoInterrupcaoSelect.find(":selected").text();

        if (motivoSelecionado === "Falta peça") {
            selectPecasContainer.show(); // Exibe o campo de peças
            carregarPecasDisponiveis(codigoConjunto); // Chama apenas uma vez
        } else {
            selectPecasContainer.hide();
            pecasDisponiveisSelect.empty(); // Limpa as opções anteriores
        }
    });

    // **Correção: Remover evento antigo antes de adicionar um novo para evitar múltiplas submissões**
    confirmInterromperButton.off("click").on("click", function () {
        finalizarInterrupcao(ordemId, motivoInterrupcaoSelect, pecasDisponiveisSelect, modal, maquinaId, dataCarga);
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
            
            const response = await fetch('api/retornar-processo/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
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

// Função para carregar peças disponíveis para a ordem selecionada
function carregarPecasDisponiveis(codigoConjunto) {
    const pecasDisponiveisSelect = $('#pecasDisponiveis');
    const confirmInterromperButton = $('#confirmInterromper');
    // NOVO: Pegando o select do motivo
    const motivoInterrupcaoSelect = $('#motivoInterrupcao'); 
    
    // Elementos do carregamento
    const loadingPecasDiv = $('#loadingPecas');
    const selectPecasContainer = $('#selectPecasContainer');

    // 1. ANTES DA REQUISIÇÃO
    confirmInterromperButton.prop('disabled', true);
    motivoInterrupcaoSelect.prop('disabled', true); // DESABILITA o select do motivo
    
    selectPecasContainer.hide();
    pecasDisponiveisSelect.empty();
    loadingPecasDiv.show(); // MOSTRA O SPINNER

    fetch(`api/listar-pecas-disponiveis/?conjunto=${codigoConjunto}`)
    .then(response => response.json())
    .then(data => {

        if (data.pecas.length !== 0) {
            data.pecas.forEach((peca, index)=> {
                pecasDisponiveisSelect.append(new Option(`${peca['CODIGO']} - ${peca['DESCRIÇÃO']}`, peca['CODIGO'], false, false));
            });
        }

        // Destroi e recria o select2
        if (pecasDisponiveisSelect.hasClass('select2-hidden-accessible')) {
            pecasDisponiveisSelect.select2('destroy');
        }

        pecasDisponiveisSelect
        .select2({
            placeholder: 'Selecione uma peça',
            allowClear: true,
            dropdownParent: $('#modalInterromper')
        })
        .off('select2:select.gerarQtd select2:clear.gerarQtd change.gerarQtd')
        .on('select2:select.gerarQtd select2:clear.gerarQtd change.gerarQtd', gerarInputsQuantidade);

        pecasDisponiveisSelect.val(null).trigger('change');
    })
    .catch(error => {
        console.error("Erro ao carregar peças disponíveis:", error);
        
        // Lógica de erro do select2
        if (pecasDisponiveisSelect.hasClass('select2-hidden-accessible')) {
            pecasDisponiveisSelect.select2('destroy');
        }
        pecasDisponiveisSelect.select2({
            placeholder: 'Não possui peças disponíveis na base referente a esse conjunto',
            allowClear: true,
            dropdownParent: $('#modalInterromper')
        });
        pecasDisponiveisSelect.val(null).trigger('change');
    })
    .finally(() => {
        // 2. APÓS A REQUISIÇÃO (sucesso ou erro)
        loadingPecasDiv.hide(); // ESCONDE O SPINNER
        selectPecasContainer.show(); // Mostra o select container
        
        confirmInterromperButton.prop('disabled', false); // Reabilita o botão
        motivoInterrupcaoSelect.prop('disabled', false); // REABILITA o select do motivo
    });
}

$(document).ready(function() {
    $('#modalInterromper').on('hidden.bs.modal', function () {
        $('#pecasQuantidadeContainer').empty(); 
        
        $('#motivoInterrupcao').val('').trigger('change');
        
        $('#pecasDisponiveis').val(null).trigger('change');
        $('#selectPecasContainer').hide();

    });
});

function gerarInputsQuantidade() {
    const pecasSelecionadas = $('#pecasDisponiveis').find(':selected');
    const container = $('#pecasQuantidadeContainer');
    container.empty(); // Limpa a área antes de gerar novos inputs

    if (pecasSelecionadas.length === 0) {
        return; // Não faz nada se nenhuma peça estiver selecionada
    }

    // Título da seção
    container.append('<h6 class="mt-3">Informe a Quantidade em Falta:</h6>');

    pecasSelecionadas.each(function() {
        const codigo = $(this).val(); // O CÓDIGO da peça
        const descricao = $(this).text(); // A DESCRIÇÃO da peça
        
        // Cria um elemento de input (usando Bootstrap form-group)
        const inputGroup = `
            <hr>
            <div class="mb-3 px-3 pb-3">
                <label for="qtd-${codigo}" class="form-label fw-bold">
                    ${descricao}:
                </label>
                <input 
                    type="number" 
                    class="form-control" 
                    id="qtd-${codigo}" 
                    name="qtd-${codigo}" 
                    min="1" 
                    value="1"
                    required
                    data-peca-codigo="${codigo}"
                    data-peca-descricao="${descricao}"
                >
            </div>
        `;
        container.append(inputGroup);
    });
}

// Função para finalizar interrupção e enviar para API
function finalizarInterrupcao(ordemId, motivoInterrupcaoSelect, pecasDisponiveisSelect, modal, maquinaId, dataCarga) {
    const motivoSelecionado = motivoInterrupcaoSelect.val();
    // Usamos 'find(":selected").text()' para garantir que pegamos o texto que o backend usa para obs_operador
    const motivoTexto = motivoInterrupcaoSelect.find(":selected").text() ?? 'N/A';
    const filtros = {
        data_carga: document.getElementById('filtro-data-carga').value,
        setor: document.getElementById('filtro-setor').value
    };

    let pecasFaltantesPayload = [];

    // --- 1. Validação do Motivo ---
    if (!motivoSelecionado) {
        Swal.fire({
            icon: 'warning',
            title: 'Atenção',
            text: 'Selecione um motivo para interromper a ordem.'
        });
        return;
    }

    const pecasSelecionadas = pecasDisponiveisSelect.val(); // Array de códigos (ex: ["P001", "P002"])

    console.log(pecasSelecionadas);

    // --- 2. Lógica e Coleta para "Falta peça" ---
    if (motivoTexto === "Falta peça" && Array.isArray(pecasSelecionadas) && pecasSelecionadas.length > 0) {

        pecasSelecionadas.forEach(codigoPeca => {
            const optionElement = pecasDisponiveisSelect.find(`option[value="${codigoPeca}"]`).first();
            
            const nomePeca = optionElement.data('descricao') 
                ? `${codigoPeca} - ${optionElement.data('descricao')}` 
                : optionElement.text().trim();

            const inputQtd = $(`#qtd-${codigoPeca}`);
            let quantidade = parseInt(inputQtd.val() || '0');

            if (quantidade > 0) {
                pecasFaltantesPayload.push({
                    nome: nomePeca,
                    quantidade: quantidade
                });
            }
        });
        // Valida se, após a coleta, alguma quantidade > 0 foi informada
        if (pecasFaltantesPayload.length === 0) {
            Swal.fire({
                icon: 'warning',
                title: 'Atenção',
                text: 'Informe a quantidade em falta (maior que zero) para a(s) peça(s) selecionada(s).'
            });
            return;
        }
    }
    
    Swal.fire({
        title: 'Interrompendo...',
        text: 'Por favor, aguarde enquanto a ordem está sendo interrompida.',
        icon: 'info',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    const payload = {
        ordem_id: parseInt(ordemId),
        status: 'interrompida',
        motivo: parseInt(motivoSelecionado)
    };

    if (motivoTexto === "Falta peça") {
        payload.pecas_faltantes = pecasFaltantesPayload; 
        payload.maquina_id = parseInt(maquinaId);
        payload.data_carga = dataCarga;
    }

    fetch("api/ordens/atualizar-status/", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        Swal.fire({ icon: 'success', title: 'Sucesso', text: 'Ordem interrompida com sucesso.' })
        .then(() => {
            modal.hide();
            carregarOrdensIniciadas(filtros);
            carregarOrdensInterrompidas(filtros);
            fetchStatusMaquinas();
        });
    })
    .catch(error => {
        console.error("Erro ao interromper a ordem:", error);
        Swal.fire({ icon: 'error', title: 'Erro', text: 'Erro ao interromper. Tente novamente.' });
    });
}

// Modal para "Finalizar"
function mostrarModalFinalizar(ordemId, maquina, max_itens) {
    const modal = new bootstrap.Modal(document.getElementById('finalizarModal'));

    const operadorSelect = document.getElementById('operadorFinal');
    const qtRealizadaInput = document.getElementById('qtRealizada');
    const labelOperadores = document.getElementById('labelOperadores');

    const todosOperadorFinal = document.getElementById('todosOperadorFinal');
    const descricaoBotaoVoltar = document.getElementById('descricaoBotaoVoltar');
    const descricaoBotaoLista = document.getElementById('descricaoBotaoLista');

    operadorSelect.style.display = 'block';
    descricaoBotaoLista.style.display = 'block';

    todosOperadorFinal.style.display = 'none';
    descricaoBotaoVoltar.style.display = 'none';
    labelOperadores.textContent = `Operador - ${maquina}` 

    document.getElementById('ordemIdFinalizar').value = ordemId;

    operadorSelect.setAttribute('data-active', 'true');
    todosOperadorFinal.setAttribute('data-active', 'false');

    labelOperadores.setAttribute('data-maquina', maquina)
    qtRealizadaInput.setAttribute('max', max_itens);

    operadorSelect.innerHTML = `<option value="" disabled selected>Selecione um operador...</option>`
    todosOperadorFinal.innerHTML = `<option value="" disabled selected>Selecione um operador...</option>`

    fetch(`api/listar-operadores/?maquina=${maquina}`)
    .then(response => {
        if (!response.ok) {
            throw new Error("Erro ao buscar operadores");
        }
        return response.json();
    })
    .then(data => {
    
        if (data.operadores_maquina.length === 0) {
            operadorSelect.innerHTML = `<option value="" disabled>Nenhum operador encontrado</option>`;
        } else {
            data.operadores_maquina.forEach(operador => {
                operadorSelect.innerHTML += `<option value="${operador.id}">${operador.matricula} - ${operador.nome}</option>`;
            });
            operadorSelect.disabled = false; // Habilita o select após carregar os dados
        }

        if (data.operadores.length === 0) {
            todosOperadorFinal.innerHTML = `<option value="" disabled>Nenhum operador encontrado</option>`;
        } else {
            data.operadores.forEach(operador => {
                todosOperadorFinal.innerHTML += `<option value="${operador.id}">${operador.matricula} - ${operador.nome}</option>`;
            });
            todosOperadorFinal.disabled = false; // Habilita o select após carregar os dados
        }
    })
    .catch(error => {
        console.error("Erro ao carregar operadores:", error);
        operadorSelect.innerHTML = `<option value="" disabled>Erro ao carregar</option>`;
        todosOperadorFinal.innerHTML = `<option value="" disabled>Erro ao carregar</option>`;
    });
    
    modal.show();
}

document.getElementById('direcionarTodosOperadores').addEventListener('click', function () {
    const operadorFinal = document.getElementById('operadorFinal');
    const todosOperadorFinal = document.getElementById('todosOperadorFinal');
    const labelOperadores = document.getElementById('labelOperadores');

    const descricaoBotaoVoltar = document.getElementById('descricaoBotaoVoltar');
    const descricaoBotaoLista = document.getElementById('descricaoBotaoLista');
    
    labelOperadores.textContent = `Todos os Operadores` 

    operadorFinal.style.display = 'none';
    operadorFinal.setAttribute('data-active', 'false');
    todosOperadorFinal.style.display = 'block';
    todosOperadorFinal.setAttribute('data-active', 'true');

    descricaoBotaoVoltar.style.display = 'block';
    descricaoBotaoLista.style.display = 'none';
});

document.getElementById('botaoVoltarOperadoresMaquina').addEventListener('click', function () {
    const operadorFinal = document.getElementById('operadorFinal');
    const todosOperadorFinal = document.getElementById('todosOperadorFinal');
    const labelOperadores = document.getElementById('labelOperadores');

    const descricaoBotaoLista = document.getElementById('descricaoBotaoLista');
    const descricaoBotaoVoltar = document.getElementById('descricaoBotaoVoltar');

    const maquina = labelOperadores.getAttribute('data-maquina')
    labelOperadores.textContent = `Operadores - ${maquina}` 

    todosOperadorFinal.style.display = 'none';
    todosOperadorFinal.setAttribute('data-active', 'false');
    operadorFinal.style.display = 'block';
    operadorFinal.setAttribute('data-active', 'true');

    descricaoBotaoLista.style.display = 'block';
    descricaoBotaoVoltar.style.display = 'none';
});

// Finalizar ordem
document.getElementById('confirmFinalizar').addEventListener('click', function () {
    const ordemId = document.getElementById('ordemIdFinalizar').value;
    const operadorFinal = document.getElementById('operadorFinal');
    const todosOperadorFinal = document.getElementById('todosOperadorFinal');
    const qtRealizada = document.getElementById('qtRealizada');
    const obsFinalizar = document.getElementById('obsFinalizar').value;
    const qtMaxima = qtRealizada.getAttribute('max');
    
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };

    // Validação: A quantidade realizada não pode ser maior que a máxima
    if (parseInt(qtRealizada.value) > parseInt(qtMaxima)) {
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: 'A quantidade realizada não pode ser maior que a quantidade máxima permitida.'
        });
        return;
    }

    // Determinar qual select está ativo e obter o valor do operador
    let operadorId;
    if (operadorFinal.style.display !== 'none' && operadorFinal.getAttribute('data-active') === 'true') {
        if (!operadorFinal.value || operadorFinal.value === "") {
            Swal.fire({
                icon: 'warning',
                title: 'Atenção',
                text: 'Por favor, selecione um operador da máquina.'
            });
            return;
        }
        operadorId = operadorFinal.value;
    } else if (todosOperadorFinal.style.display !== 'none' && todosOperadorFinal.getAttribute('data-active') === 'true') {
        if (!todosOperadorFinal.value || todosOperadorFinal.value === "") {
            Swal.fire({
                icon: 'warning',
                title: 'Atenção',
                text: 'Por favor, selecione um operador da lista geral.'
            });
            return;
        }
        operadorId = todosOperadorFinal.value;
    } else {
        Swal.fire({
            icon: 'warning',
            title: 'Atenção',
            text: 'Por favor, selecione um operador válido.'
        });
        return;
    }

    // Validação: Quantidade realizada é obrigatória
    if (!qtRealizada.value) {
        Swal.fire({
            icon: 'warning',
            title: 'Atenção',
            text: 'Por favor, informe a quantidade realizada.'
        });
        return;
    }

    Swal.fire({
        title: 'Finalizando...',
        text: 'Por favor, aguarde enquanto a ordem está sendo finalizada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    const payload = {
        status: "finalizada",
        ordem_id: parseInt(ordemId),
        operador_final: parseInt(operadorId),
        obs_finalizar: obsFinalizar,
        qt_realizada: parseInt(qtRealizada.value)
    };

    fetch("api/ordens/atualizar-status/", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Erro ao finalizar a ordem.');
            });
        }
        return response.json();
    })
    .then(data => {
        carregarOrdensIniciadas(filtros);
        resetarCardsInicial(filtros);

        // Fechar o modal após a finalização bem-sucedida
        const modalElement = document.getElementById('finalizarModal');
        const finalizarModal = bootstrap.Modal.getInstance(modalElement);
        finalizarModal.hide();
        Swal.close();
    })
    .catch(error => {
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Erro ao finalizar a ordem. Tente novamente.'
        });
    });
});

// Finalizar parcial e continuar ordem
document.getElementById('confirmFinalizarEContinuar').addEventListener('click', function () {
    const ordemId = document.getElementById('ordemIdFinalizar').value;
    const operadorFinal = document.getElementById('operadorFinal');
    const todosOperadorFinal = document.getElementById('todosOperadorFinal');
    const qtRealizada = document.getElementById('qtRealizada');
    const obsFinalizar = document.getElementById('obsFinalizar').value;
    const qtMaxima = qtRealizada.getAttribute('max');
    const continua = 'true';

    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };

    // Validação: A quantidade realizada não pode ser maior que a máxima
    if (parseInt(qtRealizada.value) > parseInt(qtMaxima)) {
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: 'A quantidade realizada não pode ser maior que a quantidade máxima permitida.'
        });
        return;
    }

    // Determinar qual select está ativo e obter o valor do operador
    let operadorId;
    if (operadorFinal.style.display !== 'none' && operadorFinal.getAttribute('data-active') === 'true') {
        if (!operadorFinal.value || operadorFinal.value === "") {
            Swal.fire({
                icon: 'warning',
                title: 'Atenção',
                text: 'Por favor, selecione um operador da máquina.'
            });
            return;
        }
        operadorId = operadorFinal.value;
    } else if (todosOperadorFinal.style.display !== 'none' && todosOperadorFinal.getAttribute('data-active') === 'true') {
        if (!todosOperadorFinal.value || todosOperadorFinal.value === "") {
            Swal.fire({
                icon: 'warning',
                title: 'Atenção',
                text: 'Por favor, selecione um operador da lista geral.'
            });
            return;
        }
        operadorId = todosOperadorFinal.value;
    } else {
        Swal.fire({
            icon: 'warning',
            title: 'Atenção',
            text: 'Por favor, selecione um operador válido.'
        });
        return;
    }

    // Validação: Quantidade realizada é obrigatória
    if (!qtRealizada.value) {
        Swal.fire({
            icon: 'warning',
            title: 'Atenção',
            text: 'Por favor, informe a quantidade realizada.'
        });
        return;
    }

    Swal.fire({
        title: 'Finalizando...',
        text: 'Por favor, aguarde enquanto a ordem está sendo finalizada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    const payload = {
        status: "finalizada",
        ordem_id: parseInt(ordemId),
        operador_final: parseInt(operadorId),
        obs_finalizar: obsFinalizar,
        qt_realizada: parseInt(qtRealizada.value),
        continua: continua
    };

    fetch("api/ordens/atualizar-status/", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Erro ao finalizar a ordem.');
            });
        }
        return response.json();
    })
    .then(data => {
        carregarOrdensIniciadas(filtros);
        resetarCardsInicial(filtros);

        // Fechar o modal após a finalização bem-sucedida
        const modalElement = document.getElementById('finalizarModal');
        const finalizarModal = bootstrap.Modal.getInstance(modalElement);
        finalizarModal.hide();

        // fechar modal de confirmação
        const modalElementConfirmacao = document.getElementById('modalFinalizarParcial');
        const finalizarModalConfirmacao = bootstrap.Modal.getInstance(modalElementConfirmacao);
        finalizarModalConfirmacao.hide();

        Swal.close();
    })
    .catch(error => {
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Erro ao finalizar a ordem. Tente novamente.'
        });
    });
});

// Modal para "Retornar"
function mostrarModalRetornar(ordemId) {
    const modalElement = document.getElementById('confirmRetornoModal');
    const modal = new bootstrap.Modal(modalElement);
    const modalTitle = document.getElementById('confirmRetornoModalLabel');

    modalTitle.innerHTML = `Retornar Ordem`;
    modal.show();

    // Obtém o botão corretamente e substitui-o para evitar múltiplos eventos
    let confirmRetornoButton = document.getElementById('confirmRetornoButton');
    const novoBotao = confirmRetornoButton.cloneNode(true);
    confirmRetornoButton.replaceWith(novoBotao);

    // Adiciona evento de clique ao novo botão
    novoBotao.addEventListener('click', () => confirmarRetorno(ordemId, modal));
}

// Função para enviar requisição de retorno da ordem
function confirmarRetorno(ordemId, modal) {
    
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };

    Swal.fire({
        title: 'Retornando...',
        text: 'Por favor, aguarde enquanto a ordem está sendo retornada.',
        icon: 'info',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    fetch(`api/ordens/atualizar-status/`, {
        method: 'POST',
        body: JSON.stringify({
            ordem_id: ordemId,
            status: 'retorno',
        }),
        headers: {
            'Content-Type': 'application/json',
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
        }).then(() => {
            Swal.close();
            modal.hide(); // Fecha o modal corretamente após confirmação
            carregarOrdensInterrompidas(filtros);
            carregarOrdensIniciadas(filtros);
            resetarCardsInicial(filtros);
            fetchStatusMaquinas();
        });

    })
    .catch((error) => {
        console.error('Erro:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message,
        });
    });
}

export function resetarCardsInicial(filtros = {}) {
    const container = document.getElementById('ordens-container');
    let isLoading = false; // Flag para evitar chamadas simultâneas

    // Obtém os filtros atualizados
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');
    const filtroDataProgramada = document.getElementById('filtro-data-programada');

    const currentFiltros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value,
        data_programada: filtroDataProgramada.value,
    };

    // Função para buscar e renderizar ordens sem paginação
    const fetchOrdens = () => {
        if (isLoading) return;
        isLoading = true;

        loadOrdens(container, currentFiltros) // Carrega todas as ordens de uma vez
            .then((data) => {
                if (data.ordens.length === 0) {
                    container.innerHTML = '<p class="text-muted">Nenhuma ordem encontrada.</p>';
                }
            })
            .catch((error) => {
                console.error('Erro ao carregar ordens:', error);
                container.innerHTML = '<p class="text-danger">Erro ao carregar as ordens.</p>';
            })
            .finally(() => {
                isLoading = false;
            });
    };

    // Limpa o container antes de carregar novos resultados e chama a função
    container.innerHTML = '';
    fetchOrdens();
}

export function filtro() {
    const form = document.getElementById('filtro-form');

    form.addEventListener('submit', (event) => {
        event.preventDefault(); // Evita comportamento padrão do formulário

        const filtroDataCarga = document.getElementById('filtro-data-carga');
        const filtroSetor = document.getElementById('filtro-setor');
        const filtroDataProgramada = document.getElementById('filtro-data-programada');

        // Captura os valores atualizados dos filtros
        const filtros = {
            data_carga: filtroDataCarga.value,
            setor: filtroSetor.value,
            data_programada: filtroDataProgramada.value,
        };

        // Recarrega os resultados com os novos filtros
        resetarCardsInicial(filtros);
        carregarOrdensIniciadas(filtros);
        carregarOrdensInterrompidas(filtros);
    });
}

// Função de contador para mostrar tempo decorrido
function iniciarContador(cambaoId, dataCriacao) {
    const contador = document.getElementById(`contador-${cambaoId}`);
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

function atualizarAndamentoCarga(dataCarga) {
    const percentualDisplay = document.getElementById("percentual-carga");

    percentualDisplay.innerHTML = `
    <div class="spinner-border text-dark" role="status">
        <span class="sr-only">Loading...</span>
    </div>`;

    fetch(`api/andamento-carga/?data_carga=${encodeURIComponent(dataCarga)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao buscar andamento da carga.");
            }
            return response.json();
        })
        .then(data => {
            const percentual = data.percentual_concluido || 0; // Se não houver dado, assume 0%

            // Adiciona efeito de transição suave ao atualizar o valor
            percentualDisplay.style.transition = "0.5s ease-in-out";
            percentualDisplay.textContent = `${percentual.toFixed(1)}%`; // Exibe 1 casa decimal
        })
        .catch(error => console.error("Erro no carregamento do andamento da carga:", error));
}

// Evento de mudança no select para atualizar automaticamente
document.getElementById("filtro-data-carga").addEventListener("change", function () {
    atualizarAndamentoCarga(this.value);
});

// Evento no botão 🔄 para atualização manual
document.getElementById("refresh-status-carga").addEventListener("click", function () {
    const dataCarga = document.getElementById("filtro-data-carga").value;
    if (dataCarga) {
        atualizarAndamentoCarga(dataCarga);
    }
})

function atualizarUltimasCargas() {
    const listaCargas = document.getElementById("ultimas-pecas-list");
    
    listaCargas.innerHTML = `
        <div class="spinner-border text-dark" role="status">
            <span class="sr-only">Loading...</span>
        </div>`;

    fetch("api/andamento-ultimas-cargas/")
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao buscar andamento das últimas cargas.");
            }
            return response.json();
        })
        .then(data => {
            listaCargas.innerHTML = ""; // Limpa antes de adicionar os novos

            if (data.andamento_cargas.length === 0) {
                listaCargas.innerHTML = `<li class="list-group-item text-muted text-center">Nenhuma carga recente.</li>`;
                return;
            }

            data.andamento_cargas.forEach(carga => {
                const li = document.createElement("li");
                li.classList.add("list-group-item", "d-flex", "justify-content-between", "align-items-center");

                // Criação de uma barra de progresso
                li.innerHTML = `
                <div class="d-flex justify-content-between align-items-center w-100">
                    <span>${carga.data_carga}</span>
                    <div class="progress w-50 position-relative">
                        <div class="progress-bar ${carga.percentual_concluido === 100 ? 'bg-success' : 'bg-warning'}" 
                            role="progressbar" 
                            style="width: ${carga.percentual_concluido}%;"
                            aria-valuenow="${carga.percentual_concluido}" 
                            aria-valuemin="0" 
                            aria-valuemax="100">
                        </div>
                        <span class="position-absolute w-100 text-center fw-bold"
                            style="top: 50%; transform: translateY(-50%); color: black;">
                            ${carga.percentual_concluido}%
                        </span>
                    </div>
                </div>
                `;

                listaCargas.appendChild(li);
            });
        })
        .catch(error => console.error("Erro ao carregar andamento das últimas cargas:", error));
}

// Evento no botão 🔄 para atualização manual
document.getElementById("refresh-pecas").addEventListener("click", atualizarUltimasCargas);

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

export function fetchStatusMaquinas() {
    // Seleciona os elementos do container
    const indicador = document.querySelector('.text-center.mb-3 .display-4');
    const descricao = document.querySelector('.text-center.mb-3 p');
    const listaStatus = document.querySelector('#machine-status-list');

    listaStatus.innerHTML = `
        <div class="spinner-border text-dark" role="status">
            <span class="sr-only">Loading...</span>
        </div>`;
    indicador.innerHTML = `
        <div class="spinner-border text-dark" role="status">
            <span class="sr-only">Loading...</span>
        </div>`;

    // Faz a requisição para a API
    fetch('/core/api/status_maquinas/?setor=montagem')
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

async function fetchMaquinasDisponiveis() {
    try {
        const response = await fetch('/core/api/buscar-maquinas-disponiveis/?setor=montagem');
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

//  Função separada para submissão do formulário de parar maquina
async function handleFormSubmit(event) {
    event.preventDefault();
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };
    Swal.fire({
        title: 'Parando...',
        text: 'Por favor, aguarde enquanto a máquina está sendo parada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    try {
        const response = await fetch(`/core/api/parar-maquina/?setor=montagem`, {
            method: 'PATCH',
            body: JSON.stringify({
                maquina: document.getElementById('escolhaMaquinaParada').value,
                motivo: document.getElementById('motivoParadaMaquina').value
            }),
            headers: {
                'Content-Type': 'application/json',
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

        fetchStatusMaquinas();
        resetarCardsInicial(filtros);
        carregarOrdensIniciadas(filtros);
        carregarOrdensInterrompidas(filtros);

    } catch (error) {
        console.error('Erro:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message,
        });
    }
}

function selecionarSetor() {
    const setorButtons = document.querySelectorAll(".setor-btn");
    const filtroSetorInput = document.getElementById("filtro-setor");
    const limparFiltroBtn = document.getElementById("limpar-filtro");
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };
    setorButtons.forEach(button => {
        button.addEventListener("click", function () {
            // Remove a seleção de todos os botões
            setorButtons.forEach(btn => {
                btn.classList.remove("btn-primary");
                btn.classList.add("btn-outline-primary");
            });

            // Ativa o botão clicado
            this.classList.remove("btn-outline-primary");
            this.classList.add("btn-primary");

            // Atualiza o input hidden
            filtroSetorInput.value = this.dataset.setor;
            console.log("Setor selecionado:", filtroSetorInput.value);
        });
    });

    // **Evento para limpar o filtro**
    limparFiltroBtn.addEventListener("click", function () {
        // Remove a seleção de todos os botões
        setorButtons.forEach(btn => {
            btn.classList.remove("btn-primary");
            btn.classList.add("btn-outline-primary");
        });

        // Resetar o campo oculto
        filtroSetorInput.value = "";

        resetarCardsInicial(filtros);
        carregarOrdensIniciadas(filtros);
        carregarOrdensInterrompidas(filtros);
        
    });
}

function salvarFiltros() {
    const filtroDataCarga = document.getElementById("filtro-data-carga");
    const filtroSetor = document.getElementById("filtro-setor");

    localStorage.setItem("filtroDataCarga", filtroDataCarga.value);
    localStorage.setItem("filtroSetor", filtroSetor.value);
}

function restaurarFiltros() {
    const filtroDataCarga = document.getElementById("filtro-data-carga");
    const filtroSetor = document.getElementById("filtro-setor");

    if (localStorage.getItem("filtroDataCarga")) {
        filtroDataCarga.value = localStorage.getItem("filtroDataCarga");
    }
    if (localStorage.getItem("filtroSetor")) {
        filtroSetor.value = localStorage.getItem("filtroSetor");
    }
}

function pegarCodigoPeca(peca){
    if (peca.includes("-")) {
        // Se a peça contém um hífen, divide a string e retorna a parte antes do hífen
        const partes = peca.split("-");
        return partes[0].trim(); // Retorna a parte antes do hífen
    }
    return peca; // Se não houver hífen, retorna a peça completa
}

document.addEventListener('DOMContentLoaded', () => {
    // Restaurar os filtros ao carregar a página
    restaurarFiltros();

    // Adiciona eventos de submissão e limpeza
    const form = document.getElementById("filtro-form");
    const btnLimpar = document.getElementById("limpar-filtro");

    form.addEventListener("submit", function () {
        salvarFiltros();
    });

    btnLimpar.addEventListener("click", function () {
        // localStorage.removeItem("filtroDataCarga");
        localStorage.removeItem("filtroSetor");

        // document.getElementById("filtro-data-carga").value = "";
        document.getElementById("filtro-setor").value = "";
    });

    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };

    // Outras funções do sistema
    resetarCardsInicial(filtros);
    carregarOrdensIniciadas(filtros);
    carregarOrdensInterrompidas(filtros);
    filtro();
    atualizarUltimasCargas();
    selecionarSetor();

    // Atualiza automaticamente ao carregar a página
    fetchStatusMaquinas();

    // Adiciona eventos para ações do usuário
    document.getElementById('refresh-status-maquinas').addEventListener('click', function () {
        console.log("Atualizando Status de Máquinas...");
        fetchStatusMaquinas();
    });

    document.getElementById('btnPararMaquina').addEventListener('click', () => {
        mostrarModalPararMaquina();
    });
});