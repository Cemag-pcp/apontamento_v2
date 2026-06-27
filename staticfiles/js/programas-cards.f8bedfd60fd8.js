import { resetarCardsInicial } from './ordem-criada-pintura.js';

let programaEdicaoAtual = null;
let itensDisponiveisPrograma = [];
let ultimoFiltroCards = {};
let termoBuscaItensPrograma = '';

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
    ultimoFiltroCards = filtros;
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

        const response = await fetch(`/pintura/api/listar-programas/?${params.toString()}`);
        
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

    // Lista mínima: peça + quantidade + lixeira
    const listaPecas = programa.pecas.map((peca, idx) => `
        <li class="list-group-item d-flex justify-content-between align-items-center peca-item" data-programacao-id="${peca.id}">
            <div style="flex-grow: 1;">
                <div class="peca-codigo">${peca.peca_codigo}</div>
                <small class="text-muted" style="font-size: 0.75rem;"><i class="far fa-calendar me-1"></i>${peca.data_carga || ''}</small>
            </div>
            <span class="badge bg-dark rounded-pill">${peca.quantidade}</span>
            <button class="btn btn-link btn-sm text-danger ms-2 p-0 lixeira-peca-btn" title="Remover peça" data-programa-id="${programa.id}" data-peca-idx="${idx}" data-programacao-id="${peca.id}" style="background: none; border: none;">
                <i class="fas fa-trash-alt"></i>
            </button>
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
                <div class="d-flex gap-2">
                    <button class="btn btn-outline-primary btn-sm flex-fill" onclick='editarPrograma(${JSON.stringify(programa)}, this)'>
                        <i class="fas fa-pen me-2"></i>Editar
                    </button>
                    <button class="btn btn-success btn-sm flex-fill" onclick='iniciarPrograma(${programa.id}, "${programa.tipo_tinta}", "${programa.cor}", ${JSON.stringify(programa.pecas)}, this)'>
                        <i class="fas fa-play me-2"></i>Iniciar
                    </button>
                </div>
            </div>
        </div>
    `;

    // Adicionar event listener para lixeiras das peças após renderização
    setTimeout(() => {
        const lixeiraBtns = col.querySelectorAll('.lixeira-peca-btn');
        lixeiraBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const programaId = btn.getAttribute('data-programa-id');
                const pecaIdx = btn.getAttribute('data-peca-idx');
                window.removerPecaDoPrograma(programaId, pecaIdx, btn);
            });
        });
    }, 0);
    return col;
}

// Função global para remover peça do programa
window.removerPecaDoPrograma = async (programaId, pecaIdx, btn) => {
    if (!confirm('Tem certeza que deseja remover esta peça deste programa?')) {
        return;
    }
    // Obter o id da programação (programacao_id) da peça
    const programacaoId = btn.getAttribute('data-programacao-id');
    if (!programacaoId) {
        alert('Não foi possível identificar a peça para remoção.');
        return;
    }
    // Chamar backend para remover
    try {
        const response = await fetch('/pintura/api/remover-peca-programa/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ programacao_id: programacaoId })
        });
        if (response.ok) {
            // Remover visualmente do card
            const li = btn.closest('li');
            if (li) {
                li.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                li.style.opacity = '0';
                li.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    li.remove();
                }, 300);
            }
        } else {
            alert('Erro ao remover peça do backend.');
        }
    } catch (error) {
        alert('Erro ao remover peça: ' + error);
    }
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
const normalizarDataCarga = (dataCarga) => {
    if (!dataCarga) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(dataCarga)) return dataCarga;

    const partes = dataCarga.split('/');
    if (partes.length === 3) {
        const [dia, mes, ano] = partes;
        return `${ano}-${mes.padStart(2, '0')}-${dia.padStart(2, '0')}`;
    }

    return '';
};

const buscarItensDisponiveisPrograma = async (cor, dataCarga) => {
    const params = new URLSearchParams({
        type_template: 'programacao',
        cor: cor || '',
        data_carga: normalizarDataCarga(dataCarga),
    });

    const response = await fetch(`/pintura/api/ordens-criadas/?${params.toString()}`);
    if (!response.ok) {
        throw new Error('Erro ao carregar itens disponiveis');
    }

    const data = await response.json();
    return data.ordens || [];
};

