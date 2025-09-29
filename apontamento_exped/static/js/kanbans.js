import { popularPacotesDaCarga, wireModalAlterarPacote } from './carregar_cargas.js';
import { getCookie } from './criar_caixa.js';

// Cache simples para não bombardear a API ao renderizar vários cards
const _pendenciasCache = new Map();

function mapStage(carga) {
  // se já vier "estagio" do backend, use direto:
  if (carga.stage) return carga.stage.toLowerCase(); 
  // fallback pelo status (ajuste se quiser):
  const s = (carga.stage || '').toLowerCase();
  if (['planejamento', 'novo', 'pendente'].includes(s)) return 'planejamento';
  if (['verificacao', 'revisao', 'erro'].includes(s)) return 'verificacao';
  if (['despachado', 'entregue', 'finalizado'].includes(s)) return 'despachado';
  return 'planejamento';
}

/**
 * Consulta a API e retorna o número total de itens pendentes (int).
 * Se houver erro, retorna null (para não travar a UI).
 */
export async function verificarPendencias(carregamentoId) {
  if (!carregamentoId) return null;

  if (_pendenciasCache.has(carregamentoId)) {
    return _pendenciasCache.get(carregamentoId);
  }

  try {
    const resp = await fetch(`api/verificar-pendencias/${encodeURIComponent(carregamentoId)}/`, {
      headers: { 'Accept': 'application/json' }
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    const total = Number(data?.total_itens_pendente ?? 0);
    _pendenciasCache.set(carregamentoId, total);
    return total;
  } catch (e) {
    console.error('Falha ao verificar pendências:', e);
    return null;
  }
}

/**
 * Cria o botão "Avançar estágio" com os mesmos atributos que você já usava
 * e conecta o listener de abertura do modal.
 */
function criarBotaoAvancar(cargaId) {
  const btn = document.createElement('button');
  btn.className = 'btn btn-sm btn-outline-primary avancar-estagio';
  btn.title = 'Proximo estágio';
  btn.setAttribute('data-bs-toggle', 'modal');
  btn.setAttribute('data-bs-target', '#modalAvancarEstagio');
  btn.setAttribute('data-id-carga', String(cargaId));
  btn.innerHTML = `<i class="fas fa-arrow-right ms-1"></i>`;

  // listener para abrir modal de avançar estágio (mantido)
  btn.addEventListener('click', function () {
    const cargaId = this.getAttribute('data-id-carga');
    const hidden = document.getElementById('idCargaPacote');
    if (hidden) hidden.value = cargaId;
    const modalTitle = document.querySelector('#modalAvancarEstagio .modal-title');
    if (modalTitle) modalTitle.textContent = `Avançar estágio #${cargaId}`;
    document.getElementById('idItemAvancar').value = cargaId;
  });

  return btn;
}

/**
 * Decide o que renderizar no "slot" do botão/alerta com base no estágio e nas pendências.
 * - Para estágio 'planejamento': busca pendências e decide entre ALERTA x BOTÃO.
 * - Demais estágios: mantém sua lógica original.
 */
export async function preencherSlotAvancar(carga, slotEl) {
  // Limpa o slot
  slotEl.innerHTML = '';

  if (carga.stage === 'planejamento') {

    const totalPend = await verificarPendencias(carga.id);

    // Se a API falhar, por segurança não avança automaticamente
    if (totalPend === null) {
      const warn = document.createElement('div');
      warn.className = 'alert alert-secondary mb-0 py-1 px-2 small';
      warn.textContent = 'Não foi possível verificar pendências.';
      slotEl.replaceChildren(warn);
      return;
    }

    if (totalPend > 0) {
      // ALERTA no lugar do botão
      const warn = document.createElement('div');
      warn.className = 'alert alert-warning mb-0 py-1 px-2 small';
      warn.textContent = '';
      warn.textContent = `Contém ${totalPend} item(ns) sem pacotes.`;
      slotEl.replaceChildren(warn);
    } else {
      // Sem pendências -> renderiza o botão
      slotEl.replaceChildren(criarBotaoAvancar(carga.id));
    }

    return;
  }

  // --- Demais estágios: mantém sua lógica
  if (carga.stage === 'verificacao' && carga.todos_pacotes_tem_foto_verificacao) {
    slotEl.replaceChildren(criarBotaoAvancar(carga.id));
  } else if (carga.stage === 'planejamento') {
    // (fallback: se chegar aqui por algum motivo, mantém botão)
    slotEl.replaceChildren(criarBotaoAvancar(carga.id));
  } else if (carga.stage === 'despachado' && carga.todos_pacotes_tem_foto_despachado) {
    const ok = document.createElement('span');
    ok.className = 'badge bg-success';
    ok.textContent = 'Despachado';
    slotEl.replaceChildren(ok);
  } else {
    const pend = document.createElement('span');
    pend.className = 'badge bg-warning';
    pend.textContent = 'Aguardando fotos';
    slotEl.replaceChildren(pend);
  }
}

/**
 * Cria o card do Kanban.
 * Observação: o "slot" do avançar é preenchido depois (assíncrono),
 * para permitir a chamada na API de pendências sem travar a renderização.
 */
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

  // Corpo do card com um "slot" onde o botão/alerta será colocado
  const body = document.createElement('div');
  body.className = 'card-body py-2';
  body.innerHTML = `
    <div class="small text-muted mb-1">Dt. Carga: ${formatarData(carga.data_carga)}</div>
    <div class="small text-muted">${carga.cliente}</div>
    <div class="mt-2 d-flex gap-2 align-items-start">
      <button class="btn btn-sm btn-outline-primary ver-pacotes" title="Ver pacotes"
              data-bs-toggle="modal" data-bs-target="#visualizarPacote" data-id-carga="${carga.id}">
        <i class="fas fa-box"></i>
      </button>
      <span class="slot-avancar d-inline-flex"></span>
    </div>
  `;

  // Evento: abrir modal de pacotes (mantido)
  body.querySelector('.ver-pacotes').addEventListener('click', function () {
    const cargaId = this.getAttribute('data-id-carga');
    const hidden = document.getElementById('idCargaPacote');
    if (hidden) hidden.value = cargaId;
    const modalTitle = document.querySelector('#visualizarPacote .modal-title');
    if (modalTitle) modalTitle.textContent = `Pacotes da carga #${cargaId}`;
    popularPacotesDaCarga(cargaId);
  });

  // Preencher o slot do avançar (botão/alerta) de forma assíncrona
  const slotAvancar = body.querySelector('.slot-avancar');
  preencherSlotAvancar(carga, slotAvancar);

  // Drag events (mantidos)
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

export async function carregarCargasKanban() {
  const colPlanej = document.getElementById('col-planejamento');
  const colVerif  = document.getElementById('col-verificacao');
  const colDesp   = document.getElementById('col-despachado');

  // estados de carregamento
  [colPlanej, colVerif, colDesp].forEach(col => {
    col.innerHTML = '<div class="text-muted small">Carregando...</div>';
  });

  try {
    const resp = await fetch('api/buscar-cargas/'); // note a barra inicial
    if (!resp.ok) throw new Error('Erro ao buscar cargas');
    const cargas = await resp.json();

    // limpar colunas
    [colPlanej, colVerif, colDesp].forEach(col => col.innerHTML = '');

    if (!Array.isArray(cargas) || cargas.length === 0) {
      [colPlanej, colVerif, colDesp].forEach(col => {
        col.innerHTML = '<div class="text-muted small">Sem cargas</div>';
      });
      return;
    }

    cargas.forEach((carga) => {
      const stage = mapStage(carga);
      const card  = createKanbanCard(carga); // cria card com .slot-avancar

      // escolhe coluna
      let targetCol = colPlanej;
      if (stage === 'verificacao') targetCol = colVerif;
      else if (stage === 'despachado')  targetCol = colDesp;

      // insere o card na coluna
      targetCol.appendChild(card);

      // >>> CHAMAR A VERIFICAÇÃO *APÓS* MONTAR O CARD <<<
      const slot = card.querySelector('.slot-avancar');
      if (slot) {
        // não bloqueia a UI — roda async
        preencherSlotAvancar(carga, slot);
      }
    });

  } catch (err) {
    console.error(err);
    [colPlanej, colApont, colVerif, colDesp].forEach(col => {
      col.innerHTML = '<div class="text-danger small">Erro ao carregar</div>';
    });
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