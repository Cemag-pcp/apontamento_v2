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

          console.log("Abrindo modal para carga:", cargaId);
        });

        tabela.appendChild(tr);
    });

  } catch (err) {
    console.error(err);
    tabela.innerHTML = '<tr><td colspan="7" class="text-danger">Erro ao carregar cargas.</td></tr>';
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
