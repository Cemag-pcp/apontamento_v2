// Inspeção de Item de Garantia: abas A inspecionar / Reinspeção / Aprovados,
// modal de inspeção (data, nº da garantia, o que foi verificado, aprovado,
// inspetor, fotos) e histórico de inspeções do item.
// Reprovado volta para "Reinspeção" até ser aprovado.

const API = '/inspecao/api/garantia';
const estado = { aba: 'pendente', pagina: 1, itens: new Map(), itemAtual: null, itemDetalhe: null, ultimaBusca: 0 };

const $lista = document.getElementById('garantia-lista');
const $paginacao = document.getElementById('garantia-paginacao');
const modalInspecionar = new bootstrap.Modal(document.getElementById('modal-inspecionar-garantia'));
const modalDetalhes = new bootstrap.Modal(document.getElementById('modal-detalhes-garantia'));

const MENSAGEM_VAZIA = {
    pendente: 'Nenhum item de garantia a inspecionar.',
    reinspecao: 'Nenhum item aguardando reinspeção.',
    aprovado: 'Nenhum item aprovado encontrado.',
};

function escapar(texto) {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
}

function csrf() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

async function lerJson(resposta) {
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) throw new Error(dados.error || `Erro ${resposta.status}`);
    return dados;
}

function ordinal(numero) {
    return `${numero}ª inspeção`;
}

// ---------------------------------------------------------------- lista

async function carregar({ atualizar = false } = {}) {
    const busca = ++estado.ultimaBusca;
    const params = new URLSearchParams({
        aba: estado.aba,
        pagina: estado.pagina,
        pesquisar: document.getElementById('filtro-pesquisa').value.trim(),
        data_inicio: document.getElementById('filtro-data-inicio').value,
        data_fim: document.getElementById('filtro-data-fim').value,
    });
    if (atualizar) params.set('atualizar', '1');

    $lista.innerHTML = '<div class="garantia-vazio"><span class="spinner-border spinner-border-sm me-2"></span>Carregando...</div>';
    try {
        const dados = await lerJson(await fetch(`${API}/itens/?${params}`));
        if (busca !== estado.ultimaBusca) return; // resposta antiga
        renderizarLista(dados);
        renderizarPaginacao(dados);
        mostrarSincronizacao(dados);
        Object.entries(dados.contadores || {}).forEach(([aba, total]) => {
            const badge = document.querySelector(`[data-contador="${aba}"]`);
            if (badge) badge.textContent = total || '';
        });
    } catch (erro) {
        if (busca !== estado.ultimaBusca) return;
        $lista.innerHTML = `<div class="garantia-vazio text-danger">${escapar(erro.message)}</div>`;
        $paginacao.innerHTML = '';
    }
}

function mostrarSincronizacao(dados) {
    const $erro = document.getElementById('garantia-erro-sync');
    if (dados.erro_sincronizacao) {
        $erro.textContent = `${dados.erro_sincronizacao} A lista mostra os itens já sincronizados.`;
        $erro.classList.remove('d-none');
    } else {
        $erro.classList.add('d-none');
    }
    const ultima = dados.ultima_sincronizacao;
    document.getElementById('garantia-sync-data').textContent = ultima ? ultima.data : 'Ainda não sincronizada';
    let texto = ultima ? `${ultima.origem} · ${ultima.itens_na_planilha} item(ns) na planilha` : '';
    if (dados.sincronizacao?.novos) texto += ` · ${dados.sincronizacao.novos} novo(s) agora`;
    document.getElementById('garantia-sync').textContent = texto;
}

function linkChamado(insp) {
    const texto = escapar(insp.garantia_titulo || `Chamado ${insp.numero_garantia}`);
    return insp.link_ploomes
        ? `<a class="link-ploomes" href="${escapar(insp.link_ploomes)}" target="_blank" rel="noopener" title="Abrir o chamado no Ploomes"><i class="bi bi-box-arrow-up-right me-1"></i>${texto}</a>`
        : `<span class="link-ploomes">${texto}</span>`;
}

function badgesItem(item) {
    const badges = [];
    if (item.situacao === 'pendente') badges.push('<span class="badge bg-primary">A inspecionar</span>');
    if (item.situacao === 'reinspecao') badges.push('<span class="badge bg-danger"><i class="bi bi-arrow-repeat me-1"></i>Reprovado · reinspecionar</span>');
    if (item.situacao === 'aprovado') badges.push('<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Aprovado</span>');
    if (item.total_inspecoes) badges.push(`<span class="badge badge-numero" title="Número desta inspeção do item">${ordinal(item.total_inspecoes)}</span>`);
    if (!item.na_planilha) badges.push('<span class="badge bg-secondary" title="O item não está mais na planilha de cargas">Saiu da planilha</span>');
    return badges.join('');
}

