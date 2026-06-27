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

const LINHAS_PADRAO_MEDICAO = 5;
let linhasMedicaoSolicitadas = LINHAS_PADRAO_MEDICAO;

function getTabelaMedicaoBody() {
    return document.querySelector("#sectionMedicaoTec table tbody");
}

function getLinhasMedicao() {
    return Array.from(document.querySelectorAll('tr[id^="linhaMedicao"]'));
}

function getLinhasMedicaoVisiveis() {
    return getLinhasMedicao().filter((linha) => linha.style.display !== "none");
}

function limparLinhaMedicao(linha) {
    linha.querySelectorAll("td input[type='number']").forEach((input) => {
        input.value = "";
    });
    const radioConforme = linha.querySelector("input[id^='conforming']");
    const radioNaoConforme = linha.querySelector("input[id^='nonConforming']");
    if (radioConforme) radioConforme.checked = false;
    if (radioNaoConforme) radioNaoConforme.checked = false;
}

function criarLinhaMedicao(indice) {
    const tbody = getTabelaMedicaoBody();
    if (!tbody) return;

    const linha = document.createElement("tr");
    linha.id = `linhaMedicao${indice}`;
    linha.innerHTML = `
        <td>
            <input type="number" step="0.01" class="form-control" placeholder="Valor" id="valor${indice}_1" style="padding: 5px;">
        </td>
        <td>
            <input type="number" step="0.01" class="form-control" placeholder="Valor" id="valor${indice}_2" style="padding: 5px;">
        </td>
        <td>
            <input type="number" step="0.01" class="form-control" placeholder="Valor" id="valor${indice}_3" style="padding: 5px;">
        </td>
        <td>
            <input type="number" step="0.01" class="form-control" placeholder="Valor" id="valor${indice}_4" style="padding: 5px;">
        </td>
        <td>
            <div class="form-check">
                <input class="form-check-input conformity-radio" type="radio" name="conformity${indice}" id="conforming${indice}" value="conforming">
            </div>
        </td>
        <td>
            <div class="form-check">
                <input class="form-check-input conformity-radio" type="radio" name="conformity${indice}" id="nonConforming${indice}" value="nonConforming">
            </div>
        </td>
    `;

    tbody.appendChild(linha);
}

function garantirQuantidadeLinhasMedicao(quantidade) {
    let totalLinhas = getLinhasMedicao().length;
    while (totalLinhas < quantidade) {
        totalLinhas += 1;
        criarLinhaMedicao(totalLinhas);
    }
}

function atualizarContadorLinhasMedicao(linhasVisiveis) {
    const contador = document.getElementById("contadorLinhasMedicao");
    if (contador) {
        contador.textContent = `${linhasVisiveis} linha(s)`;
    }
}

function adicionarLinhaMedicao() {
    linhasMedicaoSolicitadas += 1;
    controlarLinhasTabela();
}

function removerLinhaMedicao() {
    if (linhasMedicaoSolicitadas <= 1) {
        return;
    }

    linhasMedicaoSolicitadas -= 1;
    controlarLinhasTabela();
}

function getChaveRascunhoInspecao(idInspecao) {
    return `inspecao_estamparia_rascunho_${idInspecao}`;
}

function atualizarFlagParcialCard(idInspecao, ativo) {
    const card = document.querySelector(`[data-card-inspecao-id="${idInspecao}"]`);
    if (!card) return;

    const existente = card.querySelector(".flag-rascunho-parcial");
    if (!ativo) {
        if (existente) existente.remove();
        return;
    }

    if (existente) return;

    const titulo = card.querySelector(".titulo-card-inspecao");
    if (!titulo) return;

    titulo.insertAdjacentHTML(
        "beforeend",
        ' <span class="badge bg-warning text-dark flag-rascunho-parcial">Parcial</span>'
    );
}

function coletarCamposRascunho() {
    const campos = {};
    document.querySelectorAll("#inspectionForm input[id], #inspectionForm select[id], #inspectionForm textarea[id]").forEach((el) => {
        if (el.type === "file") return;
        campos[el.id] = {
            tipo: el.type,
            valor: el.value,
            checked: el.checked
        };
    });
    return campos;
}

function aplicarCamposRascunho(campos) {
    if (!campos) return;
    Object.entries(campos).forEach(([id, estado]) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (estado.tipo === "checkbox" || estado.tipo === "radio") {
            el.checked = Boolean(estado.checked);
        } else {
            el.value = estado.valor ?? "";
        }
    });
}

function aplicarChecksPendentes(ids, tentativa = 0) {
    if (!Array.isArray(ids) || ids.length === 0) return;

    const faltando = [];
    ids.forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
            el.checked = true;
        } else {
            faltando.push(id);
        }
    });

    if (faltando.length > 0 && tentativa < 20) {
        setTimeout(() => aplicarChecksPendentes(faltando, tentativa + 1), 120);
    }
}

