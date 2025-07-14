const socket = new WebSocket(`ws://${window.location.host}/ws/ordens/iniciadas/`);

socket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    console.log("Ordem atualizada:", data);
    // Pode atualizar só a ordem específica ou recarregar todas
    // carregarOrdensIniciadas(document.querySelector('#container-ordens'));
};

socket.onclose = function(e) {
    console.warn('WebSocket desconectado');
};