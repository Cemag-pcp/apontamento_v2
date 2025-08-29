document.addEventListener("DOMContentLoaded", () => {
    
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('inspecionar-solda')){
            
            // Reset do formulário e limpeza dos selects
            document.getElementById("form-inspecao").reset();
            $('.select2').val(null).trigger('change');

            const dataInspecao = document.getElementById('data-inspecao-solda-tanque');
            const hoje = new Date().toISOString().split('T')[0];
            dataInspecao.value = hoje;
            
            const modalSolda = new bootstrap.Modal(document.getElementById('modal-inspecionar-solda-tanque'));
            const nomeTanque = event.target.getAttribute('data-nome');
            const idTanque = event.target.getAttribute('data-id');

            document.getElementById("id-inspecao-solda-tanque").value = idTanque;
            document.getElementById('peca-inspecao-solda-tanque').value = nomeTanque;
            modalSolda.show();
            
        } else if (event.target.classList.contains('get-inspecionar-solda')){
            const idTanque = event.target.getAttribute('data-id');
            buscarDadosInspecaoTanque(idTanque);
        }
    });

    async function buscarDadosInspecaoTanque(idTanque) {
        try {
            // Mostrar loading no botão (se existir no modal de visualização)
            const loadingElement = document.querySelector('#modal-inspecionar-solda-tanque-get .spinner-border');
            if (loadingElement) {
                loadingElement.style.display = 'inline-block';
            }

            // Fazer requisição para a API
            const response = await fetch(`/inspecao/api/itens-enviados-tanque/${idTanque}/`);
            
            if (!response.ok) {
                throw new Error('Erro ao buscar dados da API');
            }
            
            const dados = await response.json();
            
            // Preencher o modal GET com os dados retornados
            preencherModalGetComDados(dados);
            
            // Abrir o modal GET
            const modalSoldaGet = new bootstrap.Modal(document.getElementById('modal-inspecionar-solda-tanque-get'));
            modalSoldaGet.show();
            
        } catch (error) {
            console.error('Erro:', error);
            alert('Erro ao carregar dados da inspeção');
        } finally {
            // Esconder loading
            const loadingElement = document.querySelector('#modal-inspecionar-solda-tanque-get .spinner-border');
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        }
    }

    // Função para preencher o modal GET com os dados da API
    function preencherModalGetComDados(dados) {
        // Preencher campos do modal GET com dados da API
        const form = document.getElementById('form-solda-tanque-get');
        form.reset();

        if (dados.id) {
            document.getElementById("id-inspecao-solda-tanque-get").value = dados.id;
        }
        
        if (dados.nome) {
            document.getElementById('peca-inspecao-solda-tanque-get').value = dados.nome;
        }
        
        if (dados.data_inspecao) {
            document.getElementById('data-inspecao-solda-tanque-get').value = dados.data_inspecao.split('T')[0];
        } else {
            const hoje = new Date().toISOString().split('T')[0];
            document.getElementById('data-inspecao-solda-tanque-get').value = hoje;
        }
        
        if (dados.quantidade_produzida) {
            document.getElementById('qtd-produzida-solda-tanque-get').value = dados.quantidade_produzida;
        }
        
        if (dados.inspetor) {
            document.getElementById('inspetor-inspecao-solda-tanque-get').value = dados.inspetor;
        }
        
        if (dados.conformidade >= 0) {
            document.getElementById('conformidade-inspecao-solda-tanque-get').value = dados.conformidade;
        }
        
        if (dados.nao_conformidade >= 0) {
            document.getElementById('nao-conformidade-inspecao-solda-tanque-get').value = dados.nao_conformidade;
        }
        
        if (dados.observacao) {
            document.getElementById('observacao-inspecao-solda-tanque-get').value = dados.observacao;
        }

        // Preencher lista de causas
        const listaCausasContainer = document.getElementById('lista-causas-container');
        listaCausasContainer.innerHTML = ''; // Limpar container

        if (dados.causas && dados.causas.length > 0) {
            dados.causas.forEach((causa, index) => {
                const cardCausa = document.createElement('div');
                cardCausa.className = 'card mb-3';
                cardCausa.innerHTML = `
                    <div class="card-header bg-light">
                        <strong>Causa ${index + 1}</strong>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <p><strong>Nome:</strong> ${causa.nome}</p>
                                <p><strong>Quantidade:</strong> ${causa.quantidade}</p>
                            </div>
                        </div>
                        ${causa.imagens && causa.imagens.length > 0 ? `
                            <div class="mt-3">
                                <strong>Imagens:</strong>
                                <div class="d-flex flex-wrap gap-2 mt-2">
                                    ${causa.imagens.map(img => `
                                        <img src="${img.url}" class="img-thumbnail" style="width: 100px; height: 100px; object-fit: cover;" 
                                            alt="Imagem da causa" data-bs-toggle="modal" data-bs-target="#modalImagem${index}">
                                        
                                        <!-- Modal para imagem ampliada -->
                                        <div class="modal fade" id="modalImagem${index}" tabindex="-1" aria-hidden="true">
                                            <div class="modal-dialog modal-lg">
                                                <div class="modal-content">
                                                    <div class="modal-header">
                                                        <h5 class="modal-title">Imagem da Causa</h5>
                                                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                                    </div>
                                                    <div class="modal-body text-center">
                                                        <img src="${img.url}" class="img-fluid" alt="Imagem ampliada">
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : '<p><strong>Imagens:</strong> Nenhuma imagem disponível</p>'}
                    </div>
                `;
                listaCausasContainer.appendChild(cardCausa);
            });
        } else {
            listaCausasContainer.innerHTML = `
                <div class="alert alert-info">
                    Nenhuma causa de não conformidade registrada para esta inspeção.
                </div>
            `;
        }
        
        // Desabilitar todos os campos no modal GET (apenas visualização)
        const camposGet = [
            'data-inspecao-solda-tanque-get',
            'qtd-produzida-solda-tanque-get',
            'inspetor-inspecao-solda-tanque-get',
            'conformidade-inspecao-solda-tanque-get',
            'observacao-inspecao-solda-tanque-get'
        ];
        
        camposGet.forEach(campoId => {
            const elemento = document.getElementById(campoId);
            if (elemento) {
                elemento.disabled = true;
            }
        });
    }

    // Lógica para calcular não conformidades (para o modal de edição)
    document.getElementById("conformidade-inspecao-solda-tanque").addEventListener("input", function() {
        const qtdProduzida = parseFloat(document.getElementById("qtd-produzida-solda-tanque").value) || 0;
        const conformidade = parseFloat(this.value) || 0;
        const naoConformidade = qtdProduzida - conformidade;
        const containerInspecao = document.getElementById("containerInspecao");
        const addRemoveContainer = document.getElementById("addRemoveContainer");
    
        
        document.getElementById("nao-conformidade-inspecao-solda-tanque").value = naoConformidade;
        
        if (naoConformidade <= 0) {
            containerInspecao.style.display = "none";
            addRemoveContainer.style.display = "none";
    
            // Remove o atributo 'required'
            const inputs = containerInspecao.querySelectorAll('input');
            const selects = containerInspecao.querySelectorAll('select');

            inputs.forEach(input => {
                if (input.type !== 'file') {
                    input.removeAttribute('required');
                }
                input.value = "";
            });
            selects.forEach(select => {
                select.value = "";
                select.removeAttribute('required');
            });
        } else {
            containerInspecao.style.display = "block";
            addRemoveContainer.style.display = "flex";
    
            // Adiciona o atributo 'required' de volta
            const inputs = containerInspecao.querySelectorAll('input');
            const selects = containerInspecao.querySelectorAll('select');
    
            inputs.forEach(input => {
                if (input.type !== 'file') {
                    input.setAttribute('required', 'required');
                }
            });
            selects.forEach(select => select.setAttribute('required', 'required'));
        }
    });

    // Lógica para adicionar/remover containers de causas (para o modal de edição)
    const containerInspecao = document.getElementById("containerInspecao");
    const addButton = document.getElementById("addButtonsolda-tanque");
    const removeButton = document.getElementById("removeButtonsolda-tanque");

    if (addButton && removeButton) {
        addButton.addEventListener("click", () => {
            const lastContainer = containerInspecao.lastElementChild;

            $(lastContainer).find('select.select2').select2('destroy');

            const newContainer = lastContainer.cloneNode(true);

            const span = newContainer.querySelector("span.label-modal");
            const currentCount = containerInspecao.children.length + 1;
            span.textContent = `${currentCount}ª Causa`;

            newContainer.querySelector("select").value = "";
            newContainer.querySelector("select").name = `causas_${currentCount}`;
            newContainer.querySelector("input[type='number']").value = "";
            newContainer.querySelector("input[type='file']").value = "";
            newContainer.querySelector("input[type='file']").name = `imagens_${currentCount}`;

            containerInspecao.appendChild(newContainer);

            $('.select2').each(function() {
                $(this).select2({
                    dropdownParent: $(this).closest('.modal'),
                    width: '100%'
                });
            });
        });

        removeButton.addEventListener("click", () => {
            if (containerInspecao.children.length > 1) {
                containerInspecao.removeChild(containerInspecao.lastElementChild);
            }
        });
    }
});

$(document).ready(function() {
    $('.select2').each(function() {
        $(this).select2({
            dropdownParent: $(this).closest('.modal'),
            width: '100%'
        });
    });
});