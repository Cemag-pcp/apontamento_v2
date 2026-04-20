import { getCookie } from './criar_caixa.js';
import { resetFormCriarPacote } from './criar_pacote.js';
import { atualizarSlotAvancar, preencherSlotAvancar } from './kanbans.js';

// helper pra mapear a cor (pt-BR) -> classe do Bootstrap
function classeCorBadge(cor) {
  const c = String(cor || '').toLowerCase();
  switch (c) {
    case 'amarelo':  return 'bg-warning text-dark';
    case 'laranja':  return 'bg-orange text-dark'; // se não tiver, usa 'bg-warning'
    case 'cinza':    return 'bg-secondary';
    case 'azul':     return 'bg-primary';
    case 'verde':    return 'bg-success';
    case 'preto':    return 'bg-dark';
    case 'branco':   return 'bg-light text-dark';
    case 'vermelho': return 'bg-danger';
    default:         return 'bg-secondary';
  }
}

// se quiser garantir classe para laranja no Bootstrap 5 padrÃ£o:
(function ensureOrange() {
  const css = `.bg-orange{background-color:#fd7e14!important;color:#212529!important}`;
  if (!document.getElementById('css-orange-badge')) {
    const s = document.createElement('style');
    s.id = 'css-orange-badge';
    s.textContent = css;
    document.head.appendChild(s);
  }
})();

function possuiFornecedoresPendentes(codigosEspeciais, fornecedores) {
  return Object.entries(codigosEspeciais || {}).some(([tipo, itens = []]) =>
    itens.some(({ codigo }) => !(fornecedores[`${tipo}_${codigo}`] || '').trim())
  );
}