function ajustarQuantidadeItensNaoConformidade(quantidade) {
    if (!Number.isInteger(quantidade) || quantidade < 1) return;
    const container = document.getElementById("containerNonConformityItems");
    if (!container) return;

    let atual = container.querySelectorAll(".non-conformity-item").length;
    while (atual < quantidade) {
        addNonConformityItem();
        atual++;
    }
}

function salvarParcialInspecao() {
    const idInspecao = document.getElementById("id-inspecao").value;
    if (!idInspecao) {
        Toast.fire({ icon: "warning", title: "Nenhuma inspeção selecionada para salvar parcialmente." });
        return;
    }

    const idsChecksMarcados = [];
    document.querySelectorAll("#inspectionForm input[type='checkbox']:checked, #inspectionForm input[type='radio']:checked").forEach((el) => {
        if (el.id) idsChecksMarcados.push(el.id);
    });

    const itensNaoConformidade = Array.from(document.querySelectorAll("#containerNonConformityItems .non-conformity-item")).map((item) => item.id);

    const rascunho = {
        linhasMedicaoSolicitadas,
        campos: coletarCamposRascunho(),
        idsChecksMarcados,
        quantidadeItensNaoConformidade: itensNaoConformidade.length
    };

    localStorage.setItem(getChaveRascunhoInspecao(idInspecao), JSON.stringify(rascunho));
    atualizarFlagParcialCard(idInspecao, true);
    Toast.fire({ icon: "success", title: "Rascunho salvo com sucesso." });
}

function carregarRascunhoParcialInspecao(idInspecao) {
    if (!idInspecao) return;

    const bruto = localStorage.getItem(getChaveRascunhoInspecao(idInspecao));
    if (!bruto) return;

    let rascunho = null;
    try {
        rascunho = JSON.parse(bruto);
    } catch (error) {
        localStorage.removeItem(getChaveRascunhoInspecao(idInspecao));
        return;
    }

    if (!rascunho) return;

    if (Number.isInteger(rascunho.linhasMedicaoSolicitadas) && rascunho.linhasMedicaoSolicitadas > 0) {
        linhasMedicaoSolicitadas = rascunho.linhasMedicaoSolicitadas;
    }
    controlarLinhasTabela();

    ajustarQuantidadeItensNaoConformidade(rascunho.quantidadeItensNaoConformidade);

    aplicarCamposRascunho(rascunho.campos);
    aplicarChecksPendentes(rascunho.idsChecksMarcados);

    if (document.getElementById("pecaMortaSim")?.checked) {
        togglePecaMortaSection(true);
    } else {
        togglePecaMortaSection(false);
    }

    updateConformityCounts();
}

function limparRascunhoParcialInspecao(idInspecao) {
    const id = idInspecao || document.getElementById("id-inspecao").value;
    if (!id) return;
    localStorage.removeItem(getChaveRascunhoInspecao(id));
    atualizarFlagParcialCard(id, false);
}

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

    document.getElementById("numPecaDefeituosa").addEventListener("change", () => {
        controlarLinhasTabela();
    });

    const btnSalvarParcial = document.getElementById("savePartialInspection");
    if (btnSalvarParcial) {
        btnSalvarParcial.addEventListener("click", salvarParcialInspecao);
    }

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

// document.getElementById("numPecaDefeituosa").addEventListener("change", (event) => {

//     // Verifica se o valor máximo é menor que o valor atual
//     const max = parseInt(event.target.max);
//     const value = parseInt(event.target.value);
//     if (value > max) {
//         Toast.fire({
//             icon: "warning",
//             title: "A quantidade de peca morta nao pode exceder o total de pecas produzidas."
//         });
//         event.target.value = '';  
//         return;
//     }

//     controlarLinhasTabela();

//     if ((value - max) === 0){
//         document.getElementById("medicoesTecnicas").style.display = 'none';
//         document.getElementById("inspecao_total").value = 'Sim';
//     } else {
//         document.getElementById("medicoesTecnicas").style.display = 'block';
//         document.getElementById("inspecao_total").value = '';
//     }

// });



