import { fetchStatusMaquinas, fetchUltimasPecasProduzidas, fetchContagemStatusOrdens } from './status-maquina-v2.js';

const ordensSelecionadas = new Set();

function atualizarResumoSelecao() {
    const totalSelecionadas = ordensSelecionadas.size;
    const contador = document.getElementById('selecionadas-count');
    const botaoExcluirLote = document.getElementById('btnExcluirSelecionadas');
    const selecionarPagina = document.getElementById('selecionar-todas-ordens');
    const checkboxesVisiveis = Array.from(document.querySelectorAll('.ordem-checkbox'));
    const marcadasVisiveis = checkboxesVisiveis.filter((checkbox) => checkbox.checked).length;

    if (contador) {
        contador.textContent = `${totalSelecionadas} selecionada(s)`;
    }

    if (botaoExcluirLote) {
        botaoExcluirLote.disabled = totalSelecionadas === 0;
    }

    if (selecionarPagina) {
        selecionarPagina.checked = checkboxesVisiveis.length > 0 && marcadasVisiveis === checkboxesVisiveis.length;
        selecionarPagina.indeterminate = marcadasVisiveis > 0 && marcadasVisiveis < checkboxesVisiveis.length;
    }
}

function limparSelecaoOrdens() {
    ordensSelecionadas.clear();
    document.querySelectorAll('.ordem-checkbox').forEach((checkbox) => {
        checkbox.checked = false;
    });
    atualizarResumoSelecao();
}

async function excluirOrdens(ordensIds, setor, motivoExclusao) {
    const resultados = await Promise.all(
        ordensIds.map(async (ordemId) => {
            const response = await fetch('/core/api/excluir-ordem/', {
                method: 'POST',
                body: JSON.stringify({
                    ordem_id: ordemId,
                    setor: setor,
                    motivo: motivoExclusao
                }),
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                }
            });

            const body = await response.json();

            if (!response.ok) {
                throw new Error(body.error || `Erro ao excluir a ordem ${ordemId}.`);
            }

            return body;
        })
    );

    return resultados;
}

