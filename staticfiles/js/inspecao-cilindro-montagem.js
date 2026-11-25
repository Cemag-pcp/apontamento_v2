// Inspeção de estanqueidade da célula CILINDRO. No lugar de enviar a finalização direto,
// a tela abre este modal e o envio grava apontamento + inspeção juntos no backend.
// Peça, inspetor e quantidade não são editáveis: vêm da ordem, do operador e da quantidade
// realizada na finalização (o backend usa os da ordem/apontamento, não os da tela).

const URL_FINALIZAR_CILINDRO = '/montagem/api/ordens/finalizar-cilindro/';

export function isCelulaCilindro(maquina) {
    return String(maquina || '').trim().toLowerCase() === 'cilindro';
}

let contexto = null; // { apontamento, onVoltar, onSucesso }

function csrfToken() {
    const input = document.querySelector('#formInspecaoCilindro [name=csrfmiddlewaretoken]');
    if (input) return input.value;
    const cookie = document.cookie.split('; ').find(c => c.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
}

function modalEl() {
    return document.getElementById('modalInspecaoCilindro');
}

function listaCausas() {
    return document.getElementById('listaCausasInspecaoCilindro');
}

function renumerarCausas() {
    listaCausas().querySelectorAll('.causa-cilindro').forEach((bloco, i) => {
        bloco.querySelector('.numero-causa').textContent = `Não conformidade ${i + 1}`;
    });
}

function adicionarCausa() {
    const template = document.getElementById('templateCausaCilindro');
    listaCausas().appendChild(template.content.cloneNode(true));
    renumerarCausas();
}

function removerCausa() {
    const blocos = listaCausas().querySelectorAll('.causa-cilindro');
    if (blocos.length > 1) {
        blocos[blocos.length - 1].remove();
    }
}

// Causas só aparecem quando há não conformidade
function atualizarVisibilidadeCausas() {
    const nc = parseInt(document.getElementById('ncInspecaoCilindro').value, 10) || 0;
    document.getElementById('causasInspecaoCilindro').classList.toggle('d-none', nc <= 0);
    if (nc > 0 && !listaCausas().children.length) {
        adicionarCausa();
    }
}

// Os modais de finalizar (e de confirmação, no "finalizar e continuar") ainda estão fechando
// quando este abre; abrir antes deles terminarem deixa backdrop/scroll do body quebrados.
// O Bootstrap tira a classe .show no início do hide(); quem ainda está fechando segue com display:block.
function mostrarQuandoOutrosModaisFecharem(alvo) {
    const abertos = Array.from(document.querySelectorAll('.modal'))
        .filter(m => m !== alvo && (m.classList.contains('show') || m.style.display === 'block'));
    let pendentes = abertos.length;
    const mostrar = () => bootstrap.Modal.getOrCreateInstance(alvo).show();
    if (!pendentes) {
        mostrar();
        return;
    }
    abertos.forEach(m => m.addEventListener('hidden.bs.modal', () => {
        if (--pendentes === 0) mostrar();
    }, { once: true }));
}

/**
 * Abre a inspeção no lugar da finalização.
 * apontamento: payload que iria para atualizar-status (status "finalizada", ordem_id, ...)
 * peca / operador: texto exibido (somente leitura)
 * onVoltar(): volta ao modal de finalizar sem gravar nada
 * onSucesso(data): resposta da finalização (mesma de atualizar-status)
 */
export function abrirInspecaoCilindro({ apontamento, peca, operador, onVoltar, onSucesso }) {
    const form = document.getElementById('formInspecaoCilindro');
    if (!form) return;

    contexto = { apontamento, onVoltar, onSucesso };
    form.reset();
    listaCausas().innerHTML = '';
    document.getElementById('pecaInspecaoCilindro').value = peca || '';
    document.getElementById('operadorInspecaoCilindro').value = operador || '';
    document.getElementById('qtdInspecaoCilindro').value = apontamento.qt_realizada || '';
    document.getElementById('ncInspecaoCilindro').value = 0;
    atualizarVisibilidadeCausas();

    mostrarQuandoOutrosModaisFecharem(modalEl());
}

function validar() {
    const qtd = parseInt(contexto.apontamento.qt_realizada, 10);
    const nc = parseInt(document.getElementById('ncInspecaoCilindro').value, 10);

    if (!(nc >= 0)) return 'Informe as peças não conformes (0 se não houver).';
    if (nc > qtd) return 'As peças não conformes não podem passar da quantidade inspecionada.';

    if (nc > 0) {
        let soma = 0;
        const blocos = listaCausas().querySelectorAll('.causa-cilindro');
        for (const [i, bloco] of Array.from(blocos).entries()) {
            if (!bloco.querySelector('input[type=checkbox]:checked')) {
                return `Marque pelo menos uma causa na Não conformidade ${i + 1}.`;
            }
            const quantidade = parseInt(bloco.querySelector('.quantidade-causa').value, 10);
            if (!(quantidade >= 1)) return `Informe a quantidade da Não conformidade ${i + 1}.`;
            soma += quantidade;
        }
        if (soma !== nc) {
            return `A soma das quantidades (${soma}) deve ser igual às peças não conformes (${nc}).`;
        }
    }
    return null;
}

function montarFormData() {
    const nc = parseInt(document.getElementById('ncInspecaoCilindro').value, 10) || 0;
    const formData = new FormData();
    formData.append('apontamento', JSON.stringify(contexto.apontamento));
    formData.append('nao_conformidade', nc);
    formData.append('observacao', document.getElementById('obsInspecaoCilindro').value);

    const ficha = document.getElementById('fichaInspecaoCilindro').files[0];
    if (ficha) formData.append('ficha_inspecao', ficha);

    const blocos = nc > 0 ? listaCausas().querySelectorAll('.causa-cilindro') : [];
    blocos.forEach((bloco, i) => {
        const n = i + 1;
        bloco.querySelectorAll('input[type=checkbox]:checked').forEach(cb => formData.append(`causas_${n}`, cb.value));
        formData.append(`quantidade_${n}`, bloco.querySelector('.quantidade-causa').value);
        Array.from(bloco.querySelector('.imagens-causa').files).forEach(file => formData.append(`imagens_${n}`, file));
    });
    formData.append('quantidade-total-causas', blocos.length);
    return formData;
}

function enviar(event) {
    event.preventDefault();
    if (!contexto) return;

    const erro = validar();
    if (erro) {
        Swal.fire({ icon: 'warning', title: 'Atenção', text: erro });
        return;
    }

    const botao = document.getElementById('salvarInspecaoCilindro');
    const botaoVoltar = document.getElementById('voltarInspecaoCilindro');
    botao.disabled = true;
    botaoVoltar.disabled = true;
    botao.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Finalizando...';

    fetch(URL_FINALIZAR_CILINDRO, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body: montarFormData(),
    })
        .then(response => {
            if (response.status === 401) {
                window.location.href = `/core/login/?next=${encodeURIComponent(window.location.pathname)}`;
                throw new Error('Sessão expirada.');
            }
            return response.json().catch(() => ({})).then(data => {
                if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);
                return data;
            });
        })
        .then(data => {
            const { onSucesso } = contexto;
            contexto = null;
            bootstrap.Modal.getInstance(modalEl())?.hide();
            onSucesso?.(data);
        })
        .catch(error => {
            // Nada foi gravado (inspeção e finalização são desfeitas juntas): continua no modal
            Swal.fire({ icon: 'error', title: 'Não foi possível finalizar', text: error.message });
        })
        .finally(() => {
            botao.disabled = false;
            botaoVoltar.disabled = false;
            botao.textContent = 'Finalizar e inspecionar';
        });
}

function voltar() {
    const { onVoltar } = contexto || {};
    contexto = null;
    const instancia = bootstrap.Modal.getInstance(modalEl());
    if (!instancia) return;
    modalEl().addEventListener('hidden.bs.modal', () => onVoltar?.(), { once: true });
    instancia.hide();
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formInspecaoCilindro');
    if (!form) return;
    form.addEventListener('submit', enviar);
    document.getElementById('voltarInspecaoCilindro').addEventListener('click', voltar);
    document.getElementById('ncInspecaoCilindro').addEventListener('input', atualizarVisibilidadeCausas);
    document.getElementById('adicionarCausaCilindro').addEventListener('click', adicionarCausa);
    document.getElementById('removerCausaCilindro').addEventListener('click', removerCausa);
});
