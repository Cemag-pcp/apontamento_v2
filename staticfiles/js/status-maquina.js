import { carregarOrdensIniciadas, carregarOrdensInterrompidas } from './ordem-criada-estamparia.js';

let ordensChartInstance = null;

function renderLoading(container) {
    container.innerHTML = `
        <li class="d-flex justify-content-center py-4">
            ${window.getAppLoaderHtml ? window.getAppLoaderHtml({ size: 64 }) : ''}
        </li>`;
}

function renderMessage(container, message, className = 'text-muted') {
    container.innerHTML = `<li class="${className} text-center py-3">${message}</li>`;
}

function formatarHorario(dataTexto) {
    if (!dataTexto) return '--:--';

    const data = new Date(dataTexto.replace(' ', 'T'));
    if (Number.isNaN(data.getTime())) return '--:--';

    data.setHours(data.getHours() - 3);

    return data.toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit',
    });
}

function destruirGraficoOrdens() {
    if (ordensChartInstance) {
        ordensChartInstance.destroy();
        ordensChartInstance = null;
    }
}

function statusChipClass(status) {
    if (status === 'Em produção') return 'success';
    if (status === 'Parada') return 'danger';
    return 'warning';
}

function desenharMensagemGrafico(canvas, message, color = '#64748b') {
    const ctx = canvas.getContext('2d');
    const largura = canvas.clientWidth || canvas.width || 240;
    const altura = canvas.clientHeight || canvas.height || 180;

    canvas.width = largura;
    canvas.height = altura;
    ctx.clearRect(0, 0, largura, altura);
    ctx.font = '14px sans-serif';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(message, largura / 2, altura / 2);
}

export function fetchStatusMaquinas() {
    const listaStatus = document.querySelector('#machine-status-list');
    if (!listaStatus) return;

    renderLoading(listaStatus);

    fetch('/core/api/status_maquinas/?setor=estamparia')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            listaStatus.innerHTML = '';

            if (data.status.length > 0) {
                data.status.forEach(maquina => {
                    const statusItem = document.createElement('li');
                    const statusClasse = statusChipClass(maquina.status);
                    const motivoParada = maquina.status === 'Parada'
                        ? `<div class="simple-list-subtitle text-danger">${maquina.motivo_parada || 'Sem motivo especificado'}</div>`
                        : '';
                    const botaoRetorno = maquina.status === 'Parada'
                        ? `
                            <button class="btn btn-sm btn-outline-success retornar-maquina-btn" data-maquina="${maquina.maquina_id}" title="Retomar">
                                <i class="fa fa-play"></i>
                            </button>
                        `
                        : '';

                    statusItem.innerHTML = `
                        <div class="priority-line">
                            <div class="simple-list-text">
                                <div class="simple-list-title">${maquina.maquina}</div>
                                ${motivoParada}
                            </div>
                            <div class="machine-line">
                                <span class="status-chip ${statusClasse}">${maquina.status}</span>
                                ${botaoRetorno}
                            </div>
                        </div>
                    `;

                    listaStatus.appendChild(statusItem);
                });

                document.querySelectorAll('.retornar-maquina-btn').forEach(button => {
                    button.addEventListener('click', function () {
                        const maquinaId = this.getAttribute('data-maquina');
                        retornarMaquina(maquinaId);
                    });
                });
            } else {
                renderMessage(listaStatus, 'Nenhuma maquina registrada no momento.');
            }
        })
        .catch(error => {
            console.error('Erro ao buscar status das maquinas:', error);
            renderMessage(listaStatus, 'Erro ao carregar os dados.', 'text-danger');
        });
}

export function fetchUltimasPecasProduzidas() {
    const listaPecas = document.querySelector('#ultimas-pecas-list');
    if (!listaPecas) return;

    renderLoading(listaPecas);

    fetch('/core/api/ultimas_pecas_produzidas/?setor=estamparia')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            listaPecas.innerHTML = '';

            if (data.pecas && data.pecas.length > 0) {
                data.pecas.slice(0, 5).forEach(peca => {
                    const listItem = document.createElement('li');
                    const horario = formatarHorario(peca.data_producao);
                    const destaque = horario !== '--:--' ? horario : `${peca.quantidade || 0}`;

                    listItem.innerHTML = `
                        <div class="simple-list-text">
                            <div class="simple-list-title">${peca.nome}</div>
                            <div class="simple-list-subtitle">Quantidade: ${peca.quantidade || 0}</div>
                        </div>
                        <span class="status-chip success">${destaque}</span>
                    `;

                    listaPecas.appendChild(listItem);
                });
            } else {
                renderMessage(listaPecas, 'Nenhuma peca produzida recentemente.');
            }
        })
        .catch(error => {
            console.error('Erro ao buscar as ultimas pecas produzidas:', error);
            renderMessage(listaPecas, 'Erro ao carregar os dados.', 'text-danger');
        });
}

