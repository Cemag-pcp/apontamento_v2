// Inspeção obrigatória ao finalizar uma ordem da estamparia.
//
// Ao finalizar, o servidor devolve a inspeção do lote final e o modal de
// inspeção (form-inspecao-estamparia.js) abre na própria tela de apontamento,
// sem opção de fechar. A inspeção pendente fica guardada no navegador: se a
// página recarregar antes do envio, ela é reaberta (enquanto continuar
// pendente no servidor).
(function () {
    const CHAVE = 'estamparia_inspecao_obrigatoria';

    function lerPendente() {
        try {
            return JSON.parse(localStorage.getItem(CHAVE) || 'null');
        } catch (e) {
            localStorage.removeItem(CHAVE);
            return null;
        }
    }

    function abrir(inspecao) {
        if (!inspecao || !inspecao.id) return;
        if (typeof abrirModalInspecaoEstamparia !== 'function') {
            console.error('Modal de inspeção não carregado.');
            return;
        }
        localStorage.setItem(CHAVE, JSON.stringify(inspecao));
        abrirModalInspecaoEstamparia(inspecao);
        const titulo = document.getElementById('inspectionModalLabel');
        if (titulo) {
            const numero = inspecao.ordem_numero ?? inspecao.ordem_id;
            titulo.textContent = numero
                ? `Inspeção da ordem #${numero}`
                : 'Inspeção estamparia';
        }
    }

    // Chamado pelo fluxo de finalizar (ordem-criada-estamparia.js)
    window.iniciarInspecaoOperadorEstamparia = abrir;

    document.addEventListener('inspecao-estamparia:enviada', (ev) => {
        localStorage.removeItem(CHAVE);
        Swal.fire({
            icon: ev.detail && ev.detail.jaInspecionado ? 'info' : 'success',
            title: ev.detail && ev.detail.jaInspecionado ? 'Lote já inspecionado' : 'Inspeção registrada',
            text: ev.detail && ev.detail.jaInspecionado
                ? 'Este lote já tinha sido inspecionado.'
                : 'Ordem finalizada e inspeção registrada com sucesso.',
            timer: 3000,
            showConfirmButton: false,
        });
    });

    // Reabre a inspeção que ficou pendente (página recarregada antes do envio)
    document.addEventListener('DOMContentLoaded', async () => {
        const pendente = lerPendente();
        if (!pendente || !pendente.id) return;
        try {
            const resp = await fetch(`/estamparia/api/inspecao-operador/${encodeURIComponent(pendente.id)}/`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const dados = await resp.json();
            if (dados.pendente) {
                abrir(dados);
            } else {
                localStorage.removeItem(CHAVE);
            }
        } catch (err) {
            // Sem conexão com o servidor: reabre com o que ficou guardado
            console.error('Erro ao consultar inspeção pendente:', err);
            abrir(pendente);
        }
    });
})();
