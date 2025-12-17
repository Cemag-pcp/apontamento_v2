import { popularPacotesDaCarga } from './carregar_cargas.js';
import { atualizarSlotAvancar } from './kanbans.js';


document.addEventListener('DOMContentLoaded', function () {
    const itensContainer  = document.getElementById('itensPacote');
    const btnAdicionar    = document.getElementById('btnAdicionarItem');
    const formCriarPacote = document.getElementById('formCriar');
    const btnVoltar       = document.getElementById('btnVoltarVisualizarPacote');

    // invalida cache para um carregamento específico
    function invalidatePendencias(carregamentoId) {
        if (pendenciasCache.has(carregamentoId)) pendenciasCache.delete(carregamentoId);
    }

    // --- Util: CSRF (se já tiver essa função em outro lugar, pode remover daqui)
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    // --- Cache simples por carregamento_id
    const pendenciasCache = new Map();

    // agora aceita { refresh } para forçar refetch
    async function carregarPendencias(carregamentoId, { refresh = false } = {}) {
        if (!carregamentoId) throw new Error('id de carregamento não informado.');

        if (!refresh && pendenciasCache.has(carregamentoId)) {
            return pendenciasCache.get(carregamentoId);
        }

        const resp = await fetch(`api/pendencias/${encodeURIComponent(carregamentoId)}/`, {
            headers: { 'Accept': 'application/json' }
        });
        if (!resp.ok) {
            const txt = await resp.text();
            throw new Error(`Falha ao carregar pendências (${resp.status}): ${txt}`);
        }

        const json = await resp.json();
        const itens = Array.isArray(json?.itens) ? json.itens : [];
        pendenciasCache.set(carregamentoId, itens); // grava o NOVO estado
        return itens;
    }

    // Cria DOM de uma linha
    function criarRowItem() {
        const row = document.createElement('div');
        row.className = 'row g-2 align-items-end item-pacote mt-2';
        row.innerHTML = `
        <div class="col-md-8">
            <select name="pendencia_id[]" class="form-select campo-item" required></select>
        </div>
        <div class="col-md-3">
            <input type="number" name="quantidade[]" class="form-control" placeholder="Qtd" min="1" required>
        </div>
        <div class="col-md-1 text-end">
            <button type="button" class="btn btn-danger btn-sm btnRemoverItem" title="Remover item">✕</button>
        </div>
        `;

        // Remover linha (destrói Select2 antes)
        row.querySelector('.btnRemoverItem').addEventListener('click', () => {
            const select = row.querySelector('.campo-item');
            if (select && $(select).data('select2')) $(select).select2('destroy');
            row.remove();
        });

        return row;
    }

    // Inicializa Select2 com dados pré-carregados
    function initSelect2Local(selectEl, itens) {
        if (!selectEl) return;

        // 1) destrói se já estiver inicializado
        if (window.$ && $(selectEl).data('select2')) {
            $(selectEl).select2('destroy');
        }

        // 2) mapeia dados
        const data = (itens || []).map(it => ({
            id: it.id,                                   // se quiser enviar 'codigo', troque para it.codigo
            text: `${it.codigo} — ${it.descricao}`,
            item: it
        }));

        // 3) parent = a própria linha do item (garante posicionamento correto)
        const $dropdownParent =
            $(selectEl).closest('.item-pacote').length
            ? $(selectEl).closest('.item-pacote')
            : $(selectEl).closest('.modal').length
                ? $(selectEl).closest('.modal')
                : $(document.body);

        // 4) inicializa
        $(selectEl).select2({
            data,
            width: '100%',
            placeholder: 'Selecione um item…',
            allowClear: true,
            dropdownParent: $dropdownParent,
            minimumResultsForSearch: 5,
            // evita “pular” ao rolar
            dropdownAutoWidth: true,
            // renderização
            templateResult: (opt) => {
            if (!opt.id) return opt.text;
            const it = opt.item;
            const $wrap = $(`
                <div>
                <div><strong>${it.codigo}</strong> — ${it.descricao}</div>
                <small class="text-muted">
                    Carreta: ${it.carreta || '-'} &nbsp;|&nbsp; Necessária: ${it.qt_necessaria ?? '-'}
                </small>
                </div>
            `);
            return $wrap;
            },
            templateSelection: (opt) => opt?.text || ''
        });

        // 5) fecha outros dropdowns quando este abrir (higiene)
        $(selectEl).on('select2:opening', function () {
            $('.campo-item').not(this).each(function () {
            if ($(this).data('select2')) $(this).select2('close');
            });
        });
    }
    
    // Clique: adicionar linha + carregar pendências + Select2
    btnAdicionar.addEventListener('click', async () => {
        const idCarga = document.getElementById('idCargaPacote')?.value;
        if (!idCarga) {
            alert('Selecione/defina a Carga antes de adicionar itens.');
            return;
        }

        const row = criarRowItem();
        
        const selectEl = row.querySelector('.campo-item');
        
        btnAdicionar.innerHTML = 'aguarde...';
        btnAdicionar.disabled = true;

        try {
            const itens = await carregarPendencias(idCarga);
            initSelect2Local(selectEl, itens);
            itensContainer.appendChild(row);
            btnAdicionar.innerHTML = 'Adicionar Item';
            btnAdicionar.disabled = false;

        } catch (err) {
            console.error(err);
            alert('Não foi possível carregar as pendências. Tente novamente.');
            if ($(selectEl).data('select2')) $(selectEl).select2('destroy');
            row.remove();
            btnAdicionar.innerHTML = 'Adicionar Item';
            btnAdicionar.disabled = false;

        }
    });

    // Remover item (delegação — mantém compatibilidade com seu padrão)
    itensContainer.addEventListener('click', function (e) {
        if (e.target.classList.contains('btnRemoverItem')) {
            const itemRow = e.target.closest('.item-pacote');
            if (itemRow) {
                const select = itemRow.querySelector('.campo-item');
                if (select && $(select).data('select2')) $(select).select2('destroy');
                itemRow.remove();
            }
        }
    });

    // Submeter formulário
    formCriarPacote.addEventListener('submit', async function (e) {
        e.preventDefault();

        const btnFormCriar = document.getElementById('btnFormCriar');
        btnFormCriar.disabled = true;
        btnFormCriar.innerHTML = 'Salvando...';

        // Helper seguro para extrair meta do select (com ou sem Select2)
        function getMetaDoSelect(selectEl) {
            if (!selectEl) return {};

            // Preferir dados do Select2 (quando disponível)
            try {
            const hasS2 = !!$(selectEl).data('select2');
            if (hasS2) {
                const s2Data = $(selectEl).select2('data');
                const first = Array.isArray(s2Data) ? s2Data[0] : null;
                const item = first && first.item ? first.item : null;
                if (item) {
                return {
                    codigo: item.codigo ?? null,
                    descricao: item.descricao ?? null
                };
                }
            }
            } catch (_) {
            // ignora erros do Select2 e cai no fallback nativo
            }

            // Fallback nativo
            const opt = selectEl.selectedOptions && selectEl.selectedOptions[0]
            ? selectEl.selectedOptions[0]
            : null;

            if (opt) {
                // Se você quiser, pode popular <option data-codigo="..." data-descricao="...">
                // quando montar o Select2 local, e ler aqui:
                const codigo = opt.dataset?.codigo ?? null;
                const descricao = opt.dataset?.descricao ?? opt.text ?? null;
                return { codigo, descricao };
            }

            return {};
        }

        const fd = new FormData(e.currentTarget);

        // Monta itens percorrendo as linhas (evita desalinhamento com getAll)
        const itens = [];
        const rows = itensContainer.querySelectorAll('.item-pacote');

        rows.forEach((row) => {
            const select = row.querySelector('select[name="pendencia_id[]"]');
            const qtdEl  = row.querySelector('input[name="quantidade[]"]');

            const pendencia_id = Number(select?.value || 0);
            const quantidade   = Number(qtdEl?.value || 0);

            if (pendencia_id && Number.isFinite(quantidade) && quantidade > 0) {
            const meta = getMetaDoSelect(select);
            itens.push({
                pendencia_id,
                quantidade,
                // opcionais para seu backend/log:
                codigo: meta.codigo ?? undefined,
                descricao: meta.descricao ?? undefined
            });
            }
        });

        // if (itens.length === 0) {
        //     alert('Adicione pelo menos um item válido (pendência + quantidade > 0).');
        //     btnFormCriar.disabled = false;
        //     btnFormCriar.innerHTML = 'Salvar';
        //     return;
        // }
        
        const pacoteExistenteVal = fd.get('pacoteExistente'); // <select id="pacoteExistente">

        const payload = {
            nomePacote: fd.get('nomePacote'),
            observacoesPacote: fd.get('observacoesPacote') || '',
            idCargaPacote: fd.get('idCargaPacote'),
            pacoteExistenteId: pacoteExistenteVal ? Number(pacoteExistenteVal) : null,
            itens
        };

        try {
            const resp = await fetch('api/guardar-pacote/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
            });

            if (!resp.ok) {
                const erro = await resp.text();
                console.error('Erro ao salvar pacote:', erro);
                alert(erro);
                return;
            }

            const data = await resp.json();
            console.log(data);

            // Fecha este modal e abre o visualizar
            const modalCriarEl = document.getElementById('criarPacoteModal');
            const modalCriar = bootstrap.Modal.getInstance(document.getElementById('criarPacoteModal'));
            modalCriar.hide();

            const onHidden = async () => {
            modalCriarEl.removeEventListener('hidden.bs.modal', onHidden);
                // força recarregar pendências no reset
                await resetFormCriarPacote({ novaLinha: false, refresh: true });
            };
            modalCriarEl.addEventListener('hidden.bs.modal', onHidden);

            const modalElVisualizarPacotes = document.getElementById('visualizarPacote');
            const modalVisualizarPacotes   = bootstrap.Modal.getInstance(modalElVisualizarPacotes) || new bootstrap.Modal(modalElVisualizarPacotes);
            modalVisualizarPacotes.show();

            const idCargaPacoteEl = document.getElementById('idCargaPacote');
            const idCarga = idCargaPacoteEl?.value;

            // invalida cache para garantir nova leitura
            if (idCarga) invalidatePendencias(idCarga);

            if (idCarga) {
                popularPacotesDaCarga(idCarga);
            }

            if (idCargaPacoteEl?.value) {
                // sua função já existente
                popularPacotesDaCarga(idCargaPacoteEl.value);
            }
            
            atualizarSlotAvancar(idCarga, data.info_add.todos_pacotes_tem_foto_verificacao, data.etapa);

        } catch (err) {
            console.error(err);
            alert('Falha na comunicação com o servidor.');
        } finally {
            btnFormCriar.disabled = false;
            btnFormCriar.innerHTML = 'Salvar';
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

export async function resetFormCriarPacote({ novaLinha = false, refresh = false } = {}) {
    const formCriarPacote = document.getElementById('formCriar');
    const itensContainer  = document.getElementById('itensPacote');
    if (!formCriarPacote || !itensContainer) return;

    // destruir Select2 existentes
    itensContainer.querySelectorAll('select.campo-item').forEach(sel => {
        if (window.$ && $(sel).data('select2')) $(sel).select2('destroy');
    });

    // resetar form e limpar container
    formCriarPacote.reset();
    itensContainer.innerHTML = '';

    if (!novaLinha) return;

    const idCarga = document.getElementById('idCargaPacote')?.value;

    // cria nova linha
    const row = criarRowItem();
    itensContainer.appendChild(row);
    const selectEl = row.querySelector('.campo-item');

    // placeholder visual
    if (selectEl) {
        selectEl.innerHTML = '';
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Carregando pendências...';
        selectEl.appendChild(opt);
    }

    if (!idCarga) {
        console.warn('idCargaPacote vazio ao resetar.');
        return;
    }

    try {
        // aqui forçamos nova leitura do backend se refresh = true
        const itens = await carregarPendencias(idCarga, { refresh });
        if (selectEl) selectEl.innerHTML = '';
        initSelect2Local(selectEl, itens);   // ou initSelect2Ajax(selectEl, idCarga)
    } catch (e) {
        console.error('Falha ao recarregar pendências no reset:', e);
        if (selectEl) {
        selectEl.innerHTML = '';
        const optErr = document.createElement('option');
        optErr.value = '';
        optErr.textContent = 'Erro ao carregar pendências';
        selectEl.appendChild(optErr);
        }
    }
}

