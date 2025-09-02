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

    if (data.status_carga !== 'despachado'){
      modalBody.innerHTML = `
      <div class="text-end">
        <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#criarPacoteModal">
          <i class="fas fa-plus me-2"></i>Criar Pacote
        </button>
      </div>
      `;
    };

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

      // Botão Confirmar
      const btnConfirmar = document.createElement('button');
      btnConfirmar.className = 'btn btn-outline-success btn-sm mt-2 w-100';
      btnConfirmar.textContent = 'Confirmar Pacote';
      btnConfirmar.setAttribute('data-bs-toggle', 'modal');
      btnConfirmar.setAttribute('data-bs-target', '#modalConfirmarPacote');
      btnConfirmar.setAttribute('data-id-pacote', pacote.id);

      // Passa o ID do pacote para o modal ao clicar
      btnConfirmar.addEventListener('click', () => {
        document.getElementById('idPacoteConfirmar').value = pacote.id;
        document.getElementById('observacaoPacote').value = '';  // limpa campo
      });

      console.log(pacote);

      body.appendChild(dataCriacao);
      body.appendChild(lista);
      if (data.status_carga === 'apontamento' && pacote.status !== 'ok') {
        body.appendChild(btnConfirmar);
      };

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