export const loadOrdens = (container, page = 1, limit = 10, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas
    
    return new Promise((resolve, reject) => { // Retorna uma Promise
        if (isLoading) return resolve({ ordens: [] }); // Evita chamadas duplicadas
        isLoading = true;

        fetch(`api/ordens-criadas/?page=${page}&limit=${limit}&ordem=${filtros.ordem || ''}&status=${filtros.status || ''}&mp=${filtros.mp || ''}&peca=${filtros.peca || ''}&data-programada=${filtros.data_programada || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;

                if (ordens.length > 0) {
                    ordens.forEach(ordem => {
                        const podeExcluir = !['finalizada', 'iniciada', 'interrompida'].includes(ordem.status_atual);

                        const card = document.createElement('div');
                        card.classList.add('col-md-4'); // Adiciona a classe de coluna

                        card.dataset.ordemId = ordem.ordem; // Adiciona o ID da ordem para referência
                        card.dataset.grupoMaquina = ordem.grupo_maquina || ''; // Adiciona o grupo máquina
                        card.dataset.obs = ordem.obs || ''; // Adiciona observações
                        card.dataset.ordemPk = ordem.id;
                    
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
                                <button class="btn btn-primary btn-sm btn-duplicar" title="Duplicar Ordem">
                                    <i class="fa fa-clone"></i>
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
                                <button class="btn btn-primary btn-sm btn-duplicar" title="Duplicar Ordem">
                                    <i class="fa fa-clone"></i>
                                </button>
                            `;
                        } else if (ordem.status_atual === 'interrompida') {
                            botaoAcao = `
                                <button class="btn btn-warning btn-sm btn-retornar" title="Retornar">
                                    <i class="fa fa-redo"></i>
                                </button>
                                <button class="btn btn-primary btn-sm btn-duplicar" title="Duplicar Ordem">
                                    <i class="fa fa-clone"></i>
                                </button>
                            `;
                        }

                        // Monta o card com os botões dinâmicos
                        card.innerHTML = `
                        <div class="card shadow-sm bg-light text-dark">
                            <div class="card-body">
                                <h5 class="card-title d-flex justify-content-between align-items-center">
                                    <span class="d-flex align-items-center gap-2">
                                        <input
                                            class="ordem-checkbox me-2"
                                            type="checkbox"
                                            value="${ordem.id}"
                                            aria-label="Selecionar ordem ${ordem.ordem} para exclusão em lote"
                                            title="${podeExcluir ? 'Selecionar ordem para exclusão em lote' : 'Esta ordem não pode ser excluída nesse status'}"
                                            style="width: 18px; height: 18px; margin: 0; accent-color: #dc3545; flex: 0 0 auto;"
                                            ${ordensSelecionadas.has(String(ordem.id)) ? 'checked' : ''}
                                            ${podeExcluir ? '' : 'disabled'}
                                        >
                                        <span>#${ordem.ordem}</span>
                                    </span>
                                    <span>${statusBadge}</span>
                                </h5>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">Criado em: ${ordem.data_criacao}</p>
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">Programada para: ${ordem.data_programacao}</p>
                                ${ordem.status_atual === 'finalizada' 
                                    ? `<p class="text-success fw-semibold mb-2" style="font-size: 0.85rem;">Finalizada em: ${ordem.ultima_atualizacao}</p>` 
                                    : ''
                                }                                
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
                        const buttonDuplicar= card.querySelector('.btn-duplicar');
                        const checkboxSelecionar = card.querySelector('.ordem-checkbox');

                        // Adiciona evento ao botão "Ver Peças", se existir
                        if (buttonVerPeca) {
                            buttonVerPeca.addEventListener('click', () => {
                                mostrarPecas(ordem.id, ordem.grupo_maquina);
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
                                mostrarModalIniciar(ordem.id, ordem.grupo_maquina);
                            });
                        }

                        // Adiciona evento ao botão "Excluir", se existir
                        if (buttonExcluir) {
                            buttonExcluir.addEventListener('click', () => {
                                mostrarModalExcluir(ordem.id, 'serra');
                            });
                        }

                        // Adiciona evento ao botão "Duplicar", se existir
                        if (buttonDuplicar) {
                            buttonDuplicar.addEventListener('click', () => {
                                mostrarModalDuplicar(ordem.id, 'serra');
                            });
                        }

                        if (checkboxSelecionar) {
                            checkboxSelecionar.addEventListener('change', ({ target }) => {
                                if (target.disabled) {
                                    return;
                                }

                                const ordemId = String(target.value);

                                if (target.checked) {
                                    ordensSelecionadas.add(ordemId);
                                } else {
                                    ordensSelecionadas.delete(ordemId);
                                }

                                atualizarResumoSelecao();
                            });
                        }

                        // Adiciona o card ao container
                        container.appendChild(card);
                    });

                    atualizarResumoSelecao();

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
        document.querySelector('.containerInterrompido')
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

export function carregarOrdensIniciadas(container, filtros={}) {
    
    // 1. Armazena snapshot atual
    const cardsAtuais = {};
    container.querySelectorAll('[data-ordem-id]').forEach(card => {
        cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    });
    
    fetch(`api/ordens-iniciadas/?page=1&limit=100&ordem=${filtros.ordem || ''}&mp=${filtros.mp || ''}&peca=${filtros.peca || ''}`)

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

            // Adicional: Verifica se não há ordens ou o número de ordens mudou
            if (data.ordens.length === 0 || Object.keys(cardsAtuais).length !== data.ordens.length) {
                houveMudanca = true;
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
                card.dataset.ordemId = ordem.ordem;
                card.dataset.ultimaAtualizacao = ultimaAtualizacao;

                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

                if (ordem.status_atual === 'iniciada') {
                    botaoAcao = `
                        <div class="d-flex flex-wrap justify-content-center">
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
                        </div>
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
                        <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
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
                            <i class="fa fa-eye"></i> Ver / Editar Peças 
                        </button>
                        <div class="d-flex gap-2">
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
                        mostrarPecas(ordem.id, ordem.grupo_maquina);
                    });
                }

                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', () => {
                        mostrarModalRetornarOrdemIniciada(ordem.id);
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
                        atualizarStatusOrdem(ordem.id, ordem.grupo_maquina, 'finalizada');
                    });
                }
                
                removerCardDeOutrosContainers(ordem.ordem, container);

                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao);

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
}

