export async function verificarCarretas(cargaId) {
  const resp = await fetch(`api/comparar-carretas-geradas/${encodeURIComponent(cargaId)}/`, {
    headers: { 'Accept': 'application/json' }
  });
  if (!resp.ok) throw new Error(await resp.text());
  return await resp.json();
}

export async function renderStatusCarretas(targetEl, cargaId) {
  if (!targetEl) return;

  // helper para limpar qualquer tooltip anterior e esvaziar o container
  const clearStatus = () => {
    const prev = targetEl.querySelector('[data-bs-toggle="tooltip"]');
    if (prev && window.bootstrap?.Tooltip) {
      const inst = bootstrap.Tooltip.getInstance(prev);
      if (inst) inst.dispose();
    }
    targetEl.replaceChildren(); // fica vazio
  };

  try {
    const data = await verificarCarretas(cargaId);
    const ok = !!data.ok;

    if (ok) {
      // se está tudo certo, não renderiza nada
      clearStatus();
      return;
    }

    // há pendências → badge vermelho com tooltip
    const faltando = Array.isArray(data.faltando_gerar) ? data.faltando_gerar : [];
    const tip = `Carretas faltando: ${faltando.length ? faltando.join(', ') : '—'}`;

    const badge = document.createElement('span');
    badge.className = 'badge rounded-pill bg-danger';
    badge.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i>Pendências`;
    badge.setAttribute('data-bs-toggle', 'tooltip');
    badge.setAttribute('data-bs-placement', 'top');
    badge.setAttribute('data-bs-title', tip);

    clearStatus();
    targetEl.appendChild(badge);

    if (window.bootstrap?.Tooltip) {
      new bootstrap.Tooltip(badge);
    }
  } catch (err) {
    // erro → badge neutro com tooltip do erro
    const badge = document.createElement('span');
    badge.className = 'badge rounded-pill bg-secondary';
    badge.innerHTML = `<i class="fas fa-question-circle me-1"></i>Indefinido`;
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
