import { popularPacotesDaCarga } from './carregar_cargas.js';

document.getElementById('formConfirmarPacote').addEventListener('submit', async (e) => {
  e.preventDefault();

  const btnConfirmarPacote = document.getElementById('btnConfirmarPacote');
  btnConfirmarPacote.disabled = true;
  btnConfirmarPacote.innerHTML = 'Confirmando...';

  const id  = document.getElementById('idPacoteConfirmar').value;
  const obs = document.getElementById('obsConfirmarPacote').value;

  try {
    const resp = await fetch(`api/confirmar-pacote/${encodeURIComponent(id)}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ observacao: obs })
    });

    // Tenta decodificar JSON; se não for JSON, cai para texto bruto
    let payload = null;
    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      payload = await resp.json();
    } else {
      const txt = await resp.text();
      payload = { erro: txt };
    }

    // IMPORTANTE: verificar status HTTP
    if (!resp.ok) {
      // sua view retorna {"erro": "..."} em 400
      const msg = payload?.erro || 'Falha ao confirmar o pacote.';
      throw new Error(msg);
    }

    // Sucesso → fecha modal e atualiza lista
    const modal = bootstrap.Modal.getInstance(document.getElementById('modalConfirmarPacote'));
    if (modal) modal.hide();

    const currentCargaId = document.getElementById('idCargaPacote').value;
    const modalElVisualizarPacotes = document.getElementById('visualizarPacote');
    const modalVisualizarPacotes = bootstrap.Modal.getInstance(modalElVisualizarPacotes) || new bootstrap.Modal(modalElVisualizarPacotes);
    modalVisualizarPacotes.show();

    if (currentCargaId) {
      popularPacotesDaCarga(currentCargaId);
    }

    // (opcional) toast/sucesso
    // showToast('Pacote confirmado com sucesso!');

  } catch (err) {
    // Mostra a mensagem vinda do backend (JsonResponse {'erro': '...'})
    alert(err.message || 'Erro inesperado ao confirmar o pacote.');
    console.error(err);
  } finally {
    btnConfirmarPacote.disabled = false;
    btnConfirmarPacote.innerHTML = 'Confirmar';
  }
});


function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}