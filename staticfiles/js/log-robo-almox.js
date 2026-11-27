// Tela "Log do robô" (almoxarifado): requisições x tentativas do robô no ERP.
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-filtros');
    const tbody = document.getElementById('tbody-log');
    const btnAnterior = document.getElementById('btn-anterior');
    const btnProxima = document.getElementById('btn-proxima');
    let pagina = 1;
    let totalPaginas = 1;

    const CORES_SITUACAO = {
        lancada: 'bg-success',
        erro: 'bg-danger',
        pendente: 'bg-warning text-dark',
        manual: 'bg-secondary',
        verificar: 'bg-info text-dark',
    };

    function esc(valor) {
        return String(valor ?? '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function isoLocal(d) {
        const pad = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    // Período padrão: últimos 7 dias
    const hoje = new Date();
    const inicio = new Date(); inicio.setDate(hoje.getDate() - 6);
    document.getElementById('f-data-fim').value = isoLocal(hoje);
    document.getElementById('f-data-ini').value = isoLocal(inicio);

    function parametros(extra = {}) {
        const p = new URLSearchParams();
        new FormData(form).forEach((v, k) => { if (v) p.set(k, v); });
        Object.entries(extra).forEach(([k, v]) => p.set(k, v));
        return p.toString();
    }

    async function getJSON(url) {
        const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }

    function marcarKpiAtivo() {
        const sit = document.getElementById('f-situacao').value;
        document.querySelectorAll('.kpi.clicavel').forEach(k => {
            k.classList.toggle('ativo', k.dataset.situacao === sit);
        });
    }

    async function carregarResumo() {
        try {
            // Os indicadores e as listas mostram tudo do período: os filtros de
            // situação, motivo e item (clicáveis) só valem para a tabela.
            const p = new URLSearchParams(parametros());
            ['situacao', 'motivo', 'item'].forEach(k => p.delete(k));
            const d = await getJSON(`/almox/api/log-robo/resumo/?${p.toString()}`);
            const s = d.por_situacao || {};
            const total = Object.values(s).reduce((a, b) => a + b, 0);
            document.getElementById('kpi-total').textContent = total;
            ['lancada', 'erro', 'pendente', 'manual', 'verificar'].forEach(k => {
                document.getElementById(`kpi-${k}`).textContent = s[k] || 0;
            });
            const t = d.totais || {};
            document.getElementById('kpi-tentativas').textContent = `${t.tentativas || 0} (${t.tentativas_erro || 0})`;
            document.getElementById('kpi-tentativas-sub').textContent =
                `${t.com_retentativa || 0} com mais de 1 tentativa · ${t.sem_tentativa || 0} sem tentativa no log`;

            const ulErros = document.getElementById('top-erros');
            ulErros.innerHTML = (d.top_erros || []).length
                ? d.top_erros.map(e => `<li class="clicavel" data-motivo="${esc(e.motivo)}" title="Filtrar: ${esc(e.motivo)}"><span>${esc(e.motivo)} <small class="text-muted">[${esc(e.etapa)}]</small></span><strong>${e.qtd}</strong></li>`).join('')
                : '<li class="text-muted">Nenhum erro no período</li>';

            const ulItens = document.getElementById('top-itens');
            ulItens.innerHTML = (d.top_itens || []).length
                ? d.top_itens.map(i => `<li class="clicavel" data-item="${esc(i.item_codigo)}" data-nome="${esc(i.item_nome)}" title="Filtrar: ${esc(i.item_codigo)} - ${esc(i.item_nome)}"><span>${esc(i.item_codigo)} - ${esc(i.item_nome)}</span><strong>${i.qtd}</strong></li>`).join('')
                : '<li class="text-muted">Nenhum erro no período</li>';
            marcarListasAtivas();

            // Etapas disponíveis (mantém a seleção)
            const selEtapa = document.getElementById('f-etapa');
            const atual = selEtapa.value;
            selEtapa.innerHTML = '<option value="">Todas</option>' +
                (d.etapas || []).map(e => `<option value="${esc(e)}">${esc(e)}</option>`).join('');
            selEtapa.value = atual;

            const ex = (d.execucoes || [])[0];
            document.getElementById('ultima-execucao').innerHTML = ex
                ? `Última execução do robô: <strong>#${ex.id}</strong> em ${esc(ex.maquina || '-')} · início ${esc(ex.iniciado_em)}` +
                  (ex.finalizado_em ? ` · fim ${esc(ex.finalizado_em)}` : ' · <span class="text-success">em andamento</span>') +
                  (ex.status ? ` · ${esc(ex.status)}` : '')
                : 'Nenhuma execução registrada';
        } catch (err) {
            console.error('Erro ao carregar resumo:', err);
        }
    }

    async function carregarTabela() {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center py-4"><span class="spinner-border spinner-border-sm"></span> Carregando...</td></tr>';
        btnAnterior.disabled = true; btnProxima.disabled = true;
        try {
            const d = await getJSON(`/almox/api/log-robo/solicitacoes/?${parametros({ pagina })}`);
            totalPaginas = d.paginas;
            document.getElementById('info-total').textContent = `${d.total} requisição(ões)`;
            document.getElementById('info-pagina').textContent = `Página ${d.pagina} de ${d.paginas}`;
            btnAnterior.disabled = d.pagina <= 1;
            btnProxima.disabled = d.pagina >= d.paginas;

            if (!d.dados.length) {
                tbody.innerHTML = '<tr><td colspan="12" class="text-center text-muted py-4">Nenhuma requisição encontrada</td></tr>';
                return;
            }
            tbody.innerHTML = d.dados.map(r => {
                const badge = `<span class="badge ${CORES_SITUACAO[r.situacao] || 'bg-light text-dark'}">${esc(r.situacao_display)}</span>`;
                const ult = r.ultimo_resultado
                    ? `<span class="badge ${r.ultimo_resultado === 'OK' ? 'bg-success' : 'bg-danger'}">${esc(r.ultimo_resultado)}</span> <small>${esc(r.ultima_tentativa)}</small>`
                    : '<small class="text-muted">sem tentativa</small>';
                const msg = r.ultima_mensagem || (r.situacao === 'erro' ? r.rpa : '');
                return `
                    <tr class="linha-sol" data-id="${r.id}">
                        <td>${r.id}</td>
                        <td class="text-nowrap">${esc(r.data_entrega)}</td>
                        <td>${esc(r.item)}</td>
                        <td>${r.quantidade ?? ''}</td>
                        <td>${esc(r.solicitante)}</td>
                        <td>${esc(r.cc)}</td>
                        <td>${badge}</td>
                        <td>${esc(r.chave) || '<span class="text-muted">-</span>'}</td>
                        <td class="text-center">${r.qtd_tentativas}${r.qtd_erros ? ` <small class="text-danger">(${r.qtd_erros} erro${r.qtd_erros > 1 ? 's' : ''})</small>` : ''}</td>
                        <td class="text-nowrap">${ult}</td>
                        <td>${esc(r.ultima_etapa)}</td>
                        <td class="msg">${esc(msg)}</td>
                        <td class="text-nowrap">${r.situacao === 'verificar'
                            ? `<button type="button" class="btn btn-outline-primary btn-sm badge btn-retornar-fila" data-id="${r.id}" data-chave="${esc(r.chave)}" data-rpa="${esc(r.rpa)}"><i class="bi bi-arrow-counterclockwise"></i> Retornar à fila</button>`
                            : ''}</td>
                    </tr>`;
            }).join('');
        } catch (err) {
            console.error('Erro ao carregar tabela:', err);
            tbody.innerHTML = '<tr><td colspan="12" class="text-center text-danger py-4">Erro ao carregar os dados</td></tr>';
        }
    }

    async function abrirTentativas(id) {
        const corpo = document.getElementById('modalTentativasCorpo');
        document.getElementById('modalTentativasLabel').textContent = `Tentativas do robô - requisição #${id}`;
        corpo.innerHTML = '<div class="text-center py-4"><span class="spinner-border spinner-border-sm"></span> Carregando...</div>';
        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalTentativas')).show();
        try {
            const d = await getJSON(`/almox/api/log-robo/solicitacao/${id}/tentativas/`);
            const bannerVerificar = d.verificar
                ? `<div class="alert alert-info d-flex flex-wrap justify-content-between align-items-center gap-2 py-2">
                        <span class="small"><strong>Em VERIFICAR</strong>${d.chave ? ` · chave ERP <strong>${esc(d.chave)}</strong>` : ''} · ${esc(d.rpa)}</span>
                        <button type="button" class="btn btn-primary btn-sm btn-retornar-fila" data-id="${d.solicitacao_id}" data-chave="${esc(d.chave)}" data-rpa="${esc(d.rpa)}"><i class="bi bi-arrow-counterclockwise"></i> Retornar à fila</button>
                   </div>`
                : '';
            if (!d.tentativas.length) {
                corpo.innerHTML = bannerVerificar + '<p class="text-muted mb-0">O robô ainda não registrou nenhuma tentativa para esta requisição.</p>';
                return;
            }
            corpo.innerHTML = bannerVerificar + d.tentativas.map((t, i) => {
                const ok = t.resultado === 'OK';
                const eventos = t.eventos.length
                    ? t.eventos.map(e => `<div class="evento nivel-${esc(e.nivel)}"><small class="text-muted">${esc(e.criado_em)}</small> <strong>${esc(e.nivel)}</strong> ${esc(e.mensagem)}${e.detalhe ? `<br><small class="text-muted">${esc(e.detalhe)}</small>` : ''}</div>`).join('')
                    : '<small class="text-muted">Sem eventos</small>';
                return `
                    <div class="card mb-2 ${ok ? 'border-success' : 'border-danger'}">
                        <div class="card-header d-flex flex-wrap justify-content-between gap-2 py-2">
                            <span><span class="badge ${ok ? 'bg-success' : 'bg-danger'}">${esc(t.resultado || '-')}</span>
                                Tentativa #${t.id} ${i === 0 ? '<small class="text-muted">(mais recente)</small>' : ''}</span>
                            <small class="text-muted">${esc(t.iniciado_em)} → ${esc(t.finalizado_em || '...')}
                                ${t.duracao_ms != null ? ` · ${(t.duracao_ms / 1000).toFixed(1)}s` : ''}
                                · execução #${esc(t.execucao_id)} ${t.maquina ? `(${esc(t.maquina)})` : ''}</small>
                        </div>
                        <div class="card-body py-2">
                            <div class="small mb-2">
                                Item <strong>${esc(t.item)}</strong> · Qtd ${t.quantidade ?? ''} · ${esc(t.classe)} ·
                                Matrícula ${esc(t.matricula)} · ${esc(t.cc)}
                                ${t.chave_erp ? ` · Chave ERP <strong>${esc(t.chave_erp)}</strong>` : ''}
                                ${t.etapa_falha ? ` · Etapa da falha <strong>${esc(t.etapa_falha)}</strong>` : ''}
                            </div>
                            ${t.mensagem_erro ? `<div class="mb-2"><small class="text-muted">Mensagem de erro</small><pre>${esc(t.mensagem_erro)}</pre></div>` : ''}
                            ${t.texto_modal ? `<div class="mb-2"><small class="text-muted">Texto do modal do ERP</small><pre>${esc(t.texto_modal)}</pre></div>` : ''}
                            ${t.screenshot ? `<div class="mb-2 small"><span class="text-muted">Screenshot (na máquina do robô):</span> <code>${esc(t.screenshot)}</code></div>` : ''}
                            <details><summary class="small">Eventos (${t.eventos.length})</summary><div class="mt-1">${eventos}</div></details>
                        </div>
                    </div>`;
            }).join('');
        } catch (err) {
            console.error('Erro ao carregar tentativas:', err);
            corpo.innerHTML = '<p class="text-danger mb-0">Erro ao carregar as tentativas.</p>';
        }
    }

    // ---- Filtro por motivo / item (clique nas listas do resumo) ----
    const inputMotivo = document.getElementById('f-motivo');
    const inputItem = document.getElementById('f-item');
    let nomeItemFiltro = '';

    function marcarListasAtivas() {
        document.querySelectorAll('#top-erros li[data-motivo]').forEach(li => {
            li.classList.toggle('ativo', li.dataset.motivo === inputMotivo.value);
        });
        document.querySelectorAll('#top-itens li[data-item]').forEach(li => {
            li.classList.toggle('ativo', li.dataset.item === inputItem.value);
        });
    }

    function renderFiltrosAtivos() {
        const chips = [];
        if (inputMotivo.value) {
            chips.push(`<span class="badge rounded-pill text-bg-primary filtro-chip">Motivo: ${esc(inputMotivo.value)}
                <button type="button" class="btn-close btn-close-white ms-1" style="font-size:.55rem" data-limpar="motivo" aria-label="Remover filtro"></button></span>`);
        }
        if (inputItem.value) {
            chips.push(`<span class="badge rounded-pill text-bg-primary filtro-chip">Item: ${esc(inputItem.value)}${nomeItemFiltro ? ' - ' + esc(nomeItemFiltro) : ''}
                <button type="button" class="btn-close btn-close-white ms-1" style="font-size:.55rem" data-limpar="item" aria-label="Remover filtro"></button></span>`);
        }
        document.getElementById('filtros-ativos').innerHTML = chips.join('');
        marcarListasAtivas();
    }

    function aplicarFiltroLista() {
        pagina = 1;
        renderFiltrosAtivos();
        carregarTabela();
    }

    document.getElementById('top-erros').addEventListener('click', (ev) => {
        const li = ev.target.closest('li[data-motivo]');
        if (!li) return;
        // Clicar de novo no mesmo motivo remove o filtro
        inputMotivo.value = inputMotivo.value === li.dataset.motivo ? '' : li.dataset.motivo;
        aplicarFiltroLista();
    });

    document.getElementById('top-itens').addEventListener('click', (ev) => {
        const li = ev.target.closest('li[data-item]');
        if (!li) return;
        const mesmo = inputItem.value === li.dataset.item;
        inputItem.value = mesmo ? '' : li.dataset.item;
        nomeItemFiltro = mesmo ? '' : li.dataset.nome;
        // A lista conta só os erros do item; a tabela mostra o mesmo recorte
        if (!mesmo) {
            document.getElementById('f-situacao').value = 'erro';
            marcarKpiAtivo();
        }
        aplicarFiltroLista();
    });

    document.getElementById('filtros-ativos').addEventListener('click', (ev) => {
        const btn = ev.target.closest('[data-limpar]');
        if (!btn) return;
        if (btn.dataset.limpar === 'motivo') inputMotivo.value = '';
        if (btn.dataset.limpar === 'item') { inputItem.value = ''; nomeItemFiltro = ''; }
        aplicarFiltroLista();
    });

    function recarregarTudo() {
        pagina = 1;
        marcarKpiAtivo();
        carregarResumo();
        carregarTabela();
    }

    form.addEventListener('submit', (ev) => { ev.preventDefault(); recarregarTudo(); });
    document.getElementById('f-situacao').addEventListener('change', () => {
        pagina = 1;
        marcarKpiAtivo();
        carregarTabela();
    });
    ['f-resultado', 'f-etapa', 'f-data-ini', 'f-data-fim'].forEach(id => {
        document.getElementById(id).addEventListener('change', recarregarTudo);
    });

    document.querySelectorAll('.kpi.clicavel').forEach(k => {
        k.addEventListener('click', () => {
            document.getElementById('f-situacao').value = k.dataset.situacao;
            pagina = 1;
            marcarKpiAtivo();
            carregarTabela();
        });
    });

    btnAnterior.addEventListener('click', () => { if (pagina > 1) { pagina--; carregarTabela(); } });
    btnProxima.addEventListener('click', () => { if (pagina < totalPaginas) { pagina++; carregarTabela(); } });

    tbody.addEventListener('click', (ev) => {
        if (ev.target.closest('.btn-retornar-fila')) return; // tratado abaixo
        const tr = ev.target.closest('tr.linha-sol');
        if (tr) abrirTentativas(tr.dataset.id);
    });

    // ---- Retornar para a fila do robô (requisições em VERIFICAR) ----
    const modalRetornoEl = document.getElementById('modalRetornarFila');
    const chkConferido = document.getElementById('rf-conferido');
    const btnConfirmarRetorno = document.getElementById('btn-confirmar-retorno');
    let idRetorno = null;

    function csrfToken() {
        const campo = document.querySelector('[name=csrfmiddlewaretoken]');
        if (campo) return campo.value;
        const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function mostrarAviso(texto, tipo = 'success') {
        const div = document.createElement('div');
        div.className = `alert alert-${tipo} alert-dismissible fade show py-2 small`;
        div.innerHTML = `${esc(texto)}<button type="button" class="btn-close py-2" data-bs-dismiss="alert" aria-label="Fechar"></button>`;
        form.insertAdjacentElement('beforebegin', div);
        setTimeout(() => { div.classList.remove('show'); setTimeout(() => div.remove(), 200); }, 6000);
    }

    document.addEventListener('click', (ev) => {
        const btn = ev.target.closest('.btn-retornar-fila');
        if (!btn) return;
        ev.preventDefault();
        idRetorno = btn.dataset.id;
        document.getElementById('rf-id').textContent = `#${idRetorno}`;
        const chave = btn.dataset.chave || '';
        document.getElementById('rf-chave').textContent = chave || '(sem chave)';
        document.getElementById('rf-aviso-chave').classList.toggle('d-none', !chave);
        document.getElementById('rf-rpa').textContent = btn.dataset.rpa || '';
        document.getElementById('rf-observacao').value = '';
        chkConferido.checked = false;
        btnConfirmarRetorno.disabled = true;
        btnConfirmarRetorno.textContent = 'Retornar para a fila';
        // Fecha o modal de tentativas, se aberto, para não empilhar modais
        const modalTent = bootstrap.Modal.getInstance(document.getElementById('modalTentativas'));
        if (modalTent) modalTent.hide();
        bootstrap.Modal.getOrCreateInstance(modalRetornoEl).show();
    });

    chkConferido.addEventListener('change', () => {
        btnConfirmarRetorno.disabled = !chkConferido.checked;
    });

    btnConfirmarRetorno.addEventListener('click', async () => {
        if (!idRetorno || btnConfirmarRetorno.disabled) return;
        btnConfirmarRetorno.disabled = true;
        btnConfirmarRetorno.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Retornando...';
        try {
            const resp = await fetch(`/almox/api/log-robo/solicitacao/${idRetorno}/retornar-fila/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                body: JSON.stringify({ observacao: document.getElementById('rf-observacao').value }),
            });
            const dados = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(dados.mensagem || `HTTP ${resp.status}`);
            bootstrap.Modal.getOrCreateInstance(modalRetornoEl).hide();
            mostrarAviso(dados.mensagem || 'Requisição devolvida para a fila do robô.');
            carregarResumo();
            carregarTabela();
        } catch (err) {
            console.error('Erro ao retornar para a fila:', err);
            mostrarAviso(err.message || 'Não foi possível retornar para a fila.', 'danger');
            btnConfirmarRetorno.disabled = !chkConferido.checked;
        } finally {
            btnConfirmarRetorno.textContent = 'Retornar para a fila';
        }
    });

    recarregarTudo();
});
