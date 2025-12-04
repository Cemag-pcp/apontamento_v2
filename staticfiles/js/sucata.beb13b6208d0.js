let graficoSucata = null;

function filtrarSucata() {
    const dataInicio = document.getElementById('dataInicio').value;
    const dataFim = document.getElementById('dataFim').value;
    const codigoChapa = document.getElementById('codigoChapa').value;
    const btnFiltrar = document.getElementById('btn-filtrar-sucata');
    const Toast = Swal.mixin({
        toast: true,
        position: "bottom-end",
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.onmouseenter = Swal.stopTimer;
            toast.onmouseleave = Swal.resumeTimer;
        }
    });
    btnFiltrar.disabled = true;
    btnFiltrar.querySelector('.spinner-border').style.display = 'block';
    btnFiltrar.querySelector('.bi-funnel').style.display = 'none';
    
    document.getElementById('carregando').classList.remove('d-none');
    document.getElementById('tabelaCodigoCorpo').innerHTML = '';
    document.getElementById('semResultados').classList.add('d-none');
    
    let url = '/sucata/api/corte?';
    if (dataInicio) url += `data_inicial=${dataInicio}&`;
    if (dataFim) url += `data_final=${dataFim}&`;
    if (codigoChapa) url += `codigo_chapa=${encodeURIComponent(codigoChapa)}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            document.getElementById('carregando').classList.add('d-none');
            
            if (data.grafico.datas.length === 0) {
                document.getElementById('semResultados').classList.remove('d-none');
                return;
            }
            
            // Atualizar gráfico
            atualizarGrafico(
                data.grafico.datas, 
                data.grafico.pesos, 
                data.grafico.aproveitamentos
            );
                
            // Preencher tabela por código
            const tabelaCorpo = document.getElementById('tabelaCodigoCorpo');
            data.tabela.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.codigo || ''}</td>
                    <td>${item.peso || '0,00'}</td>
                `;
                tabelaCorpo.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Erro:', error);
            document.getElementById('carregando').classList.add('d-none');
            Toast.fire({
                icon: 'error',
                title: 'Erro ao gerar o gráfico, verifique se as datas estão corretas'
            });
        })
        .finally(f => {
            btnFiltrar.disabled = false;
            btnFiltrar.querySelector('.spinner-border').style.display = 'none';
            btnFiltrar.querySelector('.bi-funnel').style.display = 'block';
        })
}

function atualizarGrafico(datas, pesos, aproveitamentos) {
    const ctx = document.getElementById('graficoSucata').getContext('2d');
    
    if (graficoSucata) {
        graficoSucata.destroy();
    }
    
    graficoSucata = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datas,
            datasets: [
                {
                    label: 'Peso de Sucata (kg)',
                    data: pesos,
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Aproveitamento Médio',
                    data: aproveitamentos,
                    type: 'line',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    borderWidth: 2,
                    pointRadius: 4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Peso de Sucata (kg)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Aproveitamento'
                    },
                    min: 0,
                    max: 100,
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

function limparFiltros() {
    document.getElementById('filtroForm').reset();
    document.getElementById('tabelaCodigoCorpo').innerHTML = '';
    document.getElementById('semResultados').classList.add('d-none');
}

// Opcional: Filtrar ao carregar a página com dados do último mês
document.addEventListener('DOMContentLoaded', function () {
    const hoje = new Date();
    const ontem = new Date();
    ontem.setDate(hoje.getDate() - 1); // subtrai 1 dia

    // Exibe a data de hoje e de ontem nos campos de input
    document.getElementById('dataInicio').valueAsDate = ontem;
    document.getElementById('dataFim').valueAsDate = hoje;

    // filtrarSucata();
});

document.getElementById('btn-filtrar-sucata').addEventListener('click', function () {
    filtrarSucata();
})

document.getElementById('btn-limpar-filtros').addEventListener('click', function () {
    limparFiltros();
})