function cardItem(item) {
    const ultima = item.ultima_inspecao;
    const botoes = [];
    if (item.total_inspecoes) {
        botoes.push(`<button type="button" class="btn btn-outline-secondary btn-sm btn-detalhes" data-id="${item.id}" title="Histórico de inspeções"><i class="bi bi-clock-history"></i></button>`);
    }
    if (item.situacao === 'pendente') {
        botoes.push(`<button type="button" class="btn btn-primary btn-sm btn-inspecionar" data-id="${item.id}"><i class="bi bi-clipboard-check me-1"></i>Inspecionar</button>`);
    } else if (item.situacao === 'reinspecao') {
        botoes.push(`<button type="button" class="btn btn-danger btn-sm btn-inspecionar" data-id="${item.id}"><i class="bi bi-arrow-repeat me-1"></i>Reinspecionar</button>`);
    }

    return `
        <div class="garantia-card ${item.situacao === 'pendente' ? (item.na_planilha ? '' : 'fora') : item.situacao}">
            <div class="d-flex justify-content-between align-items-start gap-2">
                <span class="codigo">${escapar(item.codigo)}</span>
                <div class="badges">${badgesItem(item)}</div>
            </div>
            <div class="descricao">${escapar(item.descricao)}</div>
            <div class="meta"><i class="bi bi-receipt me-1"></i>Pedido ${escapar(item.pedido)}</div>
            <div class="meta"><i class="bi bi-person me-1"></i>${escapar(item.cliente)} ${item.cidade_uf ? `· ${escapar(item.cidade_uf)}` : ''}</div>
            <div class="meta"><i class="bi bi-calendar-event me-1"></i>Programação: ${escapar(item.data_programacao || '-')}</div>
            ${ultima ? `
            <div class="ultima">
                <strong>${ordinal(ultima.numero)}</strong> · ${escapar(ultima.data_inspecao)} · <i class="bi bi-person-check"></i> ${escapar(ultima.inspetor || '-')}<br>
                ${linkChamado(ultima)}
            </div>` : ''}
            <div class="rodape">
                <span class="fw-semibold">Qtd: ${item.quantidade}</span>
                <div class="d-flex gap-2">${botoes.join('')}</div>
            </div>
        </div>`;
}

function renderizarLista(dados) {
    estado.itens = new Map(dados.dados.map((item) => [String(item.id), item]));
    $lista.innerHTML = dados.dados.length
        ? dados.dados.map(cardItem).join('')
        : `<div class="garantia-vazio">${MENSAGEM_VAZIA[estado.aba]}</div>`;
}

function renderizarPaginacao(dados) {
    if (dados.total_paginas <= 1) { $paginacao.innerHTML = ''; return; }
    const atual = dados.pagina_atual;
    const botao = (pagina, rotulo, desabilitado = false, ativo = false) =>
        `<li class="page-item ${desabilitado ? 'disabled' : ''} ${ativo ? 'active' : ''}">
            <button type="button" class="page-link" data-pagina="${pagina}">${rotulo}</button></li>`;
    let html = botao(atual - 1, '&laquo;', atual === 1);
    for (let p = Math.max(1, atual - 2); p <= Math.min(dados.total_paginas, atual + 2); p++) {
        html += botao(p, p, false, p === atual);
    }
    html += botao(atual + 1, '&raquo;', atual === dados.total_paginas);
    $paginacao.innerHTML = `<ul class="pagination pagination-sm mb-0">${html}</ul>`;
}

$paginacao.addEventListener('click', (event) => {
    const botao = event.target.closest('[data-pagina]');
    if (!botao || botao.closest('.disabled')) return;
    estado.pagina = Number(botao.dataset.pagina);
    carregar();
});

document.querySelectorAll('[data-aba]').forEach((aba) => {
    aba.addEventListener('click', () => {
        document.querySelectorAll('[data-aba]').forEach((a) => a.classList.toggle('active', a === aba));
        estado.aba = aba.dataset.aba;
        estado.pagina = 1;
        document.getElementById('label-data-inicio').textContent = estado.aba === 'pendente' ? 'Programação de' : 'Inspeção de';
        carregar();
    });
});

document.getElementById('garantia-filtros').addEventListener('submit', (event) => {
    event.preventDefault();
    estado.pagina = 1;
    carregar();
});