const montarOpcoesSelectItem = (selectedId) => {
    const itensUnicos = new Map();

    itensDisponiveisPrograma.forEach((item) => {
        itensUnicos.set(String(item.peca_ordem_id), item);
    });

    (programaEdicaoAtual?.pecas || []).forEach((item) => {
        const key = String(item.peca_ordem_id);
        if (!itensUnicos.has(key)) {
            itensUnicos.set(key, {
                peca_ordem_id: item.peca_ordem_id,
                peca_codigo: item.peca_codigo,
                ordem: item.ordem,
                qt_restante: 0
            });
        }
    });

    const options = [`<option value="">Selecione...</option>`];
    itensUnicos.forEach((item, key) => {
        const selected = key === String(selectedId) ? 'selected' : '';
        options.push(`<option value="${key}" data-ordem="${item.ordem || ''}" data-codigo="${item.peca_codigo}" data-disponivel="${item.qt_restante || 0}" ${selected}>#${item.ordem || ''} - ${item.peca_codigo}</option>`);
    });

    return options.join('');
};

const atualizarSelectAdicionar = () => {
    const select = document.getElementById('editarProgramaItemSelect');
    if (!select) return;

    select.innerHTML = '<option value="">Selecione um item disponível...</option>';
    itensDisponiveisPrograma.forEach((item) => {
        const option = document.createElement('option');
        option.value = item.peca_ordem_id;
        option.textContent = `#${item.ordem || ''} - ${item.peca_codigo} (${item.qt_restante} disponível)`;
        option.dataset.ordem = item.ordem || '';
        option.dataset.codigo = item.peca_codigo;
        option.dataset.disponivel = item.qt_restante || 0;
        select.appendChild(option);
    });
};

const renderizarTabelaEdicaoPrograma = () => {
    const tbody = document.getElementById('editarProgramaTabelaBody');
    if (!tbody) return;

    if (!programaEdicaoAtual?.pecas?.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Nenhum item no planejamento.</td></tr>';
        return;
    }

    tbody.innerHTML = programaEdicaoAtual.pecas.map((peca, index) => {
        const itemDisponivel = itensDisponiveisPrograma.find((item) => String(item.peca_ordem_id) === String(peca.peca_ordem_id));
        const saldoBase = Number(
            peca.disponivel ?? itemDisponivel?.qt_restante ?? 0
        );
        const saldo = peca.id
            ? saldoBase + Number(peca.quantidade || 0)
            : saldoBase;

        return `
            <tr data-index="${index}">
                <td class="editar-programa-ordem">#${peca.ordem || ''}</td>
                <td><select class="form-select form-select-sm editar-programa-select">${montarOpcoesSelectItem(peca.peca_ordem_id)}</select></td>
                <td class="editar-programa-disponivel">${saldo}</td>
                <td><input type="number" class="form-control form-control-sm editar-programa-quantidade" min="1" value="${peca.quantidade}"></td>
                <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger editar-programa-remover"><i class="fas fa-trash-alt"></i></button></td>
            </tr>
        `;
    }).join('');

    tbody.querySelectorAll('.editar-programa-select').forEach((select) => {
        select.addEventListener('change', (event) => {
            const row = event.target.closest('tr');
            const index = Number(row.dataset.index);
            const option = event.target.selectedOptions[0];

            programaEdicaoAtual.pecas[index].peca_ordem_id = option.value;
            programaEdicaoAtual.pecas[index].ordem = option.dataset.ordem || '';
            programaEdicaoAtual.pecas[index].peca_codigo = option.dataset.codigo || '';
            programaEdicaoAtual.pecas[index].disponivel = Number(option.dataset.disponivel || 0);
            programaEdicaoAtual.pecas[index].id = null;

            row.querySelector('.editar-programa-ordem').textContent = `#${option.dataset.ordem || ''}`;
            row.querySelector('.editar-programa-disponivel').textContent = option.dataset.disponivel || '0';
        });
    });

    tbody.querySelectorAll('.editar-programa-quantidade').forEach((input) => {
        input.addEventListener('input', (event) => {
            const row = event.target.closest('tr');
            const index = Number(row.dataset.index);
            programaEdicaoAtual.pecas[index].quantidade = event.target.value;
        });
    });

    tbody.querySelectorAll('.editar-programa-remover').forEach((button) => {
        button.addEventListener('click', (event) => {
            const row = event.target.closest('tr');
            const index = Number(row.dataset.index);
            programaEdicaoAtual.pecas.splice(index, 1);
            renderizarTabelaEdicaoPrograma();
        });
    });
};

