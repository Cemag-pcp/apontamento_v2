function getCsrfToken() {
    return document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] ?? '';
}

function abrirModalAposFechar(atual, proximo) {
    if (!atual || !proximo) {
        return;
    }

    const abrirProximo = () => {
        atual._abrindoProximoModal = false;
        new bootstrap.Modal(proximo).show();
    };

    if (atual.classList.contains('show')) {
        atual._abrindoProximoModal = true;
        atual.addEventListener('hidden.bs.modal', abrirProximo, { once: true });
        const instanciaAtual = bootstrap.Modal.getInstance(atual) || new bootstrap.Modal(atual);
        instanciaAtual.hide();
        return;
    }

    abrirProximo();
}

export function renderCallendar(options = {}) {
    const calendarEl = document.getElementById('calendario');
    if (!calendarEl) {
        return null;
    }

    const interactive =
        options.interactive ??
        (calendarEl.dataset.interactive !== 'false');
    const eventsUrl =
        options.eventsUrl ??
        calendarEl.dataset.eventsUrl ??
        null;
    const dayMaxEventRowsAttr = calendarEl.dataset.dayMaxEventRows;
    const dayMaxEventRows =
        dayMaxEventRowsAttr === undefined
            ? true
            : dayMaxEventRowsAttr === 'false'
            ? false
            : Number(dayMaxEventRowsAttr);

    // Se não houver eventsUrl, exibe tanto produção quanto liberações
    const extraUrls = calendarEl.dataset.extraEventsUrl
        ? calendarEl.dataset.extraEventsUrl.split(',').map(u => u.trim())
        : [];

    const primaryUrl = eventsUrl ?? '/cargas/api/andamento-cargas';

    if (calendarEl._fullCalendarInstance) {
        calendarEl._fullCalendarInstance.destroy();
        calendarEl._fullCalendarInstance = null;
    }

    function buildSource(url) {
        return function(fetchInfo, successCallback, failureCallback) {
            fetch(`${url}?start=${fetchInfo.startStr}&end=${fetchInfo.endStr}`)
                .then(r => r.json())
                .then(data => successCallback(data))
                .catch(err => failureCallback(err));
        };
    }

    const eventSources = [primaryUrl, ...extraUrls].map(buildSource);

    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'pt-br',
        editable: interactive,
        eventDurationEditable: false,
        displayEventTime: false,
        dayMaxEventRows: Number.isNaN(dayMaxEventRows) ? true : dayMaxEventRows,
        expandRows: calendarEl.dataset.calendarLayout === 'liberacao',
        eventDisplay: 'block',
        eventContent: function(arg) {
            const wrapper = document.createElement('div');
            wrapper.style.lineHeight = '1.15';
            wrapper.style.whiteSpace = 'normal';
            wrapper.style.overflow = 'hidden';

            const title = document.createElement('div');
            title.textContent = arg.event.title || '';
            title.style.fontSize = '0.8rem';
            title.style.fontWeight = '600';
            title.style.color = '#fff';

            wrapper.appendChild(title);

            if (arg.event.extendedProps?.tipo === 'liberacao') {
                const dataCarga = document.createElement('div');
                dataCarga.textContent = arg.event.extendedProps?.data_carga || '';
                dataCarga.style.fontSize = '0.68rem';
                dataCarga.style.opacity = '0.9';
                dataCarga.style.color = '#fff';

                const meta = document.createElement('div');
                meta.textContent = arg.event.extendedProps?.liberado_em || '';
                meta.style.fontSize = '0.68rem';
                meta.style.opacity = '0.9';
                meta.style.color = '#fff';

                if (dataCarga.textContent) {
                    wrapper.appendChild(dataCarga);
                }
                if (meta.textContent) {
                    wrapper.appendChild(meta);
                }
            }

            return { domNodes: [wrapper] };
        },
        eventSources: eventSources,
        eventClick: function(info) {
            if (info.event.extendedProps?.tipo === 'liberacao') {
                abrirDetalhesLiberacao(info.event.extendedProps.carga_uuid);
                return;
            }

            if (!interactive) {
                return;
            }

            const setor = info.event.extendedProps.setor;
            const dataAtual = info.event.startStr;
            const eventId = info.event.id || `${setor}-${dataAtual}`;

            document.getElementById('modalSetor').innerText = setor;
            document.getElementById('eventId').value = eventId;
            document.getElementById('setor').value = setor;
            document.getElementById('dataAtual').value = dataAtual;
            document.getElementById('novaData').value = dataAtual;

            const escolhaModal = new bootstrap.Modal(document.getElementById('modalEscolha'));
            escolhaModal.show();

            document.getElementById('btnExcluirCarga').onclick = function() {
                abrirModalAposFechar(
                    document.getElementById('modalEscolha'),
                    document.getElementById('modalExcluirCarga')
                );
            };

            document.getElementById('confirmarExclusao').onclick = function() {
                const setorAtual = document.getElementById('setor').value;
                const dataSelecionada = document.getElementById('dataAtual').value;

                const modalElement = document.getElementById('modalExcluirCarga');
                const modalInstance = bootstrap.Modal.getInstance(modalElement);
                if (modalInstance) {
                    modalInstance.hide();
                }

                Swal.fire({
                    title: 'Aguarde...',
                    text: 'Excluindo planejamento...',
                    allowOutsideClick: false,
                    showConfirmButton: false,
                    didOpen: () => {
                        Swal.showLoading();
                    }
                });

                fetch('/cargas/api/excluir-planejamento/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        data: dataSelecionada,
                        setor: setorAtual
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Erro ao excluir ordens');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.error) {
                        Swal.fire({
                            icon: 'error',
                            title: 'Erro!',
                            text: data.error,
                            confirmButtonText: 'OK'
                        });
                    } else {
                        renderCallendar();
                        Swal.fire({
                            icon: 'success',
                            title: 'Planejamento excluido com sucesso!',
                            confirmButtonText: 'OK'
                        });
                    }
                })
                .catch(() => {
                    Swal.fire({
                        icon: 'error',
                        title: 'Erro!',
                        text: 'Não foi possível excluir o planejamento. Tente novamente.',
                        confirmButtonText: 'OK'
                    });
                });
            };

            document.getElementById('btnAtualizar').onclick = function() {
                Swal.fire({
                    title: 'Aguarde...',
                    text: 'Atualizando informações...',
                    allowOutsideClick: false,
                    showConfirmButton: false,
                    didOpen: () => {
                        Swal.showLoading();
                    }
                });

                escolhaModal.hide();

                fetch(`/cargas/api/atualizar-planejamento/?data_inicio=${dataAtual}&setor=${setor}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        Swal.fire({
                            icon: 'error',
                            title: 'Erro!',
                            text: data.error,
                            confirmButtonText: 'OK'
                        });
                    } else {
                        renderCallendar();

                        // Tabela de itens planejados
                        let tabelaItens = '';
                        if (Array.isArray(data.itens_planejados) && data.itens_planejados.length > 0) {
                            const linhas = data.itens_planejados.flatMap((item, idx) => {
                                const badge = item.nova
                                    ? `<span style="color:#198754;font-weight:bold">NOVA</span>`
                                    : `<span style="color:#0d6efd">atualizada</span>`;
                                const extra = item.cor ? ` <em>(${item.cor})</em>` : '';
                                const celula = item.setor_conjunto || '-';
                                const temOrigem = Array.isArray(item.origem) && item.origem.length > 0;
                                const toggleId = `orig-${idx}`;

                                const linhaPrincipal = `<tr>
                                    <td style="text-align:left;padding:2px 6px">
                                        ${temOrigem ? `<span style="cursor:pointer;user-select:none" onclick="var el=document.getElementById('${toggleId}');el.style.display=el.style.display==='none'?'table-row':'none'">▶</span> ` : ''}
                                        ${item.peca}${extra}
                                    </td>
                                    <td style="text-align:center;padding:2px 6px">${celula}</td>
                                    <td style="text-align:center;padding:2px 6px"><strong>${item.qtd_planejada}</strong></td>
                                    <td style="text-align:center;padding:2px 6px">${badge}</td>
                                </tr>`;

                                if (!temOrigem) return [linhaPrincipal];

                                const linhasOrigem = item.origem.map(o =>
                                    `↳ <strong>${o.recurso}</strong> &nbsp;|&nbsp; ` +
                                    `qtd. liberada: <strong>${o.quantidade_item}</strong> × ` +
                                    `qtde/unid: <strong>${o.qtde_por_unidade}</strong> = ` +
                                    `<strong>${o.subtotal}</strong>` +
                                    (o.carga ? ` &nbsp;<em>(${o.carga})</em>` : '')
                                ).join('<br>');

                                const subLinha = `<tr id="${toggleId}" style="display:none;background:#f8f9fa;font-size:11px">
                                    <td colspan="4" style="padding:4px 6px 4px 22px;color:#555;text-align:left">${linhasOrigem}</td>
                                </tr>`;

                                return [linhaPrincipal, subLinha];
                            }).join('');
                            tabelaItens = `
                                <div style="max-height:400px;overflow-y:auto;margin-top:8px">
                                    <table style="width:100%;border-collapse:collapse;font-size:13px">
                                        <thead>
                                            <tr style="border-bottom:1px solid #dee2e6">
                                                <th style="text-align:left;padding:4px 6px">Peça</th>
                                                <th style="padding:4px 6px">Célula</th>
                                                <th style="padding:4px 6px">Qtd. planejada</th>
                                                <th style="padding:4px 6px">Status</th>
                                            </tr>
                                        </thead>
                                        <tbody>${linhas}</tbody>
                                    </table>
                                </div>`;
                        }

                        // Ordens protegidas
                        let protegidасTexto = '';
                        if (Array.isArray(data.ordens_com_apontamentos) && data.ordens_com_apontamentos.length > 0) {
                            const statusLabel = {
                                'aguardando_iniciar': 'Aguardando',
                                'iniciada': 'Iniciada',
                                'finalizada': 'Finalizada',
                                'interrompida': 'Interrompida'
                            };
                            const itens = data.ordens_com_apontamentos.map(o => {
                                const status = statusLabel[o.status_atual] || o.status_atual;
                                return `<li style="text-align:left"><strong>${o.peca || 'indefinido'}</strong> — ${status}</li>`;
                            }).join('');
                            protegidасTexto = `
                                <p style="margin-top:10px"><strong>Ordens protegidas</strong> (não alteradas — já iniciadas ou com produção):</p>
                                <ul style="margin:0;padding-left:20px">${itens}</ul>`;
                        }

                        Swal.fire({
                            icon: 'success',
                            title: 'Ordens Atualizadas!',
                            html: `
                                <p><strong>${data.novas_ordens_criadas}</strong> nova(s) ordem(ns) criada(s).</p>
                                ${tabelaItens}
                                ${protegidасTexto}
                            `,
                            confirmButtonText: 'OK',
                            width: 700,
                        });
                    }
                })
                .catch(error => {
                    console.error('Erro ao buscar detalhes da carga:', error);

                    Swal.fire({
                        icon: 'error',
                        title: 'Erro!',
                        text: 'Não foi possível atualizar as informações. Tente novamente.',
                        confirmButtonText: 'OK'
                    });
                });
            };
        },
        eventDrop: interactive ? function(info) {
            const newDate = info.event.startStr;
            const setor = info.event.extendedProps.setor;
            const dataAtual = info.oldEvent.startStr;

            remanejarCarga(setor, dataAtual, newDate);
        } : undefined
    });

    calendar.render();
    calendarEl._fullCalendarInstance = calendar;

    const confirmarRemanejamento = document.getElementById('confirmarRemanejamento');
    if (interactive && confirmarRemanejamento) {
        confirmarRemanejamento.onclick = function() {
            const eventId = document.getElementById('eventId').value;
            const setor = document.getElementById('setor').value;
            const dataAtual = document.getElementById('dataAtual').value;
            const novaData = document.getElementById('novaData').value;

            if (!novaData) {
                alert('Por favor, selecione uma nova data.');
                return;
            }

            const eventoAtualizado = calendar.getEventById(eventId);

            if (eventoAtualizado) {
                alert(`Carga do setor ${setor} remanejada para ${novaData}`);
            }

            remanejarCarga(setor, dataAtual, novaData);

            const modal = bootstrap.Modal.getInstance(document.getElementById('modalRemanejar'));
            modal.hide();
        };
    }

    return calendar;
}

async function abrirDetalhesLiberacao(cargaUuid) {
    const modalElement = document.getElementById('modalDetalhesLiberacao');
    const titulo = document.getElementById('detalhesLiberacaoTitulo');
    const subtitulo = document.getElementById('detalhesLiberacaoSubtitulo');
    const tabela = document.getElementById('detalhesLiberacaoTabela');
    const acoes = document.getElementById('detalhesLiberacaoAcoes');

    if (!modalElement || !titulo || !subtitulo || !tabela || !acoes || !cargaUuid) {
        return;
    }

    titulo.textContent = 'Carregando...';
    subtitulo.textContent = '';
    tabela.innerHTML = "<tr><td colspan='3'>Carregando itens...</td></tr>";
    acoes.innerHTML = '';

    const modal = new bootstrap.Modal(modalElement);
    modal.show();

    try {
        const response = await fetch(`/cargas/api/liberacoes/${cargaUuid}/`);
        const payload = await response.json();

        if (!response.ok) {
            throw new Error(payload.error || 'Erro ao carregar detalhes da carga.');
        }

        titulo.textContent = `${payload.carga} v${payload.versao}`;
        let subtituloHtml = `Data carga: ${payload.data_carga_formatada || payload.data_carga} | Liberado em: ${payload.liberado_em} | Usuário: ${payload.liberado_por}`;
        if (payload.data_sugerida_planejamento_formatada || payload.data_sugerida_planejamento) {
            subtituloHtml += `<br><span style="color:#dc3545;font-weight:600">Data sugerida: ${payload.data_sugerida_planejamento_formatada || payload.data_sugerida_planejamento}</span>`;
        }
        subtitulo.innerHTML = subtituloHtml;

        if (payload.data_sugerida_planejamento) {
            const btnAplicar = document.createElement('button');
            btnAplicar.className = 'btn btn-danger btn-sm';
            btnAplicar.innerHTML = '<i class="fas fa-calendar-check me-1"></i>Mudar para data sugerida';
            btnAplicar.addEventListener('click', async () => {
                const confirmado = window.confirm(`Confirmar a altera??o da carga para a data sugerida ${payload.data_sugerida_planejamento_formatada || payload.data_sugerida_planejamento}?`);
                if (!confirmado) {
                    return;
                }

                const htmlOriginal = btnAplicar.innerHTML;
                btnAplicar.disabled = true;
                btnAplicar.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Aplicando...';

                try {
                    const responseAplicar = await fetch(`/cargas/api/liberacoes/${payload.carga_uuid}/aplicar-data-sugerida/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken(),
                        },
                    });
                    const payloadAplicar = await responseAplicar.json();
                    if (!responseAplicar.ok) {
                        throw new Error(payloadAplicar.error || 'Erro ao aplicar data sugerida.');
                    }

                    alert(payloadAplicar.message || 'Data sugerida aplicada com sucesso.');
                    modal.hide();
                    renderCallendar();
                } catch (error) {
                    console.error(error);
                    alert(error.message || 'Não foi possível aplicar a data sugerida.');
                    btnAplicar.disabled = false;
                    btnAplicar.innerHTML = htmlOriginal;
                }
            });
            acoes.appendChild(btnAplicar);
        }

        // Botões de link por cliente
        const linksContainer = document.getElementById('detalhesLiberacaoLinks');
        if (linksContainer) {
            linksContainer.innerHTML = '';
            const clientesUnicos = [...new Set((payload.itens || []).map(i => i.cliente).filter(Boolean))];
            if (clientesUnicos.length > 0) {
                clientesUnicos.forEach(async (cliente) => {
                    try {
                        const r = await fetch('/cargas/api/gerar-link-acompanhamento/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                            body: JSON.stringify({ data_carga: payload.data_carga, cliente }),
                        });
                        const linkData = await r.json();
                        if (!r.ok) return;

                        const btn = document.createElement('button');
                        btn.className = 'btn btn-outline-primary btn-sm';
                        btn.innerHTML = `<i class="fas fa-link me-1"></i>Link: ${cliente}`;
                        btn.addEventListener('click', () => {
                            navigator.clipboard.writeText(linkData.url).then(() => {
                                btn.innerHTML = `<i class="fas fa-check me-1"></i>Copiado!`;
                                setTimeout(() => { btn.innerHTML = `<i class="fas fa-link me-1"></i>Link: ${cliente}`; }, 2000);
                            });
                        });
                        linksContainer.appendChild(btn);
                    } catch {}
                });
            }
        }

        if (!Array.isArray(payload.itens) || payload.itens.length === 0) {
            tabela.innerHTML = "<tr><td colspan='3'>Nenhum item encontrado.</td></tr>";
            return;
        }

        tabela.innerHTML = '';

        // Agrupa por cliente + carreta, somando quantidades
        const agrupado = [];
        const chaveMap = new Map();
        payload.itens.forEach((item) => {
            const cliente = item.cliente || 'Sem cliente';
            const chave = `${cliente}||${item.codigo_recurso}`;
            if (chaveMap.has(chave)) {
                agrupado[chaveMap.get(chave)].quantidade += item.quantidade;
            } else {
                chaveMap.set(chave, agrupado.length);
                agrupado.push({ cliente, codigo_recurso: item.codigo_recurso, quantidade: item.quantidade });
            }
        });

        let clienteAtual = null;
        agrupado.forEach((item) => {
            const linha = document.createElement('tr');
            linha.innerHTML = `
                <td class="text-start">${item.cliente !== clienteAtual ? item.cliente : ''}</td>
                <td>${item.codigo_recurso}</td>
                <td>${item.quantidade}</td>
            `;
            clienteAtual = item.cliente;
            tabela.appendChild(linha);
        });
    } catch (error) {
        console.error(error);
        titulo.textContent = 'Erro ao carregar';
        subtitulo.textContent = error.message || 'Não foi possível carregar os detalhes.';
        tabela.innerHTML = "<tr><td colspan='3'>Falha ao carregar os itens.</td></tr>";
    }
}

function remanejarCarga(setor, dataAtual, novaData) {
    fetch('/cargas/api/remanejar-carga/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            setor: setor,
            dataAtual: dataAtual,
            dataRemanejar: novaData
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(`Erro: ${data.error}`);
            renderCallendar();
        } else {
            alert(`Sucesso: ${data.message}`);
            renderCallendar();
        }
    })
    .catch(error => console.error('Erro na requisição:', error));
}

document.addEventListener('DOMContentLoaded', () => {
    const calendarEl = document.getElementById('calendario');
    if (calendarEl && calendarEl.dataset.autoRender === 'true') {
        renderCallendar();
    }
});
