// Itens "aguardando confirmação no ERP": o ERP demorou a responder e o
// apontamento pode ter entrado lá. O item fica bloqueado até alguém conferir
// no ERP e escolher "Confirmar que entrou no ERP" ou "Liberar para reenviar".
// Usado pelas telas de apontamento ERP de corte, estamparia, montagem e usinagem.

function escapar(texto) {
    return String(texto ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

export function estaAguardandoErp(row) {
    return Boolean(row?.aguardando_confirmacao_erp) && !row?.apontado;
}

export function badgeAguardandoErp() {
    return '<span class="badge text-bg-warning" title="O ERP demorou a responder; confira no ERP">'
        + '<i class="fas fa-hourglass-half"></i> Aguardando ERP</span>';
}

export function botaoAguardandoErp(rowJsonAttr) {
    return `
        <button type="button"
                class="btn btn-sm btn-warning btn-erp-aguardando"
                title="Aguardando confirmação no ERP: conferir e resolver"
                aria-label="Aguardando confirmação no ERP"
                data-row='${rowJsonAttr}'>
            <i class="fas fa-hourglass-half"></i>
        </button>
    `;
}

// Resposta de erro da API de apontar: o ERP não respondeu a tempo, ou o item
// já estava aguardando confirmação. Mostra o aviso e devolve true.
export function avisarSeAguardandoErp(payload) {
    if (!payload?.aguardando_confirmacao_erp) return false;
    if (window.Swal) {
        Swal.fire({
            icon: 'warning',
            title: 'Confira no ERP',
            text: payload.message || payload.description,
            confirmButtonText: 'Entendi',
        });
    }
    return true;
}

async function enviarResolucao(url, csrfToken, dados) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(dados),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.status !== 'success') {
        throw new Error(payload.message || 'Não foi possível concluir.');
    }
    return payload;
}

// Abre a janela para resolver um item aguardando confirmação.
// opcoes: { resolverUrlTemplate, csrfToken, descricao, onResolvido }
export async function abrirResolverAguardandoErp(row, opcoes) {
    if (!window.Swal || !opcoes?.resolverUrlTemplate || !row?.id) return;
    const url = opcoes.resolverUrlTemplate.replace('/0/', `/${Number(row.id)}/`);

    const escolha = await Swal.fire({
        icon: 'warning',
        title: 'Aguardando confirmação no ERP',
        html: `
            <p class="mb-2">${escapar(opcoes.descricao || '')}</p>
            <p class="mb-2 text-start">O ERP demorou a responder e o apontamento <strong>pode ter sido registrado</strong>.
            Procure este item no ERP antes de escolher:</p>
            <ul class="text-start small mb-2">
                <li><strong>Entrou no ERP:</strong> o item fica como apontado aqui.</li>
                <li><strong>Não entrou:</strong> o item é liberado para apontar de novo.</li>
            </ul>`,
        input: 'text',
        inputLabel: 'Chave do apontamento no ERP (opcional, só se entrou)',
        inputPlaceholder: 'Ex.: chave mostrada no ERP',
        showDenyButton: true,
        showCancelButton: true,
        confirmButtonText: 'Confirmar que entrou no ERP',
        denyButtonText: 'Liberar para reenviar',
        cancelButtonText: 'Fechar',
        confirmButtonColor: '#198754',
        denyButtonColor: '#fd7e14',
    });

    try {
        if (escolha.isConfirmed) {
            await enviarResolucao(url, opcoes.csrfToken, {
                acao: 'confirmar',
                chave_apontamento: (escolha.value || '').trim(),
            });
            Swal.fire({ icon: 'success', title: 'Marcado como apontado', timer: 1500, showConfirmButton: false });
        } else if (escolha.isDenied) {
            const certeza = await Swal.fire({
                icon: 'question',
                title: 'Liberar para reenviar?',
                text: 'Só libere se conferiu que o apontamento NÃO está no ERP. Se estiver, reenviar vai duplicar.',
                showCancelButton: true,
                confirmButtonText: 'Conferi, não está no ERP',
                cancelButtonText: 'Voltar',
                confirmButtonColor: '#fd7e14',
            });
            if (!certeza.isConfirmed) return;
            await enviarResolucao(url, opcoes.csrfToken, { acao: 'liberar' });
            Swal.fire({ icon: 'success', title: 'Liberado para apontar de novo', timer: 1500, showConfirmButton: false });
        } else {
            return;
        }
        await opcoes.onResolvido?.();
    } catch (error) {
        Swal.fire({ icon: 'error', title: 'Erro', text: error.message });
    }
}
