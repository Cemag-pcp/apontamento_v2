document.addEventListener('DOMContentLoaded', function () {
  const checkboxes = document.querySelectorAll('.material-visualizado');
  const andamentoVisualizacoes = document.getElementById('andamentoVisualizacoes');
  const botaoProvas = document.getElementById('provaDisponivel'); // Seleciona o botão

  function updatePercentage() {
      const totalCheckboxes = checkboxes.length;
      let checkboxesMarcados = 0;

      checkboxes.forEach(checkbox => {
          if (checkbox.checked) {
              checkboxesMarcados++;
          }
      });

      const percentage = totalCheckboxes > 0 ? (checkboxesMarcados / totalCheckboxes) * 100 : 0;
      andamentoVisualizacoes.textContent = `Andamento da trilha: ${percentage.toFixed(2)}`;

      // Mostra/esconde o botão com base no progresso
      if (percentage === 100) {
          botaoProvas.style.display = 'block'; // Ou 'inline-block' se preferir
      } else {
          botaoProvas.style.display = 'none';
      }
  }

  updatePercentage(); // Atualiza ao carregar a página

  checkboxes.forEach(checkbox => {
      checkbox.addEventListener('change', updatePercentage);
  });
});
