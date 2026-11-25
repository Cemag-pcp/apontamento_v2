// Vários operadores no mesmo apontamento (início na solda, finalização na
// montagem). Os selects de operador continuam como estão (lista da máquina /
// lista geral): cada operador escolhido vira uma etiqueta removível no
// container e o select volta para "Selecione...", pronto para o próximo.

const escolhidosPorContainer = new Map();

function escapar(texto) {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
}

function renderizar(container) {
    const escolhidos = escolhidosPorContainer.get(container.id) || [];
    container.innerHTML = escolhidos.length
        ? escolhidos.map((op) => `
            <span class="badge rounded-pill text-bg-primary d-inline-flex align-items-center gap-1 py-2 px-3 fs-6 fw-normal">
                ${escapar(op.nome)}
                <button type="button" class="btn-close btn-close-white ms-1 remover-operador-escolhido" style="font-size: .6rem;"
                        data-id="${escapar(op.id)}" aria-label="Remover ${escapar(op.nome)}"></button>
            </span>`).join('')
        : '<span class="text-muted small">Nenhum operador escolhido ainda.</span>';
}

// Liga os selects ao container de etiquetas (uma vez por página)
export function ativarVariosOperadores(idsSelects, idContainer) {
    const container = document.getElementById(idContainer);
    if (!container) return;
    escolhidosPorContainer.set(idContainer, []);
    renderizar(container);

    idsSelects.forEach((idSelect) => {
        const select = document.getElementById(idSelect);
        if (!select) return;
        select.addEventListener('change', () => {
            const opcao = select.options[select.selectedIndex];
            if (opcao && opcao.value) adicionarOperador(idContainer, opcao.value, opcao.textContent.trim());
            select.value = '';
        });
    });

    container.addEventListener('click', (event) => {
        const botao = event.target.closest('.remover-operador-escolhido');
        if (!botao) return;
        const lista = escolhidosPorContainer.get(idContainer) || [];
        escolhidosPorContainer.set(idContainer, lista.filter((op) => op.id !== botao.dataset.id));
        renderizar(container);
    });
}

export function adicionarOperador(idContainer, id, nome) {
    const container = document.getElementById(idContainer);
    const lista = escolhidosPorContainer.get(idContainer) || [];
    if (!lista.some((op) => op.id === String(id))) lista.push({ id: String(id), nome });
    escolhidosPorContainer.set(idContainer, lista);
    if (container) renderizar(container);
}

export function operadoresEscolhidos(idContainer) {
    return (escolhidosPorContainer.get(idContainer) || []).map((op) => op.id);
}

export function nomesOperadoresEscolhidos(idContainer) {
    return (escolhidosPorContainer.get(idContainer) || []).map((op) => op.nome);
}

export function limparOperadores(idContainer) {
    escolhidosPorContainer.set(idContainer, []);
    const container = document.getElementById(idContainer);
    if (container) renderizar(container);
}
