// Função de formatação para os detalhes da linha
function format(d) {
    // d é o objeto de dados original para a linha
    return (
        '<dl>' +
        '<dt>Robô:</dt>' +
        '<dd>' + d.rpa + '</dd>' +
        '</dl>'
    );
}

$(document).ready(function () {
    let table = $('#execucaoTable').DataTable({
        processing: true,   // Mostra o indicador de processamento enquanto carrega os dados
        serverSide: true,    // Habilita o processamento no servidor
        ajax: {
            url: '/almox/api/historico/processa-historico-transferencia/',  // A URL que vai retornar os dados
            type: 'POST',  // Método de envio (GET ou POST)
            data: function (d) {
                d.csrfmiddlewaretoken = '{{ csrf_token }}'; // Inclui o token CSRF
            }
        },
        columns: [
            {
                className: 'dt-control',
                orderable: false,
                data: null,
                defaultContent: ''
            },  // Coluna para o botão de expansão dos detalhes
            {
                data: 'rpa',
                render: function (data, type, row) {
                    if (data === 'OK') {
                        return '<span class="badge bg-success">Ok</span>';
                    } else if (data === null) {
                        return '<span class="badge bg-warning text-dark">Pendente</span>';
                    } else {
                        return '<span class="badge bg-warning text-dark">Erro</span>';
                    }
                }
            },
            { data: 'data_solicitacao' },
            { data: 'item__nome' },
            { data: 'quantidade' },
            { data: 'deposito_destino__nome' },
            { data: 'funcionario__nome' },
            { data: 'obs' },
            { data: 'entregue_por__nome' },
            { data: 'data_entrega' },
            {
                data: 'status',  // Nome diferente para evitar conflito
                render: function (data, type, row) {
                    if (data === 'Entregue') {
                        return '<span class="badge bg-success">Entregue</span>';
                    } else {
                        return '<span class="badge bg-warning text-dark">Pendente</span>';
                    }
                }
            },
            
        ],
        order: [[1, 'asc']],
        language: {
            search: "Procurar pelo nome do item"
        }
    });

    // Adicionar evento de clique para abrir e fechar os detalhes
    $('#execucaoTable tbody').on('click', 'td.dt-control', function (e) {
        let tr = $(this).closest('tr');
        let row = table.row(tr);

        if (row.child.isShown()) {
            // A linha já está aberta - fechá-la
            row.child.hide();
            tr.removeClass('shown');
        } else {
            // Abrir esta linha
            row.child(format(row.data())).show();
            tr.addClass('shown');
        }
    });
});