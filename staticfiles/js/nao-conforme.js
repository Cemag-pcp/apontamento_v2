document.addEventListener('DOMContentLoaded', () => {
    const tabela = document.getElementById('tabela-nao-conforme');
    const paginacao = document.getElementById('paginacao-nao-conforme');
    const form = document.getElementById('form-filtrar-nao-conforme');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    const modalDecidirEl = document.getElementById('modalDecidirNaoConforme');
    const modalDecidir = new bootstrap.Modal(modalDecidirEl);
    const formDecidir = document.getElementById('formDecidirNaoConforme');
    const decidirErro = document.getElementById('decidirErro');

    const modalOrdemOriginalEl = document.getElementById('modalOrdemOriginalCorte');
    const modalOrdemOriginal = new bootstrap.Modal(modalOrdemOriginalEl);
    const corpoOrdemOriginal = document.getElementById('corpoOrdemOriginalCorte');

    let paginaAtual = 1;

    function escapeHtml(texto) {
        const div = document.createElement('div');
        div.textContent = texto ?? '';
        return div.innerHTML;
    }

    function formatarNumero(valor) {
        if (valor === null || valor === undefined) return '-';
        return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
    }

    function buscarRegistros(pagina = 1) {
        paginaAtual = pagina;
        tabela.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Carregando...</td></tr>';

        const params = new URLSearchParams();
        const ordem = document.getElementById('filtro-ordem-nao-conforme').value.trim();
        const peca = document.getElementById('filtro-peca-nao-conforme').value.trim();
        const status = document.getElementById('filtro-status-nao-conforme').value;

        if (ordem) params.append('ordem', ordem);
        if (peca) params.append('peca', peca);
        params.append('status', status);
        params.append('page', pagina);
        params.append('limit', 10);

        fetch(`/corte/api/pecas-nao-conforme/?${params.toString()}`)
            .then(response => response.json())
            .then(data => {
                if (!data.registros || data.registros.length === 0) {
                    tabela.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Nenhum registro encontrado.</td></tr>';
                    paginacao.innerHTML = '';
                    return;
                }

                tabela.innerHTML = data.registros.map(registro => {
                    let destino = '-';
                    if (registro.status === 'concluida') {
                        const partes = [];
                        if (registro.qtd_sucata > 0) partes.push(`Sucata: ${formatarNumero(registro.qtd_sucata)} (${escapeHtml(registro.ordem_sucata || '-')})`);
                        if (registro.qtd_recuperada > 0) partes.push(`Recuperada: ${formatarNumero(registro.qtd_recuperada)} (${escapeHtml(registro.ordem_recuperada || '-')})`);
                        destino = partes.join('<br>');
                    }

                    return `
                        <tr>
                            <td class="fw-semibold">${escapeHtml(registro.ordem)}</td>
                            <td>${escapeHtml(registro.maquina || '-')}</td>
                            <td>${escapeHtml(registro.peca)}</td>
                            <td>${formatarNumero(registro.quantidade)}</td>
                            <td>
                                ${registro.status === 'pendente'
                                    ? '<span class="badge text-bg-warning">Pendente</span>'
                                    : '<span class="badge text-bg-success">Concluída</span>'}
                            </td>
                            <td>${destino}</td>
                            <td class="text-end">
                                <div class="d-inline-flex gap-2">
                                    ${registro.status === 'pendente'
                                        ? `<button type="button" class="btn btn-outline-primary btn-sm btn-decidir"
                                            data-id="${registro.id}"
                                            data-ordem="${escapeHtml(registro.ordem)}"
                                            data-peca="${escapeHtml(registro.peca)}"
                                            data-quantidade="${registro.quantidade}">
                                            Definir destino
                                        </button>`
                                        : ''}
                                    <button type="button" class="btn btn-outline-secondary btn-sm btn-ver-ordem" data-ordem-id="${registro.ordem_id}">
                                        Ver ordem original
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');

                montarPaginacao(data.page, data.total_pages);
            })
            .catch(() => {
                tabela.innerHTML = '<tr><td colspan="7" class="text-center text-danger py-4">Erro ao carregar registros.</td></tr>';
            });
    }

    function montarPaginacao(paginaAtualResp, totalPaginas) {
        paginacao.innerHTML = '';
        if (totalPaginas <= 1) return;

        for (let i = 1; i <= totalPaginas; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === paginaAtualResp ? 'active' : ''}`;
            li.innerHTML = `<button type="button" class="page-link">${i}</button>`;
            li.addEventListener('click', () => buscarRegistros(i));
            paginacao.appendChild(li);
        }
    }

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        buscarRegistros(1);
    });

    tabela.addEventListener('click', (event) => {
        const btnDecidir = event.target.closest('.btn-decidir');
        if (btnDecidir) {
            document.getElementById('decidirRegistroId').value = btnDecidir.dataset.id;
            document.getElementById('decidirOrdemTexto').textContent = btnDecidir.dataset.ordem;
            document.getElementById('decidirPecaTexto').textContent = btnDecidir.dataset.peca;
            document.getElementById('decidirQuantidadeTexto').textContent = formatarNumero(btnDecidir.dataset.quantidade);
            document.getElementById('decidirQtdSucata').value = 0;
            document.getElementById('decidirQtdRecuperada').value = 0;
            decidirErro.classList.add('d-none');

            modalDecidir.show();
            return;
        }

        const btnVerOrdem = event.target.closest('.btn-ver-ordem');
        if (btnVerOrdem) {
            abrirModalOrdemOriginal(btnVerOrdem.dataset.ordemId);
        }
    });

    function abrirModalOrdemOriginal(ordemId) {
        corpoOrdemOriginal.innerHTML = '<div class="text-center text-muted py-4">Carregando...</div>';
        modalOrdemOriginal.show();

        fetch(`/corte/api/ordens-criadas/${ordemId}/detalhes/`)
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || 'Erro ao carregar ordem.');
                }

                const chapa = data.chapa;
                const chapaHtml = chapa ? `
                    <dl class="row mb-0">
                        <dt class="col-sm-4">Chapa</dt>
                        <dd class="col-sm-8">${escapeHtml(chapa.descricao_mp || '-')}</dd>
                        <dt class="col-sm-4">Tamanho</dt>
                        <dd class="col-sm-8">${escapeHtml(chapa.tamanho || '-')}</dd>
                        <dt class="col-sm-4">Espessura</dt>
                        <dd class="col-sm-8">${escapeHtml(chapa.espessura || '-')}</dd>
                        <dt class="col-sm-4">Tipo de chapa</dt>
                        <dd class="col-sm-8">${escapeHtml(chapa.tipo_chapa || '-')}</dd>
                        <dt class="col-sm-4">Código chapa</dt>
                        <dd class="col-sm-8">${escapeHtml(chapa.codigo_chapa || '-')}</dd>
                        <dt class="col-sm-4">Qt. chapas</dt>
                        <dd class="col-sm-8">${formatarNumero(chapa.quantidade_chapas)}</dd>
                        <dt class="col-sm-4">Peso total</dt>
                        <dd class="col-sm-8">${chapa.peso_total !== null && chapa.peso_total !== undefined ? formatarNumero(chapa.peso_total) + ' kg' : '-'}</dd>
                    </dl>
                ` : '<p class="text-muted mb-0">Sem informação de chapa/matéria-prima para esta ordem.</p>';

                const pecasHtml = data.pecas.length > 0 ? `
                    <table class="table table-sm align-middle mb-0 mt-3">
                        <thead>
                            <tr>
                                <th>Peça</th>
                                <th class="text-end">Planejada</th>
                                <th class="text-end">Boa</th>
                                <th class="text-end">Não conforme</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.pecas.map(peca => `
                                <tr>
                                    <td>${escapeHtml(peca.peca)}</td>
                                    <td class="text-end">${formatarNumero(peca.qtd_planejada)}</td>
                                    <td class="text-end">${formatarNumero(peca.qtd_boa)}</td>
                                    <td class="text-end">${formatarNumero(peca.qtd_morta)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                ` : '<p class="text-muted mb-0 mt-3">Nenhuma peça encontrada.</p>';

                corpoOrdemOriginal.innerHTML = `
                    <dl class="row">
                        <dt class="col-sm-4">Ordem</dt>
                        <dd class="col-sm-8 fw-semibold">${escapeHtml(data.ordem)}</dd>
                        <dt class="col-sm-4">Máquina</dt>
                        <dd class="col-sm-8">${escapeHtml(data.maquina || '-')}</dd>
                        <dt class="col-sm-4">Status</dt>
                        <dd class="col-sm-8">${escapeHtml(data.status)}</dd>
                        <dt class="col-sm-4">Operador final</dt>
                        <dd class="col-sm-8">${escapeHtml(data.operador_final || '-')}</dd>
                        ${data.obs_operador ? `<dt class="col-sm-4">Obs. operador</dt><dd class="col-sm-8">${escapeHtml(data.obs_operador)}</dd>` : ''}
                    </dl>
                    <hr>
                    ${chapaHtml}
                    ${pecasHtml}
                `;
            })
            .catch((error) => {
                corpoOrdemOriginal.innerHTML = `<div class="alert alert-danger py-2 mb-0">${escapeHtml(error.message)}</div>`;
            });
    }

    const btnConfirmarDecidir = formDecidir.querySelector('button[type="submit"]');
    const spinnerConfirmarDecidir = btnConfirmarDecidir.querySelector('.spinner-border');

    function travarBotaoConfirmar(travado) {
        btnConfirmarDecidir.disabled = travado;
        btnConfirmarDecidir.classList.toggle('opacity-50', travado);
        spinnerConfirmarDecidir.style.display = travado ? 'inline-block' : 'none';
    }

    formDecidir.addEventListener('submit', (event) => {
        event.preventDefault();
        decidirErro.classList.add('d-none');
        travarBotaoConfirmar(true);

        const id = document.getElementById('decidirRegistroId').value;
        const qtdSucata = parseFloat(document.getElementById('decidirQtdSucata').value) || 0;
        const qtdRecuperada = parseFloat(document.getElementById('decidirQtdRecuperada').value) || 0;

        fetch(`/corte/api/pecas-nao-conforme/${id}/decidir/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ qtd_sucata: qtdSucata, qtd_recuperada: qtdRecuperada }),
        })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || 'Erro ao registrar decisão.');
                }

                modalDecidir.hide();
                buscarRegistros(paginaAtual);
                Swal.fire({ icon: 'success', title: 'Decisão registrada', text: data.message || '' });
            })
            .catch((error) => {
                decidirErro.textContent = error.message;
                decidirErro.classList.remove('d-none');
            })
            .finally(() => {
                travarBotaoConfirmar(false);
            });
    });

    buscarRegistros(1);
});
