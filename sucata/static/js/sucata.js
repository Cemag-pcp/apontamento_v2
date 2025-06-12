let graficoSucata = null;

    function filtrarSucata() {
        const dataInicio = document.getElementById('dataInicio').value;
        const dataFim = document.getElementById('dataFim').value;
        const codigoChapa = document.getElementById('codigoChapa').value;
        
        document.getElementById('carregando').classList.remove('d-none');
        document.getElementById('tabelaCodigoCorpo').innerHTML = '';
        document.getElementById('semResultados').classList.add('d-none');
        
        let url = '/sucata/corte?';
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
                        <td class="text-end">${item.peso || '0,00'}</td>
                    `;
                    tabelaCorpo.appendChild(row);
                });
            })
            .catch(error => {
                console.error('Erro:', error);
                document.getElementById('carregando').classList.add('d-none');
                alert('Ocorreu um erro ao buscar os dados');
            });
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

        filtrarSucata(); // Descomente se quiser carregar dados automaticamente
    });
