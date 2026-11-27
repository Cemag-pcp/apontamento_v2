// Inspeção obrigatória ao finalizar uma ordem da serra ou da usinagem.
//
// Ao finalizar, o servidor devolve as inspeções pendentes do lote final (na
// serra pode haver uma por peça da ordem). O modal de inspeção
// (form-inspecao-serra-usinagem.js) abre na própria tela de apontamento, sem
// opção de fechar, uma inspeção depois da outra. Só sai da fila quando o
// servidor marca a inspeção como finalizada (amostras suficientes); se faltar
// amostra, o modal reabre na mesma inspeção.
//
// A fila fica guardada no navegador: se a página recarregar antes do envio, as
// inspeções que continuam pendentes no servidor são reabertas.
(function () {
    const modalEl = document.getElementById('inspectionModal');
    if (!modalEl || modalEl.dataset.modo !== 'operador') return;

    const CHAVE = `${modalEl.dataset.setor || 'serra_usinagem'}_inspecao_obrigatoria`;
    let aoConcluir = null;

    function lerFila() {
        try {
            const fila = JSON.parse(localStorage.getItem(CHAVE) || '[]');
            return Array.isArray(fila) ? fila.filter((i) => i && i.id) : [];
        } catch (e) {
            localStorage.removeItem(CHAVE);
            return [];
        }
    }

    function gravarFila(fila) {
        if (fila.length) {
            localStorage.setItem(CHAVE, JSON.stringify(fila));
        } else {
            localStorage.removeItem(CHAVE);
        }
    }

    // Executa depois que o modal terminar de fechar (o envio chama hide())
    function depoisDeFechar(fn) {
        if (modalEl.classList.contains('show')) {
            modalEl.addEventListener('hidden.bs.modal', () => fn(), { once: true });
        } else {
            fn();
        }
    }

    // O operador só inspeciona o processo do próprio setor: serra -> "Inspeção
    // Serra", usinagem -> "Inspeção Usinagem". Esse fica marcado e travado; os
    // outros ficam desabilitados (o change monta a tabela de medição).
    function marcarInspecaoDoSetor() {
        modalEl.querySelectorAll('.inspection-checkbox').forEach((checkbox) => {
            const tipo = checkbox.id.replace('checkbox-inspecao-', '');
            if (tipo === modalEl.dataset.setor) {
                if (!checkbox.checked) {
                    checkbox.checked = true;
                    checkbox.dispatchEvent(new Event('change'));
                }
            } else if (!checkbox.checked) {
                // Tipo já medido pelo inspetor durante a produção continua como veio
                checkbox.disabled = true;
            }
        });
        // Desmarcar o do setor apagaria a tabela: trava depois do change
        const doSetor = document.getElementById(`checkbox-inspecao-${modalEl.dataset.setor}`);
        if (doSetor) doSetor.disabled = true;
    }

    function abrirPrimeira() {
        const fila = lerFila();
        if (!fila.length) return;
        const atual = fila[0];

        if (typeof abrirModalInspecaoSerraUsinagem !== 'function') {
            console.error('Modal de inspeção não carregado.');
            return;
        }

        abrirModalInspecaoSerraUsinagem(atual).then(() => {
            marcarInspecaoDoSetor();
            const titulo = document.getElementById('inspectionModalLabel');
            if (!titulo) return;
            const numero = atual.ordem_numero ?? atual.ordem_id;
            const posicao = fila.length > 1 ? ` (1 de ${fila.length})` : '';
            titulo.textContent = numero
                ? `Inspeção da ordem #${numero}${posicao}`
                : `Inspeção serra-usinagem${posicao}`;
        });
    }

    function concluir() {
        Swal.fire({
            icon: 'success',
            title: 'Inspeção registrada',
            text: 'Ordem finalizada e inspeção registrada com sucesso.',
            timer: 3000,
            showConfirmButton: false,
        }).then(() => {
            const fn = aoConcluir;
            aoConcluir = null;
            if (typeof fn === 'function') fn();
        });
    }

    // Chamado pelo fluxo de finalizar (ordem-criada-serra-v2.js / ordem-criada-usinagem.js).
    // Retorna false quando não há inspeção a fazer.
    window.iniciarInspecaoOperadorSerraUsinagem = function (inspecoes, opcoes = {}) {
        const novas = (inspecoes || []).filter((i) => i && i.id);
        if (!novas.length) return false;
        // Mantém o que já estava pendente e acrescenta as novas, sem repetir
        const fila = lerFila();
        novas.forEach((i) => {
            if (!fila.some((f) => String(f.id) === String(i.id))) fila.push(i);
        });
        gravarFila(fila);
        aoConcluir = opcoes.aoConcluir || null;
        abrirPrimeira();
        return true;
    };

    document.addEventListener('inspecao-serra-usinagem:enviada', (ev) => {
        const detalhe = ev.detail || {};
        let fila = lerFila();

        if (detalhe.finalizada) {
            fila = fila.filter((i) => String(i.id) !== String(detalhe.id));
            gravarFila(fila);
        }

        depoisDeFechar(() => {
            if (fila.length) {
                // Próxima inspeção, ou a mesma se ainda faltam amostras
                setTimeout(abrirPrimeira, 300);
            } else {
                concluir();
            }
        });
    });

    // Reabre as inspeções que ficaram pendentes (página recarregada antes do envio)
    document.addEventListener('DOMContentLoaded', async () => {
        const fila = lerFila();
        if (!fila.length) return;

        const pendentes = [];
        for (const item of fila) {
            try {
                const resp = await fetch(`/inspecao/api/inspecao-operador-serra-usinagem/${encodeURIComponent(item.id)}/`);
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const dados = await resp.json();
                if (dados.pendente) pendentes.push(dados);
            } catch (err) {
                // Sem conexão com o servidor: mantém o que ficou guardado
                console.error('Erro ao consultar inspeção pendente:', err);
                pendentes.push(item);
            }
        }
        gravarFila(pendentes);
        abrirPrimeira();
    });
})();
