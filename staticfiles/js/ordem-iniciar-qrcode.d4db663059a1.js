document.addEventListener('DOMContentLoaded', function() {
    // Pega a string de parâmetros da URL atual
    const params = new URLSearchParams(window.location.search);

    // Para pegar um parâmetro específico, por exemplo 'ordem_id':
    const ordemId = params.get('ordemId');
    const cardApontamentoQrCode = document.getElementById('cardApontamentoQrCode');

    console.log("Ordem ID:", ordemId);

    fetch(`/montagem/api/apontamento-qrcode/?ordemId=${ordemId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Processar os dados recebidos
                console.log(data);

                const ordem = data.dados;

                cardApontamentoQrCode.innerHTML = `
                    <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center p-3">
                        <h6 class="card-title fw-bold mb-0 fs-5">#${ordem.peca}</h6>
                        <span class="badge bg-secondary">Status: Iniciado</span>
                    </div>
                    <div class="card-body bg-white p-3">
                        <p class="card-text mb-3">
                            <strong>Data Carga:</strong> 23/09/2025
                        </p>
                        <p class="card-text mb-3">
                            <strong>Quantidade a fazer:</strong> 5
                        </p>
                        <p class="card-text mb-3">
                            <strong>Quantidade feita:</strong> 2
                        </p>
                        <p class="card-text mb-0">
                            <strong>Observação:</strong> Sem observações
                        </p>
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
    

});