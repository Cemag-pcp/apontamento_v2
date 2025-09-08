import { popularPacotesDaCarga, wireModalAlterarPacote } from './carregar_cargas.js';
import { getCookie } from './criar_caixa.js';

function mapStage(carga) {
  // se já vier "estagio" do backend, use direto:
  if (carga.stage) return carga.stage.toLowerCase(); 
  // fallback pelo status (ajuste se quiser):
  const s = (carga.stage || '').toLowerCase();
  if (['planejamento', 'novo', 'pendente'].includes(s)) return 'planejamento';
  if (['apontamento', 'andamento'].includes(s)) return 'apontamento';
  if (['verificacao', 'revisao', 'erro'].includes(s)) return 'verificacao';
  if (['despachado', 'entregue', 'finalizado'].includes(s)) return 'despachado';
  return 'planejamento';
}

function createKanbanCard(carga) {
  
    const card = document.createElement('div');
    card.className = 'card card-kanban shadow-sm mb-2';
    card.draggable = true;
    card.dataset.id = carga.id;

    const header = document.createElement('div');
    header.className = 'card-header py-1 d-flex justify-content-between align-items-center';
    header.innerHTML = `
        <span class="fw-semibold text-truncate">#${carga.id} • ${carga.carga}</span>
    `;
    
    let btnElementAvancarEstagio = '';
    console.log(carga)
    if (carga.stage === 'verificacao' && carga.todos_pacotes_tem_foto_verificacao) {
        btnElementAvancarEstagio =`
        <button class="btn btn-sm btn-outline-primary avancar-estagio" title="Proximo estágio"
                data-bs-toggle="modal" data-bs-target="#modalAvancarEstagio" data-id-carga="${carga.id}">
            <i class="fas fa-arrow-right ms-1"></i>
        </button>
        `
    } else if (carga.stage === 'apontamento') {
        btnElementAvancarEstagio =`
        <button class="btn btn-sm btn-outline-primary avancar-estagio" title="Proximo estágio"
                data-bs-toggle="modal" data-bs-target="#modalAvancarEstagio" data-id-carga="${carga.id}">
            <i class="fas fa-arrow-right ms-1"></i>
        </button>
        `
    } else if (carga.stage === 'despachado' && carga.todos_pacotes_tem_foto_despachado) {
        btnElementAvancarEstagio =`
        <span class="badge bg-success">Despachado</span>`
    } else {
        btnElementAvancarEstagio = '<span class="badge bg-warning">Aguardando fotos</span>';
    }

    const body = document.createElement('div');
    body.className = 'card-body py-2';
    body.innerHTML = `
        <div class="small text-muted mb-1">Dt. Carga: ${formatarData(carga.data_carga)}</div>
        <div class="small text-muted">${carga.cliente}</div>
        <div class="mt-2 d-flex gap-2">
        <button class="btn btn-sm btn-outline-primary ver-pacotes" title="Ver pacotes"
                data-bs-toggle="modal" data-bs-target="#visualizarPacote" data-id-carga="${carga.id}">
            <i class="fas fa-box"></i>
        </button>
        ${btnElementAvancarEstagio}
        </div>
    `;

    // evento para abrir modal de pacotes
    body.querySelector('.ver-pacotes').addEventListener('click', function () {
        const cargaId = this.getAttribute('data-id-carga');
        // atualiza hidden do "criar pacote"
        const hidden = document.getElementById('idCargaPacote');
        if (hidden) hidden.value = cargaId;
        // título do modal
        const modalTitle = document.querySelector('#visualizarPacote .modal-title');
        if (modalTitle) modalTitle.textContent = `Pacotes da carga #${cargaId}`;
        // carrega os pacotes
        popularPacotesDaCarga(cargaId);
    });

    const btnAvancar = body.querySelector('.avancar-estagio');
    if (btnAvancar) {
        // evento para abrir modal de avançar estágio
        body.querySelector('.avancar-estagio').addEventListener('click', function () {
            const cargaId = this.getAttribute('data-id-carga');
            // atualiza hidden do "criar pacote"
            const hidden = document.getElementById('idCargaPacote');
            if (hidden) hidden.value = cargaId;
            // título do modal
            const modalTitle = document.querySelector('#modalAvancarEstagio .modal-title');
            if (modalTitle) modalTitle.textContent = `Avançar estágio #${cargaId}`;
            document.getElementById('idItemAvancar').value = cargaId;

        });
    };

    // Drag events
    card.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', String(carga.id));
        e.dataTransfer.effectAllowed = 'move';
        card.classList.add('opacity-50');
    });
    card.addEventListener('dragend', () => card.classList.remove('opacity-50'));

    card.appendChild(header);
    card.appendChild(body);
    return card;
}

