import { fetchStatusMaquinas, fetchUltimasPecasProduzidas, fetchContagemStatusOrdens } from './status-maquina.js';

export const loadOrdens = (container, page = 1, limit = 10, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => { // Retorna uma Promise
        if (isLoading) return resolve({ ordens: [] }); // Evita chamadas duplicadas
        isLoading = true;

        fetch(`api/ordens-criadas/?page=${page}&limit=${limit}&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&status=${filtros.status || ''}&maquina=${filtros.maquina || ''}&data-programada=${filtros.data_programada || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;
                if (ordens.length > 0) {
                    ordens.forEach(ordem => {
                        const card = document.createElement('div');
                        card.classList.add('col-md-4'); // Adiciona a classe de coluna

                        console.log(ordem)
                        card.dataset.ordemId = ordem.id; // Adiciona o ID da ordem para referência
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
                            case 'agua_prox_proc':
                                statusBadge = '<span class="badge rounded-pill bg-prox-processo badge-small ms-2">Próximo processo</span>';
                                break;
                            default:
                                statusBadge = '<span class="badge rounded-pill bg-dark badge-small ms-2">Desconhecido</span>';
                        }

                        // Defina os botões dinamicamente com base no status
                        let botaoAcao = '';

                        if (ordem.status_atual === 'iniciada') {
                            botaoAcao = `
                                <button class="btn btn-danger btn-sm btn-interromper" title="Interromper">
                                    <i class="fa fa-stop"></i>
                                </button>
                                <button class="btn btn-success btn-sm btn-finalizar" title="Finalizar">
                                    <i class="fa fa-check"></i>
                                </button>
                                <button class="btn btn-primary btn-sm btn-proximo-processo" title="Passar para o próximo processo">
                                    <i class="fa fa-arrow-right"></i>
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
                        } else if (ordem.status_atual === 'agua_prox_proc') {
                            botaoAcao = `
                                <button class="btn btn-warning btn-sm btn-iniciar-proximo-processo" title="Iniciar próximo processo">
                                    <i class="fa fa-play"></i>
                                </button>
                            `;
                        }
                    
                        // Monta o card com os botões dinâmicos
                        card.innerHTML = `
                        <div class="card shadow-sm bg-light text-dark">
                            <div class="card-body">
                                <h5 class="card-title d-flex justify-content-between align-items-center">
                                    <a href="https://drive.google.com/drive/u/0/search?q=${ordem.peca.codigo}" target="_blank" rel="noopener noreferrer">
                                        ${ordem.peca.codigo} - ${ordem.peca.descricao}
                                    </a>
                                    ${statusBadge}
                                </h5>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">#${ordem.ordem} Criado em: ${ordem.data_criacao}</p>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">Programada para: ${ordem.data_programacao}</p>
                                ${ordem.status_atual === 'finalizada' 
                                    ? `<p class="text-success fw-semibold mb-2" style="font-size: 0.85rem;">Finalizada em: ${ordem.ultima_atualizacao}</p>` 
                                    : ''
                                }                                
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">Maquina: ${ordem.maquina}</p>
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
                        const buttonProxProcesso = card.querySelector('.btn-iniciar-proximo-processo');
                        const buttonMandarProxProcesso = card.querySelector('.btn-proximo-processo')
                        // const buttonFinalizarParcial = card.querySelector('.btn-finalizar-parcial')
                        const buttonExcluir= card.querySelector('.btn-excluir');

                        // Adiciona evento ao botão "Iniciar", se existir
                        if (buttonIniciar) {
                            buttonIniciar.addEventListener('click', () => {
                                console.log(ordem.maquina_id)
                                console.log(ordem.maquina)
                                mostrarModalIniciar(ordem.id, ordem.grupo_maquina, ordem.maquina_id);
                            });
                        }

                        if (buttonInterromper) {
                            buttonInterromper.addEventListener('click', () => {
                                mostrarModalInterromper(ordem.id, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Finalizar", se existir
                        if (buttonFinalizar) {
                            buttonFinalizar.addEventListener('click', () => {
                                mostrarModalFinalizar(ordem.id, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Retornar", se existir
                        if (buttonRetornar) {
                            buttonRetornar.addEventListener('click', () => {
                                mostrarModalRetornar(ordem.id, ordem.grupo_maquina, ordem.maquina_id);
                            });
                        }

                        // Adiciona evento ao botão para iniciar proximo processo
                        if (buttonProxProcesso) {
                            buttonProxProcesso.addEventListener('click', () => {
                                mostrarModalIniciarProxProcesso(ordem.id, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão para enviar para proximo processo
                        if (buttonMandarProxProcesso) {
                            buttonMandarProxProcesso.addEventListener('click', () => {
                                mostrarModalProxProcesso(ordem.id, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão para enviar para proximo processo
                        // if (buttonFinalizarParcial) {
                        //     buttonFinalizarParcial.addEventListener('click', () => {
                        //         mostrarModalFinalizarParcial(ordem.id, ordem.grupo_maquina);
                        //     });
                        // }

                        // Adiciona evento ao botão "Excluir", se existir
                        if (buttonExcluir) {
                            buttonExcluir.addEventListener('click', () => {
                                mostrarModalExcluir(ordem.id, 'estamparia');
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

function removerCardDeOutrosContainers(ordemId, containerAtual) {
    const todosContainers = [
        document.querySelector('.containerProcesso'),
        document.querySelector('.containerInterrompido'),
        document.querySelector('.containerProxProcesso')
    ];

    todosContainers.forEach(container => {
        if (container && container !== containerAtual) {
            const cardDuplicado = container.querySelector(`[data-ordem-id="${ordemId}"]`);
            if (cardDuplicado) {
                cardDuplicado.remove();
            }
        }
    });
}

export function carregarOrdensIniciadas(container, filtros = {}) {
    
    // 1. Armazena snapshot atual
    const cardsAtuais = {};
    container.querySelectorAll('[data-ordem-id]').forEach(card => {
        cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    });

    fetch(`api/ordens-iniciadas/?page=1&limit=100&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&maquina=${filtros.maquina || ''}`)
        .then(response => response.json())
        .then(data => {

            let houveMudanca = false;
            
            // 2. Verifica se houve alguma alteração
            for (const ordem of data.ordens) {
                const ultimaNova = new Date(ordem.ultima_atualizacao).getTime();
                const ultimaAnterior = cardsAtuais[ordem.ordem];
                
                if (!ultimaAnterior || ultimaNova !== ultimaAnterior) {
                    houveMudanca = true;
                    break;
                }
            }

            // 3. Se não mudou nada, sai
            if (!houveMudanca) return;

            // 4. Mostra o spinner  
            // container.innerHTML = `
            //     <div class="spinner-border text-dark" role="status">
            //         <span class="sr-only">Loading...</span>
            //     </div>`;

            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {
                
                const cardExistente = container.querySelector(`[data-ordem-id="${ordem.ordem}"]`);
                const ultimaAtualizacao = new Date(ordem.ultima_atualizacao).getTime();

                if (cardExistente) {
                    const contador = cardExistente.querySelector(`#contador-${ordem.ordem}`);
                    const atualAnterior = cardExistente.dataset.ultimaAtualizacao;

                    // Só atualiza se tiver realmente mudado
                    if (!atualAnterior || parseInt(atualAnterior) !== ultimaAtualizacao) {
                        cardExistente.remove(); // Remove card antigo para recriar
                    } else {
                        return; // Não atualizou, segue p/ próxima
                    }
                }

                const card = document.createElement('div');
                card.dataset.ordemId = ordem.id;

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
                    <button class="btn btn-primary btn-sm btn-proximo-processo m-2" title="Passar para o próximo processo">
                        <i class="fa fa-arrow-right"></i>
                    </button>      
                `;

                // Calcula informações consolidadas das peças
                const totalQtdBoa = ordem.pecas.reduce((acc, peca) => acc + (peca.qtd_boa || 0), 0);
                const totalQtdPlanejada = ordem.pecas.reduce((acc, peca) => acc + (peca.qtd_planejada || 0), 0);
                const pecaInfo = ordem.pecas[0]; // Assume que deseja exibir apenas a primeira peça para detalhes

                card.innerHTML = `
                <div class="card shadow-lg border-0 rounded-3 mb-3 position-relative">
                    <!-- Contador fixado no topo direito -->
                    <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                        id="contador-${ordem.ordem}" 
                        style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                        Carregando...
                    </span>
                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                        <small class="text-white">Planejada: ${pecaInfo.qtd_planejada}</small>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Observação:</strong> ${ordem.obs || 'Sem observações'}
                        </p>
                        <p class="card-text mb-0 small">
                            <a href="https://drive.google.com/drive/u/0/search?q=${pecaInfo.codigo}" target="_blank" rel="noopener noreferrer">
                                ${pecaInfo.codigo} - ${pecaInfo.descricao}
                            </a>
                        </p>
                    </div>

                    <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                        <div class="d-flex flex-wrap justify-content-center gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                const buttonDeletar = card.querySelector('.btn-deletar');
                const buttonInterromper = card.querySelector('.btn-interromper');
                const buttonFinalizar = card.querySelector('.btn-finalizar');
                const buttonProxProcesso = card.querySelector('.btn-proximo-processo');
                // const buttonFinalizarParcial = card.querySelector('.btn-finalizar-parcial')
                
                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', function() {
                        mostrarModalRetornarOrdemIniciada(ordem.id, container);
                    });
                }

                // Adiciona evento ao botão "Interromper", se existir
                if (buttonInterromper) {
                    buttonInterromper.addEventListener('click', () => {
                        mostrarModalInterromper(ordem.id, ordem.grupo_maquina);
                    });
                }

                // Adiciona evento ao botão "Finalizar", se existir
                if (buttonFinalizar) {
                    buttonFinalizar.addEventListener('click', () => {
                        atualizarStatusOrdem(ordem.id, ordem.grupo_maquina, 'finalizada', ordem.maquina_id);
                    });
                }

                if (buttonProxProcesso) {
                    buttonProxProcesso.addEventListener('click', () => {
                        mostrarModalProxProcesso(ordem.id, ordem.grupo_maquina);
                    });
                }

                // if (buttonFinalizarParcial) {
                //     buttonFinalizarParcial.addEventListener('click', () => {
                //         mostrarModalFinalizarParcial(ordem.id, ordem.grupo_maquina);
                //     });
                // }

                removerCardDeOutrosContainers(ordem.ordem, container);
                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
};