export function carregarOrdensInterrompidas(container, filtros={}) {
    
    // container.innerHTML = `
    // <div class="spinner-border text-dark" role="status">
    //     <span class="sr-only">Loading...</span>
    // </div>`;

    // 1. Armazena snapshot atual
    const cardsAtuais = {};
    container.querySelectorAll('[data-ordem-id]').forEach(card => {
        cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    });

    // Fetch para buscar ordens interrompidas
    fetch(`api/ordens-interrompidas/?page=1&limit=100&ordem=${filtros.ordem || ''}&mp=${filtros.mp || ''}&peca=${filtros.peca || ''}`)
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

                const card = document.createElement('div');
                card.dataset.ordemId = ordem.ordem;
                card.dataset.ultimaAtualizacao = ultimaAtualizacao;

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
                            <h6 class="card-title mb-0">#${ordem.ordem} - ${ordem.maquina}</h6>
                            <small class="text-white">Motivo: ${ordem.motivo_interrupcao || 'Sem motivo'}</small>
                        </div>
                        <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                            id="contador-${ordem.ordem}" 
                            style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                            Carregando...
                        </span>
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
                        <div class="d-flex flex-wrap justify-content-center gap-2">
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
                        mostrarPecas(ordem.id, ordem.grupo_maquina);
                    });
                }

                // Evento para "Retornar"
                if (buttonRetornar) {
                    buttonRetornar.addEventListener('click', () => {
                        mostrarModalIniciar(ordem.id, ordem.grupo_maquina);
                    });
                }

                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', function() {
                        mostrarModalRetornarOrdemIniciada(ordem.id);
                    });
                }
                
                removerCardDeOutrosContainers(ordem.ordem, container);

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
    const filtroDataProgramada = document.getElementById('filtro-data-programada');

    const currentFiltros = {
        ordem: filtros.ordem || filtroOrdem.value.trim(),
        mp: filtros.mp || filtroMp.value.trim(),
        status: filtros.status || filtroStatus.value.trim(),
        peca: filtros.peca || filtroPeca.value.trim(),
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
    limparSelecaoOrdens();
    fetchOrdens();

    // Configurar o botão "Carregar Mais"
    loadMoreButton.onclick = () => {
        loadMoreButton.disabled = true;
        loadMoreButton.innerHTML = `                    
            <div class="spinner-border text-dark" role="status">
                <span class="sr-only">Loading...</span>
            </div>
        `;

        fetchOrdens(); // Carrega a próxima página ao clicar no botão
    };
}

