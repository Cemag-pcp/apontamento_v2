import { confirmarInicioOrdem } from './apontamento-utils.js';

document.addEventListener('DOMContentLoaded', function() {
    // Pega a string de parâmetros da URL atual
    const params = new URLSearchParams(window.location.search);

    // Para pegar um parâmetro específico, por exemplo 'ordem_id':
    const ordemId = params.get('ordem_id');
    const cardApontamentoQrCode = document.getElementById('cardApontamentoQrCode');

    // Exibe loader antes do fetch
    cardApontamentoQrCode.innerHTML = `
        <div class="d-flex justify-content-center align-items-center" style="min-height: 270px;">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
        </div>
    `;


    fetch(`/montagem/api/apontamento-qrcode/?ordem_id=${ordemId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Processar os dados recebidos
                console.log(data);

                const ordem = data.dados;

                const statusClass =
                    ordem.status === 'finalizada' ? 'bg-success' :
                    ordem.status === 'iniciada' ? 'bg-warning text-dark' :
                    ordem.status === 'aguardando_iniciar' ? 'bg-secondary' : 
                    ordem.status === 'interrompida' ? 'bg-danger' : 'bg-secondary';

                cardApontamentoQrCode.innerHTML = `
                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title fw-bold mb-0 fs-5">#${ordem.peca}</h6>
                    </div>
                    <div class="card-body bg-white p-3">
                        <p class="card-text mb-3">
                            <strong>Data Carga:</strong> ${ordem.data_carga}
                        </p>
                        <p class="card-text mb-3">
                            <strong>Quantidade a fazer:</strong> ${ordem.qtd_planejada}
                        </p>
                        <p class="card-text mb-3">
                            <strong>Quantidade feita:</strong> ${ordem.qtd_boa}
                        </p>
                        <p class="card-text mb-0"><strong>Status: </strong><span class="badge ${statusClass}">${ordem.status}</span></p>
                    </div>
                    <div class="card-footer d-flex justify-content-end align-items-center bg-white p-3 border-top">
                        <button class="btn btn-warning btn-sm" title="Iniciar">
                            <i class="fa fa-play"></i> Iniciar
                        </button>
                    </div>
                `
                // Atualizar a interface do usuário conforme necessário
            } else {
                console.error('Erro na resposta da API:', data.message);
            }
        })
        .catch(error => {
            console.error('Erro ao chamar a API:', error);
        });

    document.addEventListener('click', function(event) {
        if (event.target.closest('.btn-warning')) {
            const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
            document.getElementById('confirmModal').removeAttribute("aria-hidden");
            modal.show();
        }
    });

    document.getElementById('confirmStartButton').addEventListener('click', async function() {
        let ordemFoiIniciada = await confirmarInicioOrdem(ordemId);
        console.log(ordemFoiIniciada);

        if (ordemFoiIniciada){
            window.location.href = "/montagem/";
        }
    });

});