document.getElementById('btn-limpar-filtros').addEventListener('click', () => {
    ['filtro-pesquisa', 'filtro-data-inicio', 'filtro-data-fim'].forEach((id) => { document.getElementById(id).value = ''; });
    estado.pagina = 1;
    carregar();
});

document.getElementById('btn-atualizar-planilha').addEventListener('click', async (event) => {
    const botao = event.currentTarget;
    botao.disabled = true;
    try { await carregar({ atualizar: true }); } finally { botao.disabled = false; }
});

$lista.addEventListener('click', (event) => {
    const inspecionar = event.target.closest('.btn-inspecionar');
    if (inspecionar) abrirInspecao(estado.itens.get(inspecionar.dataset.id));
    const detalhes = event.target.closest('.btn-detalhes');
    if (detalhes) abrirDetalhes(detalhes.dataset.id);
});

// ---------------------------------------------------------- inspecionar

const $form = document.getElementById('form-inspecionar-garantia');
const $chamado = $('#garantia-numero');
document.getElementById('garantia-data').addEventListener('input', (e) => e.target.classList.remove('is-invalid'));

function opcaoChamado(chamado) {
    if (!chamado.id || chamado.loading) return chamado.text;
    const info = [chamado.etapa, chamado.status, chamado.data && chamado.data.split('-').reverse().join('/')].filter(Boolean).join(' · ');
    return $(`
        <div class="chamado-opcao">
            <div class="titulo">${escapar(chamado.titulo || chamado.text)}</div>
            ${info ? `<div class="info">${escapar(info)}</div>` : ''}
            ${chamado.pecas ? `<div class="pecas">${escapar(chamado.pecas)}</div>` : ''}
        </div>`);
}

// seções do chamado (Pedido, Análise, Peças, Abertura, Dados básicos)
const CAMPOS_LARGOS = ['Peças', 'Descrição do problema', 'Conclusão da análise', 'Observações da análise', 'Observações da abertura', 'Link do Drive'];

function htmlSecoes(secoes) {
    return (secoes || []).map((secao) => `
        <div class="secao-chamado">
            <div class="titulo-secao">${escapar(secao.titulo)}</div>
            <div class="campos">
                ${secao.campos.map((c) => `
                    <div class="campo ${CAMPOS_LARGOS.includes(c.rotulo) ? 'largo' : ''}">
                        <div class="rotulo">${escapar(c.rotulo)}</div>
                        <div class="valor">${c.link
                            ? `<a href="${escapar(c.valor)}" target="_blank" rel="noopener">${escapar(c.valor)}</a>`
                            : escapar(c.valor)}</div>
                    </div>`).join('')}
            </div>
        </div>`).join('');
}

let buscaChamado = 0;
async function mostrarPainelChamado(id) {
    const $painel = document.getElementById('painel-chamado');
    if (!id) { $painel.classList.add('d-none'); $painel.innerHTML = ''; return; }
    const busca = ++buscaChamado;
    $painel.classList.remove('d-none');
    $painel.innerHTML = '<div class="small text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Carregando o chamado no Ploomes...</div>';
    try {
        const c = await lerJson(await fetch(`${API}/chamados-ploomes/${id}/`));
        if (busca !== buscaChamado) return;
        $painel.innerHTML = `
            <div class="cabecalho">
                <div><strong>${escapar(c.titulo)}</strong>
                    <div class="small text-muted">${escapar([c.etapa, c.status].filter(Boolean).join(' · '))}</div></div>
                <a class="btn btn-outline-primary btn-sm" href="${escapar(c.link)}" target="_blank" rel="noopener"><i class="bi bi-box-arrow-up-right me-1"></i>Abrir no Ploomes</a>
            </div>
            ${htmlSecoes(c.secoes) || '<div class="small text-muted">O chamado não tem campos preenchidos.</div>'}`;
    } catch (erro) {
        if (busca !== buscaChamado) return;
        $painel.innerHTML = `<div class="small text-danger">${escapar(erro.message)}</div>`;
    }
}

