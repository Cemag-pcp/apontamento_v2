// WebSocket desabilitado (instabilidade em producao ligada ao channel layer Redis).
// import { carregarOrdensIniciadas, carregarOrdensAgProProcesso, carregarOrdensInterrompidas } from './ordem-criada-usinagem.js';

// const protocol = window.location.protocol === "https:" ? "wss" : "ws";
// const socket = new WebSocket(`${protocol}://${window.location.host}/ws/ordens/iniciadas/`);

// socket.onmessage = function(e) {
//     const data = JSON.parse(e.data);
//     console.log("Ordem atualizada:", data);

//     console.log("chamando carregarOrdensIniciadas");
//     const containerIniciado = document.querySelector('.containerProcesso');
//     carregarOrdensIniciadas(containerIniciado);

//     console.log("chamando containerInterrompido");
//     const containerInterrompido = document.querySelector('.containerInterrompido');
//     carregarOrdensInterrompidas(containerInterrompido);

//     console.log("chamando containerProxProcesso");
//     const containerProxProcesso = document.querySelector('.containerProxProcesso')
//     carregarOrdensAgProProcesso(containerProxProcesso);

// };

// socket.onclose = function(e) {
//     console.warn('WebSocket desconectado');
// };