// Função para exibir as peças no modal
function mostrarPecas(ordemId, maquinaName, mostrarDescricao = false) {
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
            Swal.close();
            console.log(data);
            if (data.pecas.length === 0) {
                modalContent.innerHTML = `<p class="text-center text-muted">Não há peças cadastradas para esta ordem.</p>`;
            } else {
                let descricaoHTML = '';
                
                if (mostrarDescricao && data.propriedades && data.propriedades.descricao_mp) {
                    descricaoHTML = `
                        <div class="mb-3">
                            <table class="table table-bordered table-sm">
                                <tbody>
                                    <tr>
                                        <th class="table-light d-flex justify-content-center text-center">Matéria-Prima</th>
                                        <td>${data.propriedades.descricao_mp}</td>
                                    </tr>
                                    ${data.propriedades.codigo_mp ? `
                                    <tr>
                                        <th class="table-light">Código</th>
                                        <td>${data.propriedades.codigo_mp}</td>
                                    </tr>
                                    ` : ''}
                                    ${data.propriedades.quantidade_mp ? `
                                    <tr>
                                        <th class="table-light">Quantidade</th>
                                        <td>${data.propriedades.quantidade_mp}</td>
                                    </tr>
                                    ` : ''}
                                </tbody>
                            </table>
                        </div>
                    `;
                }

                modalContent.innerHTML = `
                <h5 class="text-center">Peças da Ordem ${ordemId}</h5>
                    ${descricaoHTML}
                    <table class="table table-bordered table-sm text-center">
                        <thead>
                            <tr class="table-light">
                                <th>Peça</th>
                                <th>Quantidade</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody id="tabelaPecas">
                            ${data.pecas.map((peca) => `
                                <tr id="linha-${peca.id_peca}">
                                    <td>
                                        <a href="https://drive.google.com/drive/u/0/search?q=${peca.peca_codigo}" target="_blank" rel="noopener noreferrer">
                                            ${peca.peca_nome}
                                        </a>
                                    </td>
                                    <td>${peca.quantidade}</td>
                                    <td>
                                        <button class="btn btn-danger btn-sm btn-excluir-peca" data-index="${peca.id_peca}">
                                            🗑 Excluir
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    ${data.ordem_status !== 'finalizada' ? `
                    <div class="text-end mt-2">
                        <button class="btn btn-primary btn-sm" id="btnAdicionarPeca">
                            <i class="fas fa-plus"></i> Adicionar Peça
                        </button>
                    </div>
                    ` : ''}
                    ${(mostrarDescricao && data.propriedades && data.propriedades.descricao_mp) ? `
                    <div class="modal-footer text-end mt-3">
                        <button id="btnIniciarOrdem" class="btn btn-success">
                            <i class="fas fa-play-circle"></i> Iniciar
                        </button>
                    </div>
                    ` : ''}
                `;

                // Adiciona o evento de clique para o botão de adicionar peça
                const btnAdicionar = document.getElementById('btnAdicionarPeca');
                if (btnAdicionar) {
                    btnAdicionar.addEventListener('click', function() {
                        const tabelaPecas = document.getElementById('tabelaPecas');
                        
                        // Cria um ID temporário único para a nova linha
                        const tempId = 'temp-' + Date.now();
                        
                        // Prepara as opções do select baseadas nas peças existentes
                        const optionsPecas = data.pecas.map(peca => 
                            `<option value="${peca.id_peca}">${peca.peca_nome} (${peca.peca_codigo})</option>`
                        ).join('');
                        
                        // Adiciona a nova linha no final da tabela com um select
                        const novaRow = `
                            <tr id="${tempId}">
                                <td>
                                    <select class="form-select form-select-sm select2-peca" id="selectPeca-${tempId}" style="width: 100%">
                                        <option value="" selected disabled>Selecione uma peça</option>
                                    </select>
                                </td>
                                <td>
                                    <input type="number" class="form-control form-control-sm" placeholder="Quantidade" min="1" value="1">
                                </td>
                                <td>
                                    <div class="d-flex gap-1 justify-content-center">
                                        <button class="btn btn-danger btn-sm btn-cancelar-peca" data-temp-id="${tempId}">
                                            Cancelar
                                        </button>
                                        <button class="btn btn-success btn-sm btn-salvar-peca" data-temp-id="${tempId}">
                                            Salvar
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        `;
                        
                        tabelaPecas.insertAdjacentHTML('beforeend', novaRow);
                        
                        // Inicializa o Select2 para o novo select
                        $(`#selectPeca-${tempId}`).select2({
                            placeholder: 'Selecione a Peça',
                            width: '100%',
                            theme: 'bootstrap-5',
                            dropdownParent: $('#modalPecas .modal-content'),
                            ajax: {
                                url: 'api/get-peca/',
                                dataType: 'json',
                                delay: 250,
                                data: function(params) {
                                    return {
                                        search: params.term || '',
                                        page: params.page || 1,
                                        per_page: 10
                                    };
                                },
                                processResults: function(data, params) {
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
                            minimumInputLength: 0
                        });


                        // Rola a tabela para mostrar a nova linha
                        document.querySelector(`#${tempId}`).scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    });
                };
            }
            
            const modal = new bootstrap.Modal(document.getElementById('modalPecas'));
            modal.show();


            if (mostrarDescricao && data.propriedades && data.propriedades.descricao_mp) {
                document.getElementById('btnIniciarOrdem').addEventListener('click', () => {
                    mostrarModalIniciar(ordemId, maquinaName);
                    const modalPecas = bootstrap.Modal.getInstance(document.getElementById("modalPecas"));
                    modalPecas.hide();
                });
            }
            
            document.getElementById('tabelaPecas').addEventListener('click', function (event) {
                const button = event.target.closest('.btn-excluir-peca');
                if (button) {
                    const index = button.getAttribute('data-index');
                    excluirPeca(index, ordemId);
                }
            });
        })
        .catch(error => {
            Swal.close();
            console.error('Erro ao buscar peças:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: 'Erro ao carregar as peças. Por favor, tente novamente.',
            });
        });

        modalContent.onclick = function(event) {
            const target = event.target;

            // --- Ação: Cancelar Peça ---
            const btnCancelar = target.closest('.btn-cancelar-peca');
            if (btnCancelar) {
                const tempId = btnCancelar.getAttribute('data-temp-id');
                const linhaParaRemover = document.getElementById(tempId);
                if (linhaParaRemover) {
                    linhaParaRemover.remove();
                }
                return; // Encerra a execução
            }

            // --- Ação: Salvar Peça ---
            const btnSalvar = target.closest('.btn-salvar-peca');
            if (btnSalvar) {
                const tempId = target.getAttribute('data-temp-id');
                const row = document.getElementById(tempId);
                // Exibe SweetAlert de carregamento
                Swal.fire({
                    title: 'Carregando...',
                    text: 'Salvando peça nova...',
                    allowOutsideClick: false,
                    didOpen: () => {
                        Swal.showLoading();
                    }
                });
                
                // Obtém os valores dos campos
                const selectPeca = $(`#selectPeca-${tempId}`);
                const pecaId = selectPeca.val();
                const pecaText = selectPeca.find('option:selected').text();
                const quantidade = row.querySelector('input[type="number"]').value;
                
                if (!pecaId) {
                    Swal.fire('Erro', 'Por favor, selecione uma peça', 'error');
                    return;
                }


                const Toast = Swal.mixin({
                    toast: true,
                    position: "bottom-end",
                    showConfirmButton: false,
                    timer: 3000,
                    timerProgressBar: true,
                    didOpen: (toast) => {
                    toast.onmouseenter = Swal.stopTimer;
                    toast.onmouseleave = Swal.resumeTimer;
                    }
                });

                // Requisição POST para o backend
                fetch('api/adicionar-peca-ordem/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCSRFToken() // Se estiver usando Django
                    },
                    body: JSON.stringify({
                        ordem_id: ordemId, // Usando a variável ordemId que já está no escopo
                        peca: pecaId,
                        quantidade: quantidade
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Erro ao salvar peça');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        Swal.close();
                        
                        Toast.fire({
                            icon: "success",
                            title: "Peça adicionada com sucesso."
                        });
                        
                        // Remove a linha temporária
                        const linhaParaRemover = document.getElementById(tempId);
                        if (linhaParaRemover) {
                            linhaParaRemover.remove();
                        }
                        
                        // Adiciona a nova peça diretamente na tabela
                        const tabelaPecas = document.getElementById('tabelaPecas');
                        const novaPecaHTML = `
                            <tr id="linha-${data.peca.id_peca}">
                                <td>
                                    <a href="https://drive.google.com/drive/u/0/search?q=${data.peca.peca_codigo}" target="_blank" rel="noopener noreferrer">
                                        ${data.peca.peca_nome}
                                    </a>
                                </td>
                                <td>${data.peca.quantidade}</td>
                                <td>
                                    <button class="btn btn-danger btn-sm btn-excluir-peca" data-index="${data.peca.id_peca}">
                                        🗑 Excluir
                                    </button>
                                </td>
                            </tr>
                        `;
                        
                        tabelaPecas.insertAdjacentHTML('beforeend', novaPecaHTML);

                    } else {
                        throw new Error(data.message || 'Erro ao processar resposta');
                    }
                })
                .catch(error => {
                    Toast.fire({
                        icon: "error",
                        title: error.message
                    });
                    console.error('Erro:', error);
                });
            }
        }
}

