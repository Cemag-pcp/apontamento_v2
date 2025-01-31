function carregarTableOrdens() {
    // Verifica se o DataTable já existe e destrói, se necessário
    if ($.fn.DataTable.isDataTable('#ordens-table')) {
        $('#ordens-table').DataTable().destroy(); // Destroi a instância atual
    }

    // Inicializa o DataTable
    $('#ordens-table').DataTable({
        serverSide: true,
        processing: true,
        dom: '<"top"rt><"bottom"ip><"clear">', // Remove o campo de busca e o seletor "Show Entries"

        ajax: (data, callback) => {
            // Extrair parâmetros para paginação e filtros
            const page = data.start / data.length + 1; // Calcula a página
            const limit = data.length; // Quantidade de itens por página

            const pecasSelecionadas = $('#filtro-peca').val() || [];
            const maquinaSelecionada = document.getElementById('filtro-maquina').value || '';
            const ordemEscolhida = document.getElementById('filtro-ordem').value || '';

            const filtros = {
                pecas: pecasSelecionadas.map(encodeURIComponent).join(';'), // Codifica e junta os itens
                maquina: encodeURIComponent(maquinaSelecionada),
                ordemEscolhida: encodeURIComponent(ordemEscolhida)
            };

            fetch(`api/ordens-criadas/?page=${page}&limit=${limit}&pecas=${filtros.pecas}&maquina=${filtros.maquina}&ordem=${filtros.ordemEscolhida}`)
            .then(response => response.json())
                .then(data => {
                    console.log('Dados retornados pela API:', data);

                    callback({
                        draw: data.draw,
                        recordsTotal: data.recordsTotal,
                        recordsFiltered: data.recordsFiltered,
                        data: data.data
                    });
                })
                .catch(error => {
                    console.error('Erro ao buscar ordens:', error);
                    callback({
                        draw: data.draw || 1,
                        recordsTotal: 0,
                        recordsFiltered: 0,
                        data: []
                    });
                });
        },
        columns: [
            { data: 'id', title: 'ID' },
            { data: 'data_criacao', title: 'Data de Criação' },
            { data: 'ordem', title: 'Ordem' },
            { data: 'grupo_maquina', title: 'Máquina' },
            {
                data: 'propriedade.descricao_mp',
                title: 'Descrição MP',
                defaultContent: '-' // Caso esteja vazio
            },
            {
                data: null,
                title: 'Ações',
                orderable: false, // Evita que a coluna seja ordenada
                render: function (data, type, row) {
                    return `
                        <button class="btn btn-primary btn-ver-pecas" data-id="${row.id}" data-ordem="${row.ordem}">
                            Ver Peças
                        </button>
                    `;
                }
            }
        ],
    });
}