export function carregarOrdensInterrompidas(container, filtros = {}) {
    // container.innerHTML = `
    //     <div class="spinner-border text-dark" role="status">
    //         <span class="sr-only">Loading...</span>
    //     </div>`;
    
    // 1. Armazena snapshot atual
    const cardsAtuais = {};
    container.querySelectorAll('[data-ordem-id]').forEach(card => {
        cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    });

    // Fetch para buscar ordens interrompidas
    fetch(`api/ordens-interrompidas/?page=1&limit=100&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&maquina=${filtros.maquina || ''}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao buscar as ordens interrompidas.');
            }
            return response.json();
        })
        .then(data => {
            let houveMudanca = false;

            // 2. Verifica se houve alguma alteração
            for (const ordem of data.ordens) {
                const ultimaNova = new Date(ordem.ultima_atualizacao).getTime();
                const ultimaAnterior = cardsAtuais[ordem.ordem];

                if (!ultimaAnterior || ultimaNova !== ultimaAnterior) {
                    houveMudanca = true;
                    break;
                }
            }

            // 3. Se não mudou nada, sai
            if (!houveMudanca) return;

            // 4. Mostra o spinner  
            container.innerHTML = `
            <div class="spinner-border text-dark" role="status">
                <span class="sr-only">Loading...</span>
            </div>`;

            container.innerHTML = ''; // Limpa o container

            data.ordens.forEach(ordem => {

                const cardExistente = container.querySelector(`[data-ordem-id="${ordem.ordem}"]`);
                const ultimaAtualizacao = new Date(ordem.ultima_atualizacao).getTime();

                if (cardExistente) {
                    const contador = cardExistente.querySelector(`#contador-${ordem.ordem}`);
                    const atualAnterior = cardExistente.dataset.ultimaAtualizacao;

                    // Só atualiza se tiver realmente mudado
                    if (!atualAnterior || parseInt(atualAnterior) !== ultimaAtualizacao) {
                        cardExistente.remove(); // Remove card antigo para recriar
                    } else {
                        return; // Não atualizou, segue p/ próxima
                    }
                }

                // Cria o card
                const card = document.createElement('div');
                card.dataset.ordemId = ordem.id;
            
                // Cria a lista de peças em formato simplificado
                const pecasHTML = ordem.pecas.map(peca => `
                    <a href="https://drive.google.com/drive/u/0/search?q=${peca.codigo}" target="_blank" rel="noopener noreferrer">
                        ${peca.codigo} - ${peca.descricao}
                    </a>
                `).join('<br>');
            
                // Botões de ação
                const botaoAcao = `
                    ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor'
                    ? `<button class="btn btn-danger btn-sm btn-deletar m-2" data-ordem="${ordem.id}" title="Desfazer">
                        <i class="bi bi-arrow-left-right"></i>
                    </button>`: ""}
                    <button class="btn btn-warning btn-sm btn-retornar m-2" title="Retornar">
                        <i class="fa fa-undo"></i>
                    </button>
                `;
            
                // Estrutura do card com fonte menor
                card.innerHTML = `
                    <div class="card shadow-lg border-0 rounded-3 mb-3 position-relative">
                        <!-- Contador fixado no topo direito -->
                        <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                            id="contador-${ordem.ordem}" 
                            style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                            Carregando...
                        </span>
    
                        <div class="card-header bg-danger text-white d-flex justify-content-between align-items-center p-3">
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
                            <div class="d-flex flex-wrap justify-content-center gap-2">
                                ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                            </div>
                        </div>
                    </div>`;
            
                // Adiciona eventos aos botões
                const buttonRetornar = card.querySelector('.btn-retornar');
                const buttonDeletar = card.querySelector('.btn-deletar');

                if (buttonRetornar) {
                    buttonRetornar.addEventListener('click', () => {
                        mostrarModalRetornar(ordem.id, ordem.grupo_maquina, ordem.maquina_id);
                    });
                }

                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', function() {
                        mostrarModalRetornarOrdemIniciada(ordem.id, container);
                    });
                }
            
                // Adiciona o card ao container
                removerCardDeOutrosContainers(ordem.ordem, container);
                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)

            });
        })
        .catch(error => {
            console.error('Erro ao buscar ordens interrompidas:', error);
            container.innerHTML = '<p class="text-danger">Erro ao carregar ordens interrompidas.</p>';
        });
};