export async function popularPacotesDaCarga(cargaId) {

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

  const modal = document.getElementById('visualizarPacote');
  const modalBody = modal.querySelector('.modal-body');

  // Zera o conteÃºdo antes de popular
  modalBody.innerHTML = '';

  const cardsContainer = document.createElement('div');
  cardsContainer.classList.add('row', 'mt-3', 'gx-3');

  try {
    const response = await fetch(`api/buscar-pacote/${cargaId}/`);
    const data = await response.json();

    // Atualiza o badge de fornecedores no card do kanban se necessário
    if (data.status_carga === 'verificacao') {
      const codigosEspeciais = data.codigos_especiais || {};
      const fornecedores = data.fornecedores || {};
      const fornecedoresPendentes = possuiFornecedoresPendentes(codigosEspeciais, fornecedores);

      const cardEl = document.querySelector(`.card-kanban[data-id="${cargaId}"]`);
      if (cardEl) {
        const pendentesAntes = cardEl.dataset.fornecedoresPendentes === 'true';
        if (fornecedoresPendentes !== pendentesAntes) {
          cardEl.dataset.fornecedoresPendentes = fornecedoresPendentes ? 'true' : 'false';
          const slot = cardEl.querySelector('.slot-avancar');
          if (slot) {
            preencherSlotAvancar({
              id:                                Number(cargaId),
              stage:                             cardEl.dataset.stage,
              todos_pacotes_tem_foto_verificacao: cardEl.dataset.todosPhotoVerificacao === 'true',
              todos_pacotes_tem_foto_despachado:  cardEl.dataset.todosPhotoDespachado  === 'true',
              fornecedores_pendentes:             fornecedoresPendentes,
              total_pendente:                    Number(cardEl.dataset.totalPendente || 0),
            }, slot);
          }
        }
      }
    }

    // monta a linha das carretas
    const carretas = Array.isArray(data.carretas) ? data.carretas : [];
    const carretasChips = carretas.length
      ? carretas.map(({ carreta, quantidade, cor }) => {
          const cls = classeCorBadge(cor);
          const tip = `${cor ?? '*'} * qtd: ${quantidade ?? 0}`;
          return `
            <span class="badge rounded-pill ${cls}" 
                  data-bs-toggle="tooltip" data-bs-placement="top" 
                  data-bs-title="${tip}">
              ${carreta} — ${quantidade}
            </span>`;
        }).join(' ')
      : `<span class="text-muted">Sem carretas</span>`;

    let infoHTML = `
      <div class="border rounded-3 p-3 mb-3" style="background:linear-gradient(135deg,#f8f9fa 0%,#fff 100%);" id="cabecalhoPacotes">
        <div class="d-flex align-items-start justify-content-between flex-wrap gap-3">
          <div class="d-flex gap-4 flex-wrap align-items-center">
            <div>
              <div class="text-uppercase text-secondary fw-semibold" style="font-size:.62rem;letter-spacing:.09em;">Carga</div>
              <div class="fw-bold small">${data.carga}</div>
            </div>
            <div>
              <div class="text-uppercase text-secondary fw-semibold" style="font-size:.62rem;letter-spacing:.09em;">Cliente</div>
              <div class="fw-bold small">${data.cliente_carga}</div>
            </div>
            <div>
              <div class="text-uppercase text-secondary fw-semibold" style="font-size:.62rem;letter-spacing:.09em;">Data</div>
              <div class="fw-bold small">${data.data_carga}</div>
            </div>
          </div>
          <div class="d-flex gap-2 align-items-center flex-wrap">
            <input type="text" id="filtroItensPacote" class="form-control form-control-sm" placeholder="Filtrar itens..." style="min-width:175px;">
    `;

    // Botão de fornecedores (apenas na etapa verificação, se houver tipos especiais)
    const codigosEspeciais = data.codigos_especiais || {};
    const fornecedores = data.fornecedores || {};
    if (data.status_carga === 'verificacao' && Object.keys(codigosEspeciais).length > 0) {
      const todosFornecidos = !possuiFornecedoresPendentes(codigosEspeciais, fornecedores);
      const btnCls = todosFornecidos ? 'btn-success' : 'btn-warning';
      const btnLabel = todosFornecidos
        ? '<i class="fas fa-check-circle me-1"></i>Fornecedores informados'
        : '<i class="fas fa-exclamation-triangle me-1"></i>Informar Fornecedores (obrigatório)';
      infoHTML += `<button type="button" class="btn ${btnCls} btn-sm" id="btnAbrirFornecedores">${btnLabel}</button>`;
    }

    infoHTML += `<button type="button" class="btn btn-outline-warning btn-sm" id="btnVisualizarPendencias"><i class="fas fa-clock me-1"></i>Pendências</button>`;

    if (data.status_carga !== 'despachado') {
      infoHTML += `<button type="button" class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#criarPacoteModal" id="btnAbrirModalCriarPacote"><i class="fas fa-plus me-1"></i>Criar Pacote</button>`;
    }

    infoHTML += `
          </div>
        </div>
        <div class="d-flex flex-wrap gap-1 mt-3">
          ${carretasChips}
        </div>
      </div>
    `;

    modalBody.innerHTML = infoHTML;

    // Wiring do botão de fornecedores
    const btnAbrirForn = modalBody.querySelector('#btnAbrirFornecedores');
    if (btnAbrirForn) {
      btnAbrirForn.addEventListener('click', () => {
        abrirModalFornecedores(cargaId, codigosEspeciais, fornecedores);
      });
    }

    // Wiring do botão de pendências
    const btnPendencias = modalBody.querySelector('#btnVisualizarPendencias');
    if (btnPendencias) {
      btnPendencias.addEventListener('click', () => abrirModalPendencias(cargaId));
    }

    if (data.status_carga !== 'despachado') {
      // Busca o botÃ£o dentro do escopo do modal, que Ã© mais eficiente
      const btnAbrirModal = modalBody.querySelector('#btnAbrirModalCriarPacote');

      if (btnAbrirModal) {

        const modoNovoEl = document.getElementById('modoNovo');
        const modoExistenteEl = document.getElementById('modoExistente');
        const grupoNovoPacote = document.getElementById('grupoNovoPacote');
        const grupoPacoteExistente = document.getElementById('grupoPacoteExistente');
        const nomePacoteEl = document.getElementById('nomePacote');
        const pacoteExistenteEl = document.getElementById('pacoteExistente');
        const idCargaPacoteEl = document.getElementById('idCargaPacote');

        // Alterna entre "novo" e "existente"
        function toggleModoPacote(modo) {
          const usarExistente = (modo === 'existente');
          grupoNovoPacote.classList.toggle('d-none', usarExistente);
          grupoPacoteExistente.classList.toggle('d-none', !usarExistente);
          nomePacoteEl.required = !usarExistente;
          if (usarExistente) {
            nomePacoteEl.value = '';
          } else {
            pacoteExistenteEl.value = '';
          }
        }

        modoNovoEl.addEventListener('change', () => toggleModoPacote('novo'));
        modoExistenteEl.addEventListener('change', () => toggleModoPacote('existente'));

        // Carrega pacotes existentes da carga
        async function carregarPacotesExistentes(cargaId) {
          const resp = await fetch(`api/listar-pacotes-criados/${cargaId}/`, {
            headers: { 'Accept': 'application/json' }
          });
          if (!resp.ok) throw new Error(await resp.text());
          const data = await resp.json();
          
          const lista = Array.isArray(data.pacotes) ? data.pacotes : [];

          // popula o select
          pacoteExistenteEl.innerHTML = `<option value="">Selecione...</option>` + 
            lista.map(p => `<option value="${p.id_pacote}">${p.nome_pacote}</option>`).join('');
        }

        // No botÃ£o que abre o modal:
        const btnAbrirModal = modalBody.querySelector('#btnAbrirModalCriarPacote');
        if (btnAbrirModal) {
          btnAbrirModal.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopPropagation();

            resetFormCriarPacote(false, false);

            // defina o modo
            modoNovoEl.checked = true;
            toggleModoPacote('novo');

            // pegue/defina cargaId antes de usar
            // const cargaId = this.getAttribute('data-carga-id') || (window.cargaAtualId ?? '');
            console.log(cargaId);
            if (cargaId) {
              try {
                console.log(cargaId);
                await carregarPacotesExistentes(cargaId);
              } catch (e) {
                console.warn('Falha ao carregar pacotes existentes:', e);
              }
            }

          });
        }
      }
    }

    if (!data.pacotes || data.pacotes.length === 0) {
      modalBody.appendChild(document.createElement('hr'));
      const noData = document.createElement('p');
      noData.textContent = 'Nenhum pacote encontrado para esta carga.';
      noData.classList.add('text-muted', 'mt-3');
      modalBody.appendChild(noData);
      return;
    }
    
    // filtro de itens dentro dos pacotes
    const aplicarFiltro = (termo) => {
      const texto = (termo || '').toLowerCase().trim();
      const colunas = cardsContainer.querySelectorAll('.col-pacote');
      let algumVisivel = false;

      colunas.forEach((col) => {
        const itens = col.querySelectorAll('.item-row');
        let visiveisCard = 0;
        itens.forEach((li) => {
          const cod = (li.dataset.codigo || '').toLowerCase();
          const desc = (li.dataset.descricao || '').toLowerCase();
          const match = !texto || cod.includes(texto) || desc.includes(texto);
          li.classList.toggle('d-none', !match);
          if (match) visiveisCard += 1;
        });
        col.classList.toggle('d-none', visiveisCard === 0);
        if (visiveisCard > 0) algumVisivel = true;
      });

      // feedback quando nada encontrado
      let aviso = modalBody.querySelector('#avisoFiltroPacote');
      if (!aviso) {
        aviso = document.createElement('div');
        aviso.id = 'avisoFiltroPacote';
        aviso.className = 'alert alert-warning mt-3 d-none';
        aviso.textContent = 'Nenhum item encontrado com esse filtro.';
        modalBody.appendChild(aviso);
      }
      aviso.classList.toggle('d-none', algumVisivel);
    };

    data.pacotes.forEach(pacote => {

      const col = document.createElement('div');
      col.className = 'col-md-4 col-sm-6 col-pacote';  // 3 colunas em md+, 2 em sm
      col.dataset.pacoteId = pacote.id;  // facilita filtros

      const card = document.createElement('div');
      card.className = 'card mb-3 border-0';
      card.style.display = 'flex';
      card.style.flexDirection = 'column';
      card.style.maxHeight = '420px';
      card.style.boxShadow = '0 2px 10px rgba(0,0,0,.09)';
      card.style.borderRadius = '10px';
      card.style.overflow = 'hidden';

      let statusBadgeHtml = '';
      if (pacote.status_qualidade === 'ok') {
        statusBadgeHtml = '<span class="badge bg-success ms-2" style="font-size:.6rem;"><i class="fas fa-check me-1"></i>Confirmado</span>';
      } else if (pacote.status_expedicao === 'ok') {
        statusBadgeHtml = '<span class="badge bg-primary ms-2" style="font-size:.6rem;"><i class="fas fa-check me-1"></i>Expedição</span>';
      }

      const header = document.createElement('div');
      header.className = 'd-flex justify-content-between align-items-center py-2 px-3';
      header.style.background = 'linear-gradient(90deg,#e9ecef,#f8f9fa)';
      header.style.borderBottom = '1px solid rgba(0,0,0,.07)';
      header.style.flexShrink = '0';

      const headerLeft = document.createElement('div');
      headerLeft.className = 'd-flex align-items-center min-w-0 flex-grow-1 me-2';
      headerLeft.innerHTML = `<span class="fw-semibold text-truncate small" title="${pacote.nome}">${pacote.nome}</span>${statusBadgeHtml}`;

      const headerActions = document.createElement('div');
      headerActions.className = 'd-flex align-items-center gap-2 flex-shrink-0';

      if (data.status_carga !== 'despachado') {
        const btnDuplicar = document.createElement('button');
        btnDuplicar.className = 'btn btn-outline-secondary btn-sm';
        btnDuplicar.innerHTML = '<i class="fas fa-copy"></i>';
        btnDuplicar.title = 'Duplicar pacote';
        btnDuplicar.addEventListener('click', async (event) => {
          event.stopPropagation();
          const previous = btnDuplicar.innerHTML;
          btnDuplicar.disabled = true;
          btnDuplicar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
          try {
            const resp = await fetch(`api/pacotes/duplicar/${pacote.id}/`, {
              method: 'POST',
              headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });
            const dataResp = await resp.json().catch(() => ({}));
            if (!resp.ok) {
              throw new Error(dataResp?.erro || 'Erro ao duplicar o pacote.');
            }
            Toast.fire({ icon: "success", title: dataResp?.mensagem || 'Pacote duplicado.' });
            await popularPacotesDaCarga(cargaId);
          } catch (error) {
            alert(error.message || 'Erro ao duplicar o pacote.');
          } finally {
            btnDuplicar.disabled = false;
            btnDuplicar.innerHTML = previous;
          }
        });

        headerActions.appendChild(btnDuplicar);

        const btnDeletar = document.createElement('button');
        btnDeletar.className = 'btn btn-outline-danger btn-sm';
        btnDeletar.innerHTML = '<i class="fas fa-trash"></i>';
        btnDeletar.title = 'Excluir pacote';
        btnDeletar.addEventListener('click', async (event) => {
          event.stopPropagation();
          const confirmou = confirm('Deseja excluir este pacote? Os itens voltarão para as pendências.');
          if (!confirmou) return;
          const previous = btnDeletar.innerHTML;
          btnDeletar.disabled = true;
          btnDeletar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
          try {
            const resp = await fetch(`api/pacotes/deletar/${pacote.id}/`, {
              method: 'DELETE',
              headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });
            const dataResp = await resp.json().catch(() => ({}));
            if (!resp.ok) {
              throw new Error(dataResp?.erro || 'Erro ao excluir o pacote.');
            }
            Toast.fire({ icon: "success", title: dataResp?.mensagem || 'Pacote excluÃ­do.' });
            await popularPacotesDaCarga(cargaId);
          } catch (error) {
            alert(error.message || 'Erro ao excluir o pacote.');
          } finally {
            btnDeletar.disabled = false;
            btnDeletar.innerHTML = previous;
          }
        });

        headerActions.appendChild(btnDeletar);
      }
      header.appendChild(headerLeft);
      header.appendChild(headerActions);

      // Flag de foto ao lado do nome do pacote
      // Ao clicar na flag deverÃ¡ chamar uma funÃ§Ã£o que trarÃ¡ as fotos em um modal

      if (pacote.tem_foto === true || pacote.tem_foto === "true") {
        
        const fotoIcon = document.createElement('button');
        fotoIcon.className = 'btn btn-outline-primary btn-sm flex-shrink-0';
        fotoIcon.innerHTML = 'Ver foto <i class="fas fa-camera"></i>';
        fotoIcon.title = 'Este pacote possui foto(s) anexada(s)';
        fotoIcon.style.cursor = 'pointer';

        fotoIcon.addEventListener('click', (event) => {
          event.stopPropagation();

          fotoIcon.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
          fotoIcon.disabled = true;

          (async () => {
            try {
              const response = await fetch(`api/buscar-fotos/${pacote.id}/`);
              const data = await response.json();

              const buildConteudoModal = (fotos) => {
                const fotosPorEtapa = {};
                fotos.forEach(foto => {
                  if (!fotosPorEtapa[foto.etapa]) {
                    fotosPorEtapa[foto.etapa] = [];
                  }
                  fotosPorEtapa[foto.etapa].push(foto);
                });

                if (!fotos.length) {
                  return '<p class="text-muted">Nenhuma foto encontrada.</p>';
                }

                return Object.entries(fotosPorEtapa).map(([etapa, fotosEtapa]) => {
                  const imagens = fotosEtapa.map(foto => `
                    <div class="d-inline-block me-2 mb-2 position-relative">
                      <div class="position-absolute top-0 start-0 m-1" style="z-index:10;">
                        <input class="form-check-input foto-checkbox" type="checkbox" data-foto-id="${foto.id}"
                          style="width:1.3em;height:1.3em;cursor:pointer;background-color:rgba(255,255,255,0.85);" />
                      </div>
                      <a href="${foto.url}" target="_blank">
                        <img src="${foto.url}" class="rounded shadow-sm"
                          style="max-width:200px;height:auto;cursor:zoom-in;" alt="Foto da etapa ${etapa}" />
                      </a>
                    </div>
                  `).join('');
                  return `
                    <h6 class="mt-3">Etapa: ${etapa}</h6>
                    ${imagens}
                  `;
                }).join('');
              };

              const modal = document.createElement('div');
              modal.className = 'modal fade';
              modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                  <div class="modal-content">
                    <div class="modal-header">
                      <h5 class="modal-title">Fotos do Pacote ${pacote.nome}</h5>
                      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
                    </div>
                    <div class="modal-body" id="modalFotosBody">
                      ${buildConteudoModal(data.fotos || [])}
                    </div>
                    <div class="modal-footer">
                      <button type="button" class="btn btn-danger" id="btnExcluirFotosSelecionadas" disabled>
                        <i class="fas fa-trash"></i> Excluir fotos selecionadas
                      </button>
                      <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                    </div>
                  </div>
                </div>
              `;

              document.body.appendChild(modal);
              const bsModal = new bootstrap.Modal(modal);
              bsModal.show();

              // Remove modal from DOM after hiding
              modal.addEventListener('hidden.bs.modal', () => {
                document.body.removeChild(modal);
              });

              // Atualiza estado do botÃ£o de exclusÃ£o conforme seleÃ§Ã£o
              const syncDeleteBtn = () => {
                const checados = modal.querySelectorAll('.foto-checkbox:checked');
                modal.querySelector('#btnExcluirFotosSelecionadas').disabled = checados.length === 0;
              };

              modal.addEventListener('change', (e) => {
                if (e.target.classList.contains('foto-checkbox')) syncDeleteBtn();
              });

              // BotÃ£o excluir fotos selecionadas
              modal.querySelector('#btnExcluirFotosSelecionadas').addEventListener('click', async () => {
                const checados = [...modal.querySelectorAll('.foto-checkbox:checked')];
                if (!checados.length) return;

                const qtd = checados.length;
                const confirmado = await Swal.fire({
                  title: 'Confirmar exclusÃ£o',
                  text: `Deseja excluir ${qtd} foto(s) selecionada(s)? Esta aÃ§Ã£o não pode ser desfeita.`,
                  icon: 'warning',
                  showCancelButton: true,
                  confirmButtonColor: '#d33',
                  cancelButtonColor: '#6c757d',
                  confirmButtonText: 'Sim, excluir',
                  cancelButtonText: 'Cancelar',
                }).then(r => r.isConfirmed);

                if (!confirmado) return;

                const btnExcluir = modal.querySelector('#btnExcluirFotosSelecionadas');
                btnExcluir.disabled = true;
                btnExcluir.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Excluindo...';

                try {
                  await Promise.all(checados.map(cb =>
                    fetch(`api/excluir-foto/${cb.dataset.fotoId}/`, {
                      method: 'DELETE',
                      headers: { 'X-CSRFToken': getCookie('csrftoken') }
                    }).then(r => { if (!r.ok) throw new Error('Erro ao excluir foto'); })
                  ));

                  // Recarrega fotos no modal
                  const resp = await fetch(`api/buscar-fotos/${pacote.id}/`);
                  const novosDados = await resp.json();
                  modal.querySelector('#modalFotosBody').innerHTML = buildConteudoModal(novosDados.fotos || []);

                  Toast.fire({ icon: 'success', title: `${qtd} foto(s) excluÃ­da(s) com sucesso.` });

                  // Atualiza flag do botÃ£o "Ver foto" se não houver mais fotos
                  if (!novosDados.fotos?.length) {
                    fotoIcon.remove();
                  }
                } catch (err) {
                  alert('Erro ao excluir foto(s): ' + err.message);
                } finally {
                  btnExcluir.innerHTML = '<i class="fas fa-trash"></i> Excluir fotos selecionadas';
                  syncDeleteBtn();
                }
              });

              fotoIcon.innerHTML = 'Ver foto <i class="fas fa-camera"></i>';
              fotoIcon.disabled = false;

            } catch (error) {
              console.error('Erro ao carregar fotos:', error);
              alert('Erro ao carregar as fotos do pacote.');
    
              fotoIcon.innerHTML = 'Ver foto <i class="fas fa-camera"></i>';
              fotoIcon.disabled = false;

            }
          })();
        });
        headerActions.appendChild(fotoIcon);
      }

      const body = document.createElement('div');
      body.className = 'px-0 py-0';
      body.style.overflowY = 'auto';
      body.style.flex = '1';

      const dataCriacao = document.createElement('div');
      dataCriacao.className = 'text-muted px-3 pt-2 pb-1';
      dataCriacao.style.fontSize = '.68rem';
      dataCriacao.innerText = `Criado em: ${pacote.data_criacao}`;

      const lista = document.createElement('div');
      lista.className = 'pkg-items';

      card.dataset.pacoteId = pacote.id;
      lista.dataset.pacoteId = pacote.id;

      if (pacote.itens.length === 0) {
        const vazio = document.createElement('div');
        vazio.className = 'item-row item-row-empty text-muted small px-3 py-2';
        vazio.innerText = 'Nenhum item no pacote.';
        lista.appendChild(vazio);
      } else {
        pacote.itens.forEach((item, idx) => {
          const li = document.createElement('div');
          li.className = 'item-row d-flex align-items-center gap-2 px-3 py-1 border-bottom';
          li.dataset.itemId = (item.id ?? idx);

          const codigoItem = item.codigo_peca || '(sem código)';
          const descricaoItem = item.descricao || '';

          const info = document.createElement('div');
          info.className = 'flex-grow-1 min-w-0';
          info.innerHTML = `
            <div class="fw-semibold text-truncate" style="font-size:.78rem;" title="${codigoItem}">${codigoItem}</div>
            <div class="text-muted text-truncate" style="font-size:.72rem;" title="${descricaoItem}">${descricaoItem}${item.fora_planejado ? ' <span class="badge bg-warning text-dark" style="font-size:.6rem;">Fora do plan.</span>' : ''}</div>
          `;
          li.dataset.codigo = codigoItem;
          li.dataset.descricao = descricaoItem;

          // BotÃ£o "Alterar pacote"
          const btnAlterar = document.createElement('button');
          btnAlterar.type = 'button';
          btnAlterar.className = 'btn btn-outline-primary btn-sm flex-shrink-0';
          // btnAlterar.textContent = 'Alterar pacote';
          btnAlterar.innerHTML = '<i class="fas fa-exchange-alt"></i>'; // Ãcone de troca
          btnAlterar.setAttribute('data-bs-toggle', 'modal');
          btnAlterar.setAttribute('data-bs-target', '#modalAlterarPacote');

          // Ao clicar, preenche o modal e lista os pacotes disponÃ­veis
          btnAlterar.addEventListener('click', () => {
            // guarda referÃªncia do <li> atual para mover no DOM apÃ³s sucesso
            window._editingItemLi = li;

            // campos escondidos
            document.getElementById('pacoteOrigemId').value = pacote.id;
            document.getElementById('itemId').value = (item.id ?? idx);
            document.getElementById('cargaId').value = cargaId;

            // popula o select com todos os pacotes da carga, exceto o atual
            const sel = document.getElementById('pacoteDestinoId');
            const helper = document.getElementById('helperPacoteDestino');
            sel.innerHTML = '';
            helper.textContent = '';

            const outros = (data.pacotes || []).filter(p => p.id !== pacote.id);
            if (outros.length === 0) {
              const opt = document.createElement('option');
              opt.value = '';
              opt.textContent = 'não hÃ¡ outros pacotes';
              sel.appendChild(opt);
              sel.disabled = true;
              helper.textContent = 'Crie outro pacote para mover este item.';
            } else {
              const placeholder = document.createElement('option');
              placeholder.value = '';
              placeholder.textContent = 'Selecione...';
              placeholder.disabled = true;
              placeholder.selected = true;
              sel.appendChild(placeholder);

              outros.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.nome;
                sel.appendChild(opt);
              });
              sel.disabled = false;
            }
          });

          li.appendChild(info);

          const actionsDiv = document.createElement('div');
          actionsDiv.className = 'd-flex align-items-center gap-1 flex-shrink-0';

          const podeEditarQtd = (data.status_carga === 'planejamento' || data.status_carga === 'verificacao');
          if (podeEditarQtd) {
            const inputQtd = document.createElement('input');
            inputQtd.type = 'number';
            inputQtd.min = '1';
            inputQtd.value = item.quantidade;
            inputQtd.className = 'form-control form-control-sm text-center';
            inputQtd.style.width = '52px';
            inputQtd.style.fontSize = '.78rem';

            const btnSalvarQtd = document.createElement('button');
            btnSalvarQtd.type = 'button';
            btnSalvarQtd.className = 'btn btn-outline-secondary btn-sm p-1';
            btnSalvarQtd.innerHTML = '<i class="fas fa-save" style="font-size:.7rem;"></i>';
            btnSalvarQtd.title = 'Salvar quantidade';

            btnSalvarQtd.addEventListener('click', async () => {
              const novaQt = parseInt(inputQtd.value, 10);
              if (!novaQt || novaQt <= 0) { alert('Quantidade inválida.'); return; }
              const prevText = btnSalvarQtd.innerHTML;
              btnSalvarQtd.disabled = true;
              btnSalvarQtd.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
              try {
                const resp = await fetch(`api/pacotes/itens/${item.id}/atualizar-quantidade/`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                  body: JSON.stringify({ quantidade: novaQt })
                });
                const dataResp = await resp.json().catch(() => ({}));
                if (!resp.ok) throw new Error(dataResp?.erro || 'Erro ao atualizar quantidade.');
                inputQtd.value = dataResp.nova_quantidade;
              } catch (error) {
                alert(error.message || 'Erro ao atualizar quantidade.');
              } finally {
                btnSalvarQtd.disabled = false;
                btnSalvarQtd.innerHTML = prevText;
              }
            });

            const btnExcluirItem = document.createElement('button');
            btnExcluirItem.type = 'button';
            btnExcluirItem.className = 'btn btn-outline-danger btn-sm p-1';
            btnExcluirItem.innerHTML = '<i class="fas fa-trash" style="font-size:.7rem;"></i>';
            btnExcluirItem.title = 'Remover item';
            btnExcluirItem.addEventListener('click', async () => {
              const confirma = item.fora_planejado
                ? confirm('Remover este item fora do planejado do pacote?')
                : confirm('Remover esta peça do pacote? A quantidade voltará para a pendência.');
              if (!confirma) return;
              const prev = btnExcluirItem.innerHTML;
              btnExcluirItem.disabled = true;
              btnExcluirItem.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
              try {
                const resp = await fetch(`api/pacotes/itens/${item.id}/deletar/`, {
                  method: 'DELETE',
                  headers: { 'X-CSRFToken': getCookie('csrftoken') }
                });
                const dataResp = await resp.json().catch(() => ({}));
                if (!resp.ok) throw new Error(dataResp?.erro || 'Erro ao remover peça.');
                li.remove();
                if (!lista.querySelector('.item-row:not(.item-row-empty)')) {
                  const vazio = document.createElement('div');
                  vazio.className = 'item-row item-row-empty text-muted small px-3 py-2';
                  vazio.innerText = 'Nenhum item no pacote.';
                  lista.appendChild(vazio);
                }
              } catch (error) {
                alert(error.message || 'Erro ao remover peça.');
              } finally {
                btnExcluirItem.disabled = false;
                btnExcluirItem.innerHTML = prev;
              }
            });

            actionsDiv.appendChild(inputQtd);
            actionsDiv.appendChild(btnSalvarQtd);
            actionsDiv.appendChild(btnExcluirItem);
          } else {
            const qtyBadge = document.createElement('span');
            qtyBadge.className = 'badge bg-light text-dark border';
            qtyBadge.style.fontSize = '.72rem';
            qtyBadge.textContent = `×${item.quantidade}`;
            actionsDiv.appendChild(qtyBadge);
          }

          if (data.status_carga === 'planejamento' && pacote.status_expedicao !== 'ok') {
            actionsDiv.appendChild(btnAlterar);
          } else if (data.status_carga === 'verificacao' && pacote.status_qualidade !== 'ok') {
            actionsDiv.appendChild(btnAlterar);
          }

          li.appendChild(actionsDiv);
          lista.appendChild(li);
        });
      }

      // BotÃ£o Confirmar APONTAMENTO
      const btnConfirmarExpedicao = document.createElement('button');
      btnConfirmarExpedicao.className = 'btn btn-outline-success btn-sm mt-2 w-100';
      btnConfirmarExpedicao.textContent = 'Confirmar (ExpediÃ§Ã£o)';
      btnConfirmarExpedicao.setAttribute('data-bs-toggle', 'modal');
      btnConfirmarExpedicao.setAttribute('data-bs-target', '#modalConfirmarPacote');
      btnConfirmarExpedicao.setAttribute('data-id-pacote', pacote.id);

      // Passa o ID do pacote para o modal ao clicar
      btnConfirmarExpedicao.addEventListener('click', () => {
        document.getElementById('idPacoteConfirmar').value = pacote.id;
        document.getElementById('obsConfirmarPacote').value = '';  // limpa campo
      });

      // BotÃ£o Confirmar QUALIDADE
      const btnConfirmarQualidade = document.createElement('button');
      btnConfirmarQualidade.className = 'btn btn-outline-success btn-sm mt-2 w-100';
      btnConfirmarQualidade.textContent = 'Confirmar (Qualidade)';
      btnConfirmarQualidade.setAttribute('data-bs-toggle', 'modal');
      btnConfirmarQualidade.setAttribute('data-bs-target', '#modalConfirmarPacote');
      btnConfirmarQualidade.setAttribute('data-id-pacote', pacote.id);

      // Passa o ID do pacote para o modal ao clicar
      btnConfirmarQualidade.addEventListener('click', () => {
        document.getElementById('idPacoteConfirmar').value = pacote.id;
        document.getElementById('obsConfirmarPacote').value = '';  // limpa campo
      });

      body.appendChild(dataCriacao);
      body.appendChild(lista);

      const footer = document.createElement('div');
      footer.className = 'card-footer d-flex flex-column gap-1 py-2';
      footer.style.borderTop = '1px solid rgba(0,0,0,.07)';
      footer.style.background = '#fafafa';

      // BotÃ£o de adicionar foto
      const btnFoto = document.createElement('button');
      btnFoto.className = 'btn btn-outline-secondary btn-sm';
      btnFoto.innerHTML = '<i class="fas fa-camera"></i>';
      btnFoto.title = "Câmera";
      const abrirSelecaoFoto = (usarCamera = false) => {
        // Cria input de arquivo invisÃ­vel
        const input = document.createElement('input');
        input.type = 'file';
        // Em alguns navegadores mobile, `image/*` abre a cÃ¢mera direto.
        // Usar extensÃµes forÃ§a o seletor de arquivos/galeria.
        input.accept = '.jpg,.jpeg,.png,.webp,.heic,.heif';
        if (usarCamera) {
          input.setAttribute('capture', 'environment');
        } else {
          input.removeAttribute('capture');
        }

        // Ao selecionar ou tirar a foto
        input.onchange = () => {
          const file = input.files[0];
          if (!file) {
            input.remove();
            return;
          }

          const previewURL = URL.createObjectURL(file);

          // Cria modal para confirmaÃ§Ã£o
          const modal = document.createElement('div');
          modal.className = 'modal fade';
          modal.id = 'fotoModal';
          modal.tabIndex = -1;
          modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
              <div class="modal-content">
                <div class="modal-header">
                  <h5 class="modal-title">Confirmar Foto</h5>
                  <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
                </div>
                <div class="modal-body text-center">
                  <img src="${previewURL}" alt="PrÃ©via" class="img-fluid rounded mb-3" />
                  <button id="confirmarFotoBtn" class="btn btn-success">Confirmar</button>
                </div>
              </div>
            </div>
          `;

          document.body.appendChild(modal);

          // Exibe o modal
          const bsModal = new bootstrap.Modal(modal);
          bsModal.show();

          // Ao confirmar
          modal.querySelector('#confirmarFotoBtn').onclick = (e) => {
            
            const btn = e.currentTarget;   // referÃªncia ao prÃ³prio botÃ£o
            btn.innerHTML = 'Confirmando...';
            btn.disabled = true;

            // Aqui vocÃª envia para o backend via fetch/axios/FormData
            const formData = new FormData();
            formData.append('foto', file);
            formData.append('pacote', pacote.id)

            fetch('api/salvar-foto/', {
              method: 'POST',
              body: formData,
              headers: {
                'X-CSRFToken': getCookie('csrftoken')
              }
            })
            .then(res => res.json())
            .then(data => {
              Toast.fire({
                  icon: "success",
                  title: "Foto salva com sucesso."
              });

              console.log(data.info_add.carga_id, data.info_add.etapa, data.info_add.todos_pacotes_tem_foto_verificacao);

              atualizarSlotAvancar(data.info_add.carga_id, data.info_add.todos_pacotes_tem_foto_verificacao, data.info_add.etapa);

              btn.innerHTML = 'Confirmar';
              btn.disabled = false;

              bsModal.hide();
            })
            .catch(err => {
              alert('Erro ao salvar a foto.');
              console.error(err);
              btn.innerHTML = 'Confirmar';
              btn.disabled = false;


            });
          };

          modal.addEventListener('hidden.bs.modal', () => {
            URL.revokeObjectURL(previewURL);
            modal.remove();
          }, { once: true });
        };

        // Aciona o input
        document.body.appendChild(input);
        input.click();
      };
      btnFoto.onclick = () => abrirSelecaoFoto(true);

      const btnArquivo = document.createElement('button');
      btnArquivo.className = 'btn btn-outline-secondary btn-sm';
      btnArquivo.innerHTML = '<i class="fas fa-image"></i>';
      btnArquivo.title = "Selecionar arquivo";
      btnArquivo.onclick = () => abrirSelecaoFoto(false);

      // BotÃ£o de imprimir
      const btnPrint = document.createElement('button');
      btnPrint.className = 'btn btn-outline-secondary btn-sm';
      btnPrint.innerHTML = '<i class="fas fa-print"></i>';
      btnPrint.title = "Imprimir";
      btnPrint.onclick = () => {
        // lÃ³gica para impressÃ£o
        impressaoZebra(pacote.id, pacote.cliente, pacote.data_carga, pacote.nome);
      };

      const btnGroup = document.createElement('div');
      btnGroup.className = 'd-flex gap-2';

      if (data.status_carga === 'verificacao' && pacote.status_qualidade !== 'ok') {

        // Confirmar Qualidade
        btnConfirmarQualidade.className = 'btn btn-outline-success btn-sm flex-grow-1';
        btnGroup.appendChild(btnConfirmarQualidade);

        btnGroup.appendChild(btnPrint);
        btnGroup.appendChild(btnFoto);
        btnGroup.appendChild(btnArquivo);

        footer.appendChild(btnGroup);

      } else if (data.status_carga === 'verificacao' && pacote.status_qualidade === 'ok') {
        const span = document.createElement('span');
        span.className = 'text-success fw-bold text-center ms-2';
        span.textContent = 'Pacote confirmado';

        btnGroup.appendChild(span);
        btnGroup.appendChild(btnPrint);
        btnGroup.appendChild(btnFoto);
        btnGroup.appendChild(btnArquivo);

        footer.appendChild(btnGroup);
      }

      if (data.status_carga === 'despachado' && pacote.status_qualidade === 'ok') {

        // Confirmar Qualidade
        // btnConfirmarQualidade.className = 'btn btn-outline-success btn-sm flex-grow-1';
        // btnGroup.appendChild(btnConfirmarQualidade);

        // btnGroup.appendChild(btnPrint);
        btnGroup.appendChild(btnFoto);
        btnGroup.appendChild(btnArquivo);

        footer.appendChild(btnGroup);

      }

      card.appendChild(header);
      card.appendChild(body);
      card.appendChild(footer);
      col.appendChild(card);
      cardsContainer.appendChild(col);
    });

    modalBody.appendChild(document.createElement('hr'));
    modalBody.appendChild(cardsContainer);

    const campoFiltro = modalBody.querySelector('#filtroItensPacote');
    if (campoFiltro) {
      campoFiltro.addEventListener('input', (e) => aplicarFiltro(e.target.value));
    }
    // aplica filtro vazio para resetar estado
    aplicarFiltro('');

  } catch (error) {
    console.error('Erro ao buscar pacotes:', error);
    modalBody.innerHTML += '<div class="alert alert-danger mt-3">Erro ao carregar os pacotes.</div>';
  }
}

export function wireModalAlterarPacote(){
  const form = document.getElementById('formAlterarPacote');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const itemId     = document.getElementById('itemId').value;
    const origemId   = document.getElementById('pacoteOrigemId').value;
    const destinoId  = document.getElementById('pacoteDestinoId').value;
    const cargaId    = document.getElementById('cargaId').value;

    if (!destinoId || destinoId === origemId) {
      document.getElementById('helperPacoteDestino').textContent = 'Selecione um pacote diferente.';
      return;
    }

    // botÃ£o de submit em loading
    const submitBtn = form.querySelector('button[type="submit"]');
    const prevText  = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Salvando...';

    try {
      const resp = await fetch('api/pacotes/mover-item/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
          item_id: itemId,
          pacote_origem_id: origemId,
          pacote_destino_id: destinoId
        })
      });

      if (!resp.ok) {
        const msg = await resp.text().catch(()=>'');
        throw new Error(msg || 'Falha ao mover item.');
      }

      // Atualiza DOM localmente (move o item para a lista do pacote destino)
      if (window._editingItemLi) {
        const pkgItemsDestino = document.querySelector(`.pkg-items[data-pacote-id="${destinoId}"]`);
        if (pkgItemsDestino) {
          const vazio = pkgItemsDestino.querySelector('.item-row-empty');
          if (vazio) vazio.remove();
          pkgItemsDestino.appendChild(window._editingItemLi);
        }
      }

      // fecha modal
      const modalEl = document.getElementById('modalAlterarPacote');
      const modal   = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
      modal.hide();

      const modalElVisualizarPacotes = document.getElementById('visualizarPacote');
      const modalVisualizarPacotes   = bootstrap.Modal.getInstance(modalElVisualizarPacotes) || new bootstrap.Modal(modalElVisualizarPacotes);
      modalVisualizarPacotes.show();

      popularPacotesDaCarga(cargaId);

    } catch (err) {
      alert(err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = prevText;
      // limpa ref
      window._editingItemLi = null;
    }
  })
}

function impressaoZebra(id_pacote, cliente, data_carga, nome_pacote){

  const resp = fetch('api/impressao/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
      pacote_id: id_pacote,
      cliente: cliente,
      data_carga: data_carga,
      nome_pacote: nome_pacote
    })
  });

}

// ===== Modal de Fornecedores de Peças Especiais =====

function renderizarInputsFornecedor(containerId, tipo, itens, fornecedores) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = '';

  itens.forEach(({ codigo, descricao }) => {
    const fornecedorAtual = fornecedores[`${tipo}_${codigo}`] || '';
    const wrapper = document.createElement('div');
    wrapper.className = 'border rounded p-2 bg-light-subtle';
    wrapper.innerHTML = `
      <div class="small fw-semibold mb-1">${codigo}</div>
      <div class="small text-muted mb-2">${descricao || 'Sem descrição'}</div>
      <input
        type="text"
        class="form-control forn-input-item"
        data-tipo="${tipo}"
        data-codigo="${codigo}"
        placeholder="Nome do fornecedor"
        value="${fornecedorAtual.replace(/"/g, '&quot;')}"
      >
    `;
    container.appendChild(wrapper);
  });
}

export function abrirModalFornecedores(cargaId, codigosEspeciais, fornecedores) {
  document.getElementById('fornCargaId').value = cargaId;

  const grupoMap = {
    'Pneu':     { grupo: 'fornGrupoPneu', container: 'fornInputsPneu' },
    'Cilindro': { grupo: 'fornGrupoCilindro', container: 'fornInputsCilindro' },
    'Roda':     { grupo: 'fornGrupoRoda', container: 'fornInputsRoda' },
  };

  Object.entries(grupoMap).forEach(([tipo, { grupo, container }]) => {
    const grupoEl = document.getElementById(grupo);
    if (!grupoEl) return;
    const itens = Array.isArray(codigosEspeciais[tipo]) ? codigosEspeciais[tipo] : [];

    if (itens.length > 0) {
      grupoEl.classList.remove('d-none');
      renderizarInputsFornecedor(container, tipo, itens, fornecedores);
    } else {
      grupoEl.classList.add('d-none');
      const containerEl = document.getElementById(container);
      if (containerEl) containerEl.innerHTML = '';
    }
  });

  // Fecha o modal de pacotes para evitar conflito de backdrop
  const modalPacotesEl = document.getElementById('visualizarPacote');
  bootstrap.Modal.getInstance(modalPacotesEl)?.hide();

  const modalFornEl = document.getElementById('modalFornecedores');

  // Ao fechar o modal de fornecedores, reabre o de pacotes
  const reabrir = () => {
    const modalPacotes = bootstrap.Modal.getOrCreateInstance(modalPacotesEl);
    modalPacotes.show();
    modalFornEl.removeEventListener('hidden.bs.modal', reabrir);
  };
  modalFornEl.addEventListener('hidden.bs.modal', reabrir);

  bootstrap.Modal.getOrCreateInstance(modalFornEl).show();
}

document.addEventListener('DOMContentLoaded', () => {
  const btnSalvar = document.getElementById('btnSalvarFornecedores');
  if (!btnSalvar) return;

  btnSalvar.addEventListener('click', async () => {
    const cargaId = document.getElementById('fornCargaId').value;
    const spin = document.getElementById('spinFornecedores');

    const payload = Array.from(document.querySelectorAll('#formFornecedores .forn-input-item')).map((input) => ({
      tipo: input.dataset.tipo || '',
      codigo: input.dataset.codigo || '',
      fornecedor: (input.value || '').trim(),
    }));

    btnSalvar.disabled = true;
    spin?.classList.remove('d-none');

    try {
      const resp = await fetch(`api/salvar-fornecedores/${cargaId}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.erro || 'Erro ao salvar fornecedores.');
      }

      const respData = await resp.json().catch(() => ({}));
      const fornecedoresPendentes = respData.fornecedores_pendentes ?? false;

      // Atualiza apenas o card correspondente no kanban
      const cardEl = document.querySelector(`.card-kanban[data-id="${cargaId}"]`);
      if (cardEl) {
        cardEl.dataset.fornecedoresPendentes = fornecedoresPendentes ? 'true' : 'false';
        const slot = cardEl.querySelector('.slot-avancar');
        if (slot) {
          preencherSlotAvancar({
            id:                               Number(cargaId),
            stage:                            cardEl.dataset.stage,
            todos_pacotes_tem_foto_verificacao: cardEl.dataset.todosPhotoVerificacao === 'true',
            todos_pacotes_tem_foto_despachado:  cardEl.dataset.todosPhotoDespachado  === 'true',
            fornecedores_pendentes:             fornecedoresPendentes,
            total_pendente:                   Number(cardEl.dataset.totalPendente || 0),
          }, slot);
        }
      }

      const currentCargaId = document.getElementById('idCargaPacote').value;
      const modalFornEl = document.getElementById('modalFornecedores');
      const modalPacotesEl = document.getElementById('visualizarPacote');
      const recarregar = () => {
        if (currentCargaId) popularPacotesDaCarga(currentCargaId);
        modalPacotesEl.removeEventListener('shown.bs.modal', recarregar);
      };
      modalPacotesEl.addEventListener('shown.bs.modal', recarregar);
      bootstrap.Modal.getInstance(modalFornEl)?.hide();
    } catch (err) {
      alert(err.message || 'Erro ao salvar fornecedores.');
    } finally {
      btnSalvar.disabled = false;
      spin?.classList.add('d-none');
    }
  });
});

async function abrirModalPendencias(cargaId) {
  const modalEl = document.getElementById('modalVisualizarPendencias');
  if (!modalEl) return;

  const loading = modalEl.querySelector('#pendencias-loading');
  const conteudo = modalEl.querySelector('#pendencias-conteudo');
  const tbody = modalEl.querySelector('#pendencias-tbody');
  const resumo = modalEl.querySelector('#pendencias-resumo');
  const vazio = modalEl.querySelector('#pendencias-vazio');

  loading.classList.remove('d-none');
  conteudo.classList.add('d-none');
  tbody.innerHTML = '';

  const modal = new bootstrap.Modal(modalEl);
  modal.show();

  async function carregarPendencias() {
    loading.classList.remove('d-none');
    conteudo.classList.add('d-none');
    tbody.innerHTML = '';

    try {
      const resp = await fetch(`api/pendencias/${cargaId}/`);
      if (!resp.ok) throw new Error('Erro ao buscar pendências.');
      const data = await resp.json();
      const itens = data.itens || [];

      resumo.textContent = `Total: ${itens.length} item(ns) pendente(s)`;

      if (itens.length === 0) {
        vazio.classList.remove('d-none');
      } else {
        vazio.classList.add('d-none');
        itens.forEach(item => {
          const tr = document.createElement('tr');
          tr.dataset.id = item.id;
          tr.innerHTML = `
            <td>${item.carreta ?? '-'}</td>
            <td>${item.codigo ?? '-'}</td>
            <td>${item.descricao ?? '-'}</td>
            <td class="text-end">${item.qt_necessaria ?? 0}</td>
            <td class="text-center">
              <button class="btn btn-outline-danger btn-sm btn-excluir-pendencia" title="Excluir pendência">
                <i class="fas fa-trash"></i>
              </button>
            </td>
          `;

          tr.querySelector('.btn-excluir-pendencia').addEventListener('click', async () => {
            const confirmado = await Swal.fire({
              icon: 'warning',
              title: 'Excluir pendência?',
              text: `${item.codigo} — ${item.descricao}`,
              showCancelButton: true,
              confirmButtonText: 'Excluir',
              cancelButtonText: 'Cancelar',
              confirmButtonColor: '#dc3545',
            });
            if (!confirmado.isConfirmed) return;

            try {
              const csrftoken = document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] ?? '';
              const delResp = await fetch(`api/pendencias/item/${item.id}/excluir/`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': csrftoken },
              });
              if (!delResp.ok) throw new Error('Erro ao excluir.');
              tr.remove();
              const restantes = tbody.querySelectorAll('tr').length;
              resumo.textContent = `Total: ${restantes} item(ns) pendente(s)`;
              if (restantes === 0) vazio.classList.remove('d-none');
            } catch (err) {
              Swal.fire({ icon: 'error', title: 'Erro', text: err.message });
            }
          });

          tbody.appendChild(tr);
        });
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-3">${err.message}</td></tr>`;
    } finally {
      loading.classList.add('d-none');
      conteudo.classList.remove('d-none');
    }
  }

  await carregarPendencias();
}
