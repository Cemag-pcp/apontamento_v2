import { getCookie } from './criar_caixa.js';

export async function popularPacotesDaCarga(cargaId) {
  const modal = document.getElementById('visualizarPacote');
  const modalBody = modal.querySelector('.modal-body');

  // Zera o conteúdo antes de popular
  modalBody.innerHTML = '';

  const cardsContainer = document.createElement('div');
  cardsContainer.classList.add('row', 'mt-3', 'gx-3');

  try {
    const response = await fetch(`api/buscar-pacote/${cargaId}/`);
    const data = await response.json();

    let infoHTML = `
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <strong>Cliente:</strong> ${data.cliente_carga} |
          <strong>Dt. Carga:</strong> ${data.data_carga} |
          <strong>Carga:</strong> ${data.carga}
        </div>
    `;

    // Só adiciona o botão se não estiver despachado
    if (data.status_carga !== 'despachado') {
      infoHTML += `
        <div>
          <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#criarPacoteModal">
            <i class="fas fa-plus me-2"></i>Criar Pacote
          </button>
        </div>
      `;
    }

    infoHTML += `</div>`; // fecha a div de linha
    
    modalBody.innerHTML = infoHTML;

    if (!data.pacotes || data.pacotes.length === 0) {
      modalBody.appendChild(document.createElement('hr'));
      const noData = document.createElement('p');
      noData.textContent = 'Nenhum pacote encontrado para esta carga.';
      noData.classList.add('text-muted', 'mt-3');
      modalBody.appendChild(noData);
      return;
    }
    
    data.pacotes.forEach(pacote => {

      const col = document.createElement('div');
      col.className = 'col-md-4 col-sm-6';  // 3 colunas em md+, 2 em sm

      const card = document.createElement('div');
      card.className = 'card mb-3 shadow-sm';
      card.style.height = '300px';  // Altura padrão
      card.style.display = 'flex';
      card.style.flexDirection = 'column';

      const header = document.createElement('div');
      header.className = 'card-header d-flex justify-content-between align-items-center py-2 px-3';
      header.innerHTML = `<strong class="text-truncate w-100">${pacote.nome}</strong>`;

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
            <small class="text-muted">Cor: ${item.cor || 'N/A'} | Qtde: ${item.quantidade}</small>
          `;

          // Botão "Alterar pacote"
          const btnAlterar = document.createElement('button');
          btnAlterar.type = 'button';
          btnAlterar.className = 'btn btn-outline-primary btn-sm flex-shrink-0';
          btnAlterar.textContent = 'Alterar pacote';
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
          
          // mesma regra de visibilidade do botão Confirmar (apenas em "apontamento" e pacote != ok)
          if (data.status_carga === 'apontamento' && pacote.status_expedicao !== 'ok') {
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

      // adiciona botões conforme status
      if (data.status_carga === 'apontamento' && pacote.status_expedicao !== 'ok') {
        footer.appendChild(btnConfirmarExpedicao);
      } else if (data.status_carga === 'apontamento' && pacote.status_expedicao === 'ok') {
        const span = document.createElement('span');
        span.className = 'text-success fw-bold text-center';
        span.textContent = 'Pacote confirmado';
        footer.appendChild(span);
      }

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
              alert('Foto salva com sucesso!');

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
      btnGroup.className = 'd-flex gap-2 justify-content-between';

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

        btnGroup.appendChild(btnPrint);
        btnGroup.appendChild(btnFoto);
        btnGroup.appendChild(span);   // ✅ span junto com os botões

        footer.appendChild(btnGroup);
      }

      if (data.status_carga === 'despachado' && pacote.status_qualidade !== 'ok') {

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