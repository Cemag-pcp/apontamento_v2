document.addEventListener('DOMContentLoaded', function () {

    carregarCargas();

});


async function carregarCargas() {
  const tabela = document.querySelector('#tabelaExpedicoes tbody');
  tabela.innerHTML = '<tr><td colspan="7">Carregando...</td></tr>';

  try {
    const response = await fetch('api/buscar-cargas/');
    if (!response.ok) throw new Error('Erro ao buscar cargas');

    const cargas = await response.json();

    if (cargas.length === 0) {
      tabela.innerHTML = '<tr><td colspan="7" class="text-muted">Nenhuma carga encontrada.</td></tr>';
      return;
    }

    // Mapeia status para badge
    const badgeMap = {
      entregue: 'bg-success',
      pendente: 'bg-warning text-dark',
      erro: 'bg-danger',
    };

    tabela.innerHTML = '';

    cargas.forEach(carga => {
    
        const badgeClass = badgeMap[carga.status?.toLowerCase()] || 'bg-secondary';

        const tr = document.createElement('tr');

        tr.innerHTML = `
            <td>#${carga.id}</td>
            <td>${formatarData(carga.data_carga)}</td>
            <td>${carga.carga}</td>
            <td>${carga.nome}</td>
            <td>${carga.cliente}</td>
            <td><span class="badge ${badgeClass} status-badge">${capitalizar(carga.status)}</span></td>
            <td>
            <button class="btn btn-sm btn-outline-primary" title="Ver pacotes"
                    data-bs-toggle="modal" data-bs-target="#visualizarPacote"
                    data-id-carga="${carga.id}">
                <i class="fas fa-box"></i>
            </button>
            </td>

        `;

        const verPacotesBtn = tr.querySelector('button');
        verPacotesBtn.addEventListener('click', function () {
          const cargaId = this.getAttribute('data-id-carga');

          // atualiza o campo hidden no modal CriarPacote
          document.getElementById('idCargaPacote').value = cargaId;

          // se quiser também atualizar título do modal
          const modalTitle = document.querySelector('#visualizarPacote .modal-title');
          if (modalTitle) {
            modalTitle.textContent = `Pacotes da carga #${cargaId}`;
          }

          popularPacotesDaCarga(cargaId);

        });

        tabela.appendChild(tr);
    });

  } catch (err) {
    console.error(err);
    tabela.innerHTML = '<tr><td colspan="7" class="text-danger">Erro ao carregar cargas.</td></tr>';
  }
}

async function popularPacotesDaCarga(cargaId) {
  const modal = document.getElementById('visualizarPacote');
  const modalBody = modal.querySelector('.modal-body');

  // Zera o conteúdo antes de popular
  modalBody.innerHTML = `
    <div class="text-end">
      <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#criarPacoteModal">
        <i class="fas fa-plus me-2"></i>Criar Pacote
      </button>
    </div>
  `;

  const cardsContainer = document.createElement('div');
  cardsContainer.classList.add('row', 'mt-3', 'gx-3');

  try {
    const response = await fetch(`api/buscar-pacote/${cargaId}/`);
    const data = await response.json();

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

      if (pacote.itens.length === 0) {
        const vazio = document.createElement('li');
        vazio.className = 'list-group-item text-muted';
        vazio.innerText = 'Nenhum item no pacote.';
        lista.appendChild(vazio);
      } else {
        pacote.itens.forEach(item => {
          const li = document.createElement('li');
          li.className = 'list-group-item py-1';
          li.innerHTML = `
            <div><strong>${item.codigo_peca}</strong> - ${item.descricao || ''}</div>
            <small class="text-muted">Cor: ${item.cor || 'N/A'} | Qtde: ${item.quantidade}</small>
          `;
          lista.appendChild(li);
        });
      }

      body.appendChild(dataCriacao);
      body.appendChild(lista);
      card.appendChild(header);
      card.appendChild(body);
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

// util: converter '2025-08-27' → '27/08/2025'
function formatarData(iso) {
  if (!iso) return '';
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

// util: deixar a primeira letra maiúscula
function capitalizar(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}
