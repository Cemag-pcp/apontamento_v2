document.addEventListener('DOMContentLoaded', () => {
    
    // Configuração para a tabela de transferências
    const transferenciaConfig = {
        containerId: 'table-transferencia-container',
        tbodyId: 'table-body-transferencia',
        url: '/almox/api/erros/data-transferencia/', // Substitua pela URL correta
        start: 0,
        length: 10,
        isLoading: false,
        hasMoreItems: true,
        spinnerId: 'spinner-transferencia',
        type: 'transferencia',
        columns: [
            { key: 'chave', label: 'Chave' },
            { key: 'item', label: 'Item' },
            { key: 'qtd', label: 'Quantidade' },
            { key: 'data_solicitacao', label: 'Data Solicitação' },
            { key: 'data_entrega', label: 'Data Entrega' },
            { key: 'dep_destino', label: 'Destino' },
            { key: 'solicitante', label: 'Solicitante' },
            { key: 'erro', label: 'Erro' },
            { key: 'actions', label: 'Ações' },
        ],
    };

    // Configuração para a tabela de estoque
    const requisicaoConfig = {
        containerId: 'table-requisicao-container',
        tbodyId: 'table-body-requisicao',
        url: '/almox/api/erros/data-requisicao/', // Substitua pela URL correta
        start: 0,
        length: 10,
        isLoading: false,
        hasMoreItems: true,
        spinnerId: 'spinner-requisicao',
        type: 'requisicao',
        columns: [
            { key: 'chave', label: 'Chave' },
            { key: 'item', label: 'Item' },
            { key: 'qtd', label: 'Quantidade' },
            { key: 'data_solicitacao', label: 'Data Solicitação' },
            { key: 'data_entrega', label: 'Data Entrega' },
            { key: 'classe_req', label: 'Classe Requisição' },
            { key: 'solicitante', label: 'Solicitante'},
            { key: 'cc', label: 'CC'},
            { key: 'erro', label: 'Erro' },
            { key: 'actions', label: 'Ações' },

        ],
    };

    // Função para mostrar o spinner
    function showSpinner(spinnerId) {
        const spinner = document.getElementById(spinnerId);
        if (spinner) {
            spinner.style.display = 'block';
        }
    }

    // Função para esconder o spinner
    function hideSpinner(spinnerId) {
        const spinner = document.getElementById(spinnerId);
        if (spinner) {
            spinner.style.display = 'none';
        }
    }

    // Função para buscar itens para uma tabela específica
    function fetchItems(config) {
        if (config.isLoading || !config.hasMoreItems) return;
    
        config.isLoading = true;
        showSpinner(config.spinnerId); // Mostra o spinner durante o carregamento
    
        const params = new URLSearchParams({
            start: config.start,
            length: config.length,
            draw: 1,
        });
    
        fetch(`${config.url}?${params.toString()}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erro na requisição');
                }
                return response.json();
            })
            .then(data => {
                const items = data.data;
    
                // Adiciona os itens na tabela correta
                const tableBody = document.getElementById(config.tbodyId);
                items.forEach(item => {
                    const row = document.createElement('tr');
                    row.innerHTML = config.columns
                        .map(col => {
                            if (col.key === 'actions') {
                                return `
                                    <td>
                                        <button 
                                            class="btn btn-primary btn-sm badge" 
                                            onclick="editar('${item.chave}', '${config.type}')">
                                            Editar
                                        </button>
                                        <button 
                                            class="btn btn-danger btn-sm badge" 
                                            onclick="confirmar('${item.chave}', '${config.type}')">
                                            Manual
                                        </button>
                                    </td>
                                `;
                            }
                            return `<td>${item[col.key] || 'N/A'}</td>`;
                        })
                        .join('');
                    tableBody.appendChild(row);
                });
    
                config.start += config.length;
                if (items.length < config.length) {
                    config.hasMoreItems = false;
                }
            })
            .catch(error => {
                console.error("Erro ao buscar dados:", error);
            })
            .finally(() => {
                config.isLoading = false;
                hideSpinner(config.spinnerId); // Esconde o spinner após o carregamento
            });
    }
    
    // Função para inicializar uma tabela específica
    function initializeTable(config) {
        const container = document.getElementById(config.containerId);

        // Carrega os primeiros itens
        fetchItems(config);

        // Evento de scroll no contêiner específico
        container.addEventListener('scroll', () => {
            if (container.scrollTop + container.clientHeight >= container.scrollHeight - 50) {
                fetchItems(config);
            }
        });
    }

    function resetTable(config) {
        const tableBody = document.getElementById(config.tbodyId);
    
        // Limpa a tabela
        while (tableBody.firstChild) {
            tableBody.removeChild(tableBody.firstChild);
        }
    
        // Reinicia a configuração
        config.start = 0;
        config.hasMoreItems = true;
    
        // Recarrega os itens
        fetchItems(config);
    }

    // Inicializa as tabelas
    initializeTable(transferenciaConfig);
    initializeTable(requisicaoConfig);

    document.addEventListener('show.bs.modal', () => {
        document.body.style.paddingRight = '0px';
    });

    document.addEventListener('hidden.bs.modal', () => {
        document.body.style.paddingRight = '0px';
    });

    // Enviar form de edição
    document.getElementById('btnSalvarEditar').addEventListener('click', function () {
        // Captura os dados do formulário
        const formData = new FormData(document.getElementById('formEditar'));
    
        // Converte os dados para um objeto JSON (opcional)
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });
    
        // Envia os dados para o backend via fetch
        fetch('/almox/api/receber-edicao/', {
            method: 'POST', // Método POST para envio de dados
            headers: {
                'Content-Type': 'application/json', // Define que o conteúdo é JSON
                'X-CSRFToken': getCSRFToken() // Função para obter o CSRF token
            },
            body: JSON.stringify(data) // Converte o objeto em JSON
        })
        .then(response => {
            if (response.ok) {
                return response.json(); // Parseia a resposta como JSON
            } else {
                throw new Error('Erro ao enviar o formulário');
            }
        })
        .then(result => {
            // Lógica de sucesso, como atualizar a tabela
            console.log('Dados enviados com sucesso:', result);
    
            // Fecha o modal e atualiza a tabela, se necessário
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalEditar'));
            modal.hide();

            resetTable(transferenciaConfig); // Para tabela de transferências
            resetTable(requisicaoConfig);   // Para tabela de requisições

        })
        .catch(error => {
            // Lógica de erro
            console.error('Erro no envio:', error);
            alert('Ocorreu um erro ao salvar os dados.');
        });
    });
    // Enviar form de confirmação de ajuste manual
    document.getElementById('btnConfirmarManual').addEventListener('click', function () {
        // Captura os dados do formulário
        const formData = new FormData(document.getElementById('formEditarManual'));
    
        // Converte os dados para um objeto JSON (opcional)
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });
    
        // Envia os dados para o backend via fetch
        fetch('/almox/api/receber-ajuste-manual/', {
            method: 'POST', // Método POST para envio de dados
            headers: {
                'Content-Type': 'application/json', // Define que o conteúdo é JSON
                'X-CSRFToken': getCSRFToken() // Função para obter o CSRF token
            },
            body: JSON.stringify(data) // Converte o objeto em JSON
        })
        .then(response => {
            if (response.ok) {
                return response.json(); // Parseia a resposta como JSON
            } else {
                throw new Error('Erro ao enviar o formulário');
            }
        })
        .then(result => {
            // Lógica de sucesso, como atualizar a tabela
            console.log('Dados enviados com sucesso:', result);
    
            // Fecha o modal e atualiza a tabela, se necessário
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalConfirmar'));
            modal.hide();

            resetTable(transferenciaConfig); // Para tabela de transferências
            resetTable(requisicaoConfig);   // Para tabela de requisições

        })
        .catch(error => {
            // Lógica de erro
            console.error('Erro no envio:', error);
            alert('Ocorreu um erro ao salvar os dados.');
        });
    });

});

// Função para obter o CSRF token (se você estiver usando Django)
function getCSRFToken() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    return csrfToken;
}

function editar(chave, type) {

    // Monta a URL com o parâmetro `type` e `chave`
    const url = `/almox/api/get-dados/?type=${type}&chave=${chave}`;

    // Exibe o modal de carregamento
    Swal.fire({
        title: 'Processando...',
        text: 'Aguarde enquanto processamos sua solicitação.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading(); // Exibe o spinner de carregamento
        }
    });

    // Chama a API
    chamarApi(url)
        .then(data => {
            if (data) {
                const container = document.getElementById('recursos-container');

                // Remove qualquer instância anterior do recurso
                container.innerHTML = '';

                // Adiciona o campo Select dinamicamente
                const recursoHTML = `
                    <label for="recurso" class="form-label">Recurso:</label>
                    <select name="recurso" class="form-select mb-2 recurso-select">
                        <!-- Options serão carregados dinamicamente -->
                    </select>
                `;
                container.insertAdjacentHTML('beforeend', recursoHTML);

                // Preenche os campos do modal
                document.getElementById('editarQuantidade').value = data.quantidade || '';
                document.getElementById('editarChave').value = chave;

                const classeContainer = document.getElementById('editarClasseContainer');

                if (type === 'transferencia') {
                    document.getElementById('editarType').value = "transferencia";

                    classeContainer.style.display = 'none';
                } else {
                    document.getElementById('editarType').value = "requisicao";

                    classeContainer.style.display = 'block';

                    const editarClasse = document.getElementById('editarClasse');

                    const classeValue = String(data.classe || ''); // Certifica que é string

                    if ([...editarClasse.options].some(option => option.value === classeValue)) {
                        editarClasse.value = classeValue; // Define o valor se existir nas opções
                    } else {
                        console.warn(`Valor '${classeValue}' não corresponde a nenhuma opção.`);
                        editarClasse.value = ''; // Reseta o select caso o valor seja inválido
                    }
                
                }

                // Seleciona o novo campo Select adicionado
                const recursoSelect = container.querySelector('.recurso-select');

                // Inicializa o Select2 no campo adicionado
                $(recursoSelect).select2({
                    dropdownParent: $('#modalEditar'),
                    theme: 'bootstrap-5',
                    ajax: {
                        url: `/almox/api/get-recursos/?type=${type}`,
                        dataType: 'json',
                        delay: 250,
                        data: function (params) {
                            return {
                                search: params.term,
                                page: params.page || 1,
                            };
                        },
                        processResults: function (data, params) {
                            params.page = params.page || 1;

                            return {
                                results: data.results.map(item => ({
                                    id: item.id,
                                    text: item.label,
                                })),
                                pagination: {
                                    more: data.next,
                                },
                            };
                        },
                        cache: true,
                    },
                    placeholder: 'Selecione um recurso',
                    minimumInputLength: 0,
                    allowClear: true,
                });

                // Adiciona o valor inicial ao Select2
                if (data.recurso_selecionado) {
                    console.log(data.recurso_selecionado);
                    const selectedOption = new Option(
                        `${data.recurso_selecionado.label}`,
                        data.recurso_selecionado.id,
                        true,
                        true
                    );
                    $(recursoSelect).append(selectedOption).trigger('change');
                }

                // Exibe o modal
                const modalEditar = new bootstrap.Modal(document.getElementById('modalEditar'));
                modalEditar.show();

                Swal.close();

            }
        })
        .catch(error => {
            // Exibe um alerta em caso de erro
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: 'Ocorreu um erro ao processar sua solicitação.'
            });
            console.error('Erro ao chamar API:', error);

            // Fecha o modal em caso de erro
            Swal.close();
        });
}

function confirmar(chave, type) {
    // Preenche os campos do modal de confirmação
    document.getElementById('confirmarChave').textContent = chave;
    document.getElementById('manualChave').value = chave;
    document.getElementById('manualTipo').value = type;
    
    // Exibe o modal
    const modalConfirmar = new bootstrap.Modal(document.getElementById('modalConfirmar'));
    modalConfirmar.show();
}

function chamarApi(url) {
    return fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro na API');
            }
            return response.json();
        })
        .catch(error => {
            console.error('Erro ao chamar a API:', error);
            return null;
        });
}