$chamado.select2({
    dropdownParent: $('#modal-inspecionar-garantia'),
    width: '100%',
    placeholder: 'Escolha o chamado de garantia',
    language: {
        searching: () => 'Buscando no Ploomes...',
        noResults: () => 'Nenhum chamado encontrado. Digite o nº do chamado ou o cliente.',
        errorLoading: () => 'Não foi possível consultar o Ploomes.',
    },
    ajax: {
        url: `${API}/chamados-ploomes/`,
        delay: 350,
        data: (params) => ({ q: params.term || '', item_id: estado.itemAtual?.id }),
        processResults: (dados) => ({
            results: (dados.chamados || []).map((c) => ({ ...c, id: String(c.id), text: c.titulo })),
        }),
    },
    templateResult: opcaoChamado,
    templateSelection: (c) => c.titulo || c.text,
});
function marcarChamadoInvalido(invalido) {
    $chamado.toggleClass('chamado-invalido', invalido);
    document.getElementById('garantia-numero-erro').classList.toggle('d-none', !invalido);
}

$chamado.on('change', () => {
    if ($chamado.val()) marcarChamadoInvalido(false);
    mostrarPainelChamado($chamado.val());
});

function campoResumo(rotulo, valor, coluna = 'col-6 col-md-4') {
    return `<div class="${coluna}"><div class="small text-muted">${rotulo}</div><div class="fw-semibold">${escapar(valor || '-')}</div></div>`;
}

