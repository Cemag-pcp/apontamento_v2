import { carregarOrdensIniciadas, carregarOrdensInterrompidas } from './ordem-criada-solda.js';

//testes

// const socket = new WebSocket(`ws://${window.location.host}/ws/ordens/iniciadas/`);
const protocol = window.location.protocol === "https:" ? "wss" : "ws";
const socket = new WebSocket(`${protocol}://${window.location.host}/ws/ordens/iniciadas/`);

socket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    console.log("Ordem atualizada:", data);
    
    // FUTURAMENTE carregar apenas a ordem que realmente foi atualizada, atualizar o card especificamente
    console.log("chamando carregarOrdensIniciadas");
    const containerIniciado = document.querySelector('.containerProcesso');
    carregarOrdensIniciadas(containerIniciado);

    console.log("chamando containerInterrompido");
    const containerInterrompido = document.querySelector('.containerInterrompido');
    carregarOrdensInterrompidas(containerInterrompido);

};

socket.onclose = function(e) {
    console.warn('WebSocket desconectado');
};