function configurarSelect2Pecas() {
    
    $('#filtro-peca').select2({
        placeholder: 'Selecione uma peça ou mais',
        allowClear: true,
        multiple: true,
        ajax: {
            url: 'api/pecas/',
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

}

function configurarBotaoVerPecas(){
    document.addEventListener('click', function (event) {

        // Verifica se o clique foi em um botão com a classe "btn-ver-pecas"
        if (event.target.classList.contains('btn-ver-pecas')) {
            const ordemId = event.target.getAttribute('data-id'); // Obtém o ID da ordem
            const ordemNome = event.target.getAttribute('data-ordem'); // Obtém o nome da ordem
            
            const modal = new bootstrap.Modal(document.getElementById('modalDuplicarOrdem'))
            const modalElement = document.getElementById('modalDuplicarOrdem'); // Seleciona o elemento do modal

            // Atualiza o título do modal
            document.getElementById('modalDuplicarOrdemLabel').textContent = `Duplicar ordem: ${ordemNome}`;
            
            modalElement.setAttribute('data-ordem-id', ordemId);

            Swal.fire({
                title: 'Carregando...',
                text: 'Buscando informações das peças...',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });

            // Busca as peças relacionadas à ordem
            fetch(`api/duplicar-ordem/${ordemId}/pecas/`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erro ao buscar informações da API');
                }
                return response.json();
            })
            .then(data => {

                Swal.close(); // Fecha o SweetAlert de carregamento
                document.getElementById('bodyDuplicarOrdem').innerHTML = '';

                // Renderiza propriedades
                const propriedadesHTML = `
                    <h6 class="text-center mt-3">Informações da Chapa</h6>
                    <table class="table table-bordered table-sm text-center">
                        <thead>
                            <tr class="table-light">
                                <th>Descrição</th>
                                <th>Espessura</th>
                                <th>Quantidade de Chapas</th>
                                <th>Tipo Chapa</th>
                                <th>Aproveitamento</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>${data.propriedades.descricao_mp || 'N/A'}</td>
                                <td>${data.propriedades.espessura || 'N/A'}</td>
                                <td>
                                    <input 
                                        type="number" 
                                        min="1" 
                                        max="20" 
                                        class="form-control form-control-sm" 
                                        id="propQtd" 
                                        data-qtd-chapa="${data.propriedades.quantidade}" 
                                        value="${data.propriedades.quantidade}" 
                                        style="width: 100px; text-align: center;">
                                </td>
                                <td>${data.propriedades.tipo_chapa || 'N/A'}</td>
                                <td>${data.propriedades.aproveitamento || 'N/A'}</td>
                            </tr>
                        </tbody>
                    </table>
                `;
                document.getElementById('bodyDuplicarOrdem').insertAdjacentHTML('beforeend', propriedadesHTML);

                // Renderiza peças
                if (data.pecas && data.pecas.length > 0) {
                    const pecasHTML = `
                        <h6 class="text-center mt-3">Peças da Ordem</h6>
                        <table class="table table-bordered table-sm text-center">
                            <thead>
                                <tr class="table-light">
                                    <th>Peça</th>
                                    <th>Qtd. Plan.</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.pecas.map((peca, index) => `
                                    <tr>
                                        <td>${peca.peca}</td>
                                        <td class="peca-quantidade" data-peca-id="${peca.peca}"  data-peca-index="${index}" data-quantidade-inicial="${peca.quantidade}">
                                            ${peca.quantidade}
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;
                    document.getElementById('bodyDuplicarOrdem').insertAdjacentHTML('beforeend', pecasHTML);

                    // Atualiza as quantidades de peças ao alterar a quantidade de chapas
                    const propQtdInput = document.getElementById('propQtd');
                    propQtdInput.addEventListener('change', () => {
                        const novaQtdChapas = parseInt(propQtdInput.value, 10);
                        const qtdInicialChapas = parseInt(propQtdInput.dataset.qtdChapa, 10);

                        if (novaQtdChapas && novaQtdChapas > 0) {
                            document.querySelectorAll('.peca-quantidade').forEach(cell => {
                                const qtdInicial = parseInt(cell.dataset.quantidadeInicial, 10); // Quantidade inicial de peças
                                const novaQtdPecas = (qtdInicial / qtdInicialChapas) * novaQtdChapas; // Recalcula a nova quantidade de peças
                        
                                cell.textContent = Math.floor(novaQtdPecas); // Atualiza o texto na célula
                        
                            });
                        }
                    });
                } else {
                    document.getElementById('bodyDuplicarOrdem').innerHTML += '<p class="text-center text-muted">Não há peças cadastradas para esta ordem.</p>';
                }

                modal.show();
            
            })
            .catch(error => {
                console.error('Erro capturado:', error); // Registra o erro no console para depuração
                Swal.close(); // Fecha o SweetAlert de carregamento
                Swal.fire({
                    icon: 'error',
                    title: 'Erro',
                    text: 'Erro ao buscar as informações da ordem.',
                });
            });
        }
    });
}

function duplicarOrdem(){

    Swal.fire({
        title: 'Carregando...',
        text: 'Buscando informações das peças...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    const ordemId = document.getElementById('modalDuplicarOrdem').getAttribute('data-ordem-id'); // ID da ordem original

    // Captura os dados do formulário
    const obsDuplicar = document.getElementById('obsFinalizarCorte').value; // Observação
    const dataProgramacao = document.getElementById('dataProgramacao')?.value || null; // Data de programação, se existir
    const qtdChapa = document.getElementById('propQtd').value; // Quantidade de chapas atualizada

    // Captura as peças e suas quantidades recalculadas
    const pecas = Array.from(document.querySelectorAll('.peca-quantidade')).map(cell => ({
        peca: cell.dataset.pecaId, // Identificador da peça
        qtd_planejada: parseInt(cell.textContent, 10) // Quantidade atualizada
    }));

    // Monta o objeto de dados
    const dadosDuplicacao = {
        obs_duplicar: obsDuplicar,
        dataProgramacao: dataProgramacao,
        qtdChapa: qtdChapa,
        pecas: pecas
    };

    // Envia os dados ao backend
    fetch(`api/duplicar-ordem/${ordemId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken() // Inclui o token CSRF
        },
        body: JSON.stringify(dadosDuplicacao)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro ao duplicar a ordem: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        Swal.fire({
            icon: 'success',
            title: 'Sucesso',
            text: 'A ordem foi duplicada com sucesso!',
        });
    })
    .catch(error => {
        console.error('Erro ao duplicar a ordem:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: 'Erro ao duplicar a ordem. Tente novamente.',
        });
    });
    
    // Função para obter o token CSRF
    function getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

}



document.addEventListener('DOMContentLoaded', () => {
    carregarTableOrdens();
    configurarSelect2Pecas();
    configurarBotaoVerPecas();

    document.getElementById('filtro-form').addEventListener('submit', (event) => {
        event.preventDefault();
        carregarTableOrdens(); // Recria a tabela com os filtros aplicados
    });

    const formGerarOpDuplicada = document.getElementById('formDuplicarOrdem');

    formGerarOpDuplicada.addEventListener('submit', function (event) {
        event.preventDefault(); // Impede o envio padrão do formulário
    
        // Valida manualmente o formulário
        if (!formGerarOpDuplicada.checkValidity()) {
            formGerarOpDuplicada.reportValidity(); // Exibe mensagens de erro padrão do navegador
            return;
        }
    
        duplicarOrdem();

        formGerarOpDuplicada.reset();
    });

});
