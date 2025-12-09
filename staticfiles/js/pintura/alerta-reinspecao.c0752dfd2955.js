function verificarPendenciasInspecao() {
    fetch('/inspecao/api/alerta-itens-pintura/')
        .then(response => response.json())
        .then(data => {
            const alertDiv = document.getElementById('alerta-reinspecao');
            if (!alertDiv) return;  // Se não encontrar o elemento, encerra
            
            const total = data.finalizados_nao_reinspecionados + data.em_processo_e_retrabalhar;
            
            if (total > 0) {
                // Atualiza totais
                document.getElementById('total-pendencias').textContent = `${total} itens`;
                
                // Controle de exibição condicional
                const showInspetor = data.finalizados_nao_reinspecionados > 0;
                const showSupervisor = data.em_processo_e_retrabalhar > 0;
                
                const pInspetor = document.getElementById('p-inspetor');
                const pSupervisor = document.getElementById('p-supervisor');
                
                pInspetor.style.display = showInspetor ? 'block' : 'none';
                pSupervisor.style.display = showSupervisor ? 'block' : 'none';
                
                if (showInspetor) {
                    document.getElementById('aguardando-reinspecao').textContent = 
                        `${data.finalizados_nao_reinspecionados} itens`;
                }
                
                if (showSupervisor) {
                    document.getElementById('pendentes-retrabalho').textContent = 
                        `${data.em_processo_e_retrabalhar} itens`;
                }
                
                alertDiv.style.display = 'block';
            } else {
                alertDiv.style.display = 'none';
            }
        })
        .catch(error => console.error('Erro ao verificar pendências:', error));
}

// Uso padrão quando o DOM carrega
document.addEventListener('DOMContentLoaded', verificarPendenciasInspecao);