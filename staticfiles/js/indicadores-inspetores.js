document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-filtro-indicadores');
    const inputInicio = document.getElementById('filtro-data-inicio-indicadores');
    const inputFim = document.getElementById('filtro-data-fim-indicadores');
    const container = document.getElementById('containerSemanasIndicadores');

    function escapeHtml(texto) {
        const div = document.createElement('div');
        div.textContent = texto ?? '';
        return div.innerHTML;
    }

    function formatarNumero(valor) {
        if (valor === null || valor === undefined) return '-';
        return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
    }

    function formatarTempo(segundosTotais) {
        if (segundosTotais === null || !isFinite(segundosTotais) || segundosTotais <= 0) return '-';
        const segundos = Math.round(segundosTotais);
        const pad = (n) => String(n).padStart(2, '0');
        const h = Math.floor(segundos / 3600);
        const m = Math.floor((segundos % 3600) / 60);
        const s = segundos % 60;
        return `${pad(h)}:${pad(m)}:${pad(s)}`;
    }

    function montarCardSemana(semana) {
        const linhasHtml = semana.linhas.map(linha => `
            <tr>
                <td class="fw-semibold">${escapeHtml(linha.dia_semana)}</td>
                <td>${escapeHtml(linha.data)}</td>
                <td>${formatarNumero(linha.grupo_corte)}</td>
                <td>${formatarNumero(linha.montagem_solda)}</td>
                <td>${formatarNumero(linha.pintura)}</td>
                <td>${formatarNumero(linha.recebimento)}</td>
            </tr>
        `).join('');

        const media = semana.media;
        const HORAS_TURNO = 9;
        const SEGUNDOS_TURNO = HORAS_TURNO * 3600;
        const porHora = {
            grupo_corte: media.grupo_corte / HORAS_TURNO,
            montagem_solda: media.montagem_solda / HORAS_TURNO,
            pintura: media.pintura / HORAS_TURNO,
            recebimento: media.recebimento / HORAS_TURNO,
        };
        const tempoPorInspecao = {
            grupo_corte: media.grupo_corte > 0 ? SEGUNDOS_TURNO / media.grupo_corte : null,
            montagem_solda: media.montagem_solda > 0 ? SEGUNDOS_TURNO / media.montagem_solda : null,
            pintura: media.pintura > 0 ? SEGUNDOS_TURNO / media.pintura : null,
            recebimento: media.recebimento > 0 ? SEGUNDOS_TURNO / media.recebimento : null,
        };

        return `
            <div class="card shadow-sm border-0 mb-4">
                <div class="card-body">
                    <h3 class="h6 mb-3">${escapeHtml(semana.rotulo)}</h3>
                    <div class="table-responsive">
                        <table class="table table-sm table-bordered text-center align-middle mb-0">
                            <thead>
                                <tr>
                                    <th></th>
                                    <th></th>
                                    <th>Estamparia / Corte / Usinagem / Serra</th>
                                    <th>Montagem / Solda</th>
                                    <th>Pintura</th>
                                    <th>Recebimento</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${linhasHtml}
                                <tr class="table-light fw-bold">
                                    <td colspan="2">MÉDIA</td>
                                    <td>${formatarNumero(media.grupo_corte)}</td>
                                    <td>${formatarNumero(media.montagem_solda)}</td>
                                    <td>${formatarNumero(media.pintura)}</td>
                                    <td>${formatarNumero(media.recebimento)}</td>
                                </tr>
                                <tr class="table-light text-muted">
                                    <td colspan="2">MÉDIA/HORA (turno 9h)</td>
                                    <td>${formatarNumero(porHora.grupo_corte)}</td>
                                    <td>${formatarNumero(porHora.montagem_solda)}</td>
                                    <td>${formatarNumero(porHora.pintura)}</td>
                                    <td>${formatarNumero(porHora.recebimento)}</td>
                                </tr>
                                <tr class="table-light text-muted">
                                    <td colspan="2">TEMPO MÉDIO/INSPEÇÃO</td>
                                    <td>${formatarTempo(tempoPorInspecao.grupo_corte)}</td>
                                    <td>${formatarTempo(tempoPorInspecao.montagem_solda)}</td>
                                    <td>${formatarTempo(tempoPorInspecao.pintura)}</td>
                                    <td>${formatarTempo(tempoPorInspecao.recebimento)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    }

    function buscarIndicadores() {
        const dataInicio = inputInicio.value;
        const dataFim = inputFim.value;

        if (!dataInicio || !dataFim) return;

        container.innerHTML = '<div class="card shadow-sm border-0"><div class="card-body text-muted py-4 text-center">Carregando...</div></div>';

        const params = new URLSearchParams({ data_inicio: dataInicio, data_fim: dataFim });

        fetch(`/inspecao/api/indicadores-inspetores/?${params.toString()}`)
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || 'Erro ao buscar indicadores.');
                }

                if (!data.semanas || data.semanas.length === 0) {
                    container.innerHTML = '<div class="card shadow-sm border-0"><div class="card-body text-muted py-4 text-center">Nenhum dado no período.</div></div>';
                    return;
                }

                container.innerHTML = data.semanas.map(montarCardSemana).join('');
            })
            .catch((error) => {
                container.innerHTML = `<div class="card shadow-sm border-0"><div class="card-body text-danger py-4 text-center">${escapeHtml(error.message)}</div></div>`;
            });
    }

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        buscarIndicadores();
    });

    // Padrao: semana atual (segunda a hoje), pra ja abrir com algo preenchido.
    const hoje = new Date();
    const diaSemana = hoje.getDay(); // 0=domingo
    const diffSegunda = diaSemana === 0 ? 6 : diaSemana - 1;
    const segunda = new Date(hoje);
    segunda.setDate(hoje.getDate() - diffSegunda);

    const paraISO = (data) => data.toISOString().slice(0, 10);
    inputInicio.value = paraISO(segunda);
    inputFim.value = paraISO(hoje);

    buscarIndicadores();
});
