async function carregarTabela(pagina) {
  mostrarLoading(true);

  const selectElement = document.getElementById('filtro-peca');
  const maquinaSelecionada = document.getElementById('filtro-maquina')?.value || '';
  const ordemEscolhida     = document.getElementById('filtro-ordem')?.value || '';
  const dataCriacao        = document.getElementById('filtro-data-criacao')?.value || '';
  const modoBusca          = document.getElementById('filtro-modo')?.value || 'all';

  const pecasSelecionadas  = Array.from(selectElement.selectedOptions).map(option => option.value);

  // novos campos
  const pecaPrioritaria    = (modoBusca === 'prioritize')
    ? (document.getElementById('priorizar-peca')?.value || '')
    : '';

  const qtyMapaObj = (modoBusca === 'qty') ? coletarQuantidadesPorPeca() : {};
  const qtyMapaStr = Object.keys(qtyMapaObj).length
    ? encodeURIComponent(JSON.stringify(qtyMapaObj))
    : '';

  // monta query
  const params = new URLSearchParams({
    page: String(pagina),
    limit: '100',
    pecas: pecasSelecionadas.join('|'),            // já OK sem encode extra
    maquina: maquinaSelecionada,
    ordem: ordemEscolhida,
    dataCriacao: dataCriacao,
    modo: modoBusca,                               // NEW: 'all' | 'prioritize' | 'qty'
    priorizar: pecaPrioritaria,                    // NEW: peça prioritária (se houver)
    qtymap: qtyMapaStr                             // NEW: JSON de {peca:qtd}
  });

  try {
    const response = await fetch(`api/ordens-criadas/?${params.toString()}`);
    const data = await response.json();
    atualizarTabela(data.data);
    atualizarPaginacao(data.recordsTotal, pagina);
  } catch (error) {
    console.error('Erro ao carregar a tabela:', error);
  } finally {
    mostrarLoading(false);
  }
}

// util: cria uma linha peça+quantidade
function criarLinhaQty(pecaOptions = []) {
  const row = document.createElement('div');
  row.className = 'row g-2 align-items-center';
  row.innerHTML = `
    <div class="col-md-5">
      <select class="form-select bg-light qty-peca"></select>
    </div>
    <div class="col-md-4">
      <input type="number" min="0" step="1" class="form-control bg-light qty-valor" placeholder="Quantidade">
    </div>
    <div class="col-md-3 d-flex gap-2">
      <button type="button" class="btn btn-outline-danger btn-sm btn-remove-qty">Remover</button>
    </div>
  `;

  const select = row.querySelector('.qty-peca');
  // popular opções
  pecaOptions.forEach(opt => select.appendChild(opt.cloneNode(true)));

  // botão remover
  row.querySelector('.btn-remove-qty').addEventListener('click', () => row.remove());

  return row;
}

// sincroniza opções do "priorizar-peca" com as peças atualmente selecionadas
function syncPriorizarPeca() {
  const multi = document.getElementById('filtro-peca');
  const priorizar = document.getElementById('priorizar-peca');
  priorizar.innerHTML = '';
  const selecionadas = Array.from(multi.selectedOptions);
  if (!selecionadas.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Selecione peças acima';
    priorizar.appendChild(opt);
    return;
  }
  selecionadas.forEach(optSel => {
    const opt = document.createElement('option');
    opt.value = optSel.value;
    opt.textContent = optSel.textContent;
    priorizar.appendChild(opt);
  });
}