// Função para excluir uma peça (mantendo ao menos uma)
function excluirPeca(index, ordemId) {
    const tabela = document.getElementById('tabelaPecas');
    
    // Verifica se há apenas uma peça na tabela (mantendo pelo menos uma)
    if (tabela.rows.length <= 1) { // 1 cabeçalho + pelo menos 1 peça
        Swal.fire({
            icon: 'warning',
            title: 'Atenção!',
            text: 'A ordem deve ter pelo menos uma peça.',
        });
        return;
    }

    Swal.fire({
        title: 'Tem certeza?',
        text: 'Você deseja excluir esta peça?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sim, excluir!',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            // Chama a API para excluir a peça no backend
            fetch('api/excluir-peca-ordem/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ordem_id: ordemId, index: index }) // Envia os dados corretamente
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    // Remove a linha da tabela apenas se a API confirmar exclusão
                    const linha = document.getElementById(`linha-${index}`);
                    if (linha) linha.remove();

                    Swal.fire({
                        icon: 'success',
                        title: 'Peça excluída!',
                        text: 'A peça foi removida com sucesso.',
                        timer: 2000,
                        showConfirmButton: false
                    });

                    const containerIniciado = document.querySelector('.containerProcesso');
                    carregarOrdensIniciadas(containerIniciado);

                    const containerInterrompido = document.querySelector('.containerInterrompido');
                    carregarOrdensInterrompidas(containerInterrompido);
        
                    document.getElementById('ordens-container').innerHTML = '';
                    resetarCardsInicial();

                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Erro!',
                        text: data.message,
                    });
                }
            })
            .catch(error => {
                console.error('Erro ao excluir peça:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Erro!',
                    text: 'Ocorreu um erro ao comunicar com o servidor.',
                });
            });
        }
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

        const card = document.querySelector(`[data-ordem-id="${ordemId}"]`);
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

            const containerIniciado = document.querySelector('.containerProcesso');
            const containerInterrompido = document.querySelector('.containerInterrompido');

            // Atualiza os containers com lógica interna de limpeza e comparação
            carregarOrdensIniciadas(containerIniciado);
            carregarOrdensInterrompidas(containerInterrompido);

            // Limpa cards auxiliares e recarrega outros dados
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
    const textoAjuda = document.getElementById('modalExcluirDescricao');

    modalTitle.innerHTML = `Excluir Ordem ${ordemId}`;
    if (textoAjuda) {
        textoAjuda.textContent = 'Selecione o motivo para excluir esta ordem.';
    }
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

function mostrarModalExcluirEmLote(ordensIds, setor) {
    const modal = new bootstrap.Modal(document.getElementById('modalExcluir'));
    const modalTitle = document.getElementById('modalExcluirLabel');
    const formExcluir = document.getElementById('formExcluir');
    const textoAjuda = document.getElementById('modalExcluirDescricao');
    const totalOrdens = ordensIds.length;

    modalTitle.innerHTML = `Excluir ${totalOrdens} ordens`;

    if (textoAjuda) {
        textoAjuda.textContent = 'Selecione o motivo para excluir todas as ordens marcadas.';
    }

    modal.show();

    const clonedForm = formExcluir.cloneNode(true);
    formExcluir.parentNode.replaceChild(clonedForm, formExcluir);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);
        const motivoExclusao = formData.get('motivoExclusao');

        Swal.fire({
            title: 'Excluindo...',
            text: 'Por favor, aguarde enquanto as ordens estão sendo excluídas.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        excluirOrdens(ordensIds, setor, motivoExclusao)
            .then(() => {
                limparSelecaoOrdens();

                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso',
                    text: `${totalOrdens} ordens excluídas com sucesso.`,
                });

                modal.hide();
                document.getElementById('ordens-container').innerHTML = '';
                resetarCardsInicial();
            })
            .catch((error) => {
                console.error('Erro:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: error.message || 'Ocorreu um erro inesperado. Tente novamente mais tarde.',
                });
            });
    });
}

