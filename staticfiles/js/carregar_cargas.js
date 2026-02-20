import { getCookie } from './criar_caixa.js';
import { resetFormCriarPacote } from './criar_pacote.js';
import { atualizarSlotAvancar } from './kanbans.js';

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

// se quiser garantir classe para laranja no Bootstrap 5 padrão:
(function ensureOrange() {
  const css = `.bg-orange{background-color:#fd7e14!important;color:#212529!important}`;
  if (!document.getElementById('css-orange-badge')) {
    const s = document.createElement('style');
    s.id = 'css-orange-badge';
    s.textContent = css;
    document.head.appendChild(s);
  }
})();

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

  // Zera o conteúdo antes de popular
  modalBody.innerHTML = '';

  const cardsContainer = document.createElement('div');
  cardsContainer.classList.add('row', 'mt-3', 'gx-3');

  try {
    const response = await fetch(`api/buscar-pacote/${cargaId}/`);
    const data = await response.json();

    // monta a linha das carretas
    const carretas = Array.isArray(data.carretas) ? data.carretas : [];
    const carretasChips = carretas.length
      ? carretas.map(({ carreta, quantidade, cor }) => {
          const cls = classeCorBadge(cor);
          const tip = `${cor ?? '—'} • qtd: ${quantidade ?? 0}`;
          return `
            <span class="badge rounded-pill ${cls}" 
                  data-bs-toggle="tooltip" data-bs-placement="top" 
                  data-bs-title="${tip}">
              ${carreta} × ${quantidade}
            </span>`;
        }).join(' ')
      : `<span class="text-muted">Sem carretas</span>`;

    let infoHTML = `
      <div class="d-flex justify-content-between align-items-center mb-3" id="cabecalhoPacotes">
        <div>
          <strong>Cliente:</strong> ${data.cliente_carga} |
          <strong>Dt. Carga:</strong> ${data.data_carga} |
          <strong>Carga:</strong> ${data.carga}
          <div class="mt-2 d-flex flex-wrap gap-2 align-items-center">
            ${carretasChips}
          </div>
        </div>
        <div class="ms-3 flex-grow-1">
          <label class="form-label mb-1 small">Filtrar por c\u00f3digo ou descri\u00e7\u00e3o</label>
          <input type="text" id="filtroItensPacote" class="form-control form-control-sm" placeholder="Digite c\u00f3digo ou parte da descri\u00e7\u00e3o">
        </div>
    `;

    if (data.status_carga !== 'despachado') {
      infoHTML += `
        <div>
          <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#criarPacoteModal" id='btnAbrirModalCriarPacote'>
            <i class="fas fa-plus me-2"></i>Criar Pacote
          </button>
        </div>
      `;
      
    }

    infoHTML += `</div>`; // fecha a div de linha
    
    modalBody.innerHTML = infoHTML;

    if (data.status_carga !== 'despachado') {
      // Busca o botão dentro do escopo do modal, que é mais eficiente
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

        // No botão que abre o modal:
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
        const itens = col.querySelectorAll('li.list-group-item');
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
      card.className = 'card mb-3 shadow-sm';
      card.style.height = '300px';  // Altura padrão
      card.style.display = 'flex';
      card.style.flexDirection = 'column';

      const header = document.createElement('div');
      header.className = 'card-header d-flex justify-content-between align-items-center py-2 px-3';
      const headerTitle = document.createElement('strong');
      headerTitle.className = 'text-truncate w-100';
      headerTitle.textContent = pacote.nome;

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
            Toast.fire({ icon: "success", title: dataResp?.mensagem || 'Pacote excluído.' });
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
      header.appendChild(headerTitle);
      header.appendChild(headerActions);

      // Flag de foto ao lado do nome do pacote
      // Ao clicar na flag deverá chamar uma função que trará as fotos em um modal

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

              // Atualiza estado do botão de exclusão conforme seleção
              const syncDeleteBtn = () => {
                const checados = modal.querySelectorAll('.foto-checkbox:checked');
                modal.querySelector('#btnExcluirFotosSelecionadas').disabled = checados.length === 0;
              };

              modal.addEventListener('change', (e) => {
                if (e.target.classList.contains('foto-checkbox')) syncDeleteBtn();
              });

              // Botão excluir fotos selecionadas
              modal.querySelector('#btnExcluirFotosSelecionadas').addEventListener('click', async () => {
                const checados = [...modal.querySelectorAll('.foto-checkbox:checked')];
                if (!checados.length) return;

                const qtd = checados.length;
                const confirmado = await Swal.fire({
                  title: 'Confirmar exclusão',
                  text: `Deseja excluir ${qtd} foto(s) selecionada(s)? Esta ação não pode ser desfeita.`,
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

                  Toast.fire({ icon: 'success', title: `${qtd} foto(s) excluída(s) com sucesso.` });

                  // Atualiza flag do botão "Ver foto" se não houver mais fotos
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
      body.className = 'card-body px-3 py-2';
      body.style.overflowY = 'auto';
      body.style.flex = '1';

      const dataCriacao = document.createElement('small');
      dataCriacao.className = 'text-muted d-block mb-2';
      dataCriacao.innerText = `Criado em: ${pacote.data_criacao}`;

      const lista = document.createElement('ul');
      lista.className = 'list-group list-group-flush';

      // Marque o card e a UL com o id do pacote para facilitar o update no DOM
      card.dataset.pacoteId = pacote.id;

      // const lista = document.createElement('ul');
      lista.className = 'list-group list-group-flush';
      lista.dataset.pacoteId = pacote.id;

      if (pacote.itens.length === 0) {
        const vazio = document.createElement('li');
        vazio.className = 'list-group-item text-muted';
        vazio.innerText = 'Nenhum item no pacote.';
        lista.appendChild(vazio);
      } else {
        pacote.itens.forEach((item, idx) => {
          const li = document.createElement('li');
          li.className = 'list-group-item d-flex justify-content-between align-items-start py-1';
          li.dataset.itemId = (item.id ?? idx);

          const info = document.createElement('div');
          info.className = 'me-2';
          info.innerHTML = `
            <div><strong>${item.codigo_peca}</strong> - ${item.descricao || ''}</div>
            <small class="text-muted quantidade-label">Qtde: <span class="quantidade-valor">${item.quantidade}</span></small>
          `;
          li.dataset.codigo = item.codigo_peca || '';
          li.dataset.descricao = item.descricao || '';

          // Botão "Alterar pacote"
          const btnAlterar = document.createElement('button');
          btnAlterar.type = 'button';
          btnAlterar.className = 'btn btn-outline-primary btn-sm flex-shrink-0';
          // btnAlterar.textContent = 'Alterar pacote';
          btnAlterar.innerHTML = '<i class="fas fa-exchange-alt"></i>'; // Ícone de troca
          btnAlterar.setAttribute('data-bs-toggle', 'modal');
          btnAlterar.setAttribute('data-bs-target', '#modalAlterarPacote');

          // Ao clicar, preenche o modal e lista os pacotes disponíveis
          btnAlterar.addEventListener('click', () => {
            // guarda referência do <li> atual para mover no DOM após sucesso
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
              opt.textContent = 'Não há outros pacotes';
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
          
          const podeEditarQtd = (data.status_carga === 'planejamento' || data.status_carga === 'verificacao');
          if (podeEditarQtd) {
            const quantidadeWrapper = document.createElement('div');
            quantidadeWrapper.className = 'd-flex align-items-center gap-1 mt-1';

            const inputQtd = document.createElement('input');
            inputQtd.type = 'number';
            inputQtd.min = '1';
            inputQtd.value = item.quantidade;
            inputQtd.className = 'form-control form-control-sm w-auto';

            const btnSalvarQtd = document.createElement('button');
            btnSalvarQtd.type = 'button';
            btnSalvarQtd.className = 'btn btn-outline-secondary btn-sm';
            btnSalvarQtd.innerHTML = '<i class=\"fas fa-save\"></i>';
            btnSalvarQtd.title = 'Atualizar quantidade do item';

            btnSalvarQtd.addEventListener('click', async () => {
              const novaQt = parseInt(inputQtd.value, 10);
              if (!novaQt || novaQt <= 0) {
                alert('Quantidade inválida.');
                return;
              }

              const prevText = btnSalvarQtd.innerHTML;
              btnSalvarQtd.disabled = true;
              btnSalvarQtd.innerHTML = '<span class=\"spinner-border spinner-border-sm\" role=\"status\" aria-hidden=\"true\"></span>';
              try {
                const resp = await fetch(`api/pacotes/itens/${item.id}/atualizar-quantidade/`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                  },
                  body: JSON.stringify({ quantidade: novaQt })
                });
                const dataResp = await resp.json().catch(() => ({}));
                if (!resp.ok) {
                  throw new Error(dataResp?.erro || 'Erro ao atualizar quantidade.');
                }
                const qVal = li.querySelector('.quantidade-valor');
                if (qVal) qVal.textContent = dataResp.nova_quantidade;
                inputQtd.value = dataResp.nova_quantidade;
              } catch (error) {
                alert(error.message || 'Erro ao atualizar quantidade.');
              } finally {
                btnSalvarQtd.disabled = false;
                btnSalvarQtd.innerHTML = prevText;
              }
            });

            quantidadeWrapper.appendChild(inputQtd);
            quantidadeWrapper.appendChild(btnSalvarQtd);
            info.appendChild(quantidadeWrapper);

            const btnExcluirItem = document.createElement('button');
            btnExcluirItem.type = 'button';
            btnExcluirItem.className = 'btn btn-outline-danger btn-sm';
            btnExcluirItem.innerHTML = '<i class="fas fa-trash"></i>';
            btnExcluirItem.addEventListener('click', async () => {
              const confirma = confirm('Remover esta peça do pacote? A quantidade voltará para a pendência.');
              if (!confirma) return;
              const prev = btnExcluirItem.innerHTML;
              btnExcluirItem.disabled = true;
              btnExcluirItem.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
              try {
                const resp = await fetch(`api/pacotes/itens/${item.id}/deletar/`, {
                  method: 'DELETE',
                  headers: { 'X-CSRFToken': getCookie('csrftoken') }
                });
                const dataResp = await resp.json().catch(() => ({}));
                if (!resp.ok) {
                  throw new Error(dataResp?.erro || 'Erro ao remover peça.');
                }
                li.remove();
                // se lista ficar vazia, mostra aviso
                if (!lista.querySelector('li')) {
                  const vazio = document.createElement('li');
                  vazio.className = 'list-group-item text-muted';
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
            quantidadeWrapper.appendChild(btnExcluirItem);
          }

          if (data.status_carga === 'planejamento' && pacote.status_expedicao !== 'ok') {
            li.appendChild(btnAlterar);
          } else if (data.status_carga === 'verificacao' && pacote.status_qualidade !== 'ok') {
            li.appendChild(btnAlterar);
          };

          lista.appendChild(li);
        });
      }

      // Botão Confirmar APONTAMENTO
      const btnConfirmarExpedicao = document.createElement('button');
      btnConfirmarExpedicao.className = 'btn btn-outline-success btn-sm mt-2 w-100';
      btnConfirmarExpedicao.textContent = 'Confirmar (Expedição)';
      btnConfirmarExpedicao.setAttribute('data-bs-toggle', 'modal');
      btnConfirmarExpedicao.setAttribute('data-bs-target', '#modalConfirmarPacote');
      btnConfirmarExpedicao.setAttribute('data-id-pacote', pacote.id);

      // Passa o ID do pacote para o modal ao clicar
      btnConfirmarExpedicao.addEventListener('click', () => {
        document.getElementById('idPacoteConfirmar').value = pacote.id;
        document.getElementById('obsConfirmarPacote').value = '';  // limpa campo
      });

      // Botão Confirmar QUALIDADE
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
      footer.className = 'card-footer d-flex flex-column gap-2';

      // Botão de adicionar foto
      const btnFoto = document.createElement('button');
      btnFoto.className = 'btn btn-outline-secondary btn-sm';
      btnFoto.innerHTML = '<i class="fas fa-camera"></i>';
      btnFoto.title = "Adicionar foto";
      btnFoto.onclick = () => {
        // Cria input de arquivo invisível
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.capture = 'environment';  // força uso da câmera no celular
        input.style.display = 'none';

        // Ao selecionar ou tirar a foto
        input.onchange = () => {
          const file = input.files[0];
          if (!file) return;

          const previewURL = URL.createObjectURL(file);

          // Cria modal para confirmação
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
                  <img src="${previewURL}" alt="Prévia" class="img-fluid rounded mb-3" />
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
            
            const btn = e.currentTarget;   // referência ao próprio botão
            btn.innerHTML = 'Confirmando...';
            btn.disabled = true;

            // Aqui você envia para o backend via fetch/axios/FormData
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
        };

        // Aciona o input
        document.body.appendChild(input);
        input.click();
      };

      // Botão de imprimir
      const btnPrint = document.createElement('button');
      btnPrint.className = 'btn btn-outline-secondary btn-sm';
      btnPrint.innerHTML = '<i class="fas fa-print"></i>';
      btnPrint.title = "Imprimir";
      btnPrint.onclick = () => {
        // lógica para impressão
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

        footer.appendChild(btnGroup);

      } else if (data.status_carga === 'verificacao' && pacote.status_qualidade === 'ok') {
        const span = document.createElement('span');
        span.className = 'text-success fw-bold text-center ms-2';
        span.textContent = 'Pacote confirmado';

        btnGroup.appendChild(span);
        btnGroup.appendChild(btnPrint);
        btnGroup.appendChild(btnFoto);

        footer.appendChild(btnGroup);
      }

      if (data.status_carga === 'despachado' && pacote.status_qualidade === 'ok') {

        // Confirmar Qualidade
        // btnConfirmarQualidade.className = 'btn btn-outline-success btn-sm flex-grow-1';
        // btnGroup.appendChild(btnConfirmarQualidade);

        // btnGroup.appendChild(btnPrint);
        btnGroup.appendChild(btnFoto);

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

    // botão de submit em loading
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

      // Atualiza DOM localmente (move o <li> para a lista do pacote destino)
      if (window._editingItemLi) {
        const cardsContainer = document.getElementById('cardsContainer') || document; // ajuste se seu container tiver id
        const ulDestino = cardsContainer.querySelector(`ul.list-group[data-pacote-id="${destinoId}"]`);
        if (ulDestino) {
          // remove aviso "Nenhum item..." se existir
          const vazio = ulDestino.querySelector('.list-group-item.text-muted');
          if (vazio) vazio.remove();

          ulDestino.appendChild(window._editingItemLi);
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
