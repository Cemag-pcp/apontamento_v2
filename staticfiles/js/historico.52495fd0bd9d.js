
let ordensCarregadas = [];

function carregarTabela(pagina) {
    mostrarLoading(true); //  Exibe o spinner

    document.getElementById('pagina-atual').value = pagina;

    // const pecasSelecionadas = document.getElementById('filtro-peca')?.value || '';
    // const maquinaSelecionada = document.getElementById('filtro-maquina')?.value || '';
    const ordemEscolhida = document.getElementById('filtro-ordem')?.value || '';

    const filtros = {
        // pecas: encodeURIComponent(pecasSelecionadas),
        // maquina: encodeURIComponent(maquinaSelecionada),
        ordem: encodeURIComponent(ordemEscolhida),
    };

    fetch(`/serra/api/ordens-criadas/?page=${pagina}&limit=100&status=finalizada&ordem=${filtros.ordem}`)
        .then(response => response.json())
        .then(data => {
            ordensCarregadas = data.ordens; // Armazena as ordens carregadas globalmente
            atualizarTabela(data.ordens);
            atualizarPaginacao(data.total_ordens, pagina);

        })
        .finally(() => mostrarLoading(false)); //  Oculta o spinner
}

//  Atualiza a tabela
function atualizarTabela(ordens) {
    const tabelaCorpo = document.getElementById("tabela-corpo");
    tabelaCorpo.innerHTML = "";

    if (ordens.length === 0) {
        tabelaCorpo.innerHTML = `<tr><td colspan="7" class="text-center text-muted">Nenhum dado encontrado.</td></tr>`;
        return;
    }

    ordens.forEach(ordem => {
        const linha = document.createElement("tr");
    
        const mpCodigo = ordem.propriedade?.nova_mp_codigo || ordem.propriedade?.mp_codigo;
        const mpDescricao = ordem.propriedade?.nova_mp || ordem.propriedade?.descricao_mp;
        const selectId = `selectMpSerraAlterar-${ordem.id}`;
        
        linha.innerHTML = `
            <td>${ordem.ordem}</td>
            <td>${ordem.data_criacao}</td>
            <td>${ordem.maquina}</td>
    
            <td style="text-align: center; padding: 5px;">
                <select 
                    id="${selectId}"
                    class="form-select form-select-sm select2-materia-prima"
                    style="width: 100%; max-width: 150px; font-size: 0.85rem; padding: 0.2rem 0.5rem; height: auto;"
                    disabled>
                    <option value="${mpCodigo}" selected>${mpDescricao}</option>
                </select disabled>
            </td>
    
            <td>
                <input type="number" class="form-control tamanho-input" 
                    data-id="${ordem.id}" value="${ordem.propriedade?.tamanho || ''}" 
                    disabled>
            </td>
            <td>
                <input type="number" class="form-control quantidade-input" 
                    data-id="${ordem.id}" value="${ordem.propriedade?.quantidade || ''}" 
                    disabled>
            </td>
            <td class="d-flex gap-2">
                <button class="btn-editar btn btn-sm btn-warning" data-id="${ordem.id}">
                    <i class="far fa-edit"></i>
                </button>
                <button class="btn-confirmar btn btn-sm btn-success d-none" data-id="${ordem.id}">
                    <i class="fas fa-check"></i>
                </button>
                <button class="btn-ver-pecas btn btn-sm btn-primary" data-id="${ordem.id}">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        `;
    
        tabelaCorpo.appendChild(linha); // Agora a linha já está no DOM
    
        // Inicializa o Select2 para a linha adicionada
        $(`#${selectId}`).select2({
            theme: 'bootstrap-5', // Tema específico para Bootstrap 5
            ajax: {
                url: '/serra/api/get-mp/',
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
        });
    });
    

    adicionarEventosBotoesEdicao();
}

// Adiciona eventos aos botões de edição
function adicionarEventosBotoesEdicao() {
    document.querySelectorAll('.btn-editar').forEach(botao => {
        botao.addEventListener('click', function () {
            const ordemId = this.getAttribute('data-id');
            ativarEdicao(ordemId);
        });
    });

    document.querySelectorAll('.btn-confirmar').forEach(botao => {
        botao.addEventListener('click', function () {
            const ordemId = this.getAttribute('data-id');
            confirmarAlteracao(ordemId);
        });
    });
}

// Ativa os inputs para edição e exibe o botão de confirmar
function ativarEdicao(ordemId) {
    const tamanhoInput = document.querySelector(`.tamanho-input[data-id="${ordemId}"]`);
    const quantidadeInput = document.querySelector(`.quantidade-input[data-id="${ordemId}"]`);
    const botaoEditar = document.querySelector(`.btn-editar[data-id="${ordemId}"]`);
    const botaoConfirmar = document.querySelector(`.btn-confirmar[data-id="${ordemId}"]`);
    const selectMateriaPrima = $(`#selectMpSerraAlterar-${ordemId}`); // Select2

    if (tamanhoInput && quantidadeInput && selectMateriaPrima.length) {
        tamanhoInput.removeAttribute("disabled");
        quantidadeInput.removeAttribute("disabled");
        selectMateriaPrima.prop("disabled", false); // Habilita o Select2

        botaoEditar.classList.add("d-none");
        botaoConfirmar.classList.remove("d-none");
    }
}

// Captura os valores editados e confirma a alteração
function confirmarAlteracao(ordemId) {
    const tamanhoInput = document.querySelector(`.tamanho-input[data-id="${ordemId}"]`);
    const quantidadeInput = document.querySelector(`.quantidade-input[data-id="${ordemId}"]`);
    const botaoEditar = document.querySelector(`.btn-editar[data-id="${ordemId}"]`);
    const botaoConfirmar = document.querySelector(`.btn-confirmar[data-id="${ordemId}"]`);
    // const selectMateriaPrima = $(`#selectMpSerraAlterar-${ordemId}`); // Captura o Select2
    const selectMateriaPrima = document.getElementById(`selectMpSerraAlterar-${ordemId}`).value;

    const novoTamanho = tamanhoInput.value;
    const novaQuantidade = quantidadeInput.value;
    const novaMateriaPrimaId = selectMateriaPrima; // selectMateriaPrima.val(); // Obtém o ID da matéria-prima selecionada

    // Desativar os campos novamente
    tamanhoInput.setAttribute("disabled", "true");
    quantidadeInput.setAttribute("disabled", "true");

    // Desabilita o `<select>` original e também o Select2 visual
    const selectMateriaPrima_select2 = $(`#selectMpSerraAlterar-${ordemId}`);
    selectMateriaPrima_select2.prop("disabled", true); // Desativa o `<select>` padrão
    selectMateriaPrima_select2.select2('enable', false); // Desativa o Select2 visual

    // Alternar visibilidade dos botões
    botaoEditar.classList.remove("d-none");
    botaoConfirmar.classList.add("d-none");

    // Dados a serem enviados para o backend
    const dadosAtualizados = {
        ordemId: ordemId,
        novoTamanho: novoTamanho,
        novaQuantidade: novaQuantidade,
        novaMateriaPrimaId: novaMateriaPrimaId // Adicionando a nova MP selecionada
    };

    console.log("Enviando dados para atualização:", dadosAtualizados);

    // Enviar os dados via fetch
    fetch('/serra/atualizar-propriedades/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(dadosAtualizados)
    })
    .then(response => response.json())
    .catch(error => {
        console.error("Erro na requisição:", error);
        Swal.fire({ icon: 'error', title: 'Erro!', text: 'Ocorreu um erro ao salvar as alterações.' });
    });
}

//  Atualiza a paginação
function atualizarPaginacao(totalRegistros, paginaAtual) {
    const totalPaginas = Math.ceil(totalRegistros / 10);
    const paginacaoContainer = document.getElementById("paginacao-container");

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

//  Configuração inicial ao carregar a página
document.addEventListener('DOMContentLoaded', () => {
    
    configurarBotaoVerPecas();
    salvarPecas();

    // Ação do botão de filtro
    document.getElementById("filtro-form").addEventListener("submit", (event) => {
        event.preventDefault();
        mostrarLoading(true);
        carregarTabela(1);
    });

    carregarTabela(1);
});
