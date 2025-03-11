const tituloSetor = document.getElementById('titulo-setor');
const btnSetorMontagem = document.getElementById('setor-montagem');
const btnSetorPintura = document.getElementById('setor-pintura');
const setorSelecionado = document.getElementById('setor-selecionado');
const colunaSetor = document.getElementById('colunaSetor');
const colunaCor = document.getElementById('colunaCor');
const setor = document.getElementById('setor-selecionado').value;

function carregarTabela(pagina = 1) {
    return new Promise((resolve, reject) => {  // Adicionando uma Promise
        try {

            const tbody = document.getElementById("tabela-corpo");
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-5">
                        <div class="d-flex flex-column align-items-center justify-content-center">
                            <div class="spinner-border text-primary mb-3" role="status">
                                <span class="visually-hidden">Carregando...</span>
                            </div>
                            <span class="text-muted">Processando sua solicitação...</span>
                        </div>
                    </td>
                </tr>
            `;

            document.getElementById('pagina-atual').value = pagina;
            const dataCargaEscolhida = document.getElementById('filtro-data-carga')?.value || '';
            const corPintura = document.getElementById('filtro-cor-pintura')?.value || '';
            const setorMontagem = document.getElementById('filtro-setor-montagem')?.value || '';
            const setor = document.getElementById('setor-selecionado').value;

            const limiteRegistros = 10; // Define o limite de registros por página

            const filtros = {
                dataCargaEscolhida: encodeURIComponent(dataCargaEscolhida),
                cor: encodeURIComponent(corPintura),
                setor: encodeURIComponent(setorMontagem),
            };

            if (setor === 'montagem'){
                fetch(`/cargas/api/historico-planejamento-montagem/?data_carga=${filtros.dataCargaEscolhida || ''}&setor=${filtros.setor || ''}&page=${pagina}&limit=${limiteRegistros}`)
                    .then(response => response.json())
                    .then(data => {
                        atualizarTabela(data.ordens, setor);
                        atualizarPaginacao(data.total_ordens, pagina, data.total_paginas);
                        resolve(); // Resolve a Promise após o sucesso
                    })
                    .catch(error => {
                        console.error("Erro ao carregar a tabela:", error);
                        reject(error); // Rejeita a Promise em caso de erro
                    });
            } else {
                fetch(`/cargas/api/historico-planejamento-pintura/?data_carga=${filtros.dataCargaEscolhida || ''}&cor=${filtros.cor || ''}&page=${pagina}&limit=${limiteRegistros}`)
                    .then(response => response.json())
                    .then(data => {
                        atualizarTabela(data.ordens, setor);
                        atualizarPaginacao(data.total_ordens, pagina, data.total_paginas);
                        resolve(); // Resolve a Promise após o sucesso
                    })
                    .catch(error => {
                        console.error("Erro ao carregar a tabela:", error);
                        reject(error); // Rejeita a Promise em caso de erro
                    });
            }
        } catch (error) {
            reject(error); // Captura outros erros inesperados
        }
    });
}

//  Atualiza a tabela
function atualizarTabela(ordens, setor) {
    const tabelaCorpo = document.getElementById("tabela-corpo");
    tabelaCorpo.innerHTML = "";

    if (ordens.length === 0) {
        tabelaCorpo.innerHTML = `<tr><td colspan="7" class="text-center text-muted">Nenhum dado encontrado.</td></tr>`;
        return;
    }

    ordens.forEach(ordem => {

        const colunaSetor = setor === "montagem" 
            ? `<td>${ordem.ordem__maquina__nome}</td>` 
            : `<td>${ordem.ordem__cor}</td>`;

        const linha = document.createElement("tr");

        linha.innerHTML = `
            <td>${ordem.ordem}</td>
            <td>
                <input type="date" class="form-control data-carga-input" 
                    data-id="${ordem.ordem}" value="${ordem.ordem__data_carga}" 
                    disabled>
            </td>
            ${colunaSetor}
            <td>${ordem.peca}</td>
            <td>
                <input type="number" class="form-control qtd-plan-input" 
                    data-id="${ordem.ordem}" value="${ordem.total_planejada}" 
                    disabled>
            </td>
            <td>
                <button class="btn-editar btn btn-sm btn-warning" data-id="${ordem.ordem}">
                    <i class="far fa-edit"></i>
                </button>
                <button class="btn-confirmar btn btn-sm btn-success d-none" data-id="${ordem.ordem}">
                    <i class="fas fa-check"></i>
                </button>
            </td>
        `;

        tabelaCorpo.appendChild(linha);
    });

    adicionarEventosBotoesEdicao();
}

// Adiciona eventos aos botões de edição
function adicionarEventosBotoesEdicao() {

    const setor = document.getElementById('setor-selecionado').value;

    document.querySelectorAll('.btn-editar').forEach(botao => {
        botao.addEventListener('click', function () {
            const ordemId = this.getAttribute('data-id');
            ativarEdicao(ordemId);
        });
    });

    document.querySelectorAll('.btn-confirmar').forEach(botao => {
        botao.addEventListener('click', function () {
            const ordemId = this.getAttribute('data-id');
            confirmarAlteracao(ordemId, setor);
        });
    });
}

// Ativa os inputs para edição e exibe o botão de confirmar
function ativarEdicao(ordemId) {
    const qtBoaInput = document.querySelector(`.qtd-plan-input[data-id="${ordemId}"]`);
    const dataCargaInput = document.querySelector(`.data-carga-input[data-id="${ordemId}"]`);
    const botaoEditar = document.querySelector(`.btn-editar[data-id="${ordemId}"]`);
    const botaoConfirmar = document.querySelector(`.btn-confirmar[data-id="${ordemId}"]`);

    if (qtBoaInput && dataCargaInput) {
        qtBoaInput.removeAttribute("disabled");
        dataCargaInput.removeAttribute("disabled");

        botaoEditar.classList.add("d-none");
        botaoConfirmar.classList.remove("d-none");
    }
}

// Captura os valores editados e confirma a alteração
function confirmarAlteracao(ordemId, setor) {
    const qtPlanInput = document.querySelector(`.qtd-plan-input[data-id="${ordemId}"]`);
    const dataCargaInput = document.querySelector(`.data-carga-input[data-id="${ordemId}"]`);
    const botaoEditar = document.querySelector(`.btn-editar[data-id="${ordemId}"]`);
    const botaoConfirmar = document.querySelector(`.btn-confirmar[data-id="${ordemId}"]`);

    const novaQtdPlan = qtPlanInput.value;
    const novaDataCarga = dataCargaInput.value;

    if (novaQtdPlan === '') {
        Swal.fire({ icon: 'error', title: 'Erro!', text: 'Preencha todos os campos.' });
        return;
    }

    if (novaDataCarga === '') {
        Swal.fire({ icon: 'error', title: 'Erro!', text: 'Preencha todos os campos.' });
        return;
    }

    // Desativar os campos novamente
    qtPlanInput.setAttribute("disabled", "true");
    dataCargaInput.setAttribute("disabled", "true");

    // Alternar visibilidade dos botões
    botaoEditar.classList.remove("d-none");
    botaoConfirmar.classList.add("d-none");

    // Enviar os dados via fetch
    fetch('/cargas/api/editar-planejamento/', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ordemId: ordemId,
            novaQtdPlan: novaQtdPlan,
            novaDataCarga: novaDataCarga,
            setor: setor
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.erro) {
            Swal.fire({ icon: "error", title: "Erro!", text: data.erro });
        }
    })
    .catch(error => {
        console.error("Erro ao atualizar planejamento:", error);
        Swal.fire({ icon: "error", title: "Erro!", text: "Falha na requisição." });
    });
}

//  Atualiza a paginação
function atualizarPaginacao(totalRegistros, paginaAtual) {
    const totalPaginas = Math.ceil(totalRegistros / 10);
    const paginacaoContainer = document.getElementById("paginacao-container");
    const setor = document.getElementById('setor-selecionado').value;

    paginacaoContainer.innerHTML = "";

    // if (totalPaginas <= 1) return; // Se há apenas uma página, não exibir paginação

    const botaoAnterior = document.createElement("button");
    botaoAnterior.classList.add("btn", "btn-sm", "btn-secondary");
    botaoAnterior.textContent = "Anterior";
    botaoAnterior.disabled = paginaAtual === 1;
    botaoAnterior.addEventListener("click", () => carregarTabela(paginaAtual - 1));
    paginacaoContainer.appendChild(botaoAnterior);

    let startPage, endPage;
    if (totalPaginas <= 5) {
        startPage = 1;
        endPage = totalPaginas;
    } else if (paginaAtual <= 3) {
        startPage = 1;
        endPage = 5;
    } else if (paginaAtual >= totalPaginas - 2) {
        startPage = totalPaginas - 4;
        endPage = totalPaginas;
    } else {
        startPage = paginaAtual - 2;
        endPage = paginaAtual + 2;
    }

    if (startPage > 1) {
        const primeiraPagina = document.createElement("button");
        primeiraPagina.classList.add("btn", "btn-sm", "btn-outline-secondary");
        primeiraPagina.textContent = "1";
        primeiraPagina.addEventListener("click", () => carregarTabela(1));
        paginacaoContainer.appendChild(primeiraPagina);

        if (startPage > 2) {
            const pontos = document.createElement("span");
            pontos.classList.add("mx-1");
            pontos.textContent = "...";
            paginacaoContainer.appendChild(pontos);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        const botaoPagina = document.createElement("button");
        botaoPagina.classList.add("btn", "btn-sm", i === paginaAtual ? "btn-primary" : "btn-outline-secondary");
        botaoPagina.textContent = i;
        botaoPagina.addEventListener("click", () => carregarTabela(i));
        paginacaoContainer.appendChild(botaoPagina);
    }

    if (endPage < totalPaginas) {
        if (endPage < totalPaginas - 1) {
            const pontos = document.createElement("span");
            pontos.classList.add("mx-1");
            pontos.textContent = "...";
            paginacaoContainer.appendChild(pontos);
        }

        const ultimaPagina = document.createElement("button");
        ultimaPagina.classList.add("btn", "btn-sm", "btn-outline-secondary");
        ultimaPagina.textContent = totalPaginas;
        ultimaPagina.addEventListener("click", () => carregarTabela(totalPaginas));
        paginacaoContainer.appendChild(ultimaPagina);
    }

    const botaoProximo = document.createElement("button");
    botaoProximo.classList.add("btn", "btn-sm", "btn-secondary");
    botaoProximo.textContent = "Próximo";
    botaoProximo.disabled = paginaAtual === totalPaginas;
    botaoProximo.addEventListener("click", () => carregarTabela(paginaAtual + 1));
    paginacaoContainer.appendChild(botaoProximo);
}

//  Exibe ou oculta o spinner de carregamento
function mostrarLoading(mostrar) {
    const spinner = document.getElementById("loading-spinner");
    if (spinner) {
        spinner.style.display = mostrar ? "block" : "none";
    }
}

function abrirModalVerPecas(ordemId) {
    const modal = new bootstrap.Modal(document.getElementById('modalDuplicarOrdem'));

    // Busca os dados da ordem já armazenados na memória
    const ordemSelecionada = ordensCarregadas.find(o => o.id == ordemId);
    
    if (!ordemSelecionada) {
        Swal.fire('Erro', 'Ordem não encontrada.', 'error');
        return;
    }

    preencherModalVerPecas(ordemSelecionada);
    modal.show();
}

//  Configuração do botão "Ver Peças"
function configurarBotaoVerPecas() {
    document.addEventListener('click', function (event) {

        const botao = event.target.closest('.btn-ver-pecas'); 

        if (botao) {
            const ordemId = botao.getAttribute('data-id');
            abrirModalVerPecas(ordemId);
        }
    });
}

// Preenche o modal com informações da ordem
function preencherModalVerPecas(data) {
    const bodyDuplicarOrdem = document.getElementById('bodyDuplicarOrdem');

    document.getElementById('modalDuplicarOrdem').setAttribute('data-ordem-id', data.id);

    if (data.pecas && data.pecas.length > 0) {
        bodyDuplicarOrdem.innerHTML = `
            <h4>Peças</h4>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Peça ID</th>
                        <th>Código</th>
                        <th>Nome</th>
                        <th>Quantidade Boa</th>
                        <th>Quantidade Morta</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.pecas.map(peca => `
                        <tr>
                            <td>${peca.id}</td>
                            <td>${peca.peca_codigo}</td>
                            <td>${peca.peca_nome}</td>
                            <td>
                                <input type="number" class="form-control quantidade-boa" 
                                    data-id="${peca.id}" value="${peca.qtd_boa}">
                            </td>
                            <td>
                                <input type="number" class="form-control quantidade-morta" 
                                    data-id="${peca.id}" value="${peca.qtd_morta}">
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        bodyDuplicarOrdem.innerHTML = `<p>Nenhuma peça encontrada para esta ordem.</p>`;
    }
}

function salvarPecas() {
    const formDuplicarOrdem = document.getElementById('formDuplicarOrdem');

    formDuplicarOrdem.addEventListener('submit', function (event) {
        event.preventDefault(); // Evita o recarregamento da página

        // Obtém o ID da ordem armazenado no modal
        const modal = document.getElementById('modalDuplicarOrdem');
        const ordemId = modal.getAttribute('data-ordem-id');

        if (!ordemId) {
            Swal.fire({ icon: 'error', title: 'Erro!', text: 'ID da ordem não encontrado.' });
            return;
        }

        // Captura a lista de peças editadas dentro do modal
        const pecasAtualizadas = [];
        document.querySelectorAll('.quantidade-boa').forEach(input => {
            const pecaId = input.getAttribute('data-id');
            const quantidadeBoa = parseInt(input.value) || 0;
            const quantidadeMorta = parseInt(document.querySelector(`.quantidade-morta[data-id="${pecaId}"]`).value) || 0;

            pecasAtualizadas.push({
                peca_id: pecaId,
                qtd_boa: quantidadeBoa,
                qtd_morta: quantidadeMorta
            });
        });

        // Se nenhuma peça for encontrada, exibe um erro
        if (pecasAtualizadas.length === 0) {
            Swal.fire({ icon: 'error', title: 'Erro!', text: 'Nenhuma peça encontrada para salvar.' });
            return;
        }

        // Monta o objeto com os dados a serem enviados
        const dadosAtualizados = {
            ordemId: ordemId,
            pecas: pecasAtualizadas
        };

        // Exibe o Swal de carregamento
        Swal.fire({
            title: 'Salvando alterações...',
            text: 'Por favor, aguarde...',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        // Envia a requisição via POST para atualizar todas as peças no backend
        fetch('/serra/atualizar-pecas/', {
            method: 'POST',
            body: JSON.stringify(dadosAtualizados),
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {

            const paginaAtual = document.getElementById('pagina-atual').value;

            carregarTabela(paginaAtual);
            swal.close();
        })
        .catch(error => {
            console.log(error);
            swal.close();
        })
    });
}

// Função para obter CSRF Token (caso necessário)
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Função para alternar entre setores
function alternarSetor(event) {
    const setor = event.target.value;
    setorSelecionado.value = setor;
    
    // Atualizar título
    if (setor === 'montagem') {
        tituloSetor.innerHTML = '<i class="bi bi-tools me-1"></i>Setor: Montagem';
        colunaSetor.style.display = 'block';
        colunaCor.style.display = 'none';
    } else {
        tituloSetor.innerHTML = '<i class="bi bi-brush me-1"></i>Setor: Pintura';
        colunaSetor.style.display = 'none';
        colunaCor.style.display = 'block';
    }
    
    // Recarregar dados com o novo setor
    carregarTabela(1);
}

//  Configuração inicial ao carregar a página
document.addEventListener('DOMContentLoaded', () => {
    
    configurarBotaoVerPecas();
    salvarPecas();

    btnSetorMontagem.addEventListener('change', alternarSetor);
    btnSetorPintura.addEventListener('change', alternarSetor);

    // Ação do botão de filtro
    document.getElementById("filtro-form").addEventListener("submit", (event) => {
        event.preventDefault();

        // Desabilitar botão de filtro enquanto carrega
        const btnFiltrar = event.target.querySelector('button[type="submit"]');
        const btnTextOriginal = btnFiltrar.innerHTML;
        btnFiltrar.disabled = true;
        btnFiltrar.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            Filtrando...
        `;
        
        // Chamar função para carregar os dados
        carregarTabela(1).finally(() => {
            // Restaurar botão quando terminar (independente de sucesso ou erro)
            btnFiltrar.disabled = false;
            btnFiltrar.innerHTML = btnTextOriginal;
        });
    });

    carregarTabela(1);
});
