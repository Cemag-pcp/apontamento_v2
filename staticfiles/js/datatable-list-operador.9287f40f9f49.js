export async function carregarTabela() {

  if ( $.fn.DataTable.isDataTable('#tableOperadores') ) {
      $('#tableOperadores').DataTable().clear().destroy();
  }

  document.getElementById('overlayLoading').style.display = 'block';

  await fetch('/cadastro/api/operadores/')
    .then(response => response.json())
    .then(data => {
      const tbody = document.querySelector('#tableOperadores tbody');
      tbody.innerHTML = '';
      data.operadores.forEach(operador => {
        const row = `
          <tr data-id="${operador.id}">
              <td id="operadorNome-${ operador.id }">${ operador.nome }</td>
              <td id="operadorMatricula-${ operador.id }">${ operador.matricula }</td>
              <td id="operadorSetor-${ operador.id }" data-id-setor="${ operador.setor_id }">${ operador.setor }</td>
              <td id="operadorStatus-${ operador.id }">${ operador.status }</td>
              <td>
                  <span class="badge btn btn-warning btnEditOperador" id="btnEditOperador-${ operador.id }">Editar</span>
                  <span class="badge btn btn-danger btnDesativarOperador" id="btnDesativarOperador-${ operador.id }">Desativar</span>
              </td>
          </tr>`;
        tbody.insertAdjacentHTML('beforeend', row);
      });

      document.getElementById('overlayLoading').style.display = 'none';

      $('#tableOperadores').DataTable({
        "info": true,
        "autoWidth": false,
        "responsive": true,
        "processing": true,
        language: {
          url: "//cdn.datatables.net/plug-ins/1.13.7/i18n/pt-BR.json"
        },
      });
    });
}

// Chama no carregamento inicial
// document.addEventListener("DOMContentLoaded", carregarTabela);