function inicializarExclusaoEmLote() {
    const botaoExcluirLote = document.getElementById('btnExcluirSelecionadas');
    const selecionarPagina = document.getElementById('selecionar-todas-ordens');

    if (botaoExcluirLote) {
        botaoExcluirLote.addEventListener('click', () => {
            const ordensIds = Array.from(ordensSelecionadas);

            if (ordensIds.length === 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Selecione ao menos uma ordem',
                    text: 'Marque uma ou mais ordens para excluir em lote.',
                });
                return;
            }

            mostrarModalExcluirEmLote(ordensIds, 'serra');
        });
    }

    if (selecionarPagina) {
        selecionarPagina.addEventListener('change', ({ target }) => {
            document.querySelectorAll('.ordem-checkbox').forEach((checkbox) => {
                if (checkbox.disabled) {
                    checkbox.checked = false;
                    ordensSelecionadas.delete(String(checkbox.value));
                    return;
                }

                checkbox.checked = target.checked;
                const ordemId = String(checkbox.value);

                if (target.checked) {
                    ordensSelecionadas.add(ordemId);
                } else {
                    ordensSelecionadas.delete(ordemId);
                }
            });

            atualizarResumoSelecao();
        });
    }

    atualizarResumoSelecao();
}

// Modal para "Duplicar"
function mostrarModalDuplicar(ordemId){

    const modal = new bootstrap.Modal(document.getElementById('modalDuplicar'));
    const modalTitle = document.getElementById('modalDuplicarLabel');
    const formDuplicar = document.getElementById('formDuplicar');

    modalTitle.innerHTML = `Confirmar`;
    modal.show();

    // Remove listeners antigos e adiciona novo
    const clonedForm = formDuplicar.cloneNode(true);
    formDuplicar.parentNode.replaceChild(clonedForm, formDuplicar);

    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const formData = new FormData(clonedForm);

        Swal.fire({
            title: 'Duplicando...',
            text: 'Por favor, aguarde enquanto a ordem está sendo duplicada.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch(`api/duplicar-ordem/`, {
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
                resetarCardsInicial();
            } else {
                // Exibe o erro vindo do backend
                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: body.error || 'Erro ao duplicar a ordem.',
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
function mostrarModalIniciar(ordemId, grupoMaquina, maquinaPreferidaId = null) {

    const modal = new bootstrap.Modal(document.getElementById('modalIniciar'));
    const modalTitle = document.getElementById('modalIniciarLabel');

    modalTitle.innerHTML = `Iniciar Ordem ${ordemId}`;

    // Exibe SweetAlert de carregamento
    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das peças...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    const card = document.querySelector(`[data-ordem-id="${ordemId}"]`);
    if (card) card.remove();

    fetch('/cadastro/api/buscar-maquinas/?setor=serra', {
        method: 'GET',
        headers: {'Content-Type':'application/json'}
    })
    .then(response => response.json())
    .then(
        data => {
            const escolhaMaquina = document.getElementById('escolhaMaquinaIniciarOrdem');
            escolhaMaquina.innerHTML = `<option value="">------</option>`;

            Swal.close();
            data.maquinas.forEach((maquina) => {
                const option = document.createElement('option');
                option.value = maquina.id;
                option.textContent = maquina.nome;
                escolhaMaquina.appendChild(option);
            })
            if (maquinaPreferidaId) {
                escolhaMaquina.value = String(maquinaPreferidaId);
            }
            modal.show();
        }
    )

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

                const containerInterrompido = document.querySelector('.containerInterrompido');
                carregarOrdensInterrompidas(containerInterrompido);

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

    document.getElementById('obsFinalizar').value = '';

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
                                            data-qtd-original="${peca.quantidade}"
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

            const inputQtdMp = document.getElementById('propQtd');
            const qtdMpOriginal = parseFloat(inputQtdMp?.dataset.qtdVara) || 0;
            const pecasInputs = document.querySelectorAll('.peca-quantidade');

            const atualizarQuantidadesPecas = () => {
                const qtdMpAtual = parseFloat(inputQtdMp.value) || 0;
                if (!qtdMpOriginal || !qtdMpAtual) {
                    return;
                }

                const fator = qtdMpAtual / qtdMpOriginal;
                pecasInputs.forEach((input) => {
                    const qtdOriginal = parseFloat(input.dataset.qtdOriginal) || 0;
                    const novaQuantidade = qtdOriginal * fator;
                    input.value = Number.isInteger(novaQuantidade)
                        ? novaQuantidade
                        : parseFloat(novaQuantidade.toFixed(2));
                });
            };

            if (inputQtdMp) {
                inputQtdMp.addEventListener('input', atualizarQuantidadesPecas);
                inputQtdMp.addEventListener('change', atualizarQuantidadesPecas);
            }

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

    const modalConfirmFinalizarEl = document.getElementById('modalConfirmFinalizar');
    const modalConfirmFinalizar = modalConfirmFinalizarEl ? new bootstrap.Modal(modalConfirmFinalizarEl) : null;
    let confirmModalHandlersBound = false;

    const montarResumoFinalizacao = () => {
        const resumoEl = document.getElementById('resumoFinalizacao');
        if (!resumoEl) {
            return;
        }

        const qtdVaras = document.getElementById('propQtd')?.value || '-';
        const tamanhoVara = document.getElementById('tamanhoVaraInput')?.value || '-';
        const mpSelect = document.getElementById('selectMpSerraAlterar');
        const mpTexto = mpSelect ? mpSelect.options[mpSelect.selectedIndex]?.textContent || '-' : '-';

        const pecas = Array.from(document.querySelectorAll('.peca-quantidade')).map((input) => {
            const row = input.closest('tr');
            const nome = row?.querySelector('td')?.textContent?.trim() || '-';
            return { nome, quantidade: input.value || 0 };
        });

        const pecasHtml = pecas.length
            ? `<ul class="mb-0">${pecas
                  .map((peca) => `<li>${peca.nome}: ${peca.quantidade}</li>`)
                  .join('')}</ul>`
            : '<p class="mb-0 text-muted">Nenhuma peça informada.</p>';

        resumoEl.innerHTML = `
            <div class="mb-2"><strong>Materia-prima:</strong> ${mpTexto}</div>
            <div class="mb-2"><strong>Tamanho:</strong> ${tamanhoVara}</div>
            <div class="mb-2"><strong>Quantidade de varas:</strong> ${qtdVaras}</div>
            <div><strong>Peças:</strong>${pecasHtml}</div>
        `;
    };

    const enviarFinalizacao = (payload) => {
        if (modalConfirmFinalizar) {
            modalConfirmFinalizar.hide();
        }

        Swal.fire({
            title: 'Finalizando...',
            text: 'Por favor, aguarde...',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch(`api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
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
        .then((data) => {
            const numeroNovaOrdem = data.nova_ordem_numero || data.nova_ordem_id;
            const mensagemParcial = data.nova_ordem_id
                ? `Ordem finalizada parcialmente. Nova ordem #${numeroNovaOrdem} criada.`
                : 'Ordem finalizada com sucesso.';

            const mostrarPromptIniciarRestante = () => {
                if (!data.nova_ordem_id) {
                    return;
                }

                Swal.fire({
                    icon: 'question',
                    title: 'Deseja iniciar o restante?',
                    text: `Nova ordem #${numeroNovaOrdem} pronta para iniciar.`,
                    showCancelButton: true,
                    confirmButtonText: 'Iniciar restante agora',
                    cancelButtonText: 'Depois',
                }).then((result) => {
                    if (result.isConfirmed) {
                        mostrarModalIniciar(data.nova_ordem_id, grupoMaquina, data.maquina_id);
                    }
                });
            };

            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: mensagemParcial,
            }).then(() => {
                mostrarPromptIniciarRestante();
            });
            
            const containerIniciado = document.querySelector('.containerProcesso');
            carregarOrdensIniciadas(containerIniciado);
            
            document.getElementById('ordens-container').innerHTML = '';
            resetarCardsInicial();

            fetchStatusMaquinas();
            fetchUltimasPecasProduzidas();
            fetchContagemStatusOrdens();

            modal.hide();

            formFinalizar.reset();
        })
        .catch((error) => {
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: error.message,
            });
        });
    };

    // Listener para submissão do formulário
    clonedForm.addEventListener('submit', (event) => {
        event.preventDefault();

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

        const payloadBase = {
            ordem_id: ordemId,
            grupo_maquina: grupoMaquina,
            status: 'finalizada',
            pecas_mortas: pecasMortas,
            qtd_vara: qtdVaras,
            tamanho_vara: tamanhoVara,
            operador_final: operadorFinal,
            obs_finalizar: obsFinalizar,
            mp_final: mp_final,
        };

        montarResumoFinalizacao();

        if (!modalConfirmFinalizar) {
            enviarFinalizacao({ ...payloadBase, finalizar_parcial: false });
            return;
        }

        let btnCompleto = document.getElementById('btnFinalizarCompleto');
        let btnParcial = document.getElementById('btnFinalizarParcial');

        if (btnCompleto && btnParcial) {
            const btnCompletoClone = btnCompleto.cloneNode(true);
            btnCompleto.parentNode.replaceChild(btnCompletoClone, btnCompleto);
            btnCompleto = btnCompletoClone;

            const btnParcialClone = btnParcial.cloneNode(true);
            btnParcial.parentNode.replaceChild(btnParcialClone, btnParcial);
            btnParcial = btnParcialClone;

            btnCompleto.addEventListener('click', () => {
                enviarFinalizacao({ ...payloadBase, finalizar_parcial: false });
            });

            btnParcial.addEventListener('click', () => {
                enviarFinalizacao({ ...payloadBase, finalizar_parcial: true });
            });
        }

        if (modalConfirmFinalizar && !confirmModalHandlersBound) {
            confirmModalHandlersBound = true;

            modalConfirmFinalizarEl.addEventListener('shown.bs.modal', () => {
                const backdrops = document.querySelectorAll('.modal-backdrop');
                const ultimoBackdrop = backdrops[backdrops.length - 1];
                if (ultimoBackdrop) {
                    ultimoBackdrop.classList.add('modal-backdrop-confirm-finalizar');
                    ultimoBackdrop.style.zIndex = '1055';
                }
                modalConfirmFinalizarEl.style.zIndex = '1056';
            });
        }

        modalConfirmFinalizar.show();
    });
}

