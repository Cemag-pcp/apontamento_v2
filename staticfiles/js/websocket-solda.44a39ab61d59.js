// WebSocket desabilitado (instabilidade em producao ligada ao channel layer Redis).
// import { carregarOrdensIniciadas, carregarOrdensInterrompidas } from './ordem-criada-solda.js';

// const protocol = window.location.protocol === "https:" ? "wss" : "ws";
// const socket = new WebSocket(`${protocol}://${window.location.host}/ws/ordens/iniciadas/`);

// socket.onmessage = function(e) {
//     const data = JSON.parse(e.data);
//     console.log("Ordem atualizada:", data);

//     const filtroDataCarga = document.getElementById('filtro-data-carga');
//     const filtroSetor = document.getElementById('filtro-setor');

//     const filtros = {
//         data_carga: filtroDataCarga.value,
//         setor: filtroSetor.value
//     };

//     console.log("chamando carregarOrdensIniciadas");
//     carregarOrdensIniciadas(filtros);

//     console.log("chamando containerInterrompido");
//     carregarOrdensInterrompidas(filtros);

// };

// socket.onclose = function(e) {
//     console.warn('WebSocket desconectado');
// };