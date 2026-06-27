import { getCookie } from './criar_caixa.js';

export async function verificarCarretas(cargaId) {
  const resp = await fetch(`api/comparar-carretas-geradas/${encodeURIComponent(cargaId)}/`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!resp.ok) throw new Error(await resp.text());
  return await resp.json();
}

async function reprocessarCarretaFaltante(cargaId, carreta) {
  const resp = await fetch(`api/reprocessar-carretas-faltantes/${encodeURIComponent(cargaId)}/`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({ carreta })
  });

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data?.erro || 'Falha ao reprocessar a carreta faltante.');
  return data;
}

export async function renderStatusCarretas(targetEl, cargaId) {
  if (!targetEl) return;

  const clearStatus = () => {
    const prev = targetEl.querySelector('[data-bs-toggle="tooltip"]');
    if (prev && window.bootstrap?.Tooltip) {
      const inst = bootstrap.Tooltip.getInstance(prev);
      if (inst) inst.dispose();
    }
    targetEl.replaceChildren();
  };

  try {
    const data = await verificarCarretas(cargaId);
    const ok = !!data.ok;

    if (ok) {
      clearStatus();
      return;
    }

    const faltando = Array.isArray(data.faltando_gerar) ? data.faltando_gerar : [];
    const tip = `Carretas faltando: ${faltando.length ? faltando.join(', ') : '?'}`;

    const wrapper = document.createElement('div');
    wrapper.className = 'd-flex align-items-center gap-2 flex-wrap';

    const badge = document.createElement('span');
    badge.className = 'badge rounded-pill bg-danger';
    badge.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>Algumas carretas estao faltando';
    badge.setAttribute('data-bs-toggle', 'tooltip');
    badge.setAttribute('data-bs-placement', 'top');
    badge.setAttribute('data-bs-title', tip);
    wrapper.appendChild(badge);

    faltando.forEach((carreta) => {
      const btnRefresh = document.createElement('button');
      btnRefresh.type = 'button';
      btnRefresh.className = 'btn btn-sm btn-outline-danger';
      btnRefresh.title = `Reprocessar a carreta ${carreta}`;
      btnRefresh.textContent = carreta;
      btnRefresh.addEventListener('click', async () => {
        const labelOriginal = btnRefresh.textContent;
        btnRefresh.disabled = true;
        btnRefresh.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';

        try {
          const syncData = await reprocessarCarretaFaltante(cargaId, carreta);

          window.dispatchEvent(new CustomEvent('expedicao:carretas-reprocessadas', {
            detail: {
              cargaId,
              totalPendente: Number(syncData.total_pendente ?? 0)
            }
          }));

          await renderStatusCarretas(targetEl, cargaId);

          const msg = syncData.ok
            ? `Carreta ${carreta} reprocessada.`
            : `A carreta ${carreta} foi reprocessada, mas ainda faltam: ${(syncData.faltando_gerar || []).join(', ') || 'nao identificado'}`;

          if (window.Swal) {
            Swal.fire({
              icon: syncData.ok ? 'success' : 'warning',
              title: syncData.ok ? 'Carga atualizada' : 'Reprocessamento parcial',
              text: msg,
            });
          }
        } catch (syncErr) {
          if (window.Swal) {
            Swal.fire({
              icon: 'error',
              title: 'Erro',
              text: syncErr.message || 'Falha ao reprocessar a carreta.',
            });
          }
          btnRefresh.disabled = false;
          btnRefresh.textContent = labelOriginal;
        }
      });
      wrapper.appendChild(btnRefresh);
    });

    clearStatus();
    targetEl.appendChild(wrapper);

    if (window.bootstrap?.Tooltip) {
      new bootstrap.Tooltip(badge);
    }
  } catch (err) {
    const badge = document.createElement('span');
    badge.className = 'badge rounded-pill bg-secondary';
    badge.innerHTML = '<i class="fas fa-question-circle me-1"></i>Indefinido';
    badge.setAttribute('data-bs-toggle', 'tooltip');
    badge.setAttribute('data-bs-placement', 'top');
    badge.setAttribute('data-bs-title', `Falha ao verificar carretas: ${String(err).slice(0, 160)}`);

    clearStatus();
    targetEl.appendChild(badge);

    if (window.bootstrap?.Tooltip) {
      new bootstrap.Tooltip(badge);
    }
  }
}
