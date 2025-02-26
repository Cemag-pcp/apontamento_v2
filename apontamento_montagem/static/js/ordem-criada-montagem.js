export const loadOrdens = (container, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => {
        if (isLoading) return resolve({ ordens: [] });
        isLoading = true;

        fetch(`api/ordens-criadas/?data_carga=${filtros.data_carga}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;
                container.innerHTML = ""; // Limpa antes de inserir novas ordens
                
                if (ordens.length > 0) {
                    // Criar cabeçalho da tabela
                    const table = document.createElement('table');
                    table.classList.add('table', 'table-bordered', 'table-striped');

                    table.innerHTML = `
                        <thead class="table-light">
                            <tr>
                                <th style="width: 10%;">Ch. Ordem</th>
                                <th style="width: 15%;">Data Programação</th>
                                <th style="width: 15%;">Código Conjunto</th>
                                <th style="width: 10%;">Status</th>
                                <th style="width: 10%;">Máquina</th>
                                <th style="width: 10%;">Qtd. a Fazer</th>
                                <th style="width: 10%;">Qtd. Feita</th>
                                <th style="width: 10%;">Ação</th>
                            </tr>
                        </thead>
                        <tbody id="tabela-ordens-corpo"></tbody>
                    `;

                    container.appendChild(table);
                    const tabelaCorpo = document.getElementById('tabela-ordens-corpo');
                    ordens.forEach(ordem => {
                        const linha = document.createElement('tr');
                        linha.dataset.ordemId = ordem.ordem;
                        
                        linha.innerHTML = `
                            <td>#${ordem.ordem}</td>
                            <td>${ordem.ordem__data_programacao}</td>
                            <td>
                                <a href="https://drive.google.com/drive/u/0/search?q=${ordem.peca}" 
                                   target="_blank" rel="noopener noreferrer">
                                    ${ordem.peca}
                                </a>
                            </td>
                            <td>${ordem.ordem__status_atual}</td>
                            <td>${ordem.ordem__maquina__nome}</td>
                            <td>${ordem.restante}</td>
                            <td>${ordem.total_boa}</td>
                            <td><button class="btn btn-sm btn-primary btn-start">Iniciar</button></td>
                        `;

                        tabelaCorpo.appendChild(linha);
                    });

                    resolve(data);
                } else {
                    container.innerHTML = '<p class="text-danger">Nenhuma ordem encontrada.</p>';
                    resolve(data);
                }
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
    Swal.fire({
        title: 'Iniciando...',
        text: 'Por favor, aguarde enquanto a ordem está sendo iniciada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        },
    });

    fetch("http://127.0.0.1:8000/montagem/api/ordens/atualizar-status/", {
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
            resetarCardsInicial();
            carregarOrdensIniciadas();
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
    fetch(`api/ordens-iniciadas/`)
        .then(response => response.json())
        .then(data => {
            const container = document.querySelector('.containerProcesso');
            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {

                const card = document.createElement('div');
                card.dataset.ordemId = ordem.ordem_id;
                
                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

                botaoAcao = `
                    <button class="btn btn-danger btn-sm btn-interromper" title="Interromper">
                        <i class="fa fa-stop"></i>
                    </button>
                    <button class="btn btn-success btn-sm btn-finalizar" title="Finalizar">
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
                            <a href="https://drive.google.com/drive/u/0/search?q=${ordem.pecas}" target="_blank" rel="noopener noreferrer">
                                ${ordem.pecas}
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
                        mostrarModalInterromper(ordem.ordem_id);
                    });
                }

                // Adiciona evento ao botão "Finalizar", se existir
                if (buttonFinalizar) {
                    buttonFinalizar.addEventListener('click', () => {
                        mostrarModalFinalizar(ordem.ordem_id, ordem.grupo_maquina, ordem.qtd_restante);
                    });
                }

                container.appendChild(card);

                iniciarContador(ordem.ordem_id, ordem.ultima_atualizacao)

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
};