document.getElementById('formAvancarEstagio').addEventListener('submit', async function(e) {
    e.preventDefault();

    const id = document.getElementById('idItemAvancar').value;

    const btnConfirmarAvanco = document.getElementById('btnConfirmarAvanco');
    btnConfirmarAvanco.disabled = true;
    btnConfirmarAvanco.innerHTML = 'Confirmando...';

    try {
        const resp = await fetch(`api/alterar-stage/${id}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
            body: JSON.stringify({ stage: '' })
        });
        console.log(resp);
        if (!resp.ok) throw new Error('Falha ao avançar estágio');

        bootstrap.Modal.getInstance(document.getElementById('modalAvancarEstagio')).hide();
        carregarCargasKanban();

        btnConfirmarAvanco.disabled = false;
        btnConfirmarAvanco.innerHTML = 'Confirmar avanço';

      } catch (err) {
        alert('Erro ao avançar estágio.');
        btnConfirmarAvanco.disabled = false;
        btnConfirmarAvanco.innerHTML = 'Confirmar avanço';
        console.error(err);
    }
});

function setupDropZones() {
  document.querySelectorAll('.kanban-list').forEach(list => {
    list.addEventListener('dragover', (e) => {
      e.preventDefault();
      list.classList.add('drag-over');
    });
    list.addEventListener('dragleave', () => list.classList.remove('drag-over'));
    list.addEventListener('drop', async (e) => {
      e.preventDefault();
      list.classList.remove('drag-over');
      const cardId = e.dataTransfer.getData('text/plain');
      const card = document.querySelector(`.card-kanban[data-id="${cardId}"]`);
      if (!card) return;

      list.prepend(card); // move visualmente
      const newStage = list.parentElement.dataset.stage; // pega o estágio da coluna
      // atualiza no backend (ajuste URL se necessário)
      try {
        await fetch(`api/alterar-stage/${cardId}/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
          },
          body: JSON.stringify({ stage: newStage })
        });
      } catch (err) {
        console.error('Falha ao atualizar estágio:', err);
      }
    });
  });
}

async function carregarCargasKanban() {
  const colPlanej   = document.getElementById('col-planejamento');
  const colApont    = document.getElementById('col-apontamento');
  const colVerif    = document.getElementById('col-verificacao');
  const colDesp     = document.getElementById('col-despachado');

  // limpa colunas
  [colPlanej, colApont, colVerif, colDesp].forEach(col => col.innerHTML = '<div class="text-muted small">Carregando...</div>');

  try {
    const resp = await fetch('api/buscar-cargas/');
    if (!resp.ok) throw new Error('Erro ao buscar cargas');
    const cargas = await resp.json();

    // limpa para receber cards
    [colPlanej, colApont, colVerif, colDesp].forEach(col => col.innerHTML = '');

    if (!Array.isArray(cargas) || cargas.length === 0) {
      [colPlanej, colApont, colVerif, colDesp].forEach(col => col.innerHTML = '<div class="text-muted small">Sem cargas</div>');
      return;
    }

    cargas.forEach(carga => {
      const stage = mapStage(carga);
      const card = createKanbanCard(carga);
      if (stage === 'planejamento') colPlanej.appendChild(card);
      else if (stage === 'apontamento') colApont.appendChild(card);
      else if (stage === 'verificacao') colVerif.appendChild(card);
      else if (stage === 'despachado') colDesp.appendChild(card);
      else colPlanej.appendChild(card);
    });

  } catch (err) {
    console.error(err);
    [colPlanej, colApont, colVerif, colDesp].forEach(col => col.innerHTML = '<div class="text-danger small">Erro ao carregar</div>');
  }
}

// util: converter '2025-08-27' → '27/08/2025'
function formatarData(iso) {
  if (!iso) return '';
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

document.addEventListener('DOMContentLoaded', () => {
  // setupDropZones();
  wireModalAlterarPacote();
  carregarCargasKanban();
  document.getElementById('btnRefreshKanban')?.addEventListener('click', carregarCargasKanban);
});