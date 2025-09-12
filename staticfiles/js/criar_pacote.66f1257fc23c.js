import { popularPacotesDaCarga } from './carregar_cargas.js';

document.addEventListener('DOMContentLoaded', function () {

    const itensContainer = document.getElementById('itensPacote');
    const btnAdicionar = document.getElementById('btnAdicionarItem');
    const formCriarPacote = document.getElementById('formCriar');
    const btnVoltar = document.getElementById('btnVoltarVisualizarPacote');

    // Adicionar novo item
    btnAdicionar.addEventListener('click', () => {
        const item = document.createElement('div');
        item.className = 'row g-2 align-items-end item-pacote mt-2';
        item.innerHTML = `
            <div class="col-md-8">
                <input type="text" name="descricao[]" class="form-control" placeholder="Descrição do item" required>
            </div>
            <div class="col-md-3">
                <input type="number" name="quantidade[]" class="form-control" placeholder="Qtd" min="1" required>
            </div>
            <div class="col-md-1 text-end">
                <button type="button" class="btn btn-danger btn-sm btnRemoverItem" title="Remover item">✕</button>
            </div>
        `;
        itensContainer.appendChild(item);
    });

    // Remover item
    itensContainer.addEventListener('click', function (e) {
        if (e.target.classList.contains('btnRemoverItem')) {
            const itemRow = e.target.closest('.item-pacote');
            if (itemRow) itemRow.remove();
        }
    });

    // Submeter formulário
    formCriarPacote.addEventListener('submit', async function (e) {
        e.preventDefault();

        const btnFormCriar = document.getElementById('btnFormCriar')
        btnFormCriar.disabled = true;
        btnFormCriar.innerHTML = 'Salvando...'

        const form = e.currentTarget;
        const fd = new FormData(form);

        // Coleta múltiplos valores
        const descricoes  = fd.getAll('descricao[]');    // ["Item A", "Item B", ...]
        const quantidades = fd.getAll('quantidade[]');   // ["2", "5", ...]

        // Monta itens pareando descrição x quantidade
        const itens = descricoes.map((desc, i) => ({
            descricao: (desc || '').trim(),
            quantidade: Number(quantidades[i] || 0)
        }))
        // filtra linhas vazias ou quantidade inválida
        .filter(it => it.descricao && Number.isFinite(it.quantidade) && it.quantidade > 0);

        // Payload final
        const payload = {
            nomePacote: fd.get('nomePacote'),
            observacoesPacote: fd.get('observacoesPacote') || '',
            idCargaPacote: fd.get('idCargaPacote'),
            itens
        };

        console.log('Payload para enviar:', payload);

        // Exemplo de POST em JSON (Django/DRF)
        try {
            const resp = await fetch('api/guardar-pacote/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Se usar CSRF no Django:
                'X-CSRFToken': getCookie('csrftoken')
            },
                body: JSON.stringify(payload)
            });

            if (!resp.ok) {
                const erro = await resp.text();
                console.error('Erro ao salvar pacote:', erro);
                alert('Erro ao salvar o pacote.');
                return;
            }

            // Fecha este modal e abre o visualizar
            const modalCriar = bootstrap.Modal.getInstance(document.getElementById('criarPacoteModal'));
            modalCriar.hide();

            const modalElVisualizarPacotes = document.getElementById('visualizarPacote');
            const modalVisualizarPacotes   = bootstrap.Modal.getInstance(modalElVisualizarPacotes) || new bootstrap.Modal(modalElVisualizarPacotes);
            modalVisualizarPacotes.show();
            const idCargaPacoteEl = document.getElementById('idCargaPacote');

            popularPacotesDaCarga(idCargaPacoteEl.value);

            btnFormCriar.disabled = false;
            btnFormCriar.innerHTML = 'Salvar'

        } catch (err) {
            console.error(err);
            alert('Falha na comunicação com o servidor.');
        }
    });

    // Botão voltar (sem salvar, só troca os modais)
    btnVoltar.addEventListener('click', function () {
        const modalCriar = bootstrap.Modal.getInstance(document.getElementById('criarPacoteModal'));
        const modalVisualizar = new bootstrap.Modal(document.getElementById('visualizarPacote'));
        modalCriar.hide();
        setTimeout(() => modalVisualizar.show(), 300);
    });
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