export function carregarOrdensInterrompidas(filtros = {}) {
    // Fetch para buscar ordens interrompidas

    const container = document.querySelector('.containerInterrompido');

    fetch(`api/ordens-interrompidas/`)
    .then(response => response.json())
    .then(data => {
        container.innerHTML = ''; // Limpa o container

        data.ordens.forEach(ordem => {
            const card = document.createElement('div');
            card.dataset.ordemId = ordem.ordem_id;

            // Defina os botões dinamicamente com base no status
            let botaoAcao = `
                <button class="btn btn-warning btn-sm btn-retornar" title="Retornar">
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

            card.innerHTML = `
            <div class="card shadow-lg border-0 rounded-3 mb-3 position-relative">
                <!-- Contador fixado no topo direito -->
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
                        <a href="https://drive.google.com/drive/u/0/search?q=${ordem.pecas}" target="_blank" rel="noopener noreferrer">
                            ${ordem.pecas}
                        </a>
                    </p>

                    <!-- Seção de Processos -->
                    <div class="mt-3">
                        ${processosInfo}
                    </div>
                </div>

                <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                    <div class="d-flex gap-2">
                        ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                    </div>
                </div>
            </div>`;

            const buttonRetornar = card.querySelector('.btn-retornar');
            if (buttonRetornar) {
                buttonRetornar.addEventListener('click', () => {
                    mostrarModalRetornar(ordem.ordem_id);
                });
            }

            container.appendChild(card);

            iniciarContador(ordem.ordem_id, ordem.ultima_atualizacao);
        });
    })
    .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));

};

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Modal para "Interromper"
function mostrarModalInterromper(ordemId) {
    const modal = new bootstrap.Modal(document.getElementById('modalInterromper'));
    const modalTitle = document.getElementById('modalInterromperLabel');
    const motivoInterrupcaoSelect = document.getElementById('motivoInterrupcao');
    const confirmInterromperButton = document.getElementById('confirmInterromper');

    // Define o título do modal
    modalTitle.innerHTML = `Interromper Ordem ${ordemId}`;
    modal.show();

    // Limpa e desativa o select antes de carregar os dados
    motivoInterrupcaoSelect.innerHTML = `<option value="" disabled selected>Carregando...</option>`;
    motivoInterrupcaoSelect.disabled = true;

    // Buscar motivos de interrupção
    fetch("api/listar-motivos-interrupcao/")
    .then(response => {
        if (!response.ok) {
            throw new Error("Erro ao buscar motivos de interrupção");
        }
        return response.json();
    })
    .then(data => {
        motivoInterrupcaoSelect.innerHTML = `<option value="" disabled selected>Selecione um motivo...</option>`;

        if (data.motivos.length === 0) {
            motivoInterrupcaoSelect.innerHTML = `<option value="" disabled>Nenhum motivo encontrado</option>`;
        } else {
            data.motivos.forEach(motivo => {
                const option = document.createElement("option");
                option.value = motivo.id; // Garante que o valor é numérico
                option.textContent = motivo.nome;
                motivoInterrupcaoSelect.appendChild(option);
            });
            motivoInterrupcaoSelect.disabled = false; // Habilita o select após carregar os dados
        }
    })
    .catch(error => {
        console.error("Erro ao carregar motivos:", error);
        motivoInterrupcaoSelect.innerHTML = `<option value="" disabled>Erro ao carregar</option>`;
    });

    // Remover event listener antigo antes de adicionar um novo (evita múltiplas chamadas)
    confirmInterromperButton.replaceWith(confirmInterromperButton.cloneNode(true));
    document.getElementById('confirmInterromper').addEventListener('click', () => finalizarInterrupcao(ordemId, motivoInterrupcaoSelect, modal));
}

function finalizarInterrupcao(ordemId, motivoInterrupcaoSelect, modal) {
    const motivoSelecionado = motivoInterrupcaoSelect.value;

    if (!motivoSelecionado || motivoSelecionado === "") {
        Swal.fire({
            icon: 'warning',
            title: 'Atenção',
            text: 'Selecione um motivo para interromper a ordem.'
        });
        return;
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

    fetch(`api/ordens/atualizar-status/`, {
        method: 'POST',
        body: JSON.stringify({
            ordem_id: parseInt(ordemId),
            status: 'interrompida',
            motivo: parseInt(motivoSelecionado)
        }),
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        Swal.fire({
            icon: 'success',
            title: 'Sucesso',
            text: 'Ordem interrompida com sucesso.',
        }).then(() => {
            modal.hide();
            carregarOrdensIniciadas();
            carregarOrdensInterrompidas(); // Recarrega a página para atualizar os dados
            resetarCardsInicial();
        });
    })
    .catch((error) => {
        console.error('Erro ao interromper a ordem:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.error || 'Ocorreu um erro ao tentar interromper a ordem. Tente novamente.'
        });
    });
}

// Modal para "Finalizar"
function mostrarModalFinalizar(ordemId, grupoMaquina, max_itens) {
    const modal = new bootstrap.Modal(document.getElementById('finalizarModal'));

    const operadorSelect = document.getElementById('operadorFinal');
    const qtRealizadaInput = document.getElementById('qtRealizada')
    
    document.getElementById('ordemIdFinalizar').value = ordemId;
    
    qtRealizadaInput.setAttribute('max', max_itens);

    fetch("api/listar-operadores/")
    .then(response => {
        if (!response.ok) {
            throw new Error("Erro ao buscar operadores");
        }
        return response.json();
    })
    .then(data => {
        operadorSelect.innerHTML = `<option value="" disabled selected>Selecione um operador...</option>`;
        
        if (data.operadores.length === 0) {
            operadorSelect.innerHTML = `<option value="" disabled>Nenhum operador encontrado</option>`;
        } else {
            data.operadores.forEach(operador => {
                operadorSelect.innerHTML += `<option value="${operador.id}">${operador.matricula} - ${operador.nome}</option>`;
            });
            operadorSelect.disabled = false; // Habilita o select após carregar os dados
        }
    })
    .catch(error => {
        console.error("Erro ao carregar operadores:", error);
        operadorSelect.innerHTML = `<option value="" disabled>Erro ao carregar</option>`;
    });
    
    modal.show();
}

document.getElementById('confirmFinalizar').addEventListener('click', function () {
    const ordemId = document.getElementById('ordemIdFinalizar').value;
    const operadorFinal = document.getElementById('operadorFinal').value;
    const qtRealizada = document.getElementById('qtRealizada');
    const obsFinalizar = document.getElementById('obsFinalizar').value;
    const qtMaxima = qtRealizada.getAttribute('max');
    
    // Validação: A quantidade realizada não pode ser maior que a máxima
    if (parseInt(qtRealizada.value) > parseInt(qtMaxima)) {
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: 'A quantidade realizada não pode ser maior que a quantidade máxima permitida.'
        });
        return; // Impede que continue com a requisição
    }

    // Validação: Campos obrigatórios
    if (!operadorFinal || !qtRealizada.value) {
        Swal.fire({
            icon: 'warning',
            title: 'Atenção',
            text: 'Por favor, preencha todos os campos obrigatórios.'
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
        operador_final: parseInt(operadorFinal),
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
    .then(response => response.json())
    .then(data => {

        carregarOrdensIniciadas();
        resetarCardsInicial();

        // Fechar o modal após a finalização bem-sucedida
        const modalElement = document.getElementById('finalizarModal');
        const finalizarModal = bootstrap.Modal.getInstance(modalElement);
        finalizarModal.hide();
        Swal.close();

    })
    .catch(error => {
        console.error('Erro ao finalizar a ordem:', error);
        alert("Erro ao finalizar a ordem. Tente novamente.");
        Swal.close();
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
            carregarOrdensInterrompidas();
            carregarOrdensIniciadas();
            resetarCardsInicial();
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

function resetarCardsInicial(filtros = {}) {
    const container = document.getElementById('ordens-container');
    let isLoading = false; // Flag para evitar chamadas simultâneas

    // Obtém os filtros atualizados
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    
    const currentFiltros = {
        data_carga: filtroDataCarga.value,
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

function filtro() {
    const form = document.getElementById('filtro-form');

    form.addEventListener('submit', (event) => {
        event.preventDefault(); // Evita comportamento padrão do formulário

        const filtroDataCarga = document.getElementById('filtro-data-carga');

        // Captura os valores atualizados dos filtros
        const filtros = {
            data_carga: filtroDataCarga.value,
        };

        // Recarrega os resultados com os novos filtros
        resetarCardsInicial(filtros);

    });
}

async function abrirModalCambao() {
    const checkboxes = document.querySelectorAll(".ordem-checkbox:checked");
    const tabelaCambao = document.getElementById("tabelaCambao");
    const corCambao = document.getElementById("corCambao");
    const selectCambao = document.getElementById("cambaoSelecionado");

    if (checkboxes.length === 0) {
        Swal.fire({
            icon: "warning",
            title: "Nenhuma ordem selecionada",
            text: "Selecione pelo menos uma ordem para criar um cambão.",
            confirmButtonText: "OK"
        });
        return;
    }

    let corSelecionada = checkboxes[0].dataset.cor;
    let pecaOrdens = [];
    let quantidades = [];
    let erros = [];

    tabelaCambao.innerHTML = ""; // Limpa a tabela antes de preencher
    selectCambao.innerHTML = `<option value="">Carregando...</option>`; // Carrega cambões

    Swal.fire({
        title: 'Carregando...',
        text: 'Aguarde...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Buscar cambões disponíveis da API
    try {
        const response = await fetch("api/cambao-livre/");
        const data = await response.json();

        if (data.cambao_livres.length > 0) {
            Swal.close();
            selectCambao.innerHTML = `<option value="">Selecione um cambão...</option>`;
            data.cambao_livres.forEach(cambao => {
                selectCambao.innerHTML += `<option value="${cambao.id}">Cambão ${cambao.id}</option>`;
            });
        } else {
            selectCambao.innerHTML = `<option value="">Nenhum cambão disponível</option>`;
        }
    } catch (error) {
        console.error("Erro ao buscar cambões:", error);
        selectCambao.innerHTML = `<option value="">Erro ao carregar cambões</option>`;
        Swal.close();
    }

    checkboxes.forEach(cb => {
        const linha = cb.closest("tr");
        const pecaOrdem = linha.dataset.pecaOrdem;
        const codigoPeca = linha.querySelector("a").textContent;
        const quantidadeInput = linha.querySelector(".qt-produzida");
        const quantidade = parseInt(quantidadeInput.value, 10);

        if (!quantidade || quantidade <= 0) {
            erros.push(`Ordem #${pecaOrdem}: Defina uma quantidade válida.`);
            return;
        }

        pecaOrdens.push(pecaOrdem);
        quantidades.push(quantidade);

        tabelaCambao.innerHTML += `
            <tr>
                <td>#${pecaOrdem}</td>
                <td>${codigoPeca}</td>
                <td>${quantidade}</td>
            </tr>
        `;
    });

    if (erros.length > 0) {
        Swal.fire({
            icon: "warning",
            title: "Erro ao criar Cambão",
            html: erros.join("<br>"),
            confirmButtonText: "OK"
        });
        return;
    }

    corCambao.textContent = corSelecionada;

    document.getElementById("confirmarCriacaoCambao").dataset.cambaoData = JSON.stringify({
        peca_ordens: pecaOrdens,
        quantidade: quantidades,
        cor: corSelecionada
    });

    const operadorSelect = document.getElementById('operadorInicial');

    fetch("api/listar-operadores/")
    .then(response => {
        if (!response.ok) {
            throw new Error("Erro ao buscar operadores");
        }
        return response.json();
    })
    .then(data => {
        operadorSelect.innerHTML = `<option value="" disabled selected>Selecione um operador...</option>`;
        
        if (data.operadores.length === 0) {
            operadorSelect.innerHTML = `<option value="" disabled>Nenhum operador encontrado</option>`;
        } else {
            data.operadores.forEach(operador => {
                operadorSelect.innerHTML += `<option value="${operador.id}">${operador.matricula} - ${operador.nome}</option>`;
            });
            operadorSelect.disabled = false; // Habilita o select após carregar os dados
        }
    })
    .catch(error => {
        console.error("Erro ao carregar operadores:", error);
        operadorSelect.innerHTML = `<option value="" disabled>Erro ao carregar</option>`;
    });

    let modal = new bootstrap.Modal(document.getElementById("modalCriarCambao"));
    modal.show();
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
    fetch(`api/andamento-carga/?data_carga=${encodeURIComponent(dataCarga)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao buscar andamento da carga.");
            }
            return response.json();
        })
        .then(data => {
            const percentual = data.percentual_concluido || 0; // Se não houver dado, assume 0%
            const percentualDisplay = document.getElementById("percentual-carga");

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
    fetch("api/andamento-ultimas-cargas/")
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao buscar andamento das últimas cargas.");
            }
            return response.json();
        })
        .then(data => {
            const listaCargas = document.getElementById("ultimas-pecas-list");
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

// Chama a função ao carregar a página
document.addEventListener('DOMContentLoaded', () => {
    resetarCardsInicial();
    carregarOrdensIniciadas();
    carregarOrdensInterrompidas();
    // cambaoProcesso();
    filtro();
    // coresCarga();
    atualizarUltimasCargas();
    
    // const botaoCriarCambao = document.getElementById("btn-criar-cambao");
    
    // if (botaoCriarCambao) {
    //     botaoCriarCambao.addEventListener("click", () => abrirModalCambao());
    // }
});