export function aplicarFiltrosKanban() {
  const vCliente = (document.getElementById('filtroCliente').value || '').trim().toLowerCase();
  const vData    = (document.getElementById('filtroDataCarga').value || '').trim(); // YYYY-MM-DD
  const vStage   = (document.getElementById('filtroStage').value || '').trim().toLowerCase();

  document.querySelectorAll('.card.card-kanban').forEach(card => {
    const cCliente = (card.dataset.cliente || '').toLowerCase();
    const cData    = (card.dataset.dataCarga || '');
    const cStage   = (card.dataset.stage || '').toLowerCase();

    const okCliente = !vCliente || cCliente.includes(vCliente);
    const okData    = !vData || cData === vData;
    const okStage   = !vStage || cStage === vStage;

    card.style.display = (okCliente && okData && okStage) ? '' : 'none';
  });
}

function limparFiltrosKanban() {
  document.getElementById('filtroCliente').value = '';
  document.getElementById('filtroDataCarga').value = '';
  document.getElementById('filtroStage').value = '';
  aplicarFiltrosKanban();
}

// Eventos
// document.getElementById('btnAplicarFiltros').addEventListener('click', aplicarFiltrosKanban);
document.getElementById('btnLimparFiltros').addEventListener('click', limparFiltrosKanban);

// Também aplique ao digitar/alterar (opcional, experiência mais fluida)
document.getElementById('filtroCliente').addEventListener('input', aplicarFiltrosKanban);
document.getElementById('filtroDataCarga').addEventListener('change', aplicarFiltrosKanban);
document.getElementById('filtroStage').addEventListener('change', aplicarFiltrosKanban);
