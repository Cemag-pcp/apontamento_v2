document.addEventListener('DOMContentLoaded', function () {
    var calendarEl = document.getElementById('calendario');

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'pt-br',
        editable: true, // Permite arrastar eventos no calendário
        eventDurationEditable: false, // Impede alteração da duração
        events: function(fetchInfo, successCallback, failureCallback) {
            let start = fetchInfo.startStr;
            let end = fetchInfo.endStr;

            // Faz a requisição de eventos para o calendário
            fetch(`api/andamento-cargas?start=${start}&end=${end}`)
                .then(response => response.json())
                .then(data => successCallback(data))
                .catch(error => failureCallback(error));
        },
        eventClick: function (info) {
            // Pegamos as informações do evento
            let setor = info.event.extendedProps.setor;
            let dataAtual = info.event.startStr; // Data original do evento
            let eventId = info.event.id || `${setor}-${dataAtual}`; // ✅ Garante que o ID seja gerado se não existir

            // Preenche os campos do modal automaticamente
            document.getElementById('eventId').value = eventId;
            document.getElementById('setor').value = setor;
            document.getElementById('dataAtual').value = dataAtual;
            document.getElementById('novaData').value = dataAtual; // Sugere a mesma data inicial

            // Abre o modal
            var modal = new bootstrap.Modal(document.getElementById('modalRemanejar'));
            modal.show();
        },
        eventDrop: function (info) {
            let newDate = info.event.startStr;
            let setor = info.event.extendedProps.setor;
            let dataAtual = info.oldEvent.startStr;
            let eventId = info.event.id || `${setor}-${dataAtual}`;

            remanejarCarga(setor, dataAtual, newDate);
        }
    });

    calendar.render();

    // Atualizar evento após remanejamento manual no modal
    document.getElementById('confirmarRemanejamento').addEventListener('click', function () {
        let eventId = document.getElementById('eventId').value;
        let setor = document.getElementById('setor').value;
        let dataAtual = document.getElementById('dataAtual').value;
        let novaData = document.getElementById('novaData').value;

        if (!novaData) {
            alert('Por favor, selecione uma nova data.');
            return;
        }

        // Atualiza a exibição do evento no calendário
        let eventoAtualizado = calendar.getEventById(eventId);

        if (eventoAtualizado) {
            console.log("Atualizando evento:", eventoAtualizado);
            alert(`Carga do setor ${setor} remanejada para ${novaData}`);
        }

        // Chama a API para persistir a alteração no backend
        remanejarCarga(setor, dataAtual, novaData);

        // Fecha o modal
        var modal = bootstrap.Modal.getInstance(document.getElementById('modalRemanejar'));
        modal.hide();

        location.reload();
    });

});

function renderCallendar(){

}

function infoCargas(){

}

function remanejarCarga(setor, dataAtual, novaData) {
    fetch('api/remanejar-carga/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            setor: setor,
            dataAtual: dataAtual,  // ✅ Enviamos a data da carga atual
            dataRemanejar: novaData  // ✅ Nova data para onde a carga será movida
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert("Erro: " + data.error);
        } else {
            alert("Sucesso: " + data.message);
        }
    })
    .catch(error => console.error("Erro na requisição:", error));
}