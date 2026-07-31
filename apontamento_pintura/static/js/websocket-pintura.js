// WebSocket desabilitado (instabilidade em producao ligada ao channel layer Redis).
// import { cambaoProcesso } from './ordem-criada-pintura.js';

// const protocol = window.location.protocol === "https:" ? "wss" : "ws";
// const socket = new WebSocket(`${protocol}://${window.location.host}/ws/ordens/iniciadas/`);

// socket.onmessage = function(e) {
//     const data = JSON.parse(e.data);
//     console.log("Ordem atualizada:", data);

//     console.log("chamando carregarOrdensIniciadas");
//     cambaoProcesso();

// };

// socket.onclose = function(e) {
//     console.warn('WebSocket desconectado');
// };