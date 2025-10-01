import { confirmarInicioOrdem } from './apontamento-utils.js';

document.addEventListener('DOMContentLoaded', function() {
    // Pega a string de parâmetros da URL atual
    const params = new URLSearchParams(window.location.search);

    const selecaoPendente = params.get('selecao_setor') === 'pendente';
    const ordemUrl = window.location.href; 
    
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
                finalUrl = urlSemParametro.replace(/\/montagem\//gi, '/solda/');
                setor = 'Solda';
            } else if (result.isDenied) {
                finalUrl = urlSemParametro;
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
    const cardApontamentoQrCode = document.getElementById('cardApontamentoQrCode');

    // Exibe loader antes do fetch
    cardApontamentoQrCode.innerHTML = `
        <div class="d-flex justify-content-center align-items-center" style="min-height: 270px;">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
        </div>
    `;

    fetchOrdensIniciadas();

    fetch(`/montagem/api/apontamento-qrcode/?ordem_id=${ordemId}`)
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
                        <h6 class="card-title fw-bold mb-0 fs-5">#${ordem.peca}</h6>
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
                        <button class="btn btn-warning btn-sm" title="Iniciar">
                            <i class="fa fa-play"></i> Iniciar
                        </button>
                    </div>
                `
                // Atualizar a interface do usuário conforme necessário
            } else {
                console.error('Erro na resposta da API:', data.message);

                cardApontamentoQrCode.innerHTML = `<div class="d-flex flex-column justify-content-center align-items-center" style="min-height: 270px;">
                    <div class="alert alert-danger w-100 text-center mb-4" role="alert" style="max-width: 380px;">
                        <i class="fa fa-exclamation-triangle me-2"></i>
                        <strong>Erro:</strong> ${data.message}
                        <div class="mt-2 small text-muted">
                            Verifique se o QR Code ou o link está correto.
                        </div>
                    </div>
                    <a href="/montagem/" class="btn btn-primary btn-lg">
                        <i class="fa fa-arrow-left me-2"></i> Voltar para Montagem
                    </a>
                </div>`;

                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: data.message || 'Ocorreu um erro ao tentar iniciar a ordem. Tente novamente.',
                });
            }
        })
        .catch(error => {
            console.error('Erro ao chamar a API:', error);
        });

    document.addEventListener('click', function(event) {
        if (event.target.closest('.btn-warning')) {
            const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
            document.getElementById('confirmModal').removeAttribute("aria-hidden");
            modal.show();
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

    document.getElementById('confirmStartButton').addEventListener('click', async function() {
        let ordemFoiIniciada = await confirmarInicioOrdem(ordemId);
        console.log(ordemFoiIniciada);

        if (ordemFoiIniciada){
            window.location.href = "/montagem/";
        }
    });

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
        fetch("/montagem/api/ordens/atualizar-status/", {
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

            Swal.fire({
                icon: 'success',
                title: 'Sucesso!',
                text: 'Ordem finalizada com sucesso.'

            });

            //Redirecionando para a tela de apontamento de montagem
            setTimeout(function(){
                window.location.href = '/montagem/';
            }, 1000);
            


        })
        .catch(error => {
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: error.message || 'Erro ao finalizar a ordem. Tente novamente.'
            });
        });
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
        fetch(`/montagem/api/ordens-iniciadas/?ordem_id=${ordemId}`)
            .then(response => response.json())
            .then(data => {       
                console.log(data);
                if (data.ordens) {
                    // Monta a lista de ordens
                    if (data.ordens && data.ordens.length > 0) {
                        let html = '<ul class="list-group mt-2">';
                        data.ordens.forEach((ordem, idx) => {
                        html += `
                            <li class="list-group-item d-flex flex-column flex-md-row justify-content-between align-items-md-center">
                                <div>
                                    <span class="badge bg-primary me-2">${idx + 1}</span>
                                    <strong>Ordem:</strong> <span class="text-dark">${ordem.ordem_id}</span>
                                    <span class="mx-2">|</span>
                                    <strong>Máquina:</strong> <span class="text-dark">${ordem.maquina}</span>
                                    <span class="mx-2">|</span>
                                    <strong>Data Carga:</strong> <span class="text-dark">${ordem.data_carga}</span>
                                </div>
                                <div class="mt-2 mt-md-0">
                                    <strong>Qt. Restante:</strong> <span class="text-dark">${ordem.qtd_restante}</span>
                                    <span class="mx-2">|</span>
                                    <strong>Status:</strong> <span class="badge ${
                                        ordem.status_atual === 'finalizada' ? 'bg-success' :
                                        ordem.status_atual === 'iniciada' ? 'bg-primary' :
                                        ordem.status_atual === 'interrompida' ? 'bg-danger' : 'bg-secondary'
                                    }">${ordem.status_atual}</span>
                                    ${
                                        ordem.status_atual !== 'finalizada'
                                        ? `<button class="btn btn-success btn-sm btn-finalizar-lista ms-2" data-ordem-id="${ordem.ordem_id}"
                                        data-maquina="${ordem.maquina}" data-max-itens="${ordem.qtd_restante}">
                                            <i class="fa fa-check"></i> Finalizar
                                        </button>`
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

        fetch(`/montagem/api/listar-operadores/?maquina=${maquina}`)
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
});