export function fetchContagemStatusOrdens() {
    const canvas = document.getElementById('ordensChart');
    if (!canvas || typeof Chart === 'undefined') return;

    destruirGraficoOrdens();
    desenharMensagemGrafico(canvas, 'Carregando...');

    fetch('/estamparia/api/indicador-planejado-concluido-hoje/')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const labels = ['Concluida', 'Planejada'];
            const valores = [Number(data.concluida || 0), Number(data.planejada || 0)];
            const cores = ['#10b981', '#3b82f6'];

            if (!valores.some(total => total > 0)) {
                desenharMensagemGrafico(canvas, 'Nenhuma ordem encontrada.');
                return;
            }

            const ctx = canvas.getContext('2d');
            ordensChartInstance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data: valores,
                        backgroundColor: cores,
                        borderWidth: 0,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '72%',
                    plugins: {
                        title: {
                            display: true,
                            text: `Dados de ${data.data_referencia}`,
                            color: '#64748b',
                            font: {
                                size: 11,
                                weight: '600',
                            },
                            padding: {
                                bottom: 10,
                            },
                        },
                        legend: {
                            position: 'right',
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                padding: 14,
                                color: '#475569',
                                font: {
                                    size: 11,
                                },
                            },
                        },
                    },
                },
            });
        })
        .catch(error => {
            console.error('Erro ao buscar indicador concluida x planejada:', error);
            destruirGraficoOrdens();
            desenharMensagemGrafico(canvas, 'Erro ao carregar os dados.', '#ef4444');
        });
}

async function fetchMaquinasDisponiveis() {
    try {
        const response = await fetch('/core/api/buscar-maquinas-disponiveis/?setor=estamparia');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        const selectMaquina = document.getElementById('escolhaMaquinaParada');
        selectMaquina.innerHTML = '';

        if (data.maquinas_disponiveis.length > 0) {
            data.maquinas_disponiveis.forEach(maquina => {
                const option = document.createElement('option');
                option.value = maquina.alias;
                option.textContent = maquina.nome;
                selectMaquina.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.textContent = 'Nenhuma maquina disponivel';
            option.disabled = true;
            selectMaquina.appendChild(option);
        }
    } catch (error) {
        console.error('Erro ao buscar maquinas disponiveis:', error);
    }
}

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function retornarMaquina(maquina) {
    Swal.fire({
        title: 'Retornar maquina',
        text: `Deseja retornar a máquina ${maquina} à produção?`,
        showCancelButton: true,
        confirmButtonText: 'Sim',
        cancelButtonText: 'Cancelar',
        showLoaderOnConfirm: true,
        preConfirm: () => {
            return fetch(`/core/api/retornar-maquina/`, {
                method: 'PATCH',
                body: JSON.stringify({ maquina }),
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                },
            })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `Erro na requisicao: ${response.status}`);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    fetchStatusMaquinas();
                    return data;
                })
                .catch(error => {
                    console.error('Erro:', error);
                    Swal.showValidationMessage(`Erro: ${error.message}`);
                });
        },
    }).then(result => {
        if (result.isConfirmed) {
            Swal.fire({
                icon: 'success',
                title: 'Sucesso',
                text: 'Maquina retornada a producao.',
            });
        }
    });
}

async function mostrarModalPararMaquina() {
    const formPararMaquina = document.getElementById('formPararMaquina');

    Swal.fire(window.getAppLoadingSwalOptions({
        title: 'Carregando...',
        text: 'Buscando informacoes da ordem...',
    }));

    await fetchMaquinasDisponiveis();
    Swal.close();

    formPararMaquina.removeEventListener('submit', handleFormSubmit);
    formPararMaquina.addEventListener('submit', handleFormSubmit, { once: true });
}

async function handleFormSubmit(event) {
    event.preventDefault();

    Swal.fire(window.getAppLoadingSwalOptions({
        title: 'Parando...',
        text: 'Por favor, aguarde enquanto a maquina esta sendo parada.',
    }));

    try {
        const response = await fetch(`/core/api/parar-maquina/?setor=estamparia`, {
            method: 'PATCH',
            body: JSON.stringify({
                maquina: document.getElementById('escolhaMaquinaParada').value,
                motivo: document.getElementById('motivoParadaMaquina').value,
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `Erro na requisicao: ${response.status}`);
        }

        Swal.fire({
            icon: 'success',
            title: 'Sucesso',
            text: 'Ordem interrompida com sucesso.',
        });

        fetchContagemStatusOrdens();
        fetchStatusMaquinas();

        const containerIniciado = document.querySelector('.containerProcesso');
        carregarOrdensIniciadas(containerIniciado);

        const containerInterrompido = document.querySelector('.containerInterrompido');
        carregarOrdensInterrompidas(containerInterrompido);
    } catch (error) {
        console.error('Erro:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message,
        });
    }
}

document.addEventListener('DOMContentLoaded', function () {
    fetchStatusMaquinas();
    fetchUltimasPecasProduzidas();
    fetchContagemStatusOrdens();

    document.getElementById('refresh-status-maquinas').addEventListener('click', function () {
        fetchStatusMaquinas();
    });

    document.getElementById('refresh-pecas').addEventListener('click', function () {
        fetchUltimasPecasProduzidas();
    });

    document.getElementById('refresh-ordens').addEventListener('click', function () {
        fetchContagemStatusOrdens();
    });

    document.getElementById('btnPararMaquina').addEventListener('click', () => {
        mostrarModalPararMaquina();
    });
});
