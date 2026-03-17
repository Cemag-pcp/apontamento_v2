const Toast = Swal.mixin({
    toast: true,
    position: "bottom-end",
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.onmouseenter = Swal.stopTimer;
        toast.onmouseleave = Swal.resumeTimer;
    }
});

document.addEventListener("DOMContentLoaded", () => {
    buscarItensInspecao(1); // Chama a função quando a página carrega, começando na página 1
        
    // Adicionar listeners para os radio buttons de conformidade
    const conformityRadios = document.querySelectorAll('.conformity-radio');
    conformityRadios.forEach(radio => {
        radio.addEventListener('change', updateConformityCounts);
    });
    
    // Inicializar contagem de conformidades
    updateConformityCounts();
});

document.getElementById("btn-filtrar-inspecao-serra-usinagem").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensInspecao(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-inspecao-serra-usinagem").addEventListener("click", (event) => {
    event.preventDefault(); // Evita o recarregamento da página caso esteja dentro de um formulário

    // Seleciona todos os inputs dentro do formulário
    const form = document.getElementById("form-filtrar-inspecao");
    form.querySelectorAll("input").forEach(input => {
        if (input.type === "checkbox") {
            input.checked = false; // Desmarca checkboxes
        } else {
            input.value = ""; // Limpa inputs de texto e data
        }
    });
    buscarItensInspecao(1);
});


function buscarItensInspecao(pagina) {
    let cardsInspecao = document.getElementById("cards-inspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-inspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-inspecao");
    let itensInspecionar = document.getElementById("itens-inspecionar");
    let itensFiltradosMaquina = document.getElementById("itens-filtrados-inspecao-maquina");
    let itensFiltradosStatus = document.getElementById("itens-filtrados-inspecao-status");
    let itensFiltradosDataInicio = document.getElementById("itens-filtrados-inspecao-data-inicio");
    let itensFiltradosDataFim = document.getElementById("itens-filtrados-inspecao-data-fim");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-inspecao-pesquisa");
    let paginacao = document.getElementById("paginacao-inspecao-serra-usinagem");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let maquinasSelecionadas = [];
    document.querySelectorAll('.form-check-input-inspecao-serra-usinagem:checked').forEach(checkbox => {
        maquinasSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let statusSelecionados = [];
    document.querySelectorAll('.form-check-status-input-inspecao-serra-usinagem:checked').forEach(checkbox => {
        statusSelecionados.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionadaInicio = document.getElementById('data-filtro-inspecao-inicio').value;
    let dataSelecionadaFim = document.getElementById('data-filtro-inspecao-fim').value;

    let pesquisarInspecao = document.getElementById('pesquisar-peca-inspecao').value;

    // Monta os parâmetros de busca
    let params = new URLSearchParams();
    if (maquinasSelecionadas.length > 0) {
        params.append("maquinas", maquinasSelecionadas.join(","));
        itensFiltradosMaquina.style.display = "block";
        itensFiltradosMaquina.textContent = "Máquinas: " + maquinasSelecionadas.join(", ");
    } else {
        itensFiltradosMaquina.style.display = "none";
    }

    if (statusSelecionados.length > 0) {
        console.log(statusSelecionados);
        params.append("status", statusSelecionados.join(","));
        itensFiltradosStatus.style.display = "block";
        itensFiltradosStatus.textContent = "Status: " + statusSelecionados.join(", ");
    } else {
        itensFiltradosStatus.style.display = "none";
    }

    if (dataSelecionadaInicio) {
        params.append("data_inicio", dataSelecionadaInicio);
        itensFiltradosDataInicio.style.display = "block";
        itensFiltradosDataInicio.textContent = "Data: " + dataSelecionadaInicio;
    } else {
        itensFiltradosDataInicio.style.display = "none";
    }

    if (dataSelecionadaFim) {
        params.append("data_fim", dataSelecionadaFim);
        itensFiltradosDataFim.style.display = "block";
        itensFiltradosDataFim.textContent = "Data: " + dataSelecionadaFim;
    } else {
        itensFiltradosDataFim.style.display = "none";
    }

    if (pesquisarInspecao) {
        params.append("pesquisar", pesquisarInspecao);
        itensFiltradosPesquisa.style.display = "block";
        itensFiltradosPesquisa.textContent = "Pesquisa: " + pesquisarInspecao;
    } else {
        itensFiltradosPesquisa.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/inspecao/api/itens-inspecao-serra-usinagem/?${params.toString()}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
    }).then(response => {
        if (!response.ok) {
            throw new Error(`Erro HTTP! Status: ${response.status}`);
        }
        return response.json();
    }).then(items => {
        cardsInspecao.innerHTML = "";

        const quantidadeInspecoes = items.total_inspecoes_sem_filtros;
        const quantidadeFiltradaInspecoes = items.paginacao.total_filtrado;
        const status = {
            "Não iniciado":"devolvido",
            "Em andamento": "pendente"
        }

        qtdPendenteInspecao.textContent = `${quantidadeInspecoes} itens pendentes`;

        if (params.size > 1) {
            qtdFiltradaInspecao.style.display = 'block';
        } else {
            qtdFiltradaInspecao.style.display = 'none';
        }

        qtdFiltradaInspecao.textContent = `${quantidadeFiltradaInspecoes} itens filtrados`;

        items.dados.forEach(item => {

            const cards = `
            <div class="col-md-4 mb-4">
                <div class="card p-3" style="min-height: 300px; display: flex; flex-direction: column; justify-content: space-between">
                    <div class="d-flex justify-content-between">
                        <h5 style="width:70%;"> <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(item.peca)}" target="_blank" rel="noopener noreferrer">${item.peca}</a></h5>
                        <div class="text-center">
                            <p class="status-badge status-${status[item.status]}" style="font-size:13px">${item.status}</p>
                        </div>
                    </div>
                    <p>Inspecao #${item.id}</p>
                    <p>
                        <strong>📅 Data:</strong> ${item.data}<br>
                        <strong>⚙️ Máquina:</strong> ${item.maquina}<br>
                        <strong>🔢 Quantidade Produzida:</strong> ${item.qtd_apontada}<br>
                        <strong>🧑🏻‍🏭 Operador:</strong> ${item.operador}
                    </p>
                    <hr>
                    <button 
                        data-id="${item.id}"
                        data-data="${item.data}"
                        data-qtd="${item.qtd_apontada}"
                        data-peca="${item.peca}"
                        data-maquina="${item.maquina}"
                    class="btn btn-dark w-100 iniciar-inspecao" id="openModalButton">
                    Iniciar Inspeção</button>
                </div>
            </div>`;

            cardsInspecao.innerHTML += cards;

            // Chamar modal ao clicar em "Iniciar Inspecao"
            document.querySelectorAll('.iniciar-inspecao').forEach(button => {
                button.addEventListener('click', function () {

                // Remover itens anteriores e resetar o modal
                    removeAllNonConformityItems();
                    resetModal();

                    const sections = [
                        'sectionMedicaoSerra',
                        'sectionMedicaoUsinagem',
                        'sectionMedicaoFuracao'
                    ];
                    
                    sections.forEach(sectionId => {
                        const section = document.getElementById(sectionId);
                        if (section) {
                            section.style.display = 'none';
                        }
                    });
                    // Capturar dados do botão
                    const itemId = this.getAttribute('data-id');
                    const itemData = this.getAttribute('data-data');
                    const itemQtd = this.getAttribute('data-qtd');
                    const itemPeca = this.getAttribute('data-peca');
                    const itemMaquina = this.getAttribute('data-maquina');
                    
                    const modalInspecao = document.getElementById('inspectionModal');
                    
                    // Pegar a data atual formatada
                    const currentDate = new Date();
                    const formattedDate = currentDate.toISOString().split('T')[0];

                    modalInspecao.querySelector('#dataInspecao').value = formattedDate;
                    modalInspecao.querySelector('#conjuntoName').value = itemPeca;
                    modalInspecao.querySelector('#maquina').value = itemMaquina;
                    modalInspecao.querySelector('#pecasProduzidas').value = itemQtd;
                    modalInspecao.querySelector('#id-inspecao').value = itemId;
                    if (typeof window.syncMeasurementRowsSerraUsinagem === 'function') {
                        const linhasPadrao = Math.min(parseInt(itemQtd, 10) || 1, 3);
                        window.syncMeasurementRowsSerraUsinagem(linhasPadrao, false);
                    }

                    // Desabilitar campos para edição
                    modalInspecao.querySelector('#maquina').disabled = true;
                    modalInspecao.querySelector('#pecasProduzidas').disabled = true;
                    modalInspecao.querySelector('#dataInspecao').disabled = true;
                    modalInspecao.querySelector('#conjuntoName').disabled = true;

                    // Mostrar SweetAlert de carregamento
                    Swal.fire({
                        title: 'Carregando inspeção',
                        html: 'Por favor, aguarde enquanto os dados são carregados...',
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });
                    
                    fetch(`/inspecao/api/get-execucao-inspecao-serra-usinagem/?id_inspecao=${itemId}`, {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        },
                    })
                    .then(response => response.json())
                    .then(data => {
                        Swal.close();

                        if (data.existe && data.dados && Object.keys(data.dados.tipos_processo).length > 0) {
                            // Preencher as linhas de medição com os dados retornados
                            preencherLinhasMedicao(data.dados);
                            const inspecaoTotal = document.getElementById('inspecao_total');
                            inspecaoTotal.value = data.dados.inspecao_completa ? "Sim" : "Não";
                            new bootstrap.Modal(document.getElementById('inspectionModal')).show();
                            // Só agora mostrar o modal
                        } else {
                            // Se não houver dados, pode abrir o modal vazio ou mostrar aviso
                            new bootstrap.Modal(document.getElementById('inspectionModal')).show();
                        }
                    })
                    .catch(error => {
                        console.error('Erro ao buscar execuções:', error);
                        Swal.fire({
                            icon: 'error',
                            title: 'Erro',
                            text: 'Ocorreu um erro ao carregar os dados da inspeção. Por favor, tente novamente.',
                            confirmButtonText: 'OK'
                        });
                    });
                });
            });
        });

        itensInspecionar.textContent = "Itens a Inspecionar";
        if (items.paginacao.total_paginas > 1) {
            let paginacaoHTML = `<nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">`;

            const paginaAtual = items.paginacao.pagina_atual;
            const totalPaginas = items.paginacao.total_paginas;

            // Função para adicionar um link de página
            const adicionarLinkPagina = (i) => {
                paginacaoHTML += `
                    <li class="page-item ${i === paginaAtual ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="buscarItensInspecao(${i})">${i}</a>
                    </li>`;
            };

            // Mostrar a primeira página
            adicionarLinkPagina(1);

            // Mostrar reticências antes da página atual, se necessário
            if (paginaAtual > 3) {
                paginacaoHTML += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }

            // Mostrar páginas ao redor da página atual
            for (let i = Math.max(2, paginaAtual - 1); i <= Math.min(totalPaginas - 1, paginaAtual + 1); i++) {
                adicionarLinkPagina(i);
            }

            // Mostrar reticências após a página atual, se necessário
            if (paginaAtual < totalPaginas - 2) {
                paginacaoHTML += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }

            // Mostrar a última página
            if (totalPaginas > 1) {
                adicionarLinkPagina(totalPaginas);
            }

            paginacaoHTML += `</ul></nav>`;
            paginacao.innerHTML = paginacaoHTML;
        }
    }).catch((error) => {
        console.error(error);
    });
}

function preencherLinhasMedicao(dados) {
    if (!dados || !dados.tipos_processo) return;

    const totalLinhas = Object.values(dados.tipos_processo).reduce((maiorQuantidade, dadosTipo) => {
        const quantidadeAmostras = Object.keys(dadosTipo.amostras || {}).length;
        return Math.max(maiorQuantidade, quantidadeAmostras);
    }, 1);

    if (typeof window.syncMeasurementRowsSerraUsinagem === 'function') {
        window.syncMeasurementRowsSerraUsinagem(totalLinhas, false);
    }

    // Para cada tipo de processo (serra, usinagem, furacao)
    for (const [tipo, dadosTipo] of Object.entries(dados.tipos_processo)) {
        // Ativa o checkbox correspondente
        const checkbox = document.getElementById(`checkbox-inspecao-${tipo}`);
        if (checkbox) {
            checkbox.checked = true;
            checkbox.disabled = true;
            checkbox.dispatchEvent(new Event('change'));
        }

        // Preenche os cabeçalhos (nomes das medidas)
        dadosTipo.cabecalhos.forEach((cabecalho, index) => {
            const inputCabecalho = document.querySelector(
                `.measurement-section[data-type="${tipo}"] input[name="medida-input-${index + 1}"]`
            );
            if (inputCabecalho) {
                inputCabecalho.value = cabecalho;
            }
        });

        // Preenche os valores das amostras
        for (const [amostraNum, amostraData] of Object.entries(dadosTipo.amostras)) {
            // Desabilitar TODOS os inputs desta linha/amostra input[name^="${tipo}_valor${amostraNum}_"], 
            const linhaInputs = document.querySelectorAll(
                `input[name="${tipo}_conformity${amostraNum}"]`
            );
            
            linhaInputs.forEach(input => {
                input.disabled = true;
            });

            // Preencher valores específicos
            amostraData.medidas.forEach((medida, medidaIndex) => {
                const inputValor = document.querySelector(
                    `input[name="${tipo}_valor${amostraNum}_${medidaIndex + 1}"]`
                );
                if (inputValor) {
                    inputValor.value = medida.valor;
                }
            });

            // Marca conformidade da amostra
            const conformeCheckbox = document.querySelector(
                `input[name="${tipo}_conformity${amostraNum}"][value="conforming"]`
            );
            const naoConformeCheckbox = document.querySelector(
                `input[name="${tipo}_conformity${amostraNum}"][value="nonConforming"]`
            );
            
            if (conformeCheckbox && naoConformeCheckbox) {
                if (amostraData.conforme) {
                    conformeCheckbox.checked = true;
                    naoConformeCheckbox.checked = false;
                } else {
                    conformeCheckbox.checked = false;
                    naoConformeCheckbox.checked = true;
                }
            }
        }
    }
}

async function buscarMotivosCausas() {
    try {
        const response = await fetch('/inspecao/api/motivos-causas/serra-usinagem', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        const data = await response.json();
        return data;
    } catch (error) {
        console.error(error);
    }
}

// Função para resetar o modal
function resetModal() {
    // Limpa os campos de texto
    document.getElementById('inspectionForm').reset();

    // Limpar o texto dos elementos de preview da imagem
    document.querySelectorAll('.imagePreview').forEach(function(element) {
        element.innerHTML = '';  // Limpa a visualização das imagens
    });

    // Limpar os radio buttons e checkboxes
    document.querySelectorAll('.form-check-input').forEach(function(input) {
        input.checked = false;  // Desmarca todos os checkboxes e radio buttons
    });

    // Reabilitar campos desabilitados, caso tenha sido desabilitado no fluxo
    document.querySelectorAll('input[disabled], select[disabled]').forEach(function(input) {
        input.disabled = false;
    });

    updateConformityCounts();
}

// Verificar se algum checkbox "Outro" está marcado
// function checkOutroCausa() {
//     const outroCheckboxes = document.querySelectorAll('.outro-checkbox');
//     const outroCampo = document.getElementById('outraCausa_serra-usinagem');
    
//     let outroSelecionado = false;
//     outroCheckboxes.forEach(checkbox => {
//         if (checkbox.checked) {
//             outroSelecionado = true;
//         }
//     });
    
//     if (outroSelecionado) {
//         outroCampo.disabled = false;
//         outroCampo.required = true;
//     } else {
//         outroCampo.disabled = true;
//         outroCampo.required = false;
//         outroCampo.value = '';
//     }
// }

// Atualizar contagem de conformidades e não conformidades
function updateConformityCounts() {
    // Verifica quais inspeções estão ativas
    const activeInspections = [];
    document.querySelectorAll('.inspection-checkbox:checked').forEach(checkbox => {
        activeInspections.push(checkbox.id.replace('checkbox-inspecao-', ''));
    });

    // Conta apenas os não conformes das inspeções ativas que não estão desabilitados
    let nonConformingCount = 0;
    activeInspections.forEach(type => {
        document.querySelectorAll(`.conformity-check[value="nonConforming"][name*="${type}"]`).forEach(checkbox => {
            // Só conta se o checkbox estiver marcado E não estiver desabilitado
            if (checkbox.checked && !checkbox.disabled) {
                nonConformingCount++;
            }
        });
    });

    const nonConformitySection = document.getElementById('nonConformitySection');
    nonConformitySection.style.display = nonConformingCount > 0 ? 'block' : 'none';
}

function resetConformityForType(inspectionType) {
    // Desmarca todos os checkboxes de não conformidade do tipo
    document.querySelectorAll(`.conformity-check[value="nonConforming"][name*="${inspectionType}"]`).forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Se não houver mais nenhum não conforme marcado, limpa os itens
    if (document.querySelectorAll('.conformity-check[value="nonConforming"]:checked').length === 0) {
        removeAllNonConformityItems();
    }
}

async function preencherCausasCa(nonConformityCounter) {
    try {
        const response = await fetch('/inspecao/api/motivos-causas/serra-usinagem', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();
        const motivos = data.motivos || [];

        const causasContainer = document.getElementById(`causasContainer${nonConformityCounter}`);
        causasContainer.innerHTML = '';  // Limpa o placeholder de carregamento

        if (motivos.length === 0) {
            causasContainer.innerHTML = '<p>Nenhuma causa encontrada.</p>';
            return;
        }

        motivos.forEach((motivoCausa, index) => {
            const motivoId = `causa${nonConformityCounter}_${index + 1}`;
            const motivoDiv = document.createElement('div');
            motivoDiv.className = 'form-check';

            motivoDiv.innerHTML = `
                <input class="form-check-input causa-checkbox" type="checkbox" id="${motivoId}" name="causas${nonConformityCounter}" value="${motivoCausa.id}">
                <label class="form-check-label" for="${motivoId}">${motivoCausa.nome}</label>
            `;
            
            causasContainer.appendChild(motivoDiv);
        });
    } catch (error) {
        console.error('Erro ao buscar causas:', error);
    }
}

// Função para atualizar o contador de não conformidade
function atualizarNonConformityCounter() {
    const items = document.querySelectorAll('.non-conformity-item');
    nonConformityCounter = items.length;
}

let nonConformityCounter = 1;

// Adicionar novo item de não conformidade
function addNonConformityItem() {

    // Atualiza o contador com a quantidade atual de itens já existentes
    atualizarNonConformityCounter();

    // Incrementa o contador
    nonConformityCounter++;
    
    const container = document.getElementById('containerNonConformityItems');
    const newItem = document.createElement('div');
    newItem.className = 'non-conformity-item';
    newItem.id = `nonConformityItem${nonConformityCounter}`;
    
    newItem.innerHTML = `
        <div class="d-flex justify-content-end">
            <button type="button" class="btn btn-remove-nonconformity" onclick="removeNonConformityItem(${nonConformityCounter})">
                <i class="bi bi-x"></i>
            </button>
        </div>
        <div class="row mb-3">
            <div class="col-md-6">
                <label class="form-label">Causas da não conformidade (selecione todas aplicáveis)</label>
                <div class="causes-container" id="causasContainer${nonConformityCounter}">
                    <div class="spinner-border text-dark" role="status">
                        <span class="sr-only">Loading...</span>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <label for="quantidadeAfetada${nonConformityCounter}" class="form-label">Quantidade afetada</label>
                <input type="number" class="form-control" id="quantidadeAfetada${nonConformityCounter}" min="1">

                <!-- Select de Destino abaixo do Input -->
                <label for="destino${nonConformityCounter}" class="form-label mt-2">Destino</label>
                <select id="destino${nonConformityCounter}" class="form-select">
                    <option value="">Selecione</option>
                    <option value="sucata">Sucata</option>
                    <option value="retrabalho">Retrabalho</option>
                </select>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-12">
                <label for="fotoNaoConformidade${nonConformityCounter}" class="form-label">Foto da não conformidade</label>
                <label for="fotoNaoConformidade${nonConformityCounter}" class="custom-file-upload">
                    <i class="bi bi-camera me-2"></i>Clique para adicionar uma foto
                </label>
                <input type="file" id="fotoNaoConformidade${nonConformityCounter}" accept="image/*" style="display: none;" onchange="previewImage(this, 'imagePreview${nonConformityCounter}')" multiple>
                <div id="imagePreview${nonConformityCounter}" class="d-flex mt-2 gap-2"></div>
            </div>
        </div>
    `;
    
    container.appendChild(newItem);

    // Preencher as causas dinamicamente
    preencherCausasCa(nonConformityCounter);
}

// Remover item de não conformidade
function removeNonConformityItem(id) {
    const item = document.getElementById(`nonConformityItem${id}`);
    if (item) {
        item.remove();
    }
    
    // Se não houver mais itens, adicionar um novo
    const container = document.getElementById('containerNonConformityItems');
    if (container.children.length === 0) {
        nonConformityCounter = 0;
        addNonConformityItem();
    }
    
    // Verificar se ainda há algum checkbox "Outro" marcado
    // checkOutroCausa();
}

function removeAllNonConformityItems() {
    // Seleciona todos os elementos que começam com "nonConformityItem"
    const items = document.querySelectorAll('[id^="nonConformityItem"]');
    
    if (items){
        // Remove cada item encontrado
        items.forEach(item => {
            item.remove();
        });
        
        // Resetar o contador (se necessário)
        nonConformityCounter = 1;  // Se você precisar reiniciar o contador
        
        // Adicionar um novo item de não conformidade se necessário
        addNonConformityItem();  // Caso você queira garantir que ao remover tudo, um novo item seja adicionado.
        
        // Verificar se ainda há algum checkbox "Outro" marcado
        // checkOutroCausa();

        const nonConformitySection = document.getElementById('nonConformitySection');
        nonConformitySection.style.display = 'none';
    }
}

// Pré-visualizar imagem carregada
function previewImage(input, previewId) {
    const preview = document.getElementById(previewId);
    preview.innerHTML = ''; // Limpa previews anteriores
    preview.style.flexWrap = 'wrap';

    if (input.files && input.files.length > 0) {
        for (let i = 0; i < input.files.length; i++) {
            const file = input.files[i];

            const reader = new FileReader();
            const div = document.createElement('div');

            reader.onload = function(e) {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'file-preview'; // Você pode estilizar isso com CSS
                img.style.maxWidth = '150px'; // Ajuste o tamanho conforme necessário
                div.appendChild(img);

                const fileName = document.createElement('p');
                fileName.className = 'mt-1 mb-3 text-muted small';
                fileName.textContent = file.name;
                fileName.style.whiteSpace = 'nowrap';
                fileName.style.overflow = 'hidden';
                fileName.style.textOverflow = 'ellipsis';
                fileName.style.maxWidth = '150px'; // Ajuste o tamanho conforme necessário
                div.appendChild(fileName);
                preview.appendChild(div);
            }

            reader.readAsDataURL(file);
        }
    }
}

// Coletar dados de causas selecionadas
function getSelectedCauses(itemId) {
    const causasContainer = document.getElementById(`causasContainer${itemId}`);
    const checkboxes = causasContainer.querySelectorAll('input[type="checkbox"]:checked');
    
    const selectedCauses = [];
    checkboxes.forEach(checkbox => {
        selectedCauses.push(checkbox.value);
    });
    
    return selectedCauses;
}

function validarFormulario() {
    // 1. Validação de inspetor
    const inspetor = document.getElementById('inspetor').value;
    if (inspetor === '') {
        Toast.fire({
            icon: "error",
            title: "Por favor, informe o nome do inspetor."
        });
        return false;
    }

    const checkboxSerra = document.getElementById('checkbox-inspecao-serra');
    const checkboxUsinagem = document.getElementById('checkbox-inspecao-usinagem');
    const checkboxFuracao = document.getElementById('checkbox-inspecao-furacao');
    
    if (!checkboxSerra.checked && !checkboxUsinagem.checked && !checkboxFuracao.checked) {
        Toast.fire({
            icon: "error",
            title: "Selecione pelo menos um tipo de inspeção (Serra, Usinagem ou Furação)."
        });
        return false;
    }

    // 2. Validação inspeção 100%
    const inspecao_total = document.getElementById("inspecao_total").value;
    if (inspecao_total === '') {
        Toast.fire({
            icon: "error",
            title: "Por favor, informe se será necessário inspeção 100%."
        });
        return false;
    }

    // 3. Validação das seções de medição (apenas para as seções marcadas)
    const sections = [
        { prefix: 'serra', sectionId: 'sectionMedicaoSerra', checkboxId: 'checkbox-inspecao-serra' },
        { prefix: 'usinagem', sectionId: 'sectionMedicaoUsinagem', checkboxId: 'checkbox-inspecao-usinagem' },
        { prefix: 'furacao', sectionId: 'sectionMedicaoFuracao', checkboxId: 'checkbox-inspecao-furacao' }
    ];

    for (const section of sections) {
        const checkbox = document.getElementById(section.checkboxId);
        if (checkbox?.checked) {
            const result = validarSectionMedicao(section.prefix, section.sectionId);
            if (!result.valid) {
                Toast.fire({
                    icon: "error",
                    title: result.message
                });
                return false;
            }
        }
    }

    // 4. Validação das não conformidades
    const totalNaoConformes = contarNaoConformidades();
    if (totalNaoConformes > 0) {
        const result = validarNaoConformidades(totalNaoConformes);
        if (!result.valid) {
            Toast.fire({
                icon: "error",
                title: result.message
            });
            return false;
        }
    }

    return true;
}

function validarSectionMedicao(prefix, sectionId) {
    const section = document.getElementById(sectionId);
    const medidaInputs = section.querySelectorAll(`input[name^="medida-input-"]`);
    const sectionName = section.querySelector('.fw-bold').textContent;
    const rows = section.querySelectorAll('tbody tr');
    
    // 1. Validação completa entre cabeçalhos, valores e checkboxes
    for (let col = 0; col < medidaInputs.length; col++) {
        const medidaInput = medidaInputs[col];
        const medidaValue = medidaInput.value.trim();
        const colNumber = col + 1;
        
        // Verifica se há valores preenchidos nesta coluna
        let hasValuesInColumn = false;
        for (let row = 0; row < rows.length; row++) {
            const valueInput = rows[row].querySelector(`input[name^="${prefix}_valor"][name$="_${colNumber}"]`);
            if (valueInput && valueInput.value.trim() !== '') {
                hasValuesInColumn = true;
                break;
            }
        }
        
        // Validação: Se tem cabeçalho mas não tem valores
        if (medidaValue !== '' && !hasValuesInColumn) {
            return {
                valid: false,
                message: `Para a medida "${medidaValue}" em ${sectionName}, preencha pelo menos um valor na tabela.`
            };
        }
        
        // Validação: Se tem valores mas não tem cabeçalho
        if (hasValuesInColumn && medidaValue === '') {
            return {
                valid: false,
                message: `Preencha o cabeçalho da coluna ${colNumber} em ${sectionName} para os valores inseridos.`
            };
        }
    }
    
    // 2. Validação das linhas (valores vs checkboxes)
    for (let row = 0; row < rows.length; row++) {
        const rowInputs = rows[row].querySelectorAll(`input[name^="${prefix}_valor"]`);
        let rowHasValue = false;
        
        // Verifica se a linha tem algum valor preenchido
        for (const input of rowInputs) {
            if (input.value.trim() !== '') {
                rowHasValue = true;
                break;
            }
        }
        
        // Validação: Se tem valores mas não tem checkbox marcado
        if (rowHasValue) {
            const conformityCheckboxes = rows[row].querySelectorAll(`input[name="${prefix}_conformity${row+1}"]:not(:disabled)`);
            
            if (conformityCheckboxes.length > 0) {
                let hasConformity = false;
                for (const checkbox of conformityCheckboxes) {
                    if (checkbox.checked) {
                        hasConformity = true;
                        break;
                    }
                }
                
                if (!hasConformity) {
                    return {
                        valid: false,
                        message: `Na linha ${row+1} da seção ${sectionName}, marque "Conforme" ou "Não Conforme".`
                    };
                }
            }
        }
        
        // Validação: Se tem checkbox marcado mas não tem valores
        const anyCheckboxChecked = rows[row].querySelector(`input[name="${prefix}_conformity${row+1}"]:checked`);
        if (anyCheckboxChecked && !rowHasValue) {
            return {
                valid: false,
                message: `Na linha ${row+1} da seção ${sectionName}, preencha pelo menos um valor para marcar a conformidade.`
            };
        }
    }
    
    return { valid: true };
}

function contarNaoConformidades() {
    let count = 0;
    document.querySelectorAll('input[value="nonConforming"]:checked:not(:disabled)').forEach(checkbox => {
        count++;
    });
    return count;
}

function validarNaoConformidades(totalNaoConformes) {
    const nonConformityItems = document.querySelectorAll('.non-conformity-item');
    let hasValidItem = false;
    let totalQuantidadeAfetada = 0;

    for (let i = 0; i < nonConformityItems.length; i++) {
        const item = nonConformityItems[i];
        const id = i + 1;
        
        // Verifica se o item está preenchido
        const causas = item.querySelectorAll(`input[name="causas${id}"]:checked`).length;
        const quantidade = parseInt(item.querySelector(`#quantidadeAfetada${id}`).value) || 0;
        const destino = item.querySelector(`#destino${id}`).value;
        
        if (causas > 0 || quantidade > 0 || destino !== '') {
            // Validação dos campos obrigatórios
            if (causas === 0) {
                return {
                    valid: false,
                    message: `Selecione pelo menos uma causa para o item de não conformidade ${id}`
                };
            }
            
            if (quantidade <= 0) {
                return {
                    valid: false,
                    message: `Informe a quantidade afetada (maior que zero) para o item de não conformidade ${id}`
                };
            }
            
            if (destino === '') {
                return {
                    valid: false,
                    message: `Selecione o destino para o item de não conformidade ${id}`
                };
            }
            
            totalQuantidadeAfetada += quantidade;
            hasValidItem = true;
        }
    }

    if (!hasValidItem && totalNaoConformes > 0) {
        return {
            valid: false,
            message: 'Para as não conformidades identificadas, preencha pelo menos um item completo (causa, quantidade e destino)'
        };
    }

    if (hasValidItem && totalQuantidadeAfetada !== totalNaoConformes) {
        return {
            valid: false,
            message: `A soma das quantidades afetadas (${totalQuantidadeAfetada}) deve ser igual ao total de não conformidades identificadas (${totalNaoConformes})`
        };
    }

    return { valid: true };
}

document.getElementById('inspectionModal').addEventListener('hide.bs.modal', function (event) {
    // Remover o foco do elemento ativo
    if (document.activeElement) {
        document.activeElement.blur();
    }
});

// faz a validacao
document.getElementById('inspectionForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Coletar dados de todas as não conformidades
    const nonConformityData = [];
    const items = document.querySelectorAll('[id^="nonConformityItem"]');
    
    items.forEach(item => {
        const itemId = item.id.replace('nonConformityItem', '');
        const causes = getSelectedCauses(itemId);
        const quantity = document.getElementById(`quantidadeAfetada${itemId}`).value;
        const description = document.getElementById(`descricaoNaoConformidade${itemId}`).value;
        
        nonConformityData.push({
            causes: causes,
            quantity: quantity,
            description: description
        });
    });

});