const abrirModalEdicaoPrograma = async (programa) => {
    programaEdicaoAtual = JSON.parse(JSON.stringify(programa));
    const dataCargaPrograma = programa.pecas?.[0]?.data_carga || '';
    itensDisponiveisPrograma = await buscarItensDisponiveisPrograma(programa.cor, dataCargaPrograma);
    programaEdicaoAtual.pecas = (programaEdicaoAtual.pecas || []).map((peca) => {
        const itemDisponivel = itensDisponiveisPrograma.find((item) => String(item.peca_ordem_id) === String(peca.peca_ordem_id));
        return {
            ...peca,
            disponivel: Number(itemDisponivel?.qt_restante || 0),
        };
    });

    document.getElementById('editarProgramaResumo').textContent = `Programa #${String(programa.num_programa).padStart(3, '0')} | ${programa.cor} | ${programa.tipo_tinta}`;
    document.getElementById('editarProgramaQuantidadeNova').value = 1;
    termoBuscaItensPrograma = '';
    document.getElementById('editarProgramaBuscaItem').value = '';

    atualizarSelectAdicionar();
    renderizarTabelaEdicaoPrograma();

    const modal = new bootstrap.Modal(document.getElementById('modalEditarPrograma'));
    modal.show();
};

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
window.editarPrograma = async (programa) => {
    try {
        await abrirModalEdicaoPrograma(programa);
    } catch (error) {
        console.error('Erro ao abrir ediÃ§Ã£o do programa:', error);
        alert('Erro ao carregar os dados para ediÃ§Ã£o.');
    }
};

document.getElementById('btnAdicionarItemPrograma')?.addEventListener('click', () => {
    if (!programaEdicaoAtual) return;

    const select = document.getElementById('editarProgramaItemSelect');
    const quantidadeInput = document.getElementById('editarProgramaQuantidadeNova');
    const option = select?.selectedOptions?.[0];
    const quantidade = Number(quantidadeInput?.value || 0);

    if (!option || !option.value) {
        alert('Selecione um item para adicionar.');
        return;
    }

    if (!quantidade || quantidade <= 0) {
        alert('Informe uma quantidade vÃ¡lida.');
        return;
    }

    const itemExistente = programaEdicaoAtual.pecas.find(
        (item) => String(item.peca_ordem_id) === String(option.value)
    );

    if (itemExistente) {
        itemExistente.quantidade = Number(itemExistente.quantidade || 0) + quantidade;
    } else {
        programaEdicaoAtual.pecas.push({
            id: null,
            peca_ordem_id: option.value,
            ordem: option.dataset.ordem || '',
            peca_codigo: option.dataset.codigo || '',
            disponivel: Number(option.dataset.disponivel || 0),
            quantidade
        });
    }

    quantidadeInput.value = 1;
    select.value = '';
    renderizarTabelaEdicaoPrograma();
});

document.getElementById('btnSalvarEdicaoPrograma')?.addEventListener('click', async () => {
    if (!programaEdicaoAtual) return;

    const itens = (programaEdicaoAtual.pecas || []).map((item) => ({
        id: item.id || undefined,
        peca_ordem_id: item.peca_ordem_id,
        quantidade: Number(item.quantidade)
    }));

    if (!itens.length) {
        alert('O programa precisa ter pelo menos um item.');
        return;
    }

    if (itens.some((item) => !item.peca_ordem_id || !item.quantidade || item.quantidade <= 0)) {
        alert('Revise conjunto e quantidade de todos os itens antes de salvar.');
        return;
    }

    const botaoSalvar = document.getElementById('btnSalvarEdicaoPrograma');
    const textoOriginal = botaoSalvar.innerHTML;
    botaoSalvar.disabled = true;
    botaoSalvar.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Salvando...';

    try {
        const response = await fetch('/pintura/api/editar-programa/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                programa_id: programaEdicaoAtual.id,
                itens
            })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Erro ao salvar programa');
        }

        const modalElement = document.getElementById('modalEditarPrograma');
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        modalInstance?.hide();

        const cardsTabAtiva = document.getElementById('cards-tab');
        if (cardsTabAtiva?.classList.contains('active')) {
            carregarProgramasCards(ultimoFiltroCards);
        }
    } catch (error) {
        console.error('Erro ao salvar ediÃ§Ã£o do programa:', error);
        alert(error.message || 'Erro ao salvar programa.');
    } finally {
        botaoSalvar.disabled = false;
        botaoSalvar.innerHTML = textoOriginal;
    }
});

document.getElementById('editarProgramaBuscaItem')?.addEventListener('input', (event) => {
    termoBuscaItensPrograma = event.target.value || '';

    const select = document.getElementById('editarProgramaItemSelect');
    if (!select) return;

    const termo = termoBuscaItensPrograma.trim().toLowerCase();
    select.innerHTML = '<option value="">Selecione um item disponivel...</option>';

    itensDisponiveisPrograma.forEach((item) => {
        const textoBusca = `#${item.ordem || ''} ${item.peca_codigo || ''}`.toLowerCase();
        if (termo && !textoBusca.includes(termo)) return;

        const option = document.createElement('option');
        option.value = item.peca_ordem_id;
        option.textContent = `#${item.ordem || ''} - ${item.peca_codigo} (${item.qt_restante} disponivel)`;
        option.dataset.ordem = item.ordem || '';
        option.dataset.codigo = item.peca_codigo;
        option.dataset.disponivel = item.qt_restante || 0;
        select.appendChild(option);
    });
});

export default carregarProgramasCards;
