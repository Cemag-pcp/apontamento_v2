import { resetarCardsInicial } from './ordem-criada-pintura.js';

/**
 * Módulo para gerenciar a visualização em cards dos programas de pintura
 * Mostra programas com suas respectivas peças, cores e status
 */

// Cores disponíveis para a flag dos cards
const CORES_BADGE = {
    'Cinza': '#9e9e9e',
    'Amarelo': '#ffc107',
    'Vermelho': '#f44336',
    'Azul': '#2196f3',
    'Verde': '#4caf50',
    'Laranja': '#ff9800'
};

// Cores de prioridade
const PRIORIDADE_CORES = {
    'alto': 'danger',
    'médio': 'warning',
    'baixo': 'secondary'
};

/**
 * Carrega e exibe os programas em formato de cards
 * @param {Object} filtros - Filtros para buscar programas (data_inicial, data_final, tipo_tinta, cor)
 */
export const carregarProgramasCards = async (filtros = {}) => {
    const container = document.getElementById('cards-container');
    
    if (!container) {
        console.error('Container de cards não encontrado');
        return;
    }

    // Mostrar loading
    container.innerHTML = `
        <div class="col-12 text-center py-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            <p class="mt-3 text-muted">Carregando programas...</p>
        </div>
    `;

    try {
        // Construir URL com parâmetros
        const params = new URLSearchParams();
        if (filtros.data_inicial) params.append('data_inicial', filtros.data_inicial);
        if (filtros.data_final) params.append('data_final', filtros.data_final);
        if (filtros.tipo_tinta) params.append('tipo_tinta', filtros.tipo_tinta);
        if (filtros.cor) params.append('cor', filtros.cor);

        const response = await fetch(`/pintura/api/listar-programas/`);
        
        if (!response.ok) {
            throw new Error('Erro ao buscar programas');
        }

        const data = await response.json();
        
        if (data.sucesso && data.programas.length > 0) {
            renderizarCards(data.programas, container);
        } else {
            container.innerHTML = `
                <div class="col-12 text-center text-muted py-5">
                    <i class="fas fa-inbox fa-3x mb-3"></i>
                    <p>Nenhum programa encontrado</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Erro ao carregar programas:', error);
        container.innerHTML = `
            <div class="col-12 text-center text-danger py-5">
                <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                <p>Erro ao carregar programas. Tente novamente.</p>
            </div>
        `;
    }
};

/**
 * Renderiza os cards de programas no container
 * @param {Array} programas - Lista de programas
 * @param {HTMLElement} container - Container onde os cards serão renderizados
 */
const renderizarCards = (programas, container) => {
    container.innerHTML = '';

    programas.forEach(programa => {
        const card = criarCardPrograma(programa);
        container.appendChild(card);
    });
};

/**
 * Cria um card para um programa específico
 * @param {Object} programa - Dados do programa
 * @returns {HTMLElement} - Elemento div do card
 */
const criarCardPrograma = (programa) => {
    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6';

    const corBadge = CORES_BADGE[programa.cor] || '#999';
    const textColor = (programa.cor === 'Amarelo' || programa.cor === 'Cinza') ? '#212529' : '#ffffff';
    
    // Formatar número do programa com zeros à esquerda
    const numProgramaFormatado = String(programa.num_programa).padStart(3, '0');

    // Lista mínima: peça + quantidade
    const listaPecas = programa.pecas.map(peca => `
        <li class="list-group-item d-flex justify-content-between align-items-center peca-item">
            <div style="flex-grow: 1;">
                <div class="peca-codigo">${peca.peca_codigo}</div>
                <small class="text-muted" style="font-size: 0.75rem;"><i class="far fa-calendar me-1"></i>${peca.data_carga || ''}</small>
            </div>
            <span class="badge bg-dark rounded-pill">${peca.quantidade}</span>
        </li>
    `).join('');

    col.innerHTML = `
        <div class="card minimal-card shadow-sm" style="border-left: 8px solid ${corBadge}; position: relative;">
            <button class="btn btn-link btn-sm position-absolute top-0 end-0 mt-2 me-2 p-0 text-danger" onclick="deletarPrograma(${programa.id}, event)" style="background: none; border: none; z-index: 10;" title="Deletar programa">
                <i class="fas fa-trash-alt"></i>
            </button>
            <div class="card-body py-2">
                <div class="mb-2">
                    <h6 class="mb-1 text-dark">#${numProgramaFormatado}</h6>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="badge color-label" style="background-color: ${corBadge}; color: ${textColor};">${programa.cor}</span>
                    <span class="badge ${programa.tipo_tinta === 'PÓ' ? 'bg-info' : 'bg-success'}">${programa.tipo_tinta}</span>
                </div>
                <div class="mb-2">
                    <small class="text-muted"><i class="far fa-calendar me-1"></i>Planejado: ${programa.data_planejada}</small>
                </div>
                <div class="mb-2">
                    <small class="text-muted"><i class="far fa-clock me-1"></i>Criado: ${programa.data_criacao}</small>
                </div>
                <div class="pecas-list" style="max-height: 260px; overflow-y: auto;">
                    <ul class="list-group list-group-flush">
                        ${listaPecas}
                    </ul>
                </div>
            </div>
            <div class="card-footer bg-transparent border-top py-2">
                <button class="btn btn-success btn-sm w-100" onclick='iniciarPrograma(${programa.id}, "${programa.tipo_tinta}", "${programa.cor}", ${JSON.stringify(programa.pecas)}, this)'>
                    <i class="fas fa-play me-2"></i>Iniciar
                </button>
            </div>
        </div>
    `;

    return col;
};

/**
 * Retorna badge HTML para status de peça
 * @param {string} status - Status da peça
 * @returns {string} - HTML do badge
 */
const getStatusBadge = (status) => {
    const badges = {
        'programada': '<span class="badge bg-secondary">Programada</span>',
        'em processo': '<span class="badge bg-warning text-dark">Em Processo</span>',
        'finalizada': '<span class="badge bg-success">Finalizada</span>'
    };
    return badges[status] || '<span class="badge bg-light text-dark">Desconhecido</span>';
};

/**
 * Funções globais para ações dos cards
 */
window.visualizarPrograma = (programaId) => {
    console.log('Visualizar programa:', programaId);
    // Implementar lógica de visualização
    alert(`Visualizar programa #${programaId}`);
};

window.iniciarPrograma = async (programaId, tipoPintura, cor, pecas, btn) => {
    console.log('Iniciar programa:', programaId, tipoPintura, cor, pecas);

    const button = btn instanceof HTMLElement ? btn : null;
    const originalBtnText = button ? button.innerHTML : '';
    
    // Desabilitar todos os botões "Iniciar"
    const allIniciarButtons = document.querySelectorAll('.btn.btn-success.btn-sm');
    allIniciarButtons.forEach(btn => {
        btn.disabled = true;
    });
    
    if (button) {
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Carregando...';
    }

    try {
        // Atualizar status do programa para 'finalizada'
        // try {
        //     const response = await fetch('/pintura/api/iniciar-programa/', {
        //         method: 'POST',
        //         headers: {
        //             'Content-Type': 'application/json',
        //         },
        //         body: JSON.stringify({ programa_id: programaId })
        //     });
            
        //     if (!response.ok) {
        //         console.error('Erro ao iniciar programa');
        //     }
        // } catch (error) {
        //     console.error('Erro ao atualizar status do programa:', error);
        // }
        
        // Preencher o campo de tipo de pintura
        const selectTipoPintura = document.getElementById('tipoPintura');
        if (selectTipoPintura && tipoPintura) {
            selectTipoPintura.value = tipoPintura;
            // Disparar evento change para atualizar cambões disponíveis
            selectTipoPintura.dispatchEvent(new Event('change'));
        }
        
        // Preencher a cor selecionada
        const spanCorCambao = document.getElementById('corCambao');
        if (spanCorCambao && cor) {
            spanCorCambao.textContent = cor;
        }
        
        // Carregar operadores
        const selectOperador = document.getElementById('operadorInicial');
        if (selectOperador) {
            try {
                const response = await fetch('/pintura/api/listar-operadores/');
                if (response.ok) {
                    const data = await response.json();
                    selectOperador.innerHTML = '<option value="" disabled selected>Selecione um operador...</option>';
                    if (data.operadores && data.operadores.length > 0) {
                        data.operadores.forEach(op => {
                            const option = document.createElement('option');
                            option.value = op.id;
                            option.textContent = op.nome;
                            selectOperador.appendChild(option);
                        });
                    }
                }
            } catch (error) {
                console.error('Erro ao carregar operadores:', error);
            }
        }
        
        // Preencher a tabela com as peças
        const tabelaCambao = document.getElementById('tabelaCambao');
        if (tabelaCambao && pecas && pecas.length > 0) {
            tabelaCambao.innerHTML = '';
            pecas.forEach(peca => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${peca.ordem || ''}</td>
                    <td>${peca.peca_codigo}</td>
                    <td>${peca.quantidade}</td>
                `;
                tabelaCambao.appendChild(tr);
            });
        }
        
        // Preparar dados para o botão de confirmar
        const btnConfirmar = document.getElementById('confirmarCriacaoCambao');
        if (btnConfirmar && pecas && pecas.length > 0) {
            const pecaOrdens = pecas.map(p => String(p.peca_ordem_id || '')).filter(id => id);
            const quantidades = pecas.map(p => p.quantidade);
            
            const cambaoData = {
                peca_ordens: pecaOrdens,
                quantidade: quantidades,
                cor: cor
            };
            
            btnConfirmar.setAttribute('data-cambao-data', JSON.stringify(cambaoData));
        }
        
        // Abrir o modal
        const modal = new bootstrap.Modal(document.getElementById('modalCriarCambao'));
        modal.show();
    } catch (error) {
        console.error('Erro ao iniciar programa (geral):', error);
    } finally {
        // Reabilitar todos os botões "Iniciar"
        allIniciarButtons.forEach(btn => {
            btn.disabled = false;
        });
        
        if (button) {
            button.innerHTML = originalBtnText || '<i class="fas fa-play me-2"></i>Iniciar';
        }
    }
};

window.editarPrograma = (programaId) => {
    console.log('Editar programa:', programaId);
    // Implementar lógica de edição
    alert(`Editar programa #${programaId}`);
};

window.deletarPrograma = async (programaId, event) => {
    if (!confirm('Tem certeza que deseja deletar este programa?')) {
        return;
    }
    
    // Encontrar o card do programa
    const button = event ? event.target.closest('button') : null;
    const cardElement = button ? button.closest('.col-lg-4, .col-md-6') : null;
    
    try {
        const response = await fetch('/pintura/api/deletar-programa/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ programa_id: programaId })
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // Remover o card da tela com animação
            if (cardElement) {
                cardElement.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                cardElement.style.opacity = '0';
                cardElement.style.transform = 'scale(0.9)';
                
                setTimeout(() => {
                    cardElement.remove();
                    
                    // Verificar se ainda há cards
                    const container = document.getElementById('cards-container');
                    if (container && container.children.length === 0) {
                        container.innerHTML = `
                            <div class="col-12 text-center text-muted py-5">
                                <i class="fas fa-inbox fa-3x mb-3"></i>
                                <p>Nenhum programa encontrado</p>
                            </div>
                        `;
                    }
                }, 300);
            }
        } else {
            alert('Erro ao deletar programa');
        }
    } catch (error) {
        console.error('Erro ao deletar programa:', error);
        alert('Erro ao deletar programa');
    }
};

// CSS adicional (pode ser movido para arquivo CSS separado)
const style = document.createElement('style');
style.textContent = `
    .minimal-card {
        border-radius: 8px;
    }

    .color-flag {
        position: absolute;
        top: 10px;
        right: 10px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        box-shadow: 0 0 0 2px #ffffff;
    }

    .peca-item {
        font-size: 0.95rem;
        padding-top: 10px;
        padding-bottom: 10px;
    }

    .peca-codigo {
        font-weight: 600;
    }

    .pecas-list {
        scrollbar-width: thin;
        scrollbar-color: #cbd5e0 #f7fafc;
    }
    .pecas-list::-webkit-scrollbar { width: 6px; }
    .pecas-list::-webkit-scrollbar-track { background: #f7fafc; border-radius: 10px; }
    .pecas-list::-webkit-scrollbar-thumb { background: #cbd5e0; border-radius: 10px; }
    .pecas-list::-webkit-scrollbar-thumb:hover { background: #a0aec0; }
`;
document.head.appendChild(style);

// Exportar funções
export default carregarProgramasCards;
