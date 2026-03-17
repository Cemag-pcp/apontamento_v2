import { carregarOrdensIniciadas, carregarOrdensInterrompidas } from './ordem-criada.js';
import { fetchOrdensSequenciadasLaser, fetchOrdensSequenciadasPlasma } from './status-maquina-corte.js';

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

    console.log("chamando fetchOrdensSequenciadasLaser");
    const tabAtiva = document.querySelector('#laserTabs .nav-link.active');
    const grupoLaser = tabAtiva ? tabAtiva.dataset.group : 'laser_1';
    fetchOrdensSequenciadasLaser(grupoLaser);

    console.log("chamando fetchOrdensSequenciadasPlasma");
    fetchOrdensSequenciadasPlasma();

};

socket.onclose = function(e) {
    console.warn('WebSocket desconectado');
};
