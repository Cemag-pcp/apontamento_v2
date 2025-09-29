// import { confirmarInicioOrdem } from './apontamento-utils.js';

document.addEventListener('DOMContentLoaded', function() {
    // Pega a string de parâmetros da URL atual
    const params = new URLSearchParams(window.location.search);

    // Para pegar um parâmetro específico, por exemplo 'ordem_id':
    const ordemId = params.get('ordem_id');
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
                    <div class="alert alert-danger" role="alert">
                        Erro: ${data.message}
                    </div>
                `;
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
            const maquina = event.target.closest('.btn-warning');
            const maquinaNome = maquina.getAttribute('data-maquina-nome');

            mostrarModalIniciar(ordemId, maquinaNome);
            
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
                didOpen: () => {
                    Swal.showLoading();
                },
            });

            const response = await fetch("/solda/api/ordens/atualizar-status/", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    status: "iniciada",
                    ordem_id: ordemId,
                    operador_inicio: operadorId
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw err;
            }
            await response.json();
            Swal.close();

            // Fecha o modal de confirmação
            const modalElement = document.getElementById('confirmModal');
            const confirmModal = bootstrap.Modal.getInstance(modalElement);
            confirmModal.hide();

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
                text: error.error || 'Ocorreu um erro ao tentar iniciar a ordem. Tente novamente.',
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

        const currentOrdemId = document.getElementById('ordemIdSoldaInput').value;
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
                window.location.href = "/solda/";
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
});