document.getElementById('formConfirmarPacote').addEventListener('submit', async (e) => {
  e.preventDefault();

  const id = document.getElementById('idPacoteConfirmar').value;

  try {
    const resp = await fetch(`api/confirmar-pacote/${id}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')  // se estiver usando Django
      },
    //   body: JSON.stringify({ observacao: obs })
    });

    if (!resp.ok) throw new Error('Erro na confirmação');

    // Fecha o modal e recarrega os pacotes
    bootstrap.Modal.getInstance(document.getElementById('modalConfirmarPacote')).hide();
    const currentCargaId = document.getElementById('idCargaPacote').value;
    if (currentCargaId) popularPacotesDaCarga(currentCargaId);

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