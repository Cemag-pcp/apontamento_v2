import { carregarOrdensIniciadas, carregarOrdensInterrompidas } from './ordem-criada-solda.js';

//testes

// const socket = new WebSocket(`ws://${window.location.host}/ws/ordens/iniciadas/`);
const protocol = window.location.protocol === "https:" ? "wss" : "ws";
const socket = new WebSocket(`${protocol}://${window.location.host}/ws/ordens/iniciadas/`);

socket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    console.log("Ordem atualizada:", data);
    
    const filtroDataCarga = document.getElementById('filtro-data-carga');
    const filtroSetor = document.getElementById('filtro-setor');

    // Captura os valores atualizados dos filtros
    const filtros = {
        data_carga: filtroDataCarga.value,
        setor: filtroSetor.value
    };

    // FUTURAMENTE carregar apenas a ordem que realmente foi atualizada, atualizar o card especificamente
    console.log("chamando carregarOrdensIniciadas");
    carregarOrdensIniciadas(filtros);

    console.log("chamando containerInterrompido");
    carregarOrdensInterrompidas(filtros);

};

socket.onclose = function(e) {
    console.warn('WebSocket desconectado');
};