export function carregarOrdensAgProProcesso(container, filtros = {}) {
    
    // 1. Armazena snapshot atual
    const cardsAtuais = {};
    container.querySelectorAll('[data-ordem-id]').forEach(card => {
        cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    });

    fetch(`api/ordens-ag-prox-proc/?page=1&limit=100&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&maquina=${filtros.maquina || ''}`)
        .then(response => response.json())
        .then(data => {
            let houveMudanca = false;

            // 2. Verifica se houve alguma alteração
            for (const ordem of data.ordens) {
                const ultimaNova = new Date(ordem.ultima_atualizacao).getTime();
                const ultimaAnterior = cardsAtuais[ordem.ordem];

                if (!ultimaAnterior || ultimaNova !== ultimaAnterior) {
                    houveMudanca = true;
                    break;
                }
            }

            // 3. Se não mudou nada, sai
            if (!houveMudanca) return;

            // 4. Mostra o spinner  
            container.innerHTML = `
            <div class="spinner-border text-dark" role="status">
                <span class="sr-only">Loading...</span>
            </div>`;

            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {

                const cardExistente = container.querySelector(`[data-ordem-id="${ordem.ordem}"]`);
                const ultimaAtualizacao = new Date(ordem.ultima_atualizacao).getTime();

                if (cardExistente) {
                    const contador = cardExistente.querySelector(`#contador-${ordem.ordem}`);
                    const atualAnterior = cardExistente.dataset.ultimaAtualizacao;

                    // Só atualiza se tiver realmente mudado
                    if (!atualAnterior || parseInt(atualAnterior) !== ultimaAtualizacao) {
                        cardExistente.remove(); // Remove card antigo para recriar
                    } else {
                        return; // Não atualizou, segue p/ próxima
                    }
                }

                const card = document.createElement('div');
                card.dataset.ordemId = ordem.id;

                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

                botaoAcao = `
                    ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor'
                    ? `<button class="btn btn-danger btn-sm btn-deletar m-2" data-ordem="${ordem.id}" title="Desfazer">
                        <i class="bi bi-arrow-left-right"></i>
                    </button>`: ""}
                    <button class="btn btn-warning btn-sm btn-iniciar-proximo-processo m-2" title="Iniciar próximo processo">
                        <i class="fa fa-play"></i>
                    </button>
                `;

                card.innerHTML = `

                <div class="card shadow-lg bg-prox-processo border-0 rounded-3 mb-3 position-relative">
                    <!-- Contador fixado no topo direito -->
                    <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                        id="contador-${ordem.ordem}" 
                        style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                        Carregando...
                    </span>
                    <div class="card-header bg-prox-processo text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                        <small class="text-white">Planejada: ${ordem.totais.qtd_planejada}</small>
                    </div>
                    <div class="card-body bg-light">
                        <p class="card-text mb-2 small">
                            <strong>Observação:</strong> ${ordem.obs || 'Sem observações'}
                        </p>
                        <p class="card-text mb-0 small">
                            <a href="https://drive.google.com/drive/u/0/search?q=${ordem.pecas[0].codigo}" target="_blank" rel="noopener noreferrer">
                                ${ordem.pecas[0].codigo} - ${ordem.pecas[0].descricao}
                            </a>
                        </p>
                    </div>

                    <div class="card-footer d-flex justify-content-between align-items-center bg-white small" style="border-top: 1px solid #dee2e6;">
                        <div class="d-flex flex-wrap justify-content-center gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                const buttonProxProcesso = card.querySelector('.btn-iniciar-proximo-processo');
                const buttonDeletar = card.querySelector('.btn-deletar');

                // Adiciona evento ao botão para iniciar proximo processo
                if (buttonProxProcesso) {
                    buttonProxProcesso.addEventListener('click', () => {
                        mostrarModalIniciarProxProcesso(ordem.id, ordem.grupo_maquina);
                    });
                }

                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', function() {
                        mostrarModalRetornarOrdemIniciada(ordem.id, container);
                    });
                }

                removerCardDeOutrosContainers(ordem.ordem, container);
                
                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
}

function carregarMaquinasEstamparia(selectIds) {
    // Se nenhum ID for passado, usa um array vazio
    const ids = Array.isArray(selectIds) ? selectIds : [];
    
    // Se nenhum ID foi passado, procura por um select com id padrão
    if (ids.length === 0) {
        const defaultSelect = document.querySelector('#maquinas-select');
        if (defaultSelect) {
            ids.push('#maquinas-select');
        }
    }

    // Faz a requisição para a API apenas uma vez
    fetch('/cadastro/api/buscar-maquinas/?setor=estamparia')
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao carregar máquinas');
            }
            return response.json();
        })
        .then(data => {
            // Para cada ID na lista, atualiza o select correspondente
            ids.forEach(id => {
                const select = document.querySelector(id);
                if (select) {
                    // Limpa opções existentes
                    select.innerHTML = '<option value="">Selecione uma máquina</option>';

                    // Adiciona as novas opções
                    data.maquinas.forEach(maquina => {
                        const option = document.createElement('option');
                        option.value = maquina.id;
                        option.textContent = maquina.nome;
                        select.appendChild(option);
                    });
                }
            });
        })
        .catch(error => {
            console.error('Erro:', error);
            // Adiciona uma opção de erro em todos os selects
            ids.forEach(id => {
                const select = document.querySelector(id);
                if (select) {
                    select.innerHTML = '<option value="">Erro ao carregar máquinas</option>';
                }
            });
        });
}



function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function atualizarStatusOrdem(ordemId, grupoMaquina, status, idMaquinaPlanejada) {
    switch (status) {
        case 'iniciada':
            mostrarModalIniciar(ordemId, grupoMaquina, idMaquinaPlanejada);
            break;
        case 'interrompida':
            mostrarModalInterromper(ordemId, grupoMaquina);
            break;
        case 'finalizada':
            mostrarModalFinalizar(ordemId, grupoMaquina);
            break;
        case 'agua_prox_proc':
            mostrarModalIniciarProxProcesso(ordemId, grupoMaquina);
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
        
        // dentro do container containerProcesso
        const container = document.querySelector('.containerProcesso');
        const card = container?.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();
        
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

function mostrarModalRetornarOrdemIniciada(ordemId, container) {
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
    
            // dentro do container
            // const container = document.querySelector(`.${container}`);
            const card = container?.querySelector(`[data-ordem-id="${ordemId}"]`);
            if (card) card.remove();

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
                carregarOrdensAgProProcesso(document.querySelector('.containerProxProcesso'))
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

// Modal para "Iniciar"
function mostrarModalIniciar(ordemId, grupoMaquina, idMaquinaPlanejada) {
    const modal = new bootstrap.Modal(document.getElementById('modalIniciar'));
    const modalTitle = document.getElementById('modalIniciarLabel');

    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das máquinas...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    fetch('/cadastro/api/buscar-maquinas/?setor=estamparia', {
        method: 'GET',
        headers: {'Content-Type':'application/json'}
    })
    .then(response => response.json())
    .then(data => {
        const escolhaMaquina = document.getElementById('escolhaMaquinaIniciarOrdem');
        escolhaMaquina.innerHTML = `<option value="">------</option>`;

        Swal.close();
        data.maquinas.forEach((maquina) => {
            const option = document.createElement('option');
            option.value = maquina.id;
            option.textContent = maquina.nome;
            if (maquina.id == idMaquinaPlanejada) {
                option.selected = true;
            }
            escolhaMaquina.appendChild(option);
        });

        console.log(idMaquinaPlanejada)

        modalTitle.innerHTML = 'Escolha a máquina';
        modal.show();
    });

    // Remove event listeners antigos do formulário e adiciona um novo
    const formIniciar = document.getElementById('formIniciarOrdemCorte');
    const clonedForm = formIniciar.cloneNode(true);
    formIniciar.parentNode.replaceChild(clonedForm, formIniciar);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const maquinaName = formData.get('escolhaMaquinaIniciarOrdem');

        Swal.fire({
            title: 'Iniciando Ordem...',
            text: 'Por favor, aguarde.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            },
        });

        const card = document.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();

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
                'X-CSRFToken': getCSRFToken(),
            },
        })
        .then(async (response) => {
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Erro ao iniciar a ordem.');
            }

            return data;
        })
        .then(() => {
            Swal.fire({
                title: 'Sucesso',
                text: 'Ordem iniciada com sucesso.',
            });

            modal.hide();

            const containerIniciado = document.querySelector('.containerProcesso');
            carregarOrdensIniciadas(containerIniciado);

            document.getElementById('ordens-container').innerHTML = '';
            resetarCardsInicial();

            fetchStatusMaquinas();
            fetchContagemStatusOrdens();
        })
        .catch((error) => {
            Swal.fire({
                title: 'Erro',
                text: error.message,
            });
        });
    });
}

// Modal para "Parcial"
function mostrarModalFinalizarParcial(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalFinalizarParcial'));
    const modalTitle = document.getElementById('modalFinalizarParcialLabel');
    const formFinalizar = document.getElementById('formFinalizarParcial');

    // Remove event listeners antigos para evitar duplicidade
    const clonedForm = formFinalizar.cloneNode(true);
    formFinalizar.parentNode.replaceChild(clonedForm, formFinalizar);

    // Configura título do modal
    modalTitle.innerHTML = `Finalizar Ordem Parcialmente ${ordemId}`;
    document.getElementById('bodyPecasFinalizarParcial').innerHTML = '<p class="text-center text-muted">Carregando informações...</p>';

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
            document.getElementById('bodyPecasFinalizarParcial').innerHTML = `
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
                const operadorFinal = document.getElementById('operadorFinalizarParcial').value;

                // Faz o fetch para finalizar a ordem
                fetch(`api/ordens/atualizar-status/`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        ordem_id: ordemId,
                        grupo_maquina: grupoMaquina,
                        status: 'finalizada_parcial',
                        qt_realizada: qtRealizada,
                        qt_mortas: qtMortas,
                        operador_final: operadorFinal,
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

                    // Atualiza a interface
                    const containerInterrompido = document.querySelector('.containerInterrompido');
                    carregarOrdensInterrompidas(containerInterrompido);

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

// Modal para mandar para mandar para "Proximo processo"
function mostrarModalProxProcesso(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalProxProcesso'));
    const modalTitle = document.getElementById('modalProxProcessoLabel');

    const colQtdProxProcesso = document.getElementById('colQtdProxProcesso');

    colQtdProxProcesso.style.display = 'block';
    
    const qtdProxProcesso = document.getElementById('qtdProxProcesso');
    qtdProxProcesso.value = '';
    qtdProxProcesso.required = true;
    
    // Exibe SweetAlert de carregamento
    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações dos processos...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Limpa opções antigas no select
    fetch('/cadastro/api/buscar-processos/?setor=estamparia', {
        method: 'GET',
        headers: {'Content-Type':'application/json'}
    })
    .then(response => response.json())
    .then(
        data => {
            const escolhaProcesso = document.getElementById('escolhaMaquinaProxProcesso');
            const labelModalMaquinaProxProcesso = document.getElementById('labelModalMaquinaProxProcesso');
            escolhaProcesso.innerHTML = `<option value="">------</option>`;

            Swal.close();
            data.processos.forEach((processo) => {
                const option = document.createElement('option');
                option.value = processo.id;
                option.textContent = processo.nome;
                escolhaProcesso.appendChild(option);
            })
            modalTitle.innerHTML = `Passar para próximo processo`;
            labelModalMaquinaProxProcesso.innerHTML = 'Escolha o próximo processo:'
            modal.show();
        }
    ) 

    // Remove listeners antigos e adiciona novo no formulário
    const formIniciar = document.getElementById('formProxProcesso');
    const clonedForm = formIniciar.cloneNode(true);
    formIniciar.parentNode.replaceChild(clonedForm, formIniciar);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const maquinaName = formData.get('escolhaMaquinaProxProcesso');
        const qtdProxProcesso = formData.get('qtdProxProcesso');

        const container = document.querySelector('.containerProcesso');
        const card = container?.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();

        // Exibe SweetAlert de carregamento
        Swal.fire({
            title: 'Mudando processo...',
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
                status: 'agua_prox_proc',
                maquina_nome: maquinaName,
                qtd_prox_processo: qtdProxProcesso,
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
                    text: 'Processo alterado com sucesso.',
                });

                modal.hide();

                // Atualiza a interface
                const containerIniciado = document.querySelector('.containerProcesso');
                carregarOrdensIniciadas(containerIniciado);

                // Atualiza a interface
                const containerProxProcesso = document.querySelector('.containerProxProcesso')
                carregarOrdensAgProProcesso(containerProxProcesso);
            
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

// Modal para para "Iniciar próximo processo"
function mostrarModalIniciarProxProcesso(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalProxProcesso'));
    const modalTitle = document.getElementById('modalProxProcessoLabel');

    // const escolhaMaquina = document.getElementById('escolhaMaquinaProxProcesso');
    const qtdProxProcesso = document.getElementById('qtdProxProcesso');
    const colQtdProxProcesso = document.getElementById('colQtdProxProcesso');

    colQtdProxProcesso.style.display = 'none';
    qtdProxProcesso.required = false;

    // Limpa opções antigas no select
    // escolhaMaquina.innerHTML = `<option value="">------</option>`;

    // Exibe SweetAlert de carregamento
    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das máquinas...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    // Limpa opções antigas no select

    fetch('/cadastro/api/buscar-maquinas/?setor=estamparia', {
        method: 'GET',
        headers: {'Content-Type':'application/json'}
    })
    .then(response => response.json())
    .then(
        data => {
            const labelModalMaquinaProxProcesso = document.getElementById('labelModalMaquinaProxProcesso');
            const escolhaMaquina = document.getElementById('escolhaMaquinaProxProcesso');
            escolhaMaquina.innerHTML = `<option value="">------</option>`;

            Swal.close();
            data.maquinas.forEach((maquina) => {
                const option = document.createElement('option');
                option.value = maquina.id;
                option.textContent = maquina.nome;
                escolhaMaquina.appendChild(option);
            })
            modalTitle.innerHTML = 'Iniciar próximo processo'
            labelModalMaquinaProxProcesso.innerHTML = 'Em qual máquina será iniciado?'
            modal.show();
        }
    )

    // Remove listeners antigos e adiciona novo no formulário
    const formIniciar = document.getElementById('formProxProcesso');
    const clonedForm = formIniciar.cloneNode(true);
    formIniciar.parentNode.replaceChild(clonedForm, formIniciar);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const maquinaName = formData.get('escolhaMaquinaProxProcesso');

        const container = document.querySelector('.containerProxProcesso');
        const card = container?.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();

        // Exibe SweetAlert de carregamento
        Swal.fire({
            title: 'Mudando processo...',
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
                    text: 'Processo alterado com sucesso.',
                });

                modal.hide();

                // Atualiza a interface
                const containerIniciado = document.querySelector('.containerProcesso');
                carregarOrdensIniciadas(containerIniciado);

                // Atualiza a interface
                const containerProxProcesso = document.querySelector('.containerProxProcesso')
                carregarOrdensAgProProcesso(containerProxProcesso);

                // Recarrega os dados chamando a função de carregamento
                document.getElementById('ordens-container').innerHTML = '';
                resetarCardsInicial();

                colQtdProxProcesso.style.display = 'block';
                qtdProxProcesso.required = true;

                fetchStatusMaquinas();
                fetchContagemStatusOrdens();
            
            })
            .catch((error) => {
                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: error.message,
                });

                colQtdProxProcesso.style.display = 'block';
                qtdProxProcesso.required = true;

            });
    });
}

