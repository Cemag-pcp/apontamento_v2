// import { fetchStatusMaquinas, fetchUltimasPecasProduzidas, fetchContagemStatusOrdens } from './status-maquina.js';

export const loadOrdens = (container, filtros = {}) => {
    let isLoading = false; // Flag para evitar chamadas duplicadas

    return new Promise((resolve, reject) => {
        if (isLoading) return resolve({ ordens: [] });
        isLoading = true;

        fetch(`api/ordens-criadas/?data_carga=${filtros.data_carga}&cor=${filtros.cor || ''}`)
            .then(response => response.json())
            .then(data => {
                const ordens = data.ordens;
                container.innerHTML = ""; // Limpa antes de inserir novas ordens
                
                if (ordens.length > 0) {
                    // Criar cabeçalho da tabela
                    const tableWrapper = document.createElement("div");
                    tableWrapper.classList.add("table-container");
        
                    const table = document.createElement('table');
                    table.classList.add('table', 'table-bordered', 'table-striped', 'header-fixed');

                    table.innerHTML = `
                        <thead class="table-light">
                            <tr>
                                <th style="width: 5%; text-align: center;">
                                    <input type="checkbox" id="select-all">
                                </th>
                                <th style="width: 10%;">Ch. Peça</th>
                                <th style="width: 15%;">Código Peça</th>
                                <th style="width: 15%;">Data Programação</th>
                                <th style="width: 10%;">Cor</th>
                                <th style="width: 10%;">Qtd. Disponível</th>
                                <th style="width: 10%;">Qtd. a Pendurar</th>
                            </tr>
                        </thead>
                        <tbody id="tabela-ordens-corpo"></tbody>
                    `;

                    tableWrapper.appendChild(table);
                    container.appendChild(tableWrapper);
    
                    // container.appendChild(table);
                    const tabelaCorpo = document.getElementById('tabela-ordens-corpo');

                    ordens.forEach(ordem => {
                        console.log(ordem);
                        const linha = document.createElement('tr');
                        linha.dataset.ordemId = ordem.id;
                        linha.dataset.pecaOrdem = ordem.peca_ordem_id;
                        linha.dataset.cor = ordem.cor; // Adiciona a cor da peça para controle

                        linha.innerHTML = `
                            <td style="text-align: center;">
                                <input type="checkbox" class="ordem-checkbox" data-ordem-id="${ordem.id}" data-cor="${ordem.cor}">
                            </td>
                            <td>#${ordem.ordem}</td>
                            <td>
                                <a href="https://drive.google.com/drive/u/0/search?q=${ordem.peca_codigo}" 
                                   target="_blank" rel="noopener noreferrer">
                                    ${ordem.peca_codigo}
                                </a>
                            </td>
                            <td>${ordem.data_programacao}</td>
                            <td>${ordem.cor}</td>
                            <td>${ordem.qt_restante}</td>
                            <td>
                                <input type="number" class="form-control qt-produzida" min="1" max="${ordem.qt_restante}">
                            </td>
                        `;

                        tabelaCorpo.appendChild(linha);
                    });

                    // Evento para habilitar/desabilitar o botão ao marcar checkboxes e verificar cor e quantidade preenchida
                    const checkboxes = document.querySelectorAll(".ordem-checkbox");

                    checkboxes.forEach(checkbox => {
                        checkbox.addEventListener("change", () => {
                            const selecionados = [...checkboxes].filter(cb => cb.checked);
                            const corSelecionada = selecionados.length > 0 ? selecionados[0].dataset.cor : null;
                            let isValid = true;
                    
                            selecionados.forEach(cb => {
                                const linha = cb.closest('tr');
                                const qtInput = linha.querySelector('.qt-produzida');
                                const maxQtPermitida = parseInt(qtInput.getAttribute("max"), 10);
                                const qtSelecionada = parseInt(qtInput.value, 10);
                    
                                // ⚠ Verifica se o campo de quantidade foi preenchido corretamente
                                if (!qtInput.value || qtSelecionada <= 0) {
                                    cb.checked = false; // Desmarca o checkbox inválido
                                    isValid = false;
                    
                                    Swal.fire({
                                        icon: "warning",
                                        title: "Quantidade Inválida",
                                        text: "Você precisa preencher a quantidade antes de selecionar esta ordem!",
                                        confirmButtonText: "OK"
                                    });
                                    return;
                                }
                    
                                // ⚠ Verifica se a quantidade ultrapassa o permitido
                                if (qtSelecionada > maxQtPermitida) {
                                    cb.checked = false; // Desmarca a seleção inválida
                                    isValid = false;
                    
                                    Swal.fire({
                                        icon: "warning",
                                        title: "Quantidade Excedida",
                                        text: `O valor máximo permitido é ${maxQtPermitida}.`,
                                        confirmButtonText: "OK"
                                    });
                                    return;
                                }
                            });
                    
                            // ⚠ Se houver cores diferentes, impede a seleção
                            const coresDiferentes = selecionados.some(cb => cb.dataset.cor !== corSelecionada);
                            if (coresDiferentes) {
                                checkbox.checked = false;
                                isValid = false;
                    
                                Swal.fire({
                                    icon: "warning",
                                    title: "Seleção Inválida",
                                    text: "Todas as peças do cambão devem ter a mesma cor!",
                                    confirmButtonText: "OK"
                                });
                            }
                    
                            // ✅ Habilita o botão apenas se houver seleções válidas
                            document.getElementById("btn-criar-cambao").disabled = selecionados.length === 0 || !isValid;
                        });
                    });

                    // Evento para selecionar todos os checkboxes (somente se todas forem da mesma cor e com quantidade preenchida)
                    document.getElementById("select-all").addEventListener("change", (e) => {
                        const isChecked = e.target.checked;
                        const primeiraCor = checkboxes[0]?.dataset.cor;
                        let isValid = true;

                        checkboxes.forEach(cb => {
                            const linha = cb.closest('tr');
                            const qtInput = linha.querySelector('.qt-produzida');

                            if (cb.dataset.cor === primeiraCor && qtInput.value && parseInt(qtInput.value) > 0) {
                                cb.checked = isChecked;
                            } else {
                                cb.checked = false;
                                isValid = false;
                            }
                        });

                        if (!isValid) {
                            Swal.fire({
                                icon: "warning",
                                title: "Seleção Inválida",
                                text: "Verifique se todas as ordens possuem a mesma cor e quantidade preenchida corretamente!",
                                confirmButtonText: "OK"
                            });
                        }

                        // Verifica se há checkboxes válidos marcados
                        const algumSelecionado = [...checkboxes].some(cb => cb.checked);
                        document.getElementById("btn-criar-cambao").disabled = !algumSelecionado || !isValid;
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

export function carregarOrdensIniciadas(container, filtros = {}) {
    fetch(`api/ordens-iniciadas/?page=1&limit=100&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}`)
        .then(response => response.json())
        .then(data => {
            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {

                const card = document.createElement('div');
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
                    <button class="btn btn-primary btn-sm btn-proximo-processo" title="Passar para o próximo processo">
                        <i class="fa fa-arrow-right"></i>
                    </button>      
                    <button class="btn btn-info btn-sm btn-finalizar-parcial" title="Finalizar parcial">
                        <i class="fa fa-hourglass-half"></i>
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
                        mostrarModalInterromper(ordem.id, ordem.grupo_maquina);
                    });
                }

                // Adiciona evento ao botão "Finalizar", se existir
                if (buttonFinalizar) {
                    buttonFinalizar.addEventListener('click', () => {
                        atualizarStatusOrdem(ordem.id, ordem.grupo_maquina, 'finalizada');
                    });
                }

                if (buttonProxProcesso) {
                    buttonProxProcesso.addEventListener('click', () => {
                        mostrarModalProxProcesso(ordem.id, ordem.grupo_maquina);
                    });
                }

                if (buttonFinalizarParcial) {
                    buttonFinalizarParcial.addEventListener('click', () => {
                        mostrarModalFinalizarParcial(ordem.id, ordem.grupo_maquina);
                    });
                }

                container.appendChild(card);

                iniciarContador(ordem.ordem, ordem.ultima_atualizacao)

            });
        })
        .catch(error => console.error('Erro ao buscar ordens iniciadas:', error));
};

export function carregarOrdensInterrompidas(container, filtros = {}) {
    // Fetch para buscar ordens interrompidas
    fetch(`api/ordens-interrompidas/?page=1&limit=10&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao buscar as ordens interrompidas.');
            }
            return response.json();
        })
        .then(data => {
            container.innerHTML = ''; // Limpa o container
            console.log(data);
            data.ordens.forEach(ordem => {
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
                    <button class="btn btn-warning btn-sm btn-retornar" title="Retornar">
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
                            <div class="d-flex gap-2">
                                ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                            </div>
                        </div>
                    </div>`;
            
                // Adiciona eventos aos botões
                const buttonRetornar = card.querySelector('.btn-retornar');
                if (buttonRetornar) {
                    buttonRetornar.addEventListener('click', () => {
                        mostrarModalRetornar(ordem.id, ordem.grupo_maquina, ordem.maquina_id);
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
};

function carregarOrdensAgProProcesso(container, filtros = {}) {
    fetch(`api/ordens-ag-prox-proc/?page=1&limit=10&ordem=${filtros.ordem || ''}&peca=${filtros.peca || ''}`)
        .then(response => response.json())
        .then(data => {
            container.innerHTML = ''; // Limpa o container
            data.ordens.forEach(ordem => {

                const card = document.createElement('div');
                card.dataset.ordemId = ordem.id;

                // Defina os botões dinamicamente com base no status
                let botaoAcao = '';

                botaoAcao = `
                    <button class="btn btn-warning btn-sm btn-iniciar-proximo-processo" title="Iniciar próximo processo">
                        <i class="fa fa-play"></i>
                    </button>
                `;

                card.innerHTML = `

                <div class="card shadow-lg border-0 rounded-3 mb-3 position-relative">
                    <!-- Contador fixado no topo direito -->
                    <span class="badge bg-warning text-dark fw-bold px-3 py-2 position-absolute" 
                        id="contador-${ordem.ordem}" 
                        style="top: -10px; right: 0px; font-size: 0.75rem; z-index: 10;">
                        Carregando...
                    </span>

                    <div class="card-header bg-warning text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title mb-0"><small>#${ordem.ordem} - ${ordem.maquina}</small></h6>
                        <small class="text-white">
                            Planejada: ${ordem.totais.qtd_planejada || 0} 
                            Realizada: ${ordem.totais.qtd_boa || 0} 
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
                        <div class="d-flex gap-2">
                            ${botaoAcao} <!-- Insere os botões dinâmicos aqui -->
                        </div>
                    </div>
                </div>`;

                const buttonProxProcesso = card.querySelector('.btn-iniciar-proximo-processo');

                // Adiciona evento ao botão para iniciar proximo processo
                if (buttonProxProcesso) {
                    buttonProxProcesso.addEventListener('click', () => {
                        mostrarModalIniciarProxProcesso(ordem.id, ordem.grupo_maquina);
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

// Modal para "Iniciar"
function mostrarModalIniciar(ordemId, grupoMaquina) {
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
            escolhaMaquina.appendChild(option);
        });

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
                    mostrarModalIniciar(data.ordem_id, 'estamparia');
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
    let isLoading = false; // Flag para evitar chamadas simultâneas

    // Obtém os filtros atualizados
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroCor = document.getElementById('filtro-cor');
    
    const currentFiltros = {
        data_carga: filtroDataCarga.value,
        cor: filtroCor.value,
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
        const filtroCor = document.getElementById('filtro-cor');

        // Captura os valores atualizados dos filtros
        const filtros = {
            data_carga: filtroDataCarga.value,
            cor: filtroCor.value,
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

// Evento para confirmar a criação do cambão
document.getElementById("confirmarCriacaoCambao").addEventListener("click", () => {

    const botaoConfirmar = document.getElementById("confirmarCriacaoCambao");
    
    const selectCambao = document.getElementById("cambaoSelecionado");
    const selectTipo = document.getElementById("tipoPintura");
    const selectOperador = document.getElementById("operadorInicial");
    const cambaoId = selectCambao.value;
    const tipoId = selectTipo.value;
    const operadorId = selectOperador.value;
    
    const dadosCambao = JSON.parse(botaoConfirmar.dataset.cambaoData);
    let modal = document.getElementById("modalCriarCambao");
    
    if (!cambaoId) {

        console.log("Alerta: Cambão não selecionado!");
        Swal.fire({
            icon: "warning",
            title: "Seleção obrigatória",
            text: "Por favor, selecione um cambão antes de continuar.",
            confirmButtonText: "OK",
            allowOutsideClick: false
        });
        return;
    } else if (!tipoId) {
        console.log("Alerta: Tipo não selecionado!");
        Swal.fire({
            icon: "warning",
            title: "Seleção obrigatória",
            text: "Por favor, selecione um tipo antes de continuar.",
            confirmButtonText: "OK",
            allowOutsideClick: false
        });
        return;
    } else if (!operadorId) {
        console.log("Alerta: Operador não selecionado!");
        Swal.fire({
            icon: "warning",
            title: "Seleção obrigatória",
            text: "Por favor, selecione um operador antes de continuar.",
            confirmButtonText: "OK",
            allowOutsideClick: false
        });
        return;
    }


    // Adiciona o cambão selecionado ao payload
    dadosCambao.cambao_id = parseInt(cambaoId);
    dadosCambao.tipo = tipoId;
    dadosCambao.operador = operadorId;

    Swal.fire({
        title: 'Carregando...',
        text: 'Aguarde...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    fetch("api/add-pecas-cambao/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            // "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
        },
        body: JSON.stringify(dadosCambao)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({
                icon: "success",
                title: "Cambão Criado",
                text: "O cambão foi gerado com sucesso.",
                confirmButtonText: "OK"
            }).then(() => {
                Swal.close();

                let modalInstance = bootstrap.Modal.getInstance(modal);
                if (modalInstance) {
                    modalInstance.hide();
                };
                
                resetarCardsInicial();
                cambaoProcesso();
            });
        } else {
            Swal.fire({
                icon: "error",
                title: "Erro ao Criar Cambão",
                text: data.error || "Ocorreu um erro ao gerar o cambão.",
                confirmButtonText: "OK"
            });
        }
    })
    .catch(error => {
        console.error("Erro ao criar cambão:", error);
        Swal.fire({
            icon: "error",
            title: "Erro",
            text: "Ocorreu um erro ao tentar criar o cambão.",
            confirmButtonText: "OK"
        });
    });
});

async function cambaoProcesso() {
    try {
        const response = await fetch("api/cambao-processo/");
        const data = await response.json();
        const cambaoContainer = document.getElementById("cambao-container");
        cambaoContainer.innerHTML = ""; // Limpa antes de adicionar os novos

        if (data.cambao_em_processo.length === 0) {
            cambaoContainer.innerHTML = '<p class="text-muted text-center">Nenhum cambão em processo.</p>';
            return;
        }

        const colorMap = {
            "Vermelho": "#FF4D4D",
            "Azul": "#4D79FF",
            "Verde": "#4CAF50",
            "Amarelo": "#FFC107",
            "Laranja": "#FF9800",
            "Roxo": "#9C27B0",
            "Cinza": "#6C757D",
            "Preto": "#212529",
            "Branco": "#FFFFFF",
            "Marrom": "#795548"
        };

        const coresAgrupadas = {}; // Objeto para agrupar os cambões por cor

        // Agrupa os cambões por cor
        data.cambao_em_processo.forEach(cambao => {
            if (!coresAgrupadas[cambao.cor]) {
                coresAgrupadas[cambao.cor] = [];
            }
            coresAgrupadas[cambao.cor].push(cambao);
        });

        const maxLength = 22; // Número máximo de caracteres a exibir

        // Gera as colunas para cada cor
        Object.entries(coresAgrupadas).forEach(([cor, camboes]) => {
            const corHex = colorMap[cor] || "#808080"; // Se não encontrar, usa cinza padrão
            const colDiv = document.createElement("div");
            colDiv.classList.add("col-md-4");
            console.log(camboes);
            colDiv.innerHTML = `
                <div class="card shadow-sm position-relative">
                    <div class="card-header text-white text-center" style="background-color: ${corHex};">
                        <h5>${cor}</h5>
                    </div>
                    <div class="card-body p-2">
                        ${camboes.map(cambao => `
                            <div class="border rounded p-2 mb-2">
                                <div class="d-flex justify-content-between">
                                    <strong>Cambão #${cambao.id}</strong> 
                                    <span class="badge bg-warning">${cambao.tipo}</span>
                                </div>
                                <span class="badge bg-dark text-light px-2 py-1 my-2" 
                                      id="contador-cambao-${cambao.id}" 
                                      style="font-size: 0.85rem;">
                                    Carregando...
                                </span>
                                <ul class="list-unstyled mt-2">
                                    ${cambao.pecas.map(peca => `
                                        <li class="d-flex justify-content-between">
                                            <span>Peça: 
                                                <strong title="${peca.peca}">
                                                    ${peca.peca.length > maxLength ? peca.peca.substring(0, maxLength) + "..." : peca.peca}
                                                </strong>
                                            </span> 
                                            <span>Qtd: <strong>${peca.quantidade_pendurada}</strong></span>
                                        </li>
                                    `).join('')}
                                </ul>
                                <div class="d-flex justify-content-between mt-2">
                                    <small class="text-muted">Início: ${new Date(cambao.data_pendura).toLocaleString()}</small>
                                    <button class="btn btn-sm btn-danger btn-finalizar" data-cambao-id="${cambao.id}">
                                        Encerrar
                                    </button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            cambaoContainer.appendChild(colDiv);

            // Iniciar contador para cada cambão
            camboes.forEach(cambao => {
                iniciarContador(`cambao-${cambao.id}`, cambao.data_pendura);
            });
        });

        // Evento de clique para abrir o modal de finalização
        document.querySelectorAll(".btn-finalizar").forEach(botao => {
            botao.addEventListener("click", function () {
                const cambaoId = this.dataset.cambaoId;
                document.getElementById("confirmarEncerramentoCambao").dataset.cambaoId = cambaoId;

                const operadorSelect = document.getElementById("operadorSelect");
                operadorSelect.disabled = true; // Bloqueia o select antes de carregar
                operadorSelect.innerHTML = `<option value="" disabled selected>Carregando operadores...</option>`; 

                // Buscar operadores disponíveis para o select
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

                // Exibe o modal
                let modal = new bootstrap.Modal(document.getElementById("modalFinalizarCambao"));
                modal.show();
            });
        });


    } catch (error) {
        console.error("Erro ao buscar cambões:", error);
    }
}

// Evento de clique para confirmar a finalização
document.getElementById("confirmarEncerramentoCambao").removeEventListener("click", finalizarCambao);
document.getElementById("confirmarEncerramentoCambao").addEventListener("click", finalizarCambao);

function finalizarCambao() {
    let modal = document.getElementById("modalFinalizarCambao");
    let modalInstance = bootstrap.Modal.getInstance(modal);

    const cambaoId = this.dataset.cambaoId;
    const operadorId = document.getElementById("operadorSelect").value;

    if (!operadorId) {
        Swal.fire({
            icon: "warning",
            title: "Operador não selecionado",
            text: "Por favor, selecione um operador antes de finalizar o cambão.",
            confirmButtonText: "OK"
        });
        return;
    }

    Swal.fire({
        title: 'Carregando...',
        text: 'Finalizando cambão...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    fetch("api/finalizar-cambao/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            // "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
        },
        body: JSON.stringify({ cambao_id: cambaoId, operador: operadorId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({
                icon: "success",
                title: "Cambão Finalizado",
                text: "O cambão foi encerrado com sucesso.",
                confirmButtonText: "OK"
            }).then(() => {
                if (modalInstance) {
                    modalInstance.hide(); // Fecha corretamente o modal
                }
                cambaoProcesso();
            });
        } else {
            Swal.fire({
                icon: "error",
                title: "Erro ao Finalizar",
                text: data.error || "Ocorreu um erro ao finalizar o cambão.",
                confirmButtonText: "OK"
            });
        }
    })
    .catch(error => {
        console.error("Erro ao finalizar cambão:", error);
        Swal.fire({
            icon: "error",
            title: "Erro",
            text: "Ocorreu um erro ao tentar finalizar o cambão.",
            confirmButtonText: "OK"
        });
    });
}

function carregarCores(dataCarga) {
    const filtroCor = document.getElementById('filtro-cor');
    filtroCor.disabled = true; // Desabilita enquanto carrega

    fetch(`api/cores-carga/?data_carga=${encodeURIComponent(dataCarga)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao buscar cores da carga.");
            }
            return response.json();
        })
        .then(data => {
            const selectCor = document.getElementById('filtro-cor');
            if (!selectCor) {
                console.error("Elemento 'filtro-cor' não encontrado.");
                return;
            }

            // Limpa as opções existentes
            selectCor.innerHTML = `<option value="">------</option>`;

            if (data.cores && data.cores.length > 0) {
                // Adiciona as cores sem duplicação
                data.cores.forEach(cor => {
                    const option = document.createElement('option');
                    option.value = cor; // Agora `cor` é diretamente o valor correto
                    option.textContent = cor;
                    selectCor.appendChild(option);
                });
                filtroCor.disabled = false; // Habilita o select após o carregamento
            } else {
                console.warn("Nenhuma cor encontrada para a data selecionada.");
            }
        })
        .catch(error => console.error("Erro no carregamento das cores:", error));
}

// Evento para carregar cores ao mudar a data de carga
function coresCarga() {
    document.getElementById('filtro-data-carga').addEventListener('change', (event) => {
        const dataCarga = event.target.value; // Pega o valor da data selecionada
        if (dataCarga) {
            carregarCores(dataCarga);
        }
    });
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
    cambaoProcesso();
    filtro();
    coresCarga();
    atualizarUltimasCargas();
    
    const botaoCriarCambao = document.getElementById("btn-criar-cambao");
    
    if (botaoCriarCambao) {
        botaoCriarCambao.addEventListener("click", () => abrirModalCambao());
    }
});