// Modal para "Retornar"
function mostrarModalRetornar(ordemId, grupoMaquina, maquina) {

    // const maquinaTratada = maquina.toLowerCase().replace(" ","_");

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
            <select id="pecaEscolhida_${index}" class="form-select pecasCriarOrdem" name="pecaEscolhida_${index}" required>
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
        verificarOrdemCriada();
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
            status: document.getElementById('filtro-status').value.trim(),
            mp: document.getElementById('filtro-mp').value.trim(),
            peca: document.getElementById('filtro-peca').value.trim(),

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

function inicializarEventosOrdem() {

    $('#mpEscolhida').on('change.select2', function () {
        verificarOrdemCriada();
    });

    // Evento para todos os Select2 de peças
    $(document).on('change', '.pecasCriarOrdem', function () {
        verificarOrdemCriada();
    });

}

function verificarOrdemCriada() {
    const mpEscolhida = document.getElementById("mpEscolhida")?.value;
    const pecasCriarOrdemElements = document.querySelectorAll(".pecasCriarOrdem");
    const alertOp = document.getElementById("alert-op");
    
    // Resetar alerta
    alertOp.style.display = "none";
    alertOp.innerHTML = "";

    const pecas = Array.from(pecasCriarOrdemElements)
                      .map(el => el.value)
                      .filter(value => value.trim() !== "");

    const data = {
        mp: mpEscolhida,
        pecas: pecas,
    };

    fetch('api/verificar-dados-ordem/', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        console.log(data)
        if (data.status === "success") {
            alertOp.style.display = "block";

            const link = document.createElement('a');
            link.className = 'alert-link';
            link.style.cursor = 'pointer';
            link.textContent = `OP #${data.ordem}`;
            link.addEventListener('click', () => {
                mostrarPecas(data.id_ordem, data.grupo_maquina, true);
                const modalSerra = bootstrap.Modal.getInstance(document.getElementById("modalSerra"));
                modalSerra.hide();
            });
            
            alertOp.innerHTML = 'Os dados preenchidos já foram criados na ';
            alertOp.appendChild(link);
        } 
    })
    .catch(error => {
        console.error('Erro:', error);
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        resetarCardsInicial();

        // Inicializa carregamento de ordens simultaneamente
        const containerIniciado = document.querySelector('.containerProcesso');
        const containerInterrompido = document.querySelector('.containerInterrompido');

        if (containerIniciado) carregarOrdensIniciadas(containerIniciado);
        if (containerInterrompido) carregarOrdensInterrompidas(containerInterrompido);

        // Adiciona evento ao botão "Add" se ele existir
        const addPecaBtn = document.getElementById("addPeca");
        if (addPecaBtn) {
            addPecaBtn.addEventListener("click", addPeca);
        }

        // Configuração do Select2 para diferentes campos
        configurarSelect2('#mpEscolhida', 'api/get-mp/', '#modalSerra');
        configurarSelect2('#pecaEscolhida_0', 'api/get-peca/', '#containerPecas');
        configurarSelect2('#filtro-mp', 'api/get-mp/', null, true);
        configurarSelect2('#filtro-peca', 'api/get-peca/', null, true);

        inicializarEventosOrdem();
        inicializarExclusaoEmLote();
        criarOrdem();
        filtro();
        importarOrdensSerra();

        if (containerIniciado) {
            carregarOrdensIniciadas(containerIniciado);
        }

        if (containerInterrompido) {
            carregarOrdensInterrompidas(containerInterrompido);
        }

        // Atualização periódica para ambos (se existirem)
        // setInterval(() => {
        //     if (containerIniciado) {
        //         carregarOrdensIniciadas(containerIniciado);
        //     }
        //     if (containerInterrompido) {
        //         carregarOrdensInterrompidas(containerInterrompido);
        //     }
        // }, 30000);
        
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