// Modal para "Finalizar"
function mostrarModalFinalizar(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalFinalizar'));
    const modalTitle = document.getElementById('modalFinalizarLabel');
    const formFinalizar = document.getElementById('formFinalizarOrdemEstamparia');

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
            
            document.getElementById('obsFinalizar').value = '';

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

                    fetchContagemStatusOrdens();
                    fetchStatusMaquinas();
                    fetchUltimasPecasProduzidas();
        
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
function mostrarModalRetornar(ordemId, grupoMaquina, maquina) {

    // const maquinaTratada = maquina.toLowerCase().replace(" ","_");

    const modal = new bootstrap.Modal(document.getElementById('modalRetornar'));
    const modalTitle = document.getElementById('modalRetornarLabel');
    const formRetornar = document.getElementById('formRetornarProducao');

    modalTitle.innerHTML = `Retornar Ordem`;
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

        // dentro do container containerProcesso
        const container = document.querySelector('.containerInterrompido');
        const card = container?.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();

        fetch(`api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify({
                ordem_id: ordemId,
                grupo_maquina: grupoMaquina,
                status: 'iniciada',
                maquina_nome: maquina,

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
                fetchContagemStatusOrdens();

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

// Função separada para evitar múltiplos event listeners
async function handleSubmit(event) {
    event.preventDefault(); // Evita o recarregamento da página

    const form = event.target;
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
        const response = await fetch('api/criar-ordem-estamparia/', {
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
                title: 'Sucesso!',
                text: 'Ordem de Produção criada com sucesso.',
                confirmButtonText: 'OK',
            });

            form.reset();

            //  Remove o foco do elemento ativo antes de fechar o modal
            document.activeElement.blur();

            // Fecha corretamente o modal atual
            const modalPlanejarInstance = bootstrap.Modal.getInstance(document.getElementById('modalEstamparia'));
            if (modalPlanejarInstance) {
                modalPlanejarInstance.hide();
            }

            // Recarrega os cards
            document.getElementById('ordens-container').innerHTML = '';
            resetarCardsInicial();

            // Abre o modal correto
            const modal = new bootstrap.Modal(document.getElementById('modalIniciarAposPlanejar'));
            modal.show();

            // Remove event listeners antigos antes de adicionar novos
            const btnIniciar = document.querySelector('.btn-iniciar-planejar');
            const btnNaoIniciar = document.querySelector('.btn-nao-iniciar-planejar');

            if (btnIniciar) {
                btnIniciar.replaceWith(btnIniciar.cloneNode(true));
                document.querySelector('.btn-iniciar-planejar').addEventListener('click', function () {
                    modal.hide();
                    mostrarModalIniciar(data.ordem_id, 'estamparia', data.maquina_id);
                });
            }

            if (btnNaoIniciar) {
                btnNaoIniciar.replaceWith(btnNaoIniciar.cloneNode(true));
                document.querySelector('.btn-nao-iniciar-planejar').addEventListener('click', function () {
                    modal.hide();
                });
            }

            fetchContagemStatusOrdens();

        } else {
            Swal.fire({
                title: 'Erro!',
                text: data.error || 'Erro ao criar a Ordem de Produção.',
                confirmButtonText: 'OK',
            });
        }
    } catch (error) {
        Swal.close();
        Swal.fire({
            title: 'Erro inesperado!',
            text: 'Ocorreu um erro ao processar sua solicitação. Tente novamente.',
            confirmButtonText: 'OK',
        });
        console.error('Erro:', error);
    }
}

// Modal para "planejar"
function modalPlanejar() {
    const form = document.getElementById('opEstampariaForm');

    if (!form) {
        console.error("Formulário não encontrado!");
        
        return;
    }

    // Remove qualquer evento de submit duplicado antes de adicionar um novo
    form.removeEventListener('submit', handleSubmit);
    form.addEventListener('submit', handleSubmit);
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
    const filtroMaquina = document.getElementById('filtro-maquina');
    const filtroDataProgramada = document.getElementById('filtro-data-programada');

    const currentFiltros = {
        ordem: filtros.ordem || filtroOrdem.value.trim(),
        peca: filtros.peca || filtroPeca.value.trim(),
        status: filtros.status || filtroStatus.value.trim(),
        maquina: filtros.maquina || filtroMaquina.value.trim(),
        data_programada: filtros.data_programada || filtroDataProgramada.value.trim(),
    };

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
                    hasMoreData = true; // Permite continuar carregando mais dados
                    loadMoreButton.style.display = 'block'; // Mostra o botão se houver mais dados
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

    // Limpa o container antes de carregar novos dados
    container.innerHTML = '';
    fetchOrdens();

    // Configurar o botão "Carregar Mais"
    loadMoreButton.onclick = async () => {
        loadMoreButton.disabled = true;
        loadMoreButton.innerHTML = `                    
            <div class="spinner-border text-dark" role="status">
                <span class="sr-only">Loading...</span>
            </div>
        `;
        fetchOrdens(); 
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
            maquina: document.getElementById('filtro-maquina').value.trim(),
        };

        // Recarrega os resultados com os novos filtros
        resetarCardsInicial(filtros);

        // Filtrar ordens em andamento
        const containerIniciado = document.querySelector('.containerProcesso');
        carregarOrdensIniciadas(containerIniciado, filtros);

        // Filtrar ordens interrompidas
        const containerInterrompido = document.querySelector('.containerInterrompido');
        carregarOrdensInterrompidas(containerInterrompido, filtros);

        // Filtrar ordens aguardando prox processo
        const containerProxProcesso = document.querySelector('.containerProxProcesso');
        carregarOrdensAgProProcesso(containerProxProcesso, filtros);

    });
}

export function inicializarAutoAtualizacaoOrdens() {
    const containerIniciado = document.querySelector('.containerProcesso');
    const containerInterrompido = document.querySelector('.containerInterrompido');
    const containerProxProcesso = document.querySelector('.containerProxProcesso');

    setInterval(() => {
        carregarOrdensIniciadas(containerIniciado);
        carregarOrdensInterrompidas(containerInterrompido);
        carregarOrdensAgProProcesso(containerProxProcesso);
    }, 30000);
}

document.addEventListener('DOMContentLoaded', () => {

    resetarCardsInicial();
    modalPlanejar();
    
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
        dropdownParent: $('#modalEstamparia'),
    });

    const containerIniciado = document.querySelector('.containerProcesso');
    const containerInterrompido = document.querySelector('.containerInterrompido');
    const containerProxProcesso = document.querySelector('.containerProxProcesso');

    carregarOrdensIniciadas(containerIniciado);
    carregarOrdensInterrompidas(containerInterrompido);
    carregarOrdensAgProProcesso(containerProxProcesso);
    carregarMaquinasEstamparia(['#maquinas-select', '#filtro-maquina']); // Lista de selects que receberao maquinas

    filtro();
    // inicializarAutoAtualizacaoOrdens();

});