function abrirInspecao(item) {
    if (!item) return;
    estado.itemAtual = item;
    $form.reset();
    $chamado.empty().trigger('change');  // também esconde o painel do chamado
    // data vem vazia: o inspetor precisa informar
    document.getElementById('garantia-data').classList.remove('is-invalid');
    marcarChamadoInvalido(false);

    const proxima = (item.total_inspecoes || 0) + 1;
    document.getElementById('inspecionar-titulo').textContent =
        proxima > 1 ? `Reinspeção · ${ordinal(proxima)}` : `Inspecionar · ${ordinal(proxima)}`;

    const ultima = item.ultima_inspecao;
    const $aviso = document.getElementById('inspecionar-aviso');
    if (ultima && !ultima.aprovado) {
        // reinspeção: o chamado é o mesmo, já vem escolhido
        if (ultima.numero_garantia) {
            const opcao = new Option(ultima.garantia_titulo || `Chamado ${ultima.numero_garantia}`, ultima.numero_garantia, true, true);
            $chamado.append(opcao).trigger('change');
        }
        $aviso.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>Reprovado na ${ordinal(ultima.numero)} (${escapar(ultima.data_inspecao)}, ${escapar(ultima.inspetor || '-')}). Veja o histórico no card.`;
        $aviso.classList.remove('d-none');
    } else {
        $aviso.classList.add('d-none');
    }

    document.getElementById('inspecionar-resumo').innerHTML = [
        campoResumo('Código', item.codigo),
        campoResumo('Pedido', item.pedido),
        campoResumo('Quantidade', String(item.quantidade)),
        campoResumo('Descrição', item.descricao, 'col-12'),
        campoResumo('Cliente', item.cliente),
        campoResumo('Cidade', item.cidade_uf),
        campoResumo('Programação', item.data_programacao),
    ].join('');
    modalInspecionar.show();
}

function avisar(titulo, texto, campo) {
    Swal.fire({ icon: 'warning', title: titulo, text: texto }).then(() => campo?.focus());
}

$form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const item = estado.itemAtual;
    const $data = document.getElementById('garantia-data');
    const chamado = $chamado.select2('data')[0];
    const $verificado = document.getElementById('garantia-verificado');
    const aprovado = $form.querySelector('input[name="aprovado"]:checked')?.value;

    if (!chamado?.id) {
        marcarChamadoInvalido(true);
        return avisar('Escolha o chamado', 'Escolha o chamado de garantia do Ploomes.');
    }
    if (!$data.value) {
        $data.classList.add('is-invalid');
        return avisar('Informe a data', 'Preencha a data da inspeção.', $data);
    }
    if ($data.value > window.GARANTIA.hoje) return avisar('Data inválida', 'A data da inspeção não pode ser no futuro.', $data);
    if (!$verificado.value.trim()) return avisar('Descreva a inspeção', 'Preencha o que foi verificado.', $verificado);
    if (!aprovado) return avisar('Informe o resultado', 'Marque se o item está aprovado ou reprovado.');

    const formData = new FormData();
    formData.append('item_id', item.id);
    formData.append('data_inspecao', $data.value);
    formData.append('numero_garantia', chamado.id);
    formData.append('garantia_titulo', chamado.titulo || chamado.text || '');
    formData.append('garantia_etapa', chamado.etapa || '');
    formData.append('verificado', $verificado.value.trim());
    formData.append('aprovado', aprovado);
    [...document.getElementById('garantia-fotos').files].forEach((f) => formData.append('fotos', f));

    const botao = document.getElementById('btn-salvar-inspecao');
    botao.disabled = true;
    try {
        const resposta = await lerJson(await fetch(`${API}/inspecionar/`, {
            method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: formData,
        }));
        modalInspecionar.hide();
        Swal.fire(resposta.aprovado
            ? { icon: 'success', title: `${ordinal(resposta.numero)}: aprovado`, timer: 1800, showConfirmButton: false }
            : { icon: 'warning', title: `${ordinal(resposta.numero)}: reprovado`, text: 'O item foi para "Reinspeção" e fica lá até ser aprovado.' });
        carregar();
    } catch (erro) {
        Swal.fire({ icon: 'error', title: 'Não foi possível salvar', text: erro.message });
    } finally {
        botao.disabled = false;
    }
});

// ------------------------------------------------------------- histórico

function fotos(lista) {
    return lista.length
        ? `<div class="detalhe-fotos">${lista.map((u) => `<a href="${escapar(u)}" target="_blank" rel="noopener"><img src="${escapar(u)}" alt="Foto da inspeção"></a>`).join('')}</div>`
        : '';
}

function blocoInspecao(insp) {
    return `
        <div class="historico-inspecao ${insp.aprovado ? '' : 'reprovado'}">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-1">
                <strong>${ordinal(insp.numero)}</strong>
                ${insp.aprovado
                    ? '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Aprovado</span>'
                    : '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>Reprovado</span>'}
            </div>
            <div class="small text-muted mb-2">
                ${escapar(insp.data_inspecao)} · Inspecionado por ${escapar(insp.inspetor || '-')}
            </div>
            <div class="mb-2">${linkChamado(insp)}${insp.garantia_etapa ? ` <span class="small text-muted">(etapa na inspeção: ${escapar(insp.garantia_etapa)})</span>` : ''}</div>
            <div class="verificado">${escapar(insp.verificado)}</div>
            ${insp.garantia_dados?.secoes?.length ? `
            <details class="mt-2">
                <summary class="small text-primary">Dados do chamado no dia da inspeção</summary>
                <div class="painel-chamado mt-2">${htmlSecoes(insp.garantia_dados.secoes)}</div>
            </details>` : ''}
            ${fotos(insp.fotos)}
            <div class="small text-muted mt-2">Registrado por ${escapar(insp.registrado_por || '-')} em ${escapar(insp.registrado_em)}</div>
        </div>`;
}

async function abrirDetalhes(itemId) {
    const corpo = document.getElementById('detalhes-garantia-corpo');
    corpo.innerHTML = '<div class="text-center py-4"><span class="spinner-border"></span></div>';
    estado.itemDetalhe = itemId;
    modalDetalhes.show();
    try {
        const { item, inspecoes } = await lerJson(await fetch(`${API}/detalhes/${itemId}/`));
        corpo.innerHTML = `
            <div class="row g-2 mb-3">
                ${campoResumo('Código', item.codigo)}
                ${campoResumo('Pedido', item.pedido)}
                ${campoResumo('Quantidade', String(item.quantidade))}
                ${campoResumo('Descrição', item.descricao, 'col-12')}
                ${campoResumo('Cliente', item.cliente)}
                ${campoResumo('Cidade', item.cidade_uf)}
                ${campoResumo('Programação', item.data_programacao)}
            </div>
            <hr>
            ${inspecoes.length ? inspecoes.map(blocoInspecao).join('') : '<p class="text-muted">Item ainda não inspecionado.</p>'}`;
    } catch (erro) {
        corpo.innerHTML = `<p class="text-danger">${escapar(erro.message)}</p>`;
    }
}

document.getElementById('btn-desfazer-inspecao')?.addEventListener('click', async () => {
    const confirmacao = await Swal.fire({
        icon: 'warning',
        title: 'Desfazer a última inspeção?',
        text: 'A última inspeção do item e suas fotos serão apagadas; a anterior volta a valer.',
        showCancelButton: true,
        confirmButtonText: 'Sim, desfazer',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#dc3545',
    });
    if (!confirmacao.isConfirmed) return;
    try {
        await lerJson(await fetch(`${API}/desfazer/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ item_id: estado.itemDetalhe }),
        }));
        modalDetalhes.hide();
        Swal.fire({ icon: 'success', title: 'Inspeção desfeita', timer: 1500, showConfirmButton: false });
        carregar();
    } catch (erro) {
        Swal.fire({ icon: 'error', title: 'Não foi possível desfazer', text: erro.message });
    }
});

carregar();