function buscarItensInspecao(pagina) {
    let cardsInspecao = document.getElementById("cards-inspecao");
    let qtdPendenteInspecao = document.getElementById("qtd-pendente-inspecao");
    let qtdFiltradaInspecao = document.getElementById("qtd-filtrada-inspecao");
    let itensInspecionar = document.getElementById("itens-inspecionar");
    let itensFiltradosMaquina = document.getElementById("itens-filtrados-inspecao-maquina");
    let itensFiltradosDataInicio = document.getElementById("itens-filtrados-inspecao-data-inicio");
    let itensFiltradosDataFim = document.getElementById("itens-filtrados-inspecao-data-fim");
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

    let dataInicio = document.getElementById('data-inicio-inspecao').value;
    let dataFim = document.getElementById('data-fim-inspecao').value;

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

    if (dataInicio) {
        params.append("data_inicio", dataInicio);
        itensFiltradosDataInicio.style.display = "block";
        itensFiltradosDataInicio.textContent = "De: " + dataInicio;
    } else {
        itensFiltradosDataInicio.style.display = "none";
    }

    if (dataFim) {
        params.append("data_fim", dataFim);
        itensFiltradosDataFim.style.display = "block";
        itensFiltradosDataFim.textContent = "Até: " + dataFim;
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
            const existeRascunhoParcial = Boolean(localStorage.getItem(getChaveRascunhoInspecao(item.id)));

            const cards = `
            <div class="col-md-4 mb-4">
                <div class="card p-3" data-card-inspecao-id="${item.id}" style="min-height: 300px; display: flex; flex-direction: column; justify-content: space-between">
                    <h5 class="d-flex align-items-center gap-2 titulo-card-inspecao">
                        <a href="https://drive.google.com/drive/u/0/search?q=${pegarCodigoPeca(item.peca)}" target="_blank" rel="noopener noreferrer">${item.peca}</a>
                        ${existeRascunhoParcial ? '<span class="badge bg-warning text-dark flag-rascunho-parcial">Parcial</span>' : ''}
                    </h5>
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

                    modalInspecao.querySelector('#numPecaDefeituosa').removeAttribute("max");                 
                    controlarLinhasTabela();
                    resetInspetorSelect();
                    carregarRascunhoParcialInspecao(itemId);

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
    const linhasExibidas = Math.max(1, linhasMedicaoSolicitadas);
    garantirQuantidadeLinhasMedicao(linhasExibidas);

    const linhas = getLinhasMedicao();
    linhas.forEach((linha, indice) => {
        if (indice < linhasExibidas) {
            linha.style.display = "";
            return;
        }

        linha.style.display = "none";
        limparLinhaMedicao(linha);
    });

    document.getElementById("sectionMedicaoTec").style.display = "block";
    atualizarContadorLinhasMedicao(linhasExibidas);

    const btnRemoverLinha = document.getElementById("btnRemoverLinhaMedicao");
    if (btnRemoverLinha) {
        btnRemoverLinha.disabled = linhasExibidas <= 1;
    }

    updateConformityCounts();
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

    linhasMedicaoSolicitadas = LINHAS_PADRAO_MEDICAO;
    controlarLinhasTabela();
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

    // Validacao de inspetor
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
    }

    // 2. Validacao das medicoes tecnicas conforme as linhas exibidas 
    const linhasVisiveis = getLinhasMedicaoVisiveis();
    let linhasObrigatorias = linhasVisiveis.length;
    let linhasPreenchidas = 0;
    let somaQuantidadeNaoConforme = 0;

    for (let i = 0; i < linhasVisiveis.length; i++) {
        const numeroLinha = parseInt(linhasVisiveis[i].id.replace("linhaMedicao", ""), 10);
        let linhaPreenchida = false;
        let algumCampoPreenchido = false;
        let conformeMarcado = false;
        let naoConformeMarcado = false;

        // Verificar se pelo menos um campo da linha foi preenchido
        for (let j = 1; j <= 4; j++) {
            const valor = document.getElementById(`valor${numeroLinha}_${j}`).value.trim();
            if (valor !== "") { // Verifica se o campo possui algum valor
                algumCampoPreenchido = true;
            }
        }

        // Verificar se um dos botões de conformidade foi marcado
        conformeMarcado = document.getElementById(`conforming${numeroLinha}`).checked;
        naoConformeMarcado = document.getElementById(`nonConforming${numeroLinha}`).checked;

        if (naoConformeMarcado) {
            somaQuantidadeNaoConforme += 1;
        }

        // A linha é considerada preenchida se pelo menos um campo tiver valor E uma conformidade for marcada
        if (algumCampoPreenchido && (conformeMarcado || naoConformeMarcado)) {
            linhaPreenchida = true;
            linhasPreenchidas++;
        }

        // Verificar se a linha obrigatória não está preenchida corretamente
        if ((i + 1) <= linhasObrigatorias && !linhaPreenchida) {
            Toast.fire({
                icon: "error",
                title: `Por favor, preencha pelo menos um campo e marque conformidade na linha ${numeroLinha} da tabela de medições técnicas.`
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

    if (conformidadeMarcada === 0) {
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

    // 6. Verificar consistencia das quantidades de nao conformidade
    const totalNaoConformidade = somaQuantidadeNaoConforme;

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
    if (event.target.classList.contains("conformity-radio")) {
        updateConformityCounts();
    }
    
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













