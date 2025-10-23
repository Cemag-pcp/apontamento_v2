import { fetchStatusMaquinas, fetchUltimasPecasProduzidas, fetchContagemStatusOrdens } from './status-maquina-usinagem.js';

export const loadOrdens = (container, page = 1, limit = 10, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => { // Retorna uma Promise
        if (isLoading) return resolve({ ordens: [] }); // Evita chamadas duplicadas
        isLoading = true;

        fetch(`/usinagem/api/ordens-criadas/?page=${page}&limit=${limit}&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&status=${filtros.status || ''}&data-programada=${filtros.data_programada || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;

                if (ordens.length > 0) {

                    ordens.forEach(ordem => {
                        const card = document.createElement('div');
                        card.classList.add('col-md-4'); // Adiciona a classe de coluna

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
                                <button class="btn btn-sm btn-proximo-processo" title="Passar para o próximo processo">
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

                                <button class="btn btn-danger btn-sm btn-excluir" title="Excluir">
                                    <i class="fa fa-trash"></i>
                                </button>
                                
                            `;
                        } else if (ordem.status_atual === 'agua_prox_proc') {
                            botaoAcao = `
                                <button class="btn btn-warning btn-sm btn-iniciar-proximo-processo" title="Iniciar próximo processo">
                                    <i class="fa fa-play"></i>
                                </button>
                                <button class="btn btn-danger btn-sm btn-excluir" title="Excluir">
                                    <i class="fa fa-trash"></i>
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
                                <p class="text-muted mb-2" style="font-size: 0.85rem;">
                                Programada para: ${ordem.data_programacao} | Qt.: ${
                                    Number(ordem.peca.quantidade_boa) === 0
                                    ? ordem.peca.quantidade
                                    : ordem.peca.quantidade_boa
                                }
                                </p>
                                ${ordem.status_atual === 'finalizada' 
                                    ? `<p class="text-success fw-semibold mb-2" style="font-size: 0.85rem;">Finalizada em: ${ordem.ultima_atualizacao}</p>` 
                                    : ''
                                }                                
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
                        const buttonFinalizarParcial = card.querySelector('.btn-finalizar-parcial')
                        const buttonExcluir= card.querySelector('.btn-excluir');

                        // Adiciona evento ao botão "Iniciar", se existir
                        if (buttonIniciar) {
                            buttonIniciar.addEventListener('click', () => {
                                mostrarModalIniciar(ordem.id, ordem.maquina_id);
                            });
                        }

                        // Adiciona evento ao botão "Interromper", se existir
                        if (buttonInterromper) {
                            buttonInterromper.addEventListener('click', () => {
                                mostrarModalInterromper(ordem.id, ordem.maquina_id, ordem.ordem);
                            });
                        }

                        // Adiciona evento ao botão "Finalizar", se existir
                        if (buttonFinalizar) {
                            buttonFinalizar.addEventListener('click', () => {
                                mostrarModalFinalizar(ordem.id, ordem.ordem);
                            });
                        }

                        // Adiciona evento ao botão "Retornar", se existir
                        if (buttonRetornar) {
                            buttonRetornar.addEventListener('click', () => {
                                mostrarModalRetornar(ordem.id, ordem.maquina_id);
                            });
                        }

                        // Adiciona evento ao botão para iniciar proximo processo
                        if (buttonProxProcesso) {
                            buttonProxProcesso.addEventListener('click', () => {
                                mostrarModalIniciarProxProcesso(ordem.id, ordem.maquina_id);
                            });
                        }

                        // Adiciona evento ao botão para enviar para proximo processo
                        if (buttonMandarProxProcesso) {
                            buttonMandarProxProcesso.addEventListener('click', () => {
                                mostrarModalProxProcesso(ordem.id, ordem.maquina_id);
                            });
                        }

                        // Adiciona evento ao botão para enviar para proximo processo
                        if (buttonFinalizarParcial) {
                            buttonFinalizarParcial.addEventListener('click', () => {
                                mostrarModalFinalizarParcial(ordem.id, ordem.ordem);
                            });
                        }

                        // Adiciona evento ao botão "Excluir", se existir
                        if (buttonExcluir) {
                            buttonExcluir.addEventListener('click', () => {
                                mostrarModalExcluir(ordem.id, 'usinagem');
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
                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso',
                    text: data.message || 'Ordem retornada para "Aguardando Iniciar".',
                });
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

                const containerInterrompido = document.querySelector('.containerInterrompido');
                carregarOrdensInterrompidas(containerInterrompido);

                // Atualiza a interface
                const containerProxProcesso = document.querySelector('.containerProxProcesso')
                carregarOrdensAgProProcesso(containerProxProcesso);

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

export function carregarOrdensIniciadas(container, filtros = {}) {
    
    // 1. Armazena snapshot atual
    // const cardsAtuais = {};
    // container.querySelectorAll('[data-ordem-id]').forEach(card => {
    //     cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    // });

    fetch(`/usinagem/api/ordens-iniciadas/?page=1&limit=100&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&processo=${filtros.processo || ''}`)
        .then(response => response.json())
        .then(data => {

            // let houveMudanca = false;
            
            // 2. Verifica se houve alguma alteração
            // for (const ordem of data.ordens) {
            //     const ultimaNova = new Date(ordem.ultima_atualizacao).getTime();
            //     const ultimaAnterior = cardsAtuais[ordem.ordem];
                
            //     if (!ultimaAnterior || ultimaNova !== ultimaAnterior) {
            //         houveMudanca = true;
            //         break;
            //     }
            // }

            // 3. Se não mudou nada, sai
            // if (!houveMudanca) return;

            // 4. Mostra o spinner  
            // container.innerHTML = `
            //     <div class="spinner-border text-dark" role="status">
            //         <span class="sr-only">Loading...</span>
            //     </div>`;

            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {

                const card = document.createElement('div');
                card.classList.add("col-xl-6");
                card.classList.add("col-md-12");
                card.dataset.ordemId = ordem.id;

                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

                botaoAcao = `
                    <button class="btn btn-danger btn-sm btn-interromper" title="Interromper">
                        <i class="fa fa-stop"></i>
                    </button>
                    <button class="btn btn-success btn-sm btn-finalizar" title="Finalizar">
                        <i class="fa fa-check"></i>
                    </button>
                    <button class="btn btn-sm btn-proximo-processo" title="Passar para o próximo processo">
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
                        <small class="text-white">Planejada: ${totalQtdPlanejada || 0} Realizada: ${totalQtdBoa}</small>
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
                        <div class="d-flex gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                const buttonInterromper = card.querySelector('.btn-interromper');
                const buttonFinalizar = card.querySelector('.btn-finalizar');
                const buttonProxProcesso = card.querySelector('.btn-proximo-processo');
                const buttonFinalizarParcial = card.querySelector('.btn-finalizar-parcial')

                // Adiciona evento ao botão "Interromper", se existir
                if (buttonInterromper) {
                    buttonInterromper.addEventListener('click', () => {
                        mostrarModalInterromper(ordem.id, ordem.maquina_id, ordem.ordem);
                    });
                }

                // Adiciona evento ao botão "Finalizar", se existir
                if (buttonFinalizar) {
                    buttonFinalizar.addEventListener('click', () => {
                        mostrarModalFinalizar(ordem.id, ordem.ordem);
                    });
                }

                if (buttonProxProcesso) {
                    buttonProxProcesso.addEventListener('click', () => {
                        mostrarModalProxProcesso(ordem.id, ordem.maquina_id);
                    });
                }

                if (buttonFinalizarParcial) {
                    buttonFinalizarParcial.addEventListener('click', () => {
                        mostrarModalFinalizarParcial(ordem.id, ordem.ordem);
                    });
                }

                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
}

export function carregarOrdensInterrompidas(container, filtros = {}) {
    // container.innerHTML = `
    // <div class="spinner-border text-dark" role="status">
    //     <span class="sr-only">Loading...</span>
    // </div>`;
    // const cardsAtuais = {};
    // container.querySelectorAll('[data-ordem-id]').forEach(card => {
    //     cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    // });

    // Fetch para buscar ordens interrompidas
    fetch(`/usinagem/api/ordens-interrompidas/?page=1&limit=100&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao buscar as ordens interrompidas.');
            }
            return response.json();
        })
        .then(data => {
            // let houveMudanca = false;

            // 2. Verifica se houve alguma alteração
            // for (const ordem of data.ordens) {
            //     const ultimaNova = new Date(ordem.ultima_atualizacao).getTime();
            //     const ultimaAnterior = cardsAtuais[ordem.ordem];

            //     if (!ultimaAnterior || ultimaNova !== ultimaAnterior) {
            //         houveMudanca = true;
            //         break;
            //     }
            // }

            // 3. Se não mudou nada, sai
            // if (!houveMudanca) return;

            // 4. Mostra o spinner  
            // container.innerHTML = `
            // <div class="spinner-border text-dark" role="status">
            //     <span class="sr-only">Loading...</span>
            // </div>`;

            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {
                // Cria o card
                const card = document.createElement('div');
                card.classList.add("col-xl-6");
                card.classList.add("col-md-12");
                card.dataset.ordemId = ordem.id;
            
                // Cria a lista de peças em formato simplificado
                const pecasHTML = ordem.pecas.map(peca => `
                    <a href="https://drive.google.com/drive/u/0/search?q=${peca.codigo}" target="_blank" rel="noopener noreferrer">
                        ${peca.codigo} - ${peca.descricao}
                    </a>
                `).join('<br>');
                    

                // Define os botões dinamicamente
                const botaoAcao = `
                    ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor' || data.usuario_tipo_acesso == 'admin'
                    ? `<button class="btn btn-info btn-sm btn-deletar m-2" data-ordem="${ordem.id}" title="Deletar">
                            <i class="bi bi-arrow-left-right"></i>
                    </button>`: ""} 
                    <button class="btn btn-warning btn-sm btn-retornar m-2" title="Retornar">
                        <i class="fa fa-undo"></i>
                    </button>

                    ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor' || data.usuario_tipo_acesso == 'admin'
                    ? `<button class="btn btn-danger btn-sm btn-excluir m-2" title="Excluir">
                                    <i class="fa fa-trash"></i>
                        </button>`: ""} 
                    
                `;
                // // Botões de ação
                // const botaoAcao = `
                //     <button class="btn btn-warning btn-sm btn-retornar" title="Retornar">
                //         <i class="fa fa-undo"></i>
                //     </button>
                // `;
            
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
                            <div class="d-flex gap-2">
                                ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                            </div>
                        </div>
                    </div>`;
            
                // Adiciona eventos aos botões
                const buttonRetornar = card.querySelector('.btn-retornar');
                if (buttonRetornar) {
                    buttonRetornar.addEventListener('click', () => {
                        mostrarModalRetornar(ordem.id, ordem.maquina_id);
                    });
                }

                const buttonDeletar = card.querySelector('.btn-deletar');
                if (buttonDeletar) {
                    buttonDeletar.addEventListener('click', () => {
                        mostrarModalRetornarOrdemIniciada(ordem.id, 'usinagem');
                    });
                }

                const buttonExcluir= card.querySelector('.btn-excluir');
                if (buttonExcluir) {
                    buttonExcluir.addEventListener('click', () => {
                        mostrarModalExcluir(ordem.id, 'usinagem');
                    });
                }
            
                // Adiciona o card ao container
                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)

            });
        })
        .catch(error => {
            console.error('Erro ao buscar ordens interrompidas:', error);
            container.innerHTML = '<p class="text-danger">Erro ao carregar ordens interrompidas.</p>';
        });
}

export function carregarOrdensAgProProcesso(container, filtros = {}) {
    
    // 1. Armazena snapshot atual
    // const cardsAtuais = {};
    // container.querySelectorAll('[data-ordem-id]').forEach(card => {
    //     cardsAtuais[card.dataset.ordemId] = parseInt(card.dataset.ultimaAtualizacao || 0);
    // });

    fetch(`/usinagem/api/ordens-ag-prox-proc/?page=1&limit=100&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}&processo=${filtros.processo || ''}`)
        .then(response => response.json())
        .then(data => {

            // let houveMudanca = false;

            // 2. Verifica se houve alguma alteração
            // for (const ordem of data.ordens) {
            //     const ultimaNova = new Date(ordem.ultima_atualizacao).getTime();
            //     const ultimaAnterior = cardsAtuais[ordem.ordem];

            //     if (!ultimaAnterior || ultimaNova !== ultimaAnterior) {
            //         houveMudanca = true;
            //         break;
            //     }
            // }

            // 3. Se não mudou nada, sai
            // if (!houveMudanca) return;

            // 4. Mostra o spinner  
            // container.innerHTML = `
            // <div class="spinner-border text-dark" role="status">
            //     <span class="sr-only">Loading...</span>
            // </div>`;

            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {

                const card = document.createElement('div');
                card.classList.add("col-xl-6");
                card.classList.add("col-md-12");
                card.dataset.ordemId = ordem.id;

                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

                botaoAcao = `
                    <button class="btn btn-warning btn-sm btn-iniciar-proximo-processo" title="Iniciar próximo processo">
                        <i class="fa fa-play"></i>
                    </button>
                    
                    ${data.usuario_tipo_acesso == 'pcp' || data.usuario_tipo_acesso == 'supervisor' || data.usuario_tipo_acesso == 'admin'
                    ? `<button class="btn btn-danger btn-sm btn-excluir m-2" title="Excluir">
                                    <i class="fa fa-trash"></i>
                        </button>`: ""} 
                `;

                card.innerHTML = `
                <div class="card shadow-lg bg-prox-processo border-0 rounded-3 mb-3 position-relative">
                    
                    <!-- Contador fixado no topo direito -->
                    <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                        id="contador-${ordem.ordem}" 
                        style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                        Carregando...
                    </span>

                    <div class="card-header text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title mb-0"><small>#${ordem.ordem} - ${ordem.maquina}</small></h6>
                        <small class="text-white">
                            Planejada: ${ordem.totais.qtd_planejada || 0} 
                        </small>
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
                        ${botaoAcao} <!-- Botões dinâmicos -->
                        <span class="text-muted">${ordem.processo_atual}º processo</span>
                    </div>
                </div>`;

                const buttonProxProcesso = card.querySelector('.btn-iniciar-proximo-processo');

                // Adiciona evento ao botão para iniciar proximo processo
                if (buttonProxProcesso) {
                    buttonProxProcesso.addEventListener('click', () => {
                        mostrarModalIniciarProxProcesso(ordem.id, ordem.maquina_id);
                    });
                }

                const buttonExcluir= card.querySelector('.btn-excluir');
                if (buttonExcluir) {
                    buttonExcluir.addEventListener('click', () => {
                        mostrarModalExcluir(ordem.id, 'usinagem');
                    });
                }

                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
}

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// function atualizarStatusOrdem(ordemId, grupoMaquina, status) {
//     switch (status) {
//         case 'iniciada':
//             mostrarModalIniciar(ordemId, grupoMaquina);
//             break;
//         case 'interrompida':
//             mostrarModalInterromper(ordemId, grupoMaquina);
//             break;
//         case 'finalizada':
//             mostrarModalFinalizar(ordemId, ordem_numero);
//             break;
//         case 'agua_prox_proc':
//             mostrarModalIniciarProxProcesso(ordemId, grupoMaquina);
//             break;

//         default:
//         alert('Status desconhecido.');
//     }
// }

// Modal para "Interromper"
function mostrarModalInterromper(ordemId, grupoMaquina, ordem_numero) {
    const modal = new bootstrap.Modal(document.getElementById('modalInterromper'));
    const modalTitle = document.getElementById('modalInterromperLabel');
    const formInterromper = document.getElementById('formInterromperOrdemCorte');

    modalTitle.innerHTML = `Interromper Ordem #${ordem_numero}`;
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

        fetch(`/usinagem/api/ordens/atualizar-status/`, {
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
            if (document.getElementById('ordens-container') === null) {
                return;
            } else {
                document.getElementById('ordens-container').innerHTML = '';
            }
            resetarCardsInicial();

            fetchStatusMaquinas();
            // fetchUltimasPecasProduzidas();
            fetchContagemStatusOrdens();

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

    // Exibe SweetAlert de carregamento
    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das peças...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Limpa opções antigas no select
    fetch('/cadastro/api/buscar-maquinas/?setor=usinagem', {
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
            modalTitle.innerHTML = `Iniciar Ordem ${ordemId}`;
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

        const card = document.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();

        fetch(`/usinagem/api/ordens/atualizar-status/`, {
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
                if (document.getElementById('ordens-container') === null) {
                    return;
                } else {
                    document.getElementById('ordens-container').innerHTML = '';
                }
                resetarCardsInicial();

                fetchStatusMaquinas();
                // fetchUltimasPecasProduzidas();
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

// Modal para "Parcial"
function mostrarModalFinalizarParcial(ordemId, ordem_numero) {
    const modal = new bootstrap.Modal(document.getElementById('modalFinalizarParcial'));
    const modalTitle = document.getElementById('modalFinalizarParcialLabel');
    const formFinalizar = document.getElementById('formFinalizarParcial');

    // Remove event listeners antigos para evitar duplicidade
    const clonedForm = formFinalizar.cloneNode(true);
    formFinalizar.parentNode.replaceChild(clonedForm, formFinalizar);

    // Configura título do modal
    modalTitle.innerHTML = `Finalizar Parcial #${ordem_numero}`;
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
    fetch(`/usinagem/api/ordens-criadas/${ordemId}/pecas/`)
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
                fetch(`/usinagem/api/ordens/atualizar-status/`, {
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
                    if (document.getElementById('ordens-container') === null) {
                        return;
                    } else {
                        document.getElementById('ordens-container').innerHTML = '';
                    }
                    resetarCardsInicial();

                    modal.hide();

                    fetchStatusMaquinas();
                    fetchUltimasPecasProduzidas();
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
    const labelModalMaquinaProxProcesso = document.getElementById('labelModalMaquinaProxProcesso');

    const colQtdProxProcesso = document.getElementById('colQtdProxProcesso');

    colQtdProxProcesso.style.display = 'block';
    
    // const escolhaProcesso = document.getElementById('escolhaMaquinaProxProcesso');
    const qtdProxProcesso = document.getElementById('qtdProxProcesso');
    qtdProxProcesso.required = true;
    
    // Limpa opções antigas no select
    // escolhaProcesso.innerHTML = `<option value="">------</option>`;

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
    fetch('/cadastro/api/buscar-processos/?setor=usinagem', {
        method: 'GET',
        headers: {'Content-Type':'application/json'}
    })
    .then(response => response.json())
    .then(
        data => {
            const escolhaProcesso = document.getElementById('escolhaMaquinaProxProcesso');
            escolhaProcesso.innerHTML = `<option value="">------</option>`;
            const labelModalMaquinaProxProcesso = document.getElementById('labelModalMaquinaProxProcesso');
            labelModalMaquinaProxProcesso.innerHTML = 'Escolha o próximo processo:'

            Swal.close();
            data.processos.forEach((processo) => {
                const option = document.createElement('option');
                option.value = processo.id;
                option.textContent = processo.nome;
                escolhaProcesso.appendChild(option);
            })
            modalTitle.innerHTML = `Passar para próximo processo`;
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

        // Exibe SweetAlert de carregamento
        Swal.fire({
            title: 'Mudando processo...',
            text: 'Por favor, aguarde.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            },
        });

        const container = document.querySelector('.containerProcesso');
        const card = container?.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();

        fetch(`/usinagem/api/ordens/atualizar-status/`, {
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
                if (document.getElementById('ordens-container') === null) {
                    return;
                } else {
                    document.getElementById('ordens-container').innerHTML = '';
                }
                resetarCardsInicial();

                fetchStatusMaquinas();
                // fetchUltimasPecasProduzidas();
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

// Modal para "Iniciar próximo processo"
function mostrarModalIniciarProxProcesso(ordemId, grupoMaquina) {
    const modal = new bootstrap.Modal(document.getElementById('modalProxProcesso'));
    const modalTitle = document.getElementById('modalProxProcessoLabel');

    const qtdProxProcesso = document.getElementById('qtdProxProcesso');
    const colQtdProxProcesso = document.getElementById('colQtdProxProcesso');

    colQtdProxProcesso.style.display = 'none';
    qtdProxProcesso.required = false;

    // Exibe SweetAlert de carregamento
    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das máquinas...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    fetch('/cadastro/api/buscar-maquinas/?setor=usinagem', {
        method: 'GET',
        headers: {'Content-Type':'application/json'}
    })
    .then(response => response.json())
    .then(
        data => {
            const escolhaMaquina = document.getElementById('escolhaMaquinaProxProcesso');
            escolhaMaquina.innerHTML = `<option value="">------</option>`;

            Swal.close();
            data.maquinas.forEach((maquina) => {
                const option = document.createElement('option');
                option.value = maquina.id;
                option.textContent = maquina.nome;
                escolhaMaquina.appendChild(option);
            })
            modalTitle.innerHTML = `Iniciar próximo processo`;

            const labelModalMaquinaProxProcesso = document.getElementById('labelModalMaquinaProxProcesso');

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

        fetch(`/usinagem/api/ordens/atualizar-status/`, {
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
                if (document.getElementById('ordens-container') === null) {
                    return;
                } else {
                    document.getElementById('ordens-container').innerHTML = '';
                }
                resetarCardsInicial();

                colQtdProxProcesso.style.display = 'block';
                qtdProxProcesso.required = true;

                fetchStatusMaquinas();
                // fetchUltimasPecasProduzidas();
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
function mostrarModalFinalizar(ordemId, ordem_numero) {
    const modal = new bootstrap.Modal(document.getElementById('modalFinalizar'));
    const modalTitle = document.getElementById('modalFinalizarLabel');
    const formFinalizar = document.getElementById('formFinalizarOrdemUsinagem');

    // Remove event listeners antigos para evitar duplicidade
    const clonedForm = formFinalizar.cloneNode(true);
    formFinalizar.parentNode.replaceChild(clonedForm, formFinalizar);

    // Configura título do modal
    modalTitle.innerHTML = `Finalizar Ordem #${ordem_numero}`;
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
    fetch(`/usinagem/api/ordens-criadas/${ordemId}/pecas/`)
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
                fetch(`/usinagem/api/ordens/atualizar-status/`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        ordem_id: ordemId,
                        // grupo_maquina: grupoMaquina,
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
                    if (document.getElementById('ordens-container') === null) {
                        return;
                    } else {
                        document.getElementById('ordens-container').innerHTML = '';
                    }
                    resetarCardsInicial();

                    modal.hide();

                    fetchStatusMaquinas();
                    fetchUltimasPecasProduzidas();
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
        
        const container = document.querySelector('.containerInterrompido');
        const card = container?.querySelector(`[data-ordem-id="${ordemId}"]`);
        if (card) card.remove();

        Swal.fire({
            title: 'Retornando Ordem...',
            text: 'Por favor, aguarde.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        const formData = new FormData(clonedForm);

        fetch(`/usinagem/api/ordens/atualizar-status/`, {
            method: 'PATCH',
            body: JSON.stringify({
                ordem_id: ordemId,
                maquina_nome: maquina,
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
            if (document.getElementById('ordens-container') === null) {
                return;
            } else {
                document.getElementById('ordens-container').innerHTML = '';
            }
        
            resetarCardsInicial();

            fetchStatusMaquinas();
            fetchContagemStatusOrdens();

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
                const response = await fetch('/usinagem/api/criar-ordem-usinagem/', {
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
                    if (document.getElementById('ordens-container') === null) {
                        return;
                    } else {
                        document.getElementById('ordens-container').innerHTML = '';
                    }
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
    if (document.getElementById('ordens-container') === null) {
        return;
    }

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
    const filtroDataProgramada = document.getElementById('filtro-data-programada');

    const currentFiltros = {
        ordem: filtros.ordem || filtroOrdem.value.trim(),
        peca: filtros.peca || filtroPeca.value.trim(),
        status: filtros.status || filtroStatus.value.trim(),
        data_programada: filtros.data_programada || filtroDataProgramada.value.trim(),
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

function filtro_prox_processo(){

    if (document.getElementById('btn-filtrar-processo') === null) {
        return;
    }

    const btnFiltro = document.getElementById("btn-filtrar-processo");

    btnFiltro.addEventListener("click", () => {
        const filtroProcesso = document.getElementById("filtro-processo").value.trim();

        const containerProxProcesso = document.querySelector('.containerProxProcesso');
        carregarOrdensAgProProcesso(containerProxProcesso, { processo: filtroProcesso });
    })
}

function filtro() {
    const form = document.getElementById('filtro-form');

    form.addEventListener('submit', (event) => {
        event.preventDefault(); // Evita comportamento padrão do formulário

        // Captura os valores atualizados dos filtros
        const filtros = {
            ordem: document.getElementById('filtro-ordem')?.value.trim() || '',
            peca: document.getElementById('filtro-peca')?.value.trim() || '',
            processo: document.getElementById('filtro-processo')?.value || '',
        };

        const statusEl = document.getElementById('filtro-status');
        if (statusEl) {
            filtros.status = statusEl.value.trim();
        }

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

// async function carregarProcessos() {
//     try {
//         const response = await fetch('api/buscar-processos');
//         const data = await response.json();

//         const selectSetor = document.getElementById('filtro-processo');

//         if (data.processos && Array.isArray(data.processos)) {
//             data.processos.forEach(processo => {
//                 const option = document.createElement('option');
//                 option.value = processo.id;
//                 option.textContent = processo.nome;
//                 selectSetor.appendChild(option);
//             });
//         }
//     } catch (error) {
//         console.error('Erro ao carregar processos:', error);
//     }
// }

document.addEventListener('DOMContentLoaded', () => {

    resetarCardsInicial();
    configurarFormulario();
    
    $('#pecaSelect').select2({
        placeholder: 'Selecione a peça',
        ajax: {
            url: '/usinagem/api/get-pecas/',
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
    const containerInterrompido = document.querySelector('.containerInterrompido');
    const containerProxProcesso = document.querySelector('.containerProxProcesso')
    
    carregarOrdensIniciadas(containerIniciado);
    carregarOrdensInterrompidas(containerInterrompido);
    carregarOrdensAgProProcesso(containerProxProcesso);

    filtro();

    filtro_prox_processo();

});
