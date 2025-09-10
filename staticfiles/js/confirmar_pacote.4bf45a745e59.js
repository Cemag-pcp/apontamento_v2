import { popularPacotesDaCarga } from './carregar_cargas.js';

document.getElementById('formConfirmarPacote').addEventListener('submit', async (e) => {
  e.preventDefault();

  const btnConfirmarPacote = document.getElementById('btnConfirmarPacote');
  btnConfirmarPacote.disabled = true;
  btnConfirmarPacote.innerHTML = 'Confirmando...'

  const id = document.getElementById('idPacoteConfirmar').value;
  const obs = document.getElementById('obsConfirmarPacote').value;

  try {
    const resp = await fetch(`api/confirmar-pacote/${id}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ observacao: obs })
    });

    const data = await resp.json();
    console.log('Resposta:', data);

    // Fecha o modal e recarrega os pacotes
    bootstrap.Modal.getInstance(document.getElementById('modalConfirmarPacote')).hide();
    const currentCargaId = document.getElementById('idCargaPacote').value;

    const modalElVisualizarPacotes = document.getElementById('visualizarPacote');
    const modalVisualizarPacotes   = bootstrap.Modal.getInstance(modalElVisualizarPacotes) || new bootstrap.Modal(modalElVisualizarPacotes);
    modalVisualizarPacotes.show();

    popularPacotesDaCarga(currentCargaId);
    
    const btnConfirmarPacote = document.getElementById('btnConfirmarPacote');
    btnConfirmarPacote.disabled = false;
    btnConfirmarPacote.innerHTML = 'Confirmar'


  } catch (err) {
    alert('Erro ao confirmar pacote');
    console.error(err);
  }
});

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}