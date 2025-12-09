import { popularPacotesDaCarga, wireModalAlterarPacote } from './carregar_cargas.js';
import { getCookie } from './criar_caixa.js';
import { renderStatusCarretas } from './verificar_carretas.js'

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

async function excluirCarregamento(cargaId, cardEl) {
  try {
    const resp = await fetch(`api/excluir-carga/${encodeURIComponent(cargaId)}/`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
      },
    });

    if (!resp.ok) {
      const msg = await resp.text();
      throw new Error(msg || 'Erro ao excluir carregamento');
    }

    cardEl?.remove();
  } catch (error) {
    console.error('Falha ao excluir carregamento:', error);
    alert(error);
  }
}

/**
 * Consulta a API e retorna o número total de itens pendentes (int).
 * Se houver erro, retorna null (para não travar a UI).
 */
export async function verificarPendencias(carregamentoId) {
  if (!carregamentoId) return null;

  try {
    const resp = await fetch(`api/verificar-pendencias/${encodeURIComponent(carregamentoId)}/`, {
      headers: { 'Accept': 'application/json' }
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    const total = Number(data?.total_itens_pendente ?? 0);
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
export function criarBotaoAvancar(cargaId) {
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
    // container horizontal para botão + avisos
    const row = document.createElement('div');
    row.className = 'd-flex align-items-center gap-2';

    // botão sempre presente
    const btn = criarBotaoAvancar(carga.id);
    row.appendChild(btn);

    // verificar pendências
    let totalPend = null;
    try {
      totalPend = await verificarPendencias(carga.id);
    } catch (_) {
      totalPend = null;
    }

    const pend = (totalPend === null || totalPend === undefined) ? null : Number(totalPend);

    if (pend === null) {
      const warn = document.createElement('div');
      warn.className = 'alert alert-secondary mb-0 py-1 px-2 small';
      warn.textContent = 'Não foi possível verificar pendências.';
      row.appendChild(warn);
    } else if (pend > 0) {
      const warn = document.createElement('div');
      warn.className = 'alert alert-warning mb-0 py-1 px-2 small';
      warn.textContent = `Contém ${pend} item(ns) sem pacotes.`;
      row.appendChild(warn);
    }

    slotEl.replaceChildren(row);
    return;
  }

  // --- Demais estágios ---
  if (carga.stage === 'verificacao' && carga.todos_pacotes_tem_foto_verificacao) {
    // Verificação ok -> botão avançar
    slotEl.replaceChildren(criarBotaoAvancar(carga.id));
  } else if (carga.stage === 'despachado' && carga.todos_pacotes_tem_foto_despachado) {
    // Despachado -> badge OK
    const ok = document.createElement('span');
    ok.className = 'badge bg-success';
    ok.textContent = 'Despachado';
    slotEl.replaceChildren(ok);
  } else {
    // Aguardando fotos -> badge + (novo) warning de pendências ao lado
    const row = document.createElement('div');
    row.className = 'd-flex align-items-center gap-2';

    const pendBadge = document.createElement('span');
    pendBadge.className = 'badge bg-warning';
    pendBadge.textContent = 'Aguardando fotos';
    row.appendChild(pendBadge);

    // buscar pendências para exibir ao lado
    let totalPend = null;
    try {
      totalPend = await verificarPendencias(carga.id);
    } catch (_) {
      totalPend = null;
    }
    const pend = (totalPend === null || totalPend === undefined) ? null : Number(totalPend);

    if (pend === null) {
      const warn = document.createElement('div');
      warn.className = 'alert alert-secondary mb-0 py-1 px-2 small';
      warn.textContent = 'Não foi possível verificar pendências.';
      row.appendChild(warn);
    } else if (pend > 0) {
      const warn = document.createElement('div');
      warn.className = 'alert alert-warning mb-0 py-1 px-2 small';
      warn.textContent = `Contém ${pend} item(ns) sem pacotes.`;
      row.appendChild(warn);
    }
    // se pend === 0, não mostra o warning (fica só o badge)

    slotEl.replaceChildren(row);
  }
}

export async function atualizarSlotAvancar(dataId, todas_fotos_verificacao, etapa_atual) {
  // acha o card/slot
  const card = document.querySelector(`.card[data-id='${dataId}']`);
  if (!card) return;
  const slotEl = card.querySelector('.slot-avancar');
  if (!slotEl) return;

  // container horizontal para botão + aviso
  const row = document.createElement('div');
  row.className = 'd-flex align-items-center gap-2';

  if (etapa_atual === 'verificacao' && todas_fotos_verificacao){
    const btn = criarBotaoAvancar(dataId);
    row.appendChild(btn);

  } else if (etapa_atual === 'planejamento') {
    const btn = criarBotaoAvancar(dataId);
    row.appendChild(btn);
  }

  const pendBadge = document.createElement('span');
  pendBadge.innerHTML = '';
  
  if (!todas_fotos_verificacao){
    pendBadge.className = 'badge bg-warning';
    pendBadge.textContent = 'Aguardando fotos';
    row.appendChild(pendBadge);
  }

  // busca pendências
  let totalPend = null;
  try {
    totalPend = await verificarPendencias(dataId);
  } catch (_) {
    totalPend = null;
  }

  // normaliza para número
  const pend = (totalPend === null || totalPend === undefined) ? null : Number(totalPend);

  // adiciona aviso à direita do botão (quando aplicável)
  if (pend === null) {
    const note = document.createElement('span');
    note.className = 'badge rounded-pill bg-secondary';
    note.title = 'Não foi possível verificar pendências agora';
    note.textContent = 'indefinido';
    row.appendChild(note);
  } else if (pend > 0) {
    // ALERTA (texto) como antes
    const warn = document.createElement('div');
    warn.className = 'alert alert-warning mb-0 py-1 px-2 small';
    warn.textContent = `Contém ${pend} item(ns) sem pacotes.`;
    row.appendChild(warn);
  }
  // se pend === 0, não mostra nada além do botão

  // !!! Um único replaceChildren no final (não sobrescreve o aviso)
  slotEl.replaceChildren(row);

  console.log('alterado com sucesso', pend);
}

/**
 * Cria o card do Kanban.
 * Observação: o "slot" do avançar é preenchido depois (assíncrono),
 * para permitir a chamada na API de pendências sem travar a renderização.
 */
export function createKanbanCard(carga) {
  
  const card = document.createElement('div');
  card.className = 'card card-kanban shadow-sm mb-2';
  card.draggable = true;
  
  console.log(carga);

  card.dataset.id = carga.id;
  card.dataset.stage = (carga.stage || '').toLowerCase();
  card.dataset.cliente = (carga.cliente || '').toLowerCase();
  card.dataset.dataCarga = (carga.data_carga || ''); // formato YYYY-MM-DD

  const header = document.createElement('div');
  header.className = 'card-header py-1 d-flex justify-content-between align-items-center';
  const title = document.createElement('span');
  title.className = 'fw-semibold text-truncate';
  title.textContent = `#${carga.id} - ${carga.carga}`;

  const actions = document.createElement('div');
  actions.className = 'd-flex align-items-center gap-2';

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn btn-sm btn-outline-danger';
  deleteBtn.title = 'Excluir carregamento';
  deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
  deleteBtn.addEventListener('click', async () => {
    const confirmou = confirm('Deseja excluir este carregamento e todos os seus pacotes?');
    if (!confirmou) return;
    deleteBtn.disabled = true;
    deleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    try {
      await excluirCarregamento(carga.id, card);
    } finally {
      if (document.body.contains(deleteBtn)) {
        deleteBtn.disabled = false;
        deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
      }
    }
  });

  actions.appendChild(deleteBtn);
  header.appendChild(title);
  header.appendChild(actions);

  // Corpo do card com um "slot" onde o botao/alerta sera colocado
  const body = document.createElement('div');

  body.className = 'card-body py-2';
  body.innerHTML = `
    <div class="small text-muted mb-1">
      Dt. Carga: ${formatarData(carga.data_carga)}
      <span class="status-carretas align-middle ms-2"></span>
      <span class="status-por-carreta align-middle ms-2"></span>
    </div>
    <div class="small text-muted">${carga.cliente}</div>
    <div class="mt-2 d-flex gap-2 align-items-start">
      <button class="btn btn-sm btn-outline-primary ver-pacotes" title="Ver pacotes"
              data-bs-toggle="modal" data-bs-target="#visualizarPacote" data-id-carga="${carga.id}">
        <i class="fas fa-box"></i>
      </button>
      <span class="slot-avancar d-inline-flex"></span>
    </div>
  `;

  // Renderiza o badge de status assim que o card for montado:
  renderStatusCarretas(body.querySelector('.status-carretas'), carga.id);

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
  // const slotAvancar = body.querySelector('.slot-avancar');
  // preencherSlotAvancar(carga, slotAvancar);

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

document.getElementById('formAvancarEstagio').addEventListener('submit', async function (e) {
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

    if (!resp.ok) throw new Error('Falha ao avançar estágio');

    const data = await resp.json(); // espera { stage_antigo, novo_stage, ... }

    // Fecha modal
    bootstrap.Modal.getInstance(document.getElementById('modalAvancarEstagio'))?.hide();

    // === 1) Seleciona o card atual pelo data-id
    const cardEl = document.querySelector(`.card.card-kanban[data-id='${id}']`);
    if (!cardEl) {
      console.warn('Card não encontrado no DOM:', id);
    } else {
      // === 2) Acha a nova lista do kanban (#col-<stage>) e move o card pra lá
      const stageKey = String(data.novo_stage || '').toLowerCase(); // ex.: 'verificacao'
      const destinoCol = document.getElementById(`col-${stageKey}`);

      if (!destinoCol) {
        console.error('Coluna destino não encontrada:', `col-${stageKey}`);
      } else {
        destinoCol.appendChild(cardEl);          // move o card
        cardEl.dataset.stage = data.novo_stage;  // opcional
      }
    }

    // Atualiza o slot do botão + warning do próprio card movido
    try {
      await atualizarSlotAvancar(id, false, data.novo_stage);
    } catch (e2) {
      console.warn('Falha ao atualizar slot avançar:', e2);
    }

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
