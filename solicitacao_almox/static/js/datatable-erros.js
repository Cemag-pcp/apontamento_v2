document.addEventListener('DOMContentLoaded', () => {
    
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

    // Monta o conteúdo (células) de uma linha da tabela
    function renderRowCells(item, config) {
        return config.columns
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
    }

    function findRow(config, chave) {
        const tableBody = document.getElementById(config.tbodyId);
        if (!tableBody) return null;
        return tableBody.querySelector(`tr[data-chave="${CSS.escape(String(chave))}"]`);
    }

    // Estilos do feedback visual da linha (carregando / salvo)
    if (!document.getElementById('erros-linha-estilos')) {
        const estilo = document.createElement('style');
        estilo.id = 'erros-linha-estilos';
        estilo.textContent = `
            tr.linha-carregando td { opacity: .45; pointer-events: none; }
            tr.linha-carregando td.celula-status { opacity: 1; }
            tr.linha-salva td { background-color: #d1e7dd !important; transition: background-color .3s; }
        `;
        document.head.appendChild(estilo);
    }

    // Coloca/retira o "loading" na linha enquanto o servidor processa
    function marcarLinhaCarregando(config, chave, carregando, texto = 'Salvando...') {
        const row = findRow(config, chave);
        if (!row) return;
        const celulaAcoes = row.lastElementChild;
        if (carregando) {
            row.classList.add('linha-carregando');
            row.querySelectorAll('button').forEach(btn => { btn.disabled = true; });
            if (celulaAcoes && !celulaAcoes.querySelector('.linha-spinner')) {
                celulaAcoes.classList.add('celula-status');
                celulaAcoes.dataset.htmlOriginal = celulaAcoes.innerHTML;
                celulaAcoes.innerHTML = `
                    <span class="linha-spinner text-primary small text-nowrap">
                        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                        ${texto}
                    </span>`;
            }
        } else {
            row.classList.remove('linha-carregando');
            if (celulaAcoes && celulaAcoes.dataset.htmlOriginal !== undefined) {
                celulaAcoes.innerHTML = celulaAcoes.dataset.htmlOriginal;
                delete celulaAcoes.dataset.htmlOriginal;
                celulaAcoes.classList.remove('celula-status');
            }
            row.querySelectorAll('button').forEach(btn => { btn.disabled = false; });
        }
    }

    // Atualiza apenas a linha editada, sem recarregar a tabela
    function atualizarLinha(config, linha) {
        const row = findRow(config, linha.chave);
        if (row) {
            row.classList.remove('linha-carregando');
            row.innerHTML = renderRowCells(linha, config);
            // Destaque rápido de "salvo"
            row.classList.add('linha-salva');
            setTimeout(() => row.classList.remove('linha-salva'), 1500);
        }
    }

    // Remove apenas a linha (ajuste manual tira o item da lista de erros)
    function removerLinha(config, chave) {
        const row = findRow(config, chave);
        if (row) {
            row.remove();
            // A paginação é por offset: com um item a menos no servidor,
            // o próximo lote começa uma posição antes.
            config.start = Math.max(0, config.start - 1);
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
                if (!tableBody) return;
                items.forEach(item => {
                    // Evita duplicar linha quando o offset recua após remoções
                    if (findRow(config, item.chave)) return;
                    const row = document.createElement('tr');
                    row.dataset.chave = item.chave;
                    row.innerHTML = renderRowCells(item, config);
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
        if (!container) return;

        fetchItems(config);

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
    initializeTable(requisicaoConfig);

    document.addEventListener('show.bs.modal', () => {
        document.body.style.paddingRight = '0px';
    });

    document.addEventListener('hidden.bs.modal', () => {
        document.body.style.paddingRight = '0px';
    });

    // Enviar form de edição
    document.getElementById('btnSalvarEditar').addEventListener('click', function () {
        const botao = this;
        // Evita cliques repetidos enquanto a edição está sendo enviada
        if (botao.disabled) return;
        const textoOriginalBotao = botao.innerHTML;
        botao.disabled = true;
        botao.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Salvando...';

        // Captura os dados do formulário
        const formData = new FormData(document.getElementById('formEditar'));
    
        // Converte os dados para um objeto JSON (opcional)
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });

        // Fecha o modal na hora e mostra o "loading" na própria linha
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalEditar')).hide();
        marcarLinhaCarregando(requisicaoConfig, data.editarChave, true, 'Salvando...');

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
    
            if (result.linha) {
                atualizarLinha(requisicaoConfig, result.linha);
            } else {
                resetTable(requisicaoConfig);
            }

        })
        .catch(error => {
            // Lógica de erro
            marcarLinhaCarregando(requisicaoConfig, data.editarChave, false);
            console.error('Erro no envio:', error);
            alert('Ocorreu um erro ao salvar os dados.');
        })
        .finally(() => {
            botao.disabled = false;
            botao.innerHTML = textoOriginalBotao;
        });
    });
    // Enviar form de confirmação de ajuste manual
    document.getElementById('btnConfirmarManual').addEventListener('click', function () {
        const botao = this;
        // Evita cliques repetidos enquanto o ajuste está sendo enviado
        if (botao.disabled) return;
        const textoOriginalBotao = botao.innerHTML;
        botao.disabled = true;
        botao.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Confirmando...';

        // Captura os dados do formulário
        const formData = new FormData(document.getElementById('formEditarManual'));
    
        // Converte os dados para um objeto JSON (opcional)
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });

        // Fecha o modal na hora e mostra o "loading" na própria linha
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalConfirmar')).hide();
        marcarLinhaCarregando(requisicaoConfig, data.manualChave, true, 'Confirmando...');

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
    
            removerLinha(requisicaoConfig, data.manualChave);

        })
        .catch(error => {
            // Lógica de erro
            marcarLinhaCarregando(requisicaoConfig, data.manualChave, false);
            console.error('Erro no envio:', error);
            alert('Ocorreu um erro ao salvar os dados.');
        })
        .finally(() => {
            botao.disabled = false;
            botao.innerHTML = textoOriginalBotao;
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
                const modalEditar = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalEditar'));
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
    const modalConfirmar = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalConfirmar'));
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



