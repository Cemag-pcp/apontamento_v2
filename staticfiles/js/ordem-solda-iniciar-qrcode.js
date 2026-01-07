// import { confirmarInicioOrdem } from './apontamento-utils.js';

document.addEventListener('DOMContentLoaded', function() {
    const params = new URLSearchParams(window.location.search);

    const selecaoPendente = params.get('selecao_setor') === 'pendente';
    
    if (selecaoPendente) {
        params.delete('selecao_setor'); 
        const urlSemParametro = `${window.location.pathname}?${params.toString()}`;
        
        Swal.fire({
            title: 'Setor de Destino',
            html: `QR Code lido com sucesso. Selecione o setor de destino.`,
            icon: 'question',
            showDenyButton: true,
            showCancelButton: true,
            confirmButtonText: '<i class="fas fa-hammer me-1"></i> Solda',
            denyButtonText: '<i class="fas fa-cogs me-1"></i> Montagem',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#0d6efd',
            denyButtonColor: '#198754',
            cancelButtonColor: '#6c757d',
            allowOutsideClick: false
        }).then((result) => {
            let finalUrl = '';
            let setor = '';
            
            if (result.isConfirmed) {
                finalUrl = urlSemParametro;
                setor = 'Solda';
            } else if (result.isDenied) {
                finalUrl = urlSemParametro.replace(/\/solda\//gi, '/montagem/');
                setor = 'Montagem';
            } else {
                window.location.href = "/";
                return;
            }

            Swal.fire({
                title: `Redirecionando para ${setor}...`,
                icon: 'success',
                showConfirmButton: false,
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                    window.location.href = finalUrl;
                }
            });

        });
        
        return; 
    }
    
    // Para pegar um parâmetro específico, por exemplo 'ordem_id':
    const ordemId = params.get('ordem_id');
    const ordemIdSoldaInput = document.getElementById('ordemIdSolda');

    // Carrega os dados iniciais da ordem
    carregarDadosOrdem(ordemId);
    fetchOrdensIniciadas();

    document.addEventListener('click', function(event) {
        if (event.target.closest('.btn-warning')) {
            const maquina = event.target.closest('.btn-warning');
            const maquinaNome = maquina.getAttribute('data-maquina-nome');

            mostrarModalIniciar(ordemId, maquinaNome);
            
        }

        if (event.target.closest('.btn.btn-primary.btn-lg')){
            const btn = event.target.closest('.btn.btn-primary.btn-lg');
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Carregando...`;
        }

        if (event.target.closest('.btn-finalizar-lista')) {
            const btn = event.target.closest('.btn-finalizar-lista');
            const ordemIdFinalizar = btn.getAttribute('data-ordem-id');
            const maquina = btn.getAttribute('data-maquina');
            const maxItens = btn.getAttribute('data-max-itens');

            mostrarModalFinalizar(ordemIdFinalizar, maquina, maxItens);

        }
    });

    document.getElementById('direcionarTodosOperadoresOperadorInicial').addEventListener('click', function () {
        const operadorFinal = document.getElementById('operadorInicial');
        const todosOperadorInicial = document.getElementById('todosOperadorInicial');
        const labelOperadores = document.getElementById('labelOperadoresInicial');

        const descricaoBotaoVoltar = document.getElementById('descricaoBotaoVoltarOperadorInicial');
        const descricaoBotaoLista = document.getElementById('descricaoBotaoListaOperadorInicial');
        
        labelOperadores.textContent = `Todos os Operadores` 

        operadorFinal.style.display = 'none';
        operadorFinal.setAttribute('data-active', 'false');
        todosOperadorInicial.style.display = 'block';
        todosOperadorInicial.setAttribute('data-active', 'true');

        descricaoBotaoVoltar.style.display = 'block';
        descricaoBotaoLista.style.display = 'none';
    });

    // document.getElementById('confirmStartButton').addEventListener('click', async function() {
    //     let ordemFoiIniciada = await confirmarInicioOrdem(ordemId);
    //     console.log(ordemFoiIniciada);

    //     if (ordemFoiIniciada){
    //         window.location.href = "/solda/";
    //     }
    // });

    function carregarDadosOrdem(ordemId) {
        const cardApontamentoQrCode = document.getElementById('cardApontamentoQrCode');
        const ordemIdSoldaInput = document.getElementById('ordemIdSolda');

        // Exibe loader antes do fetch
        cardApontamentoQrCode.innerHTML = `
            <div class="d-flex justify-content-center align-items-center" style="min-height: 270px;">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Carregando...</span>
                </div>
            </div>
        `;

        fetch(`/solda/api/apontamento-qrcode/?ordem_id=${ordemId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Processar os dados recebidos
                    console.log(data);

                    const ordem = data.dados;

                    const statusClass =
                        ordem.status === 'finalizada' ? 'bg-success' :
                        ordem.status === 'iniciada' ? 'bg-primary' :
                        ordem.status === 'aguardando_iniciar' ? 'bg-warning' : 
                        ordem.status === 'interrompida' ? 'bg-danger' : 'bg-secondary';

                    cardApontamentoQrCode.innerHTML = `
                        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center p-3">
                            <h6 class="card-title fw-bold mb-0 fs-5">#${ordem.peca ? ordem.peca : 'Ordem Inexistente'}</h6>
                        </div>
                        <div class="card-body bg-white p-3">
                            <p class="card-text mb-3">
                                <strong>Data Carga:</strong> ${ordem.data_carga}
                            </p>
                            <p class="card-text mb-3">
                                <strong>Quantidade a fazer:</strong> ${ordem.qtd_planejada}
                            </p>
                            <p class="card-text mb-3">
                                <strong>Quantidade feita:</strong> ${ordem.qtd_boa}
                            </p>
                            <p class="card-text mb-0"><strong>Status: </strong><span class="badge ${statusClass}">${ordem.status}</span></p>
                        </div>
                        <div class="card-footer d-flex justify-content-end align-items-center bg-white p-3 border-top">
                            <button class="btn btn-warning btn-sm" data-title="Iniciar" data-maquina-nome="${ordem.maquina}">
                                <i class="fa fa-play"></i> Iniciar
                            </button>
                        </div>
                    `
                    if (ordem){
                        ordemIdSoldaInput.value = ordem.ordem;
                    }
                    
                    // Atualizar a interface do usuário conforme necessário
                } else {
                    console.error('Erro na resposta da API:', data.message);
                    cardApontamentoQrCode.innerHTML = `
                        <div class="d-flex flex-column justify-content-center align-items-center" style="min-height: 270px;">
                            <div class="alert alert-danger w-100 text-center mb-4" role="alert" style="max-width: 380px;">
                                <i class="fa fa-exclamation-triangle me-2"></i>
                                <strong>Erro:</strong> ${data.message}
                                <div class="mt-2 small text-muted">
                                    Verifique se o QR Code ou o link está correto.
                                </div>
                            </div>
                            <a href="/solda/" class="btn btn-primary btn-lg">
                                <i class="fa fa-arrow-left me-2"></i> Voltar para Solda
                            </a>
                        </div>
                    `;
                    Swal.fire({
                        icon: 'error',
                        title: 'Erro',
                        text: data.message || 'Ocorreu um erro ao tentar carregar a ordem. Tente novamente.',
                    });
                }
            })
            .catch(error => {
                console.error('Erro ao chamar a API:', error);
            });
    }

    function mostrarModalIniciar(ordemId, maquina) {
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));

        const operadorSelect = document.getElementById('operadorInicial');
        const labelOperadores = document.getElementById('labelOperadoresInicial');

        const todosOperadorInicial = document.getElementById('todosOperadorInicial');

        operadorSelect.style.display = 'block';

        todosOperadorInicial.style.display = 'none';
        labelOperadores.textContent = `Operador - ${maquina}` 

        document.getElementById('ordemIdIniciar').value = ordemId;

        operadorSelect.setAttribute('data-active', 'true');
        todosOperadorInicial.setAttribute('data-active', 'false');

        labelOperadores.setAttribute('data-maquina', maquina)

        operadorSelect.innerHTML = `<option value="" disabled selected>Selecione um operador...</option>`
        todosOperadorInicial.innerHTML = `<option value="" disabled selected>Selecione um operador...</option>`

        fetch(`/solda/api/listar-operadores/?maquina=${maquina}`)
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
                todosOperadorInicial.innerHTML = `<option value="" disabled>Nenhum operador encontrado</option>`;
            } else {
                data.operadores.forEach(operador => {
                    todosOperadorInicial.innerHTML += `<option value="${operador.id}">${operador.matricula} - ${operador.nome}</option>`;
                });
                todosOperadorInicial.disabled = false; // Habilita o select após carregar os dados
            }
        })
        .catch(error => {
            console.error("Erro ao carregar operadores:", error);
            operadorSelect.innerHTML = `<option value="" disabled>Erro ao carregar</option>`;
            todosOperadorInicial.innerHTML = `<option value="" disabled>Erro ao carregar</option>`;
        });
        
        modal.show();
    }

    async function iniciarOrdem(ordemId, operadorId) {
        try {
            Swal.fire({
                title: 'Iniciando...',
                text: 'Por favor, aguarde enquanto a ordem está sendo iniciada.',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading(),
            });

            const response = await fetch("/solda/api/ordens/atualizar-status/", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': (typeof csrftoken !== 'undefined' ? csrftoken : (document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''))
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    status: "iniciada",
                    ordem_id: ordemId,
                    operador_inicio: operadorId
                })
            });

            if (response.status === 401) {
                window.location.href = `/core/login/?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
                return false;
            }

            if (response.redirected) {
                window.location.href = response.url;
                return false;
            }

            if (!response.ok) {
                let err = {};
                try { err = await response.json(); } catch {}
                throw err;
            }

            try { await response.json(); } catch {}
            Swal.close();

            const modalElement = document.getElementById('confirmModal');
            const confirmModal = bootstrap.Modal.getInstance(modalElement);
            if (confirmModal) confirmModal.hide();

            Swal.fire({
                icon: 'success',
                title: 'Sucesso!',
                text: 'A ordem foi iniciada com sucesso.'
            });

            return true;
        } catch (error) {
            console.error('Erro ao iniciar a ordem:', error);

            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: error?.error || error?.detail || 'Ocorreu um erro ao tentar iniciar a ordem. Tente novamente.',
            });

            return false;
        }
    }


    document.getElementById('botaoVoltarOperadoresMaquinaOperadorInicial').addEventListener('click', function () {
        const operadorInicial = document.getElementById('operadorInicial');
        const todosOperadorInicial = document.getElementById('todosOperadorInicial');
        const labelOperadores = document.getElementById('labelOperadoresInicial');

        const descricaoBotaoLista = document.getElementById('descricaoBotaoListaOperadorInicial');
        const descricaoBotaoVoltar = document.getElementById('descricaoBotaoVoltarOperadorInicial');

        const maquina = labelOperadores.getAttribute('data-maquina')
        labelOperadores.textContent = `Operadores - ${maquina}` 

        todosOperadorInicial.style.display = 'none';
        todosOperadorInicial.setAttribute('data-active', 'false');
        operadorInicial.style.display = 'block';
        operadorInicial.setAttribute('data-active', 'true');

        descricaoBotaoLista.style.display = 'block';
        descricaoBotaoVoltar.style.display = 'none';
    });

    document.getElementById('confirmStartButton').addEventListener('click', async function() {
        const operadorInicio = document.getElementById('operadorInicial');
        const todosOperadorInicio = document.getElementById('todosOperadorInicial');

        // Determinar qual select está ativo e obter o valor do operador
        let operadorId;
        if (operadorInicio.style.display !== 'none' && operadorInicio.getAttribute('data-active') === 'true') {
            if (!operadorInicio.value || operadorInicio.value === "") {
                Swal.fire({
                    icon: 'warning',
                    title: 'Atenção',
                    text: 'Por favor, selecione um operador da máquina.'
                });
                return;
            }
            operadorId = operadorInicio.value;
        } else if (todosOperadorInicio.style.display !== 'none' && todosOperadorInicio.getAttribute('data-active') === 'true') {
            if (!todosOperadorInicio.value || todosOperadorInicio.value === "") {
                Swal.fire({
                    icon: 'warning',
                    title: 'Atenção',
                    text: 'Por favor, selecione um operador da lista geral.'
                });
                return;
            }
            operadorId = todosOperadorInicio.value;
        } else {
            Swal.fire({
                icon: 'warning',
                title: 'Atenção',
                text: 'Por favor, selecione um operador válido.'
            });
            return;
        }

        Swal.fire({
            title: 'Verificando quantidade pendente...',
            text: 'Aguarde enquanto verificamos se a ordem pode ser iniciada.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            },
        });

        // const currentOrdemId = document.getElementById('ordemIdIniciar').value;

        const currentOrdemId = ordemIdSoldaInput.value;
        try {
            const response = await fetch(`/solda/api/verificar-qt-restante/?ordem_id=${currentOrdemId}`);
            if (!response.ok) {
                const err = await response.json();
                throw err;
            }
            const data = await response.json();
            Swal.close();

            if (data.ordens.length === 0) {
                throw new Error("Ordem não encontrada.");
            }

            const ordem = data.ordens[0];
            if (ordem.restante === 0.0) {
                throw new Error("Essa ordem já foi totalmente produzida. Não é possível iniciá-la novamente.");
            }

            // Se chegou até aqui, pode iniciar a ordem
            let ordemFoiIniciada = await iniciarOrdem(currentOrdemId, operadorId);
            console.log(ordemFoiIniciada);

            if (ordemFoiIniciada){
                // Ao invés de redirecionar, recarrega os dados
                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso!',
                    text: 'A ordem foi iniciada com sucesso.'
                }).then(() => {
                    // Recarrega o card com os dados atualizados da ordem
                    carregarDadosOrdem(ordemId);
                    // Atualiza a lista de ordens iniciadas
                    fetchOrdensIniciadas();
                });
            }
        } catch (error) {
            console.error('Erro ao verificar quantidade pendente:', error);

            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: error.message || 'Não foi possível verificar a quantidade pendente. Tente novamente.',
            });
        }
    });

    function fetchOrdensIniciadas(){
        const listaContainer = document.getElementById('listaOrdensIniciadas');
        // Exibe loader antes do fetch
        listaContainer.innerHTML = `
            <div class="d-flex justify-content-center align-items-center" style="min-height: 200px;">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Carregando...</span>
                </div>
            </div>
        `;
        fetch(`/solda/api/ordens-iniciadas/?ordem_id=${ordemId}`)
            .then(response => response.json())
            .then(data => {       
                console.log(data);
                if (data.ordens) {
                    // Monta a lista de ordens
                    if (data.ordens && data.ordens.length > 0) {
                        let html = '<ul class="list-group mt-2">';
                        data.ordens.forEach((ordem, idx) => {
                           html += `
                                <li class="list-group-item rounded-3 shadow-sm mb-3 px-3 py-3">
                                    <div class="row align-items-center">
                                        <div class="col-12 col-md-auto mb-2 mb-md-0 d-flex align-items-center">
                                            <span class="badge bg-primary me-2">${idx + 1}</span>
                                            <strong class="me-2">Ordem:</strong>
                                            <span class="text-dark me-3">${ordem.ordem_id}</span>
                                        </div>
                                        <div class="col-12 col-md-auto mb-2 mb-md-0">
                                            <strong class="me-2">Máquina:</strong>
                                            <span class="text-dark me-3">${ordem.maquina}</span>
                                        </div>
                                        <div class="col-12 col-md-auto mb-2 mb-md-0">
                                            <strong class="me-2">Data Carga:</strong>
                                            <span class="text-dark me-3">${ordem.data_carga}</span>
                                        </div>
                                        <div class="col-12 col-md-auto mb-2 mb-md-0">
                                            <strong class="me-2">Operador:</strong>
                                            <span class="text-dark me-3">${ordem.operador_inicio}</span>
                                        </div>
                                        <div class="col-12 col-md-auto mb-2 mb-md-0">
                                            <strong class="me-2">Qt. Restante:</strong>
                                            <span class="text-dark me-3">${ordem.qtd_restante}</span>
                                        </div>
                                        <div class="col-12 col-md-auto mb-2 mb-md-0">
                                            <strong class="me-2">Status:</strong>
                                            <span class="badge ${
                                                ordem.status_atual === 'finalizada' ? 'bg-success' :
                                                ordem.status_atual === 'iniciada' ? 'bg-primary' :
                                                ordem.status_atual === 'interrompida' ? 'bg-danger' : 'bg-secondary'
                                            } me-3">${ordem.status_atual}</span>
                                        </div>
                                        ${
                                            ordem.status_atual !== 'finalizada'
                                            ? `<div class="col-12 col-md-auto mt-2 mt-md-0 d-grid">
                                                    <button class="btn btn-success btn-sm btn-finalizar-lista w-100 w-md-auto" data-ordem-id="${ordem.ordem_id}"
                                                        data-maquina="${ordem.maquina}" data-max-itens="${ordem.qtd_restante}">
                                                        <i class="fa fa-check"></i> Finalizar
                                                    </button>
                                                </div>`
                                            : ''
                                        }
                                    </div>
                                </li>
                                `;
                        });
                        html += '</ul>';
                        listaContainer.innerHTML = html;
                    } else {
                        listaContainer.innerHTML = '<div class="alert alert-info">Nenhuma ordem iniciada encontrada.</div>';
                    }
                } else {
                    listaContainer.innerHTML = `<div class="alert alert-danger">Algum erro encontrado</div>`;
                }
            })
            .catch(error => {
                document.getElementById('listaOrdensIniciadas').innerHTML =
                    `<div class="alert alert-danger">Erro ao chamar a API: ${error}</div>`;
            });
    }

    document.getElementById('confirmFinalizar').addEventListener('click', function () {
        const ordemId = document.getElementById('ordemIdFinalizar').value;
        const operadorFinal = document.getElementById('operadorFinal');
        const todosOperadorFinal = document.getElementById('todosOperadorFinal');
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

        console.log('Payload para finalizar a ordem:', payload);
        fetch("/solda/api/ordens/atualizar-status/", {
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
            // Fechar o modal após a finalização bem-sucedida
            const modalElement = document.getElementById('finalizarModal');
            const finalizarModal = bootstrap.Modal.getInstance(modalElement);
            finalizarModal.hide();
            Swal.close();

            // Ao invés de redirecionar, recarrega os dados
            const params = new URLSearchParams(window.location.search);
            const currentOrdemId = params.get('ordem_id');
            
            Swal.fire({
                icon: 'success',
                title: 'Sucesso!',
                text: 'Ordem finalizada com sucesso.'
            }).then(() => {
                // Recarrega o card com os dados atualizados da ordem
                carregarDadosOrdem(currentOrdemId);
                // Atualiza a lista de ordens iniciadas
                fetchOrdensIniciadas();
            });
        })
        .catch(error => {
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: error.message || 'Erro ao finalizar a ordem. Tente novamente.'
            });
        });
    });

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

        fetch(`/solda/api/listar-operadores/?maquina=${maquina}&ordem=${ordemId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao buscar operadores");
            }
            return response.json();
        })
        .then(data => {
            const operadorInicioId = data.operador_inicio_id;

            if (data.operadores_maquina.length === 0) {
                operadorSelect.innerHTML = `<option value="" disabled>Nenhum operador encontrado</option>`;
            } else {
                data.operadores_maquina.forEach(operador => {
                    const selected = operador.id === operadorInicioId ? 'selected' : '';
                    operadorSelect.innerHTML += `<option value="${operador.id}" ${selected}>${operador.matricula} - ${operador.nome}</option>`;
                });
                operadorSelect.disabled = false;
            }

            if (data.operadores.length === 0) {
                todosOperadorFinal.innerHTML = `<option value="" disabled>Nenhum operador encontrado</option>`;
            } else {
                data.operadores.forEach(operador => {
                    const selected = operador.id === operadorInicioId ? 'selected' : '';
                    todosOperadorFinal.innerHTML += `<option value="${operador.id}" ${selected}>${operador.matricula} - ${operador.nome}</option>`;
                });
                todosOperadorFinal.disabled = false;
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

});