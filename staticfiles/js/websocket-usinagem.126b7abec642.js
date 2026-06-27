import { carregarOrdensIniciadas, carregarOrdensAgProProcesso, carregarOrdensInterrompidas } from './ordem-criada-usinagem.js';

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

    console.log("chamando containerProxProcesso");
    const containerProxProcesso = document.querySelector('.containerProxProcesso')
    carregarOrdensAgProProcesso(containerProxProcesso);

};

socket.onclose = function(e) {
    console.warn('WebSocket desconectado');
};