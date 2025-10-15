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

    preencherCausas_1();

});

document.getElementById("btn-filtrar-inspecao-estamparia").addEventListener("click", (event) => {
    event.preventDefault();
    buscarItensInspecao(1); // Chama a função quando o botão de filtro é clicado, começando na página 1
});

document.getElementById("btn-limpar-inspecao-estamparia").addEventListener("click", (event) => {
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

document.getElementById("numPecaDefeituosa").addEventListener("change", (event) => {

    // Verifica se o valor máximo é menor que o valor atual
    const max = parseInt(event.target.max);
    const value = parseInt(event.target.value);
    if (value > max) {
        Toast.fire({
            icon: "warning",
            title: "A quantidade de peça morta não pode exceder o total de peças produzidas."
        });
        event.target.value = '';  
        return;
    }

    controlarLinhasTabela();

    if ((value - max) === 0){
        document.getElementById("medicoesTecnicas").style.display = 'none';
        document.getElementById("inspecao_total").value = 'Sim';
    } else {
        document.getElementById("medicoesTecnicas").style.display = 'block';
        document.getElementById("inspecao_total").value = '';
    }

});

function buscarItensInspecao(pagina) {
    let cardsInspecao = document.getElementById("cards-inspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-inspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-inspecao");
    let itensInspecionar = document.getElementById("itens-inspecionar");
    let itensFiltradosMaquina = document.getElementById("itens-filtrados-inspecao-maquina");
    let itensFiltradosData = document.getElementById("itens-filtrados-inspecao-data");
    let itensFiltradosPesquisa = document.getElementById("itens-filtrados-inspecao-pesquisa");
    let paginacao = document.getElementById("paginacao-inspecao-estamparia");

    // Limpa os cards antes de buscar novos
    cardsInspecao.innerHTML = `<div class="text-center">
                                    <div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>`;
    paginacao.innerHTML = "";

    // Coletar os filtros aplicados
    let maquinasSelecionadas = [];
    document.querySelectorAll('.form-check-input-inspecao-estamparia:checked').forEach(checkbox => {
        maquinasSelecionadas.push(checkbox.nextElementSibling.textContent.trim());
    });

    let dataSelecionada = document.getElementById('data-filtro-inspecao').value;
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

    if (dataSelecionada) {
        params.append("data", dataSelecionada);
        itensFiltradosData.style.display = "block";
        itensFiltradosData.textContent = "Data: " + dataSelecionada;
    } else {
        itensFiltradosData.style.display = "none";
    }

    if (pesquisarInspecao) {
        params.append("pesquisar", pesquisarInspecao);
        itensFiltradosPesquisa.style.display = "block";
        itensFiltradosPesquisa.textContent = "Pesquisa: " + pesquisarInspecao;
    } else {
        itensFiltradosPesquisa.style.display = "none";
    }

    params.append("pagina", pagina); // Adiciona a página atual aos parâmetros

    fetch(`/inspecao/api/itens-inspecao-estamparia/?${params.toString()}`, {
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

        const quantidadeInspecoes = items.total;
        const quantidadeFiltradaInspecoes = items.total_filtrado;

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
                    <h5> ${item.peca}</h5>
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

                    // Capturar dados do botão
                    const itemId = this.getAttribute('data-id');
                    const itemData = this.getAttribute('data-data');
                    const itemQtd = this.getAttribute('data-qtd');
                    const itemPeca = this.getAttribute('data-peca');
                    const itemMaquina = this.getAttribute('data-maquina');
                    
                    // Remover itens anteriores e resetar o modal
                    removeAllNonConformityItems();
                    resetModal();
                    
                    const modalInspecao = document.getElementById('inspectionModal');
                    
                    // Pegar a data atual formatada
                    const currentDate = new Date();
                    const formattedDate = currentDate.toISOString().split('T')[0];
                    
                    modalInspecao.querySelector('#dataInspecao').value = formattedDate;
                    modalInspecao.querySelector('#conjuntoName').value = itemPeca;
                    modalInspecao.querySelector('#maquina').value = itemMaquina;
                    modalInspecao.querySelector('#pecasProduzidas').value = itemQtd;
                    modalInspecao.querySelector('#id-inspecao').value = itemId;

                    // Desabilitar campos para edição
                    modalInspecao.querySelector('#maquina').disabled = true;
                    modalInspecao.querySelector('#pecasProduzidas').disabled = true;
                    modalInspecao.querySelector('#dataInspecao').disabled = true;
                    modalInspecao.querySelector('#conjuntoName').disabled = true;

                    modalInspecao.querySelector('#numPecaDefeituosa').setAttribute("max", itemQtd);                 
                    modalInspecao.querySelector('#numPecaDefeituosa').setAttribute("max", itemQtd);                 
                    controlarLinhasTabela();
                    resetInspetorSelect();
                    resetInspetorSelect();

                    // Mostrar o modal
                    new bootstrap.Modal(modalInspecao).show();
                });
            });
        });

        itensInspecionar.textContent = "Itens a Inspecionar";

        if (items.total_paginas > 1) {
            let paginacaoHTML = `<nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">`;

            const paginaAtual = items.pagina_atual;
            const totalPaginas = items.total_paginas;

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

function controlarLinhasTabela() { 
    const qtdProduzida = parseInt(document.getElementById("pecasProduzidas").value) || 0;
    const qtdMorta = parseInt(document.getElementById("numPecaDefeituosa").value) || 0;
    
    if (qtdProduzida <= 0) {
        Toast.fire({
            icon: "warning",
            title: "Por favor, informe uma quantidade válida de peças produzidas."
        });
        return;
    }

    // A quantidade de peças válidas para análise é a quantidade produzida menos a quantidade de peças mortas.
    const qtdParaAnalise = qtdProduzida - qtdMorta;

    // if (qtdParaAnalise <= 0) {
    //     alert("A quantidade de peças mortas é igual ou maior que a quantidade produzida. Não há peças para análise.");
    //     return;
    // }

    // Número máximo de linhas exibidas na tabela (limitado a 3)
    const maxLinhas = 3;
    const linhasExibidas = Math.min(qtdParaAnalise, maxLinhas);
    // Mostrar ou ocultar as linhas da tabela
    for (let i = 1; i <= maxLinhas; i++) {
        const linha = document.getElementById(`linhaMedicao${i}`);
        const linhaInput = document.querySelectorAll(`#linhaMedicao${i} td input`)
        const linhaCheckbox = document.querySelectorAll(`#linhaMedicao${i} .form-check input`)
        if (i <= linhasExibidas) {
            linha.style.display = ""; // Mostra a linha
        } else {
            linha.style.display = "none"; // Esconde a linha
            linhaInput.forEach((input) => {
                input.value = "";
            })
            linhaCheckbox.forEach((checkbox) => {
                checkbox.checked = false;
            })
        }
    }

    if(qtdParaAnalise === 0){
        document.getElementById("sectionMedicaoTec").style.display = "none";
    } else {
        document.getElementById("sectionMedicaoTec").style.display = "block";
    } 
}

function togglePecaMortaSection(mostrar) {
    const secao = document.getElementById('pecaMortaSection');
    const statusBadge = document.getElementById('statusPecasDefeituosas');
    const qtMorta = document.getElementById('numPecaDefeituosa');
    
    if (mostrar) {
        secao.style.display = 'block';
        statusBadge.textContent = 'Peças com defeito';
        statusBadge.className = 'badge bg-danger text-white';
    } else {
        secao.style.display = 'none';
        statusBadge.textContent = 'Sem defeitos';
        statusBadge.className = 'badge bg-success text-white';
        
        // Limpa o valor do input e dispara a função de controle da tabela
        qtMorta.value = "";
        controlarLinhasTabela();
    }

    document.getElementById('medicoesTecnicas').style.display = 'block';
}

async function buscarMotivosCausas() {
    try {
        const response = await fetch('/inspecao/api/motivos-causas/estamparia', {
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

async function preencherCausas_1() {
    const dados_causas = await buscarMotivosCausas();  // Aguarda os dados serem carregados

    if (!dados_causas || !dados_causas.motivos) {
        console.error("Dados inválidos ou vazios retornados da API.");
        return;
    }

    const causasContainer = document.getElementById('causasPecaMorta');
    causasContainer.innerHTML = '';  // Limpa o conteúdo anterior

    dados_causas.motivos.forEach((motivoCausa, index) => {
        const motivoId = `causa1_${index + 1}`;
        const motivoDiv = document.createElement('div');
        motivoDiv.className = 'form-check mb-2';

        motivoDiv.innerHTML = `
            <input class="form-check-input causa-checkbox" type="checkbox" id="${motivoId}" name="causas1" value="${motivoCausa.id}">
            <label class="form-check-label" for="${motivoId}">${motivoCausa.nome}</label>
        `;
        
        causasContainer.appendChild(motivoDiv);
    });
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

    // Limpar as causas de peças mortas
    preencherCausas_1();

    // Resetar o valor do campo de quantidade de peças mortas
    const qtMorta = document.getElementById('numPecaDefeituosa');
    if (qtMorta) qtMorta.value = '';

    // Ocultar a seção de peças mortas (resetar para estado inicial)
    const secaoPecaMorta = document.getElementById('pecaMortaSection');
    if (secaoPecaMorta) secaoPecaMorta.style.display = 'none';

    // Atualizar o status badge para o estado inicial
    const statusBadge = document.getElementById('statusPecasDefeituosas');
    if (statusBadge) {
        statusBadge.textContent = 'Não verificado';
        statusBadge.className = 'badge bg-secondary text-dark';
    }
}

// Verificar se algum checkbox "Outro" está marcado
// function checkOutroCausa() {
//     const outroCheckboxes = document.querySelectorAll('.outro-checkbox');
//     const outroCampo = document.getElementById('outraCausa_estamparia');
    
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
    const totalRadios = document.querySelectorAll('[name^="conformity"]').length / 2;
    let nonConformCount = 0;
    
    for (let i = 1; i <= totalRadios; i++) {
        const nonConformRadio = document.getElementById(`nonConforming${i}`);
        if (nonConformRadio && nonConformRadio.checked) {
            nonConformCount++;
        }
    }
    
    // Mostrar ou ocultar a seção de não conformidades
    const nonConformitySection = document.getElementById('nonConformitySection');
    if (nonConformCount > 0) {
        nonConformitySection.style.display = 'block';
    } else {
        nonConformitySection.style.display = 'none';
    }
}

async function preencherCausasCa(nonConformityCounter) {
    try {
        const response = await fetch('/inspecao/api/motivos-causas/estamparia', {
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

// Função para validar o formulário antes do envio
function validarFormulario() {

    const qtdProduzida = parseInt(document.getElementById("pecasProduzidas").value);

    // Validação de inspetor
    const inspetor = document.getElementById('inspetor').value;
    if (inspetor === '') {
        Toast.fire({
            icon: "error",
            title: "Por favor, informe o nome do inspetor."
        });
        return false;
    }

    // 1. Validação de peças mortas
    const pecaMortaSim = document.getElementById("pecaMortaSim").checked;
    let qtdPecaMorta = 0;
    
    if (pecaMortaSim) {
        const quantidade = parseInt(document.getElementById("numPecaDefeituosa").value);
        const causasSelecionadas = document.querySelectorAll("#causasPecaMorta .causa-checkbox:checked").length;

        if (!quantidade || quantidade <= 0) {
            Toast.fire({
                icon: "error",
                title: "Por favor, informe a quantidade de peças mortas."
            });
            return false;
        }

        if (causasSelecionadas === 0) {
            Toast.fire({
                icon: "error",
                title: "Por favor, selecione pelo menos uma causa para as peças mortas."
            });
            return false;
        }

        qtdPecaMorta = quantidade; // Armazena a quantidade de peças mortas
    }

    // 2. Validação das medições técnicas conforme a quantidade produzida 
    let linhasObrigatorias = Math.min(qtdProduzida-qtdPecaMorta, 3); // No máximo 3 linhas obrigatórias
    let linhasPreenchidas = 0;
    let somaQuantidadeNaoConforme = 0;

    for (let i = 1; i <= 3; i++) {
        let linhaPreenchida = false;
        let algumCampoPreenchido = false;
        let conformeMarcado = false;
        let naoConformeMarcado = false;

        // Verificar se pelo menos um campo da linha foi preenchido
        for (let j = 1; j <= 4; j++) {
            const valor = document.getElementById(`valor${i}_${j}`).value.trim();
            if (valor !== "") { // Verifica se o campo possui algum valor
                algumCampoPreenchido = true;
            }
        }

        // Verificar se um dos botões de conformidade foi marcado
        conformeMarcado = document.getElementById(`conforming${i}`).checked;
        naoConformeMarcado = document.getElementById(`nonConforming${i}`).checked;

        if(naoConformeMarcado){
            somaQuantidadeNaoConforme += 1;
        }

        // A linha é considerada preenchida se pelo menos um campo tiver valor E uma conformidade for marcada
        if (algumCampoPreenchido && (conformeMarcado || naoConformeMarcado)) {
            linhaPreenchida = true;
            linhasPreenchidas++;
        }

        // Verificar se a linha obrigatória não está preenchida corretamente
        if (i <= linhasObrigatorias && !linhaPreenchida) {
            Toast.fire({
                icon: "error",
                title: `Por favor, preencha pelo menos um campo e marque conformidade na linha ${i} da tabela de medições técnicas.`
            });

            return false;
        }
    }

    // Verifica se o número de linhas preenchidas é suficiente
    if (linhasPreenchidas < linhasObrigatorias) {
        Toast.fire({
            icon: "error",
            title: `Por favor, preencha pelo menos ${linhasObrigatorias} linha(s) da tabela de medições técnicas.`
        });
        return false;
    }

    // 3. Validação inspeção 100%
    const inspecao_total = document.getElementById("inspecao_total").value;
    if (inspecao_total === '') {
        Toast.fire({
            icon: "error",
            title: `Por favor, informe se será necessário inspeção 100%.`
        });
        return false;
    }

    // 4. Validação de conformidade (pelo menos um marcado)
    const conformidadeMarcada = document.querySelectorAll('[name^="conformity"]:checked').length;
    const quantidade = parseInt(document.getElementById("numPecaDefeituosa").value);

    if (!((qtdProduzida - quantidade) === 0) && (conformidadeMarcada === 0)) {
        Toast.fire({
            icon: "error",
            title: `Por favor, marque pelo menos uma opção de conformidade (Conforme ou Não Conforme).`
        });
        return false;
    }

    // 5. Validação de não conformidades (cada não conformidade deve ter quantidade e pelo menos uma causa)
    let somaQuantidadesAfetadas = 0;

    const naoConformidades = document.querySelectorAll('.non-conformity-item');
    for (const item of naoConformidades) {
        const id = item.id.replace('nonConformityItem', '');
        const quantidade = parseInt(document.getElementById(`quantidadeAfetada${id}`).value);
        const causasSelecionadas = document.querySelectorAll(`#causasContainer${id} .causa-checkbox:checked`).length;
        const destinoSelecionado = document.getElementById(`destino${id}`).value;
        

        if (somaQuantidadeNaoConforme > 0){
            if (!quantidade || quantidade <= 0) {
                Toast.fire({
                    icon: "error",
                    title: `Por favor, informe a quantidade afetada para a não conformidade #${id}.`
                });
                return false;
            }

            if (causasSelecionadas === 0) {
                Toast.fire({
                    icon: "error",
                    title: `Por favor, selecione pelo menos uma causa para a não conformidade #${id}.`
                });

                return false;
            }

            if (destinoSelecionado === '') {
                Toast.fire({
                    icon: "error",
                    title: `Por favor, selecione o destino correto para a não conformidade #${id}.`
                });

                return false;
            }
        }
        // Acumular quantidade afetada das não conformidades
        somaQuantidadesAfetadas += quantidade;
    }

    // 6. Verificar se a quantidade de peças mortas + quantidade afetada é maior que a quantidade produzida
    const totalPecasProblema = qtdPecaMorta + somaQuantidadesAfetadas;
    const totalNaoConformidade = somaQuantidadeNaoConforme;
    console.log(totalNaoConformidade)
    console.log(somaQuantidadesAfetadas)

    if (totalPecasProblema > qtdProduzida) {
        Toast.fire({
            icon: "error",
            title: `A soma da quantidade de peças mortas e das quantidades afetadas por não conformidades não pode ultrapassar a quantidade produzida.`
        });

        return false;
    }
    

    if (totalNaoConformidade > 0 && totalNaoConformidade !== somaQuantidadesAfetadas) {
        Toast.fire({
            icon: "error",
            title: `A soma da quantidade de não conformidades tem que ser igual a soma das quantidades afetadas`
        });

        return false;
    }

    return true;
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

document.addEventListener("change", (event) =>{
    console.log(event.target);
    if(event.target.id === "autoInspecaoNoturna"){
        const optionAutoInspecaoNoturna = document.getElementById("optionAutoInspecaoNoturna");
        const selectInspetor = document.getElementById("inspetor");
        const currentDate = new Date();
        
        
        if (event.target.checked){
            // Pegar a data atual formatada
            currentDate.setDate(currentDate.getDate() - 1); // Define para o dia anterior
            const formattedDate = currentDate.toISOString().split('T')[0];
            document.getElementById('inspectionModal').querySelector('#dataInspecao').value = formattedDate;

            for (let i = 0; i < selectInspetor.options.length; i++) {
                const option = selectInspetor.options[i];
                option.disabled = true;
            }
            optionAutoInspecaoNoturna.textContent = "autoInspecaoNoturna";
            optionAutoInspecaoNoturna.disabled = false;
            optionAutoInspecaoNoturna.selected = true;
             
        }else{
            // Pegar a data atual formatada
            const formattedDate = currentDate.toISOString().split('T')[0];
            document.getElementById('inspectionModal').querySelector('#dataInspecao').value = formattedDate;
            
            for (let i = 0; i < selectInspetor.options.length; i++) {
                const option = selectInspetor.options[i];
                option.disabled = false;
            }
            optionAutoInspecaoNoturna.textContent = "autoInspecaoNoturna - Indisponível";
            optionAutoInspecaoNoturna.disabled = true;
            optionAutoInspecaoNoturna.selected = false;
        }

    }
});

function resetInspetorSelect(){
    const selectInspetor = document.getElementById("inspetor");
    const optionAutoInspecaoNoturna = document.getElementById("optionAutoInspecaoNoturna");

    for (let i = 0; i < selectInspetor.options.length; i++) {
        const option = selectInspetor.options[i];
        option.disabled = false;
    }
    
    optionAutoInspecaoNoturna.textContent = "autoInspecaoNoturna - Indisponível";
    optionAutoInspecaoNoturna.disabled = true;
    optionAutoInspecaoNoturna.selected = false;
}