// mostra/esconde blocos conforme o modo
function toggleModoBusca() {
  const modo = document.getElementById('filtro-modo').value;
  document.getElementById('wrap-priorizar-peca').style.display = (modo === 'prioritize') ? '' : 'none';
  document.getElementById('wrap-qty-peca').style.display        = (modo === 'qty')        ? '' : 'none';
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
                <button class="btn-ver-pecas btn btn-sm btn-primary m-1" data-id="${ordem.id}">Ver Peças</button>
                <button class="btn-excluir-op btn btn-sm btn-danger m-1" data-id="${ordem.id}" data-ordem="${ordem.ordem}">Excluir OP</button>
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

function configurarBotaoExcluirOp() {
    document.addEventListener('click', function (event) {
        if (event.target.classList.contains('btn-excluir-op')) {
            const ordem = event.target.getAttribute('data-ordem'); 
            const ordemId = event.target.getAttribute('data-id');
            const textModal = document.querySelector('.text-body');
            const formExcluir = document.getElementById('formExcluirOrdem');
            const modal = new bootstrap.Modal(document.getElementById('modalExcluirOrdem'));

            // Adiciona um campo hidden ao formulário com o ID da ordem
            let idInput = formExcluir.querySelector('input[name="ordemId"]');
            if (!idInput) {
                idInput = document.createElement('input');
                idInput.type = 'hidden';
                idInput.name = 'ordemId';
                formExcluir.appendChild(idInput);
            }
            idInput.value = ordemId;

            textModal.textContent = `Tem certeza que deseja excluir a ordem de número ${ordem}?`;
            modal.show();
        }
    });
}

//  Preenche o modal com informações da duplicação
function preencherModalDuplicacao(data,ordemId) {
    const bodyDuplicarOrdem = document.getElementById('bodyDuplicarOrdem');
    
    console.log(data);

    document.getElementById('modalDuplicarOrdem').setAttribute('data-ordem-id', ordemId);
    
    const maquinas = ['laser_1', 'laser_2','laser_3']; // laser_1: 16, laser_2: 17
    const maquina = data.propriedades.maquina;
    const selectMaquina = document.getElementById('maquina');
    const colMaquina = document.getElementById('col-maquina');
    
    // Mapeamento: nome da máquina => ID
    const maquinaMap = {
        'laser_1': '16',
        'laser_2': '17',
        'laser_3': '58'
    };
    
    if (maquinas.includes(maquina)) {
        colMaquina.style.display = 'block';
        selectMaquina.required = true;
    
        // Preenche as opções
        selectMaquina.innerHTML = `
            <option value="">Selecione uma máquina</option>
            <option value="16">Laser 1</option>
            <option value="17">Laser 2 (JFY)</option>
            <option value="58">Laser 3 (Trumpf)</option>`
        ;
    
        // Seleciona automaticamente com base na máquina recebida
        selectMaquina.value = maquinaMap[maquina];
    
    } else {
        selectMaquina.innerHTML = `<option value="">Selecione uma máquina</option>`;
        colMaquina.style.display = 'none';
        selectMaquina.required = false;
        selectMaquina.value = '';
    }

    // Criando o conteúdo inicial do modal com a tabela da chapa
    bodyDuplicarOrdem.innerHTML = `
        <h5 class="text-center mt-3">ORDEM: ${data.propriedades.ordem}</h6>
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
                    <td>
                        <select class="form-select form-select-sm" id="selectEspessura" style="width: 120px;">
                            ${data.espessuras.map(espessura => 
                                `<option value="${espessura}" ${data.propriedades?.espessura === espessura ? 'selected' : ''}>
                                    ${espessura}
                                </option>`
                            ).join('')}
                        </select>
                    </td>
                    <td>
                        <input type="number" id="quantidadeChapas" 
                            class="form-control form-control-sm" 
                            data-value-original="${data.propriedades?.quantidade || 1}" 
                            value="${data.propriedades?.quantidade || 1}" 
                            min="1" style="width: 80px;">
                    </td>
                    <td>
                        <select class="form-select form-select-sm" id="selectTipoChapa" style="width: 150px;">
                            ${data.tipos_chapas.map(tipo => 
                                `<option value="${tipo}" ${data.propriedades?.tipo_chapa === tipo ? 'selected' : ''}>
                                    ${tipo}
                                </option>`
                            ).join('')}
                        </select>
                    </td>
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

function excluirOrdem() {
    document.getElementById('formExcluirOrdem').addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Obtém o botão de submit e o spinner
        const submitBtn = document.getElementById('submitExcluirOrdem');
        const spinner = submitBtn.querySelector('.spinner-border-sm');
        const btnText = submitBtn.querySelector('[role="status"]');
        
        // Desabilita o botão e mostra o spinner
        submitBtn.disabled = true;
        spinner.style.display = 'inline-block';
        btnText.textContent = 'Excluindo...';
        
        const formData = new FormData(this);
        const ordemId = formData.get('ordemId');
        
        fetch('/corte/api/excluir-op-padrao/', {
            method: 'POST',
            body: JSON.stringify({ ordem_id: ordemId }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() 
            }
        })
        .then(response => response.json())
        .then(data => {
            const bootstrapModal = bootstrap.Modal.getInstance(document.getElementById('modalExcluirOrdem'));
            bootstrapModal.hide();
            carregarTabela(1);
        })
        .catch(error => {
            console.error('Erro ao excluir ordem:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erro!',
                text: error,
            });
        })
        .finally(() => {
            // Reabilita o botão e esconde o spinner, independente de sucesso ou falha
            submitBtn.disabled = false;
            spinner.style.display = 'none';
            btnText.textContent = 'Excluir OP';
        });
    });
}

function duplicarOrdem() {
    const formDuplicarOrdem = document.getElementById('formDuplicarOrdem');

    formDuplicarOrdem.addEventListener('submit', function (event) {
        event.preventDefault(); // Evita recarregar a página

        // Obtém o ID da ordem armazenado no modal
        const modal = document.getElementById('modalDuplicarOrdem');
        const ordemId = modal.getAttribute('data-ordem-id');

        if (!ordemId) {
            Swal.fire({ icon: 'error', title: 'Erro!', text: 'ID da ordem não encontrado.' });
            return;
        }

        // Captura os valores do formulário
        const obsDuplicar = document.getElementById('obsFinalizarCorte').value;
        const dataProgramacao = document.getElementById('dataProgramacao').value;
        const maquina = document.getElementById('maquina').value;
        const espessura = document.getElementById('selectEspessura').value;
        const tipoChapa = document.getElementById('selectTipoChapa').value;
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
            maquina: maquina,
            pecas: pecas,
            espessura: espessura,
            tipoChapa: tipoChapa
        };

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
                title: `Sucesso! Nova ordem: ${data.nova_ordem}`,
                text: 'Ordem duplicada com sucesso.',
                // timer: 1500,  // Fecha automaticamente após 1.5s
                showConfirmButton: true
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
    configurarBotaoExcluirOp();
    excluirOrdem();

    configurarBotaoVerPecas();
    duplicarOrdem();

    // Ação do botão de filtro
    document.getElementById("filtro-form").addEventListener("submit", async (event) => {
        event.preventDefault();

        const btnFiltrarDup = document.getElementById("btn-filtrar-duplicador");
        btnFiltrarDup.innerHTML = '<i class="fa fa-spinner fa-spin"></i>'; // Exibe o ícone de carregamento
        btnFiltrarDup.disabled = true; // Desabilita o botão enquanto carrega
        await carregarTabela(1);
        btnFiltrarDup.disabled = false; // Reabilita o botão após carregar
        btnFiltrarDup.innerHTML = '<i class="bi bi-filter me-2"></i> Filtrar';
    });

    carregarTabela(1);

      const modo = document.getElementById('filtro-modo');
  const multi = document.getElementById('filtro-peca');
  const btnAddQty = document.getElementById('btn-add-qty');
  const qtyRows = document.getElementById('qty-rows');

  // muda modo
  modo.addEventListener('change', toggleModoBusca);

  // quando mudar peças, sincroniza priorizar e opções do repetidor
  multi.addEventListener('change', () => {
    syncPriorizarPeca();
    // opcional: atualizar selects existentes no repetidor
    const options = Array.from(multi.options).map(o => {
      const opt = document.createElement('option');
      opt.value = o.value;
      opt.textContent = o.textContent;
      return opt;
    });
    qtyRows.querySelectorAll('.qty-peca').forEach(select => {
      const valAtual = select.value;
      select.innerHTML = '';
      options.forEach(opt => select.appendChild(opt.cloneNode(true)));
      // tenta restaurar valor
      if (Array.from(select.options).some(o => o.value === valAtual)) {
        select.value = valAtual;
      }
    });
  });

  // adicionar linha no repetidor
  btnAddQty.addEventListener('click', () => {
    const options = Array.from(multi.options).map(o => {
      const opt = document.createElement('option');
      opt.value = o.value;
      opt.textContent = o.textContent;
      return opt;
    });
    const row = criarLinhaQty(options);
    qtyRows.appendChild(row);
  });

  // estado inicial
  toggleModoBusca();
  syncPriorizarPeca();
});

function coletarQuantidadesPorPeca() {
  const rows = document.querySelectorAll('#qty-rows .row');
  const mapa = {};
  rows.forEach(r => {
    const peca = r.querySelector('.qty-peca')?.value;
    const qtdStr = r.querySelector('.qty-valor')?.value;
    const qtd = Number(qtdStr);
    if (peca && Number.isFinite(qtd) && qtd >= 0) {
      mapa[peca] = qtd;
    }
  });
  return mapa;
}