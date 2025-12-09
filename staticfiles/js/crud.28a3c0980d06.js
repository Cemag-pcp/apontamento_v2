function carregarTabela(pagina) {
    mostrarLoading(true); // 🔥 Exibe o spinner

    const pecasSelecionadas = document.getElementById('filtro-peca')?.value || '';
    const maquinaSelecionada = document.getElementById('filtro-maquina')?.value || '';
    const ordemEscolhida = document.getElementById('filtro-ordem')?.value || '';

    const filtros = {
        pecas: encodeURIComponent(pecasSelecionadas),
        maquina: encodeURIComponent(maquinaSelecionada),
        ordem: encodeURIComponent(ordemEscolhida),
    };

    fetch(`api/ordens-criadas/?page=${pagina}&limit=100&pecas=${filtros.pecas}&maquina=${filtros.maquina}&ordem=${filtros.ordem}`)
        .then(response => response.json())
        .then(data => {
            atualizarTabela(data.data);
            atualizarPaginacao(data.recordsTotal, pagina);
        })
        .finally(() => mostrarLoading(false)); // 🔥 Oculta o spinner
}

//  Atualiza a tabela
function atualizarTabela(ordens) {
    const tabelaCorpo = document.getElementById("tabela-corpo");
    tabelaCorpo.innerHTML = "";

    if (ordens.length === 0) {
        tabelaCorpo.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Nenhum dado encontrado.</td></tr>`;
        return;
    }

    ordens.forEach(ordem => {
        const linha = document.createElement("tr");

        linha.innerHTML = `
            <td>${ordem.ordem}</td>
            <td>${ordem.data_criacao}</td>
            <td>${ordem.grupo_maquina}</td>
            <td>${ordem.propriedade?.descricao_mp || '-'}</td>
            <td>${ordem.propriedade?.aproveitamento || '-'}</td>
            <td>
                <button class="btn-ver-pecas btn btn-sm btn-primary" data-id="${ordem.id}">Ver Peças</button>
            </td>
        `;

        tabelaCorpo.appendChild(linha);
    });
}

//  Atualiza a paginação
function atualizarPaginacao(totalRegistros, paginaAtual) {
    const totalPaginas = Math.ceil(totalRegistros / 10);
    const paginacaoContainer = document.getElementById("paginacao-container");

    paginacaoContainer.innerHTML = "";

    if (totalPaginas <= 1) return; // Se há apenas uma página, não exibir paginação

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

//  Configuração do Select2 para o filtro de peças
function configurarSelect2Pecas() {
    $('#filtro-peca').select2({
        placeholder: 'Selecione uma peça ou mais',
        allowClear: true,
        multiple: true,
        ajax: {
            url: 'api/pecas/',
            dataType: 'json',
            delay: 250,
            data: params => ({
                search: params.term || '',
                page: params.page || 1,
                per_page: 10
            }),
            processResults: (data, params) => ({
                results: data.results.map(item => ({
                    id: item.id,
                    text: item.text
                })),
                pagination: { more: data.pagination.more }
            }),
            cache: true
        },
        minimumInputLength: 0,
    });
}

function abrirModalDuplicacao(ordemId) {
    const modal = new bootstrap.Modal(document.getElementById('modalDuplicarOrdem'));

    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das peças...',
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading()
    });

    fetch(`api/duplicar-ordem/${ordemId}/pecas/`)
        .then(response => response.json())
        .then(data => {
            Swal.close();
            preencherModalDuplicacao(data,ordemId);
            modal.show();
        })
        .catch(error => {
            console.error('Erro capturado:', error);
            Swal.close();
            Swal.fire({ icon: 'error', title: 'Erro', text: 'Erro ao buscar informações da ordem.' });
        });
}

//  Configuração do botão "Ver Peças"
function configurarBotaoVerPecas() {
    document.addEventListener('click', function (event) {
        if (event.target.classList.contains('btn-ver-pecas')) {
            const ordemId = event.target.getAttribute('data-id'); 
            abrirModalDuplicacao(ordemId);
        }
    });
}

//  Preenche o modal com informações da duplicação
function preencherModalDuplicacao(data,ordemId) {
    const bodyDuplicarOrdem = document.getElementById('bodyDuplicarOrdem');

    document.getElementById('modalDuplicarOrdem').setAttribute('data-ordem-id', ordemId);

    // Criando o conteúdo inicial do modal com a tabela da chapa
    bodyDuplicarOrdem.innerHTML = `
        <h6 class="text-center mt-3">Informações da Chapa</h6>
        <table class="table table-bordered table-sm text-center">
            <thead>
                <tr class="table-light">
                    <th>Chave</th>
                    <th>Descrição</th>
                    <th>Espessura</th>
                    <th>Quantidade</th>
                    <th>Tipo Chapa</th>
                    <th>Aproveitamento</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>${ordemId}</td> 
                    <td>${data.propriedades?.descricao_mp || 'N/A'}</td>
                    <td>${data.propriedades?.espessura || 'N/A'}</td>
                    <td>
                        <input type="number" id="quantidadeChapas" 
                               class="form-control form-control-sm" 
                               data-value-original="${data.propriedades?.quantidade || 1}" 
                               value="${data.propriedades?.quantidade || 1}" 
                               min="1" style="width: 80px;">
                    </td>
                    <td>${data.propriedades?.tipo_chapa || 'N/A'}</td>
                    <td>${data.propriedades?.aproveitamento || 'N/A'}</td>
                </tr>
            </tbody>
        </table>
    `;

    // Criando a tabela de peças, armazenando os dados no HTML para futura atualização
    if (data.pecas.length > 0) {
        bodyDuplicarOrdem.innerHTML += `
            <h6 class="text-center mt-3">Peças da Ordem</h6>
            <table class="table table-bordered table-sm text-center">
                <thead>
                    <tr class="table-light">
                        <th>Peça</th>
                        <th>Qtd. Plan.</th>
                    </tr>
                </thead>
                <tbody id="tabelaPecas">
                    ${data.pecas.map(peca => `
                        <tr data-peca="${peca.peca}" 
                            data-qtd-original="${peca.quantidade}">
                            <td>${peca.peca}</td>
                            <td class="qtd-peca">${peca.quantidade}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    // Captura o campo de quantidade de chapas
    const inputQuantidadeChapas = document.getElementById('quantidadeChapas');
    const quantidadeOriginalChapas = parseInt(inputQuantidadeChapas.getAttribute('data-value-original')) || 1;

    // Evento para recalcular a quantidade de peças proporcionalmente
    inputQuantidadeChapas.addEventListener('input', () => {
        const novaQuantidadeChapas = parseInt(inputQuantidadeChapas.value) || 1;
        atualizarQuantidadePecas(quantidadeOriginalChapas, novaQuantidadeChapas);
    });
}

// Função para recalcular as quantidades de peças conforme a quantidade de chapas
function atualizarQuantidadePecas(quantidadeOriginalChapas, novaQuantidadeChapas) {
    const tabelaPecas = document.getElementById('tabelaPecas');

    if (tabelaPecas) {
        tabelaPecas.querySelectorAll('tr').forEach(row => {
            const quantidadeOriginalPeca = parseInt(row.getAttribute('data-qtd-original')) || 0;

            // Regra de três para recalcular proporcionalmente
            const novaQuantidadePeca = Math.floor(
                (novaQuantidadeChapas * quantidadeOriginalPeca) / quantidadeOriginalChapas
            );

            // Atualiza a célula com a nova quantidade
            row.querySelector('.qtd-peca').textContent = novaQuantidadePeca;
        });
    }
}

function duplicarOrdem() {
    const formDuplicarOrdem = document.getElementById('formDuplicarOrdem');

    formDuplicarOrdem.addEventListener('submit', function (event) {
        event.preventDefault(); // Evita recarregar a página

        // Obtém o ID da ordem armazenado no modal
        const modal = document.getElementById('modalDuplicarOrdem');
        const ordemId = modal.getAttribute('data-ordem-id');
        console.log(ordemId);

        if (!ordemId) {
            Swal.fire({ icon: 'error', title: 'Erro!', text: 'ID da ordem não encontrado.' });
            return;
        }

        // Captura os valores do formulário
        const obsDuplicar = document.getElementById('obsFinalizarCorte').value;
        const dataProgramacao = document.getElementById('dataProgramacao').value;
        const quantidadeChapas = parseFloat(document.getElementById('quantidadeChapas').value) || 1;

        // Captura a lista de peças com as novas quantidades
        const pecas = [];
        document.querySelectorAll('#tabelaPecas tr').forEach(row => {
            const pecaNome = row.getAttribute('data-peca');
            const qtdPlanejada = parseInt(row.querySelector('.qtd-peca').textContent) || 0;

            pecas.push({ peca: pecaNome, qtd_planejada: qtdPlanejada });
        });

        // Monta o objeto com os dados a serem enviados
        const dadosDuplicacao = {
            obs_duplicar: obsDuplicar,
            dataProgramacao: dataProgramacao,
            qtdChapa: quantidadeChapas,
            pecas: pecas
        };

        console.log("Enviando dados para duplicação:", dadosDuplicacao);

        // Exibe o Swal de carregamento
        Swal.fire({
            title: 'Duplicando Ordem...',
            text: 'Por favor, aguarde...',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        // Enviar a requisição para a API
        fetch(`/corte/duplicar-op/api/duplicar-ordem/${ordemId}/`, {
            method: 'POST',
            body: JSON.stringify(dadosDuplicacao),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() // Certifica-se de incluir o CSRF Token
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errorData => {
                    throw new Error(errorData.error || `Erro na requisição: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Sucesso:', data);

            // Fecha o Swal de loading e exibe mensagem de sucesso
            Swal.fire({
                icon: 'success',
                title: 'Sucesso!',
                text: 'Ordem duplicada com sucesso.',
                timer: 1500,  // Fecha automaticamente após 1.5s
                showConfirmButton: false
            });

            // Esconde o modal após o sucesso
            const bootstrapModal = bootstrap.Modal.getInstance(modal);
            bootstrapModal.hide();

        })
        .catch(error => {
            console.error('Erro:', error);

            // Fecha o Swal de loading e exibe erro
            Swal.fire({
                icon: 'error',
                title: 'Erro!',
                text: error.message,
            });
        });
    });
}

// Função para obter CSRF Token (caso necessário)
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

//  Configuração inicial ao carregar a página
document.addEventListener('DOMContentLoaded', () => {
    configurarSelect2Pecas();
    configurarBotaoVerPecas();
    duplicarOrdem();

    // Ação do botão de filtro
    document.getElementById("filtro-form").addEventListener("submit", (event) => {
        event.preventDefault();
        carregarTabela(1);
    });

    carregarTabela(1);
});


