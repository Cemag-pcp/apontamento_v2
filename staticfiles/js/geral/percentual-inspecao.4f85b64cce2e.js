// Percentual de inspecao no topo das telas de inspecao.
//
// Uso no template:
//   <div data-pct-inspecao='[{"titulo": "Pintura", "meta": 100, "api": "/inspecao/pintura/api/...-resumo-analise-temporal/",
//                            "prod": "N° de peças produzidas", "insp": "N° de inspeções"}]'></div>
// meta: % de inspecao que o setor precisa atingir no mes (opcional).
// Usa as mesmas APIs de resumo dos dashboards (uma linha por mes) e soma as linhas
// do mes atual (dia 1 ate hoje).

(function () {
    const ATUALIZAR_A_CADA_MS = 5 * 60 * 1000;

    function isoLocal(d) {
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const dia = String(d.getDate()).padStart(2, '0');
        return `${d.getFullYear()}-${m}-${dia}`;
    }

    async function totaisPeriodo(setor, inicio, fim) {
        const url = `${setor.api}?data_inicio=${inicio}&data_fim=${fim}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`Erro ao buscar ${url}`);
        const linhas = await resp.json();
        let prod = 0, insp = 0;
        linhas.forEach((l) => {
            prod += Number(l[setor.prod]) || 0;
            insp += Number(l[setor.insp]) || 0;
        });
        return { prod, insp };
    }

    function formatarPct(valor) {
        return valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 });
    }

    // Cor pela meta do setor: atingiu = verde; perto (80% da meta) = amarelo; abaixo = vermelho.
    // Sem meta: faixas antigas (95/80).
    function corPct(pct, meta) {
        const alvo = meta || 95;
        if (pct >= alvo) return '#16a34a';
        if (pct >= alvo * 0.8) return '#f59e0b';
        return '#dc2626';
    }

    function blocoPeriodo(rotulo, t, meta) {
        if (!t) {
            return `<div class="flex-fill"><div class="small text-muted">${rotulo}</div>
                    <div class="fw-bold text-muted">indisponível</div></div>`;
        }
        if (t.prod === 0) {
            return `<div class="flex-fill"><div class="small text-muted">${rotulo}</div>
                    <div class="fw-bold text-muted">sem produção</div></div>`;
        }
        const pct = (t.insp / t.prod) * 100;
        const cor = corPct(pct, meta);
        const temMeta = Number.isFinite(meta) && meta > 0;
        const atingiu = temMeta && pct >= meta;
        const linhaMeta = !temMeta ? '' : atingiu
            ? `<span class="fw-bold" style="color: #16a34a;">✔ Meta atingida</span>`
            : `<span class="fw-bold" style="color: ${cor};">Faltam ${formatarPct(meta - pct)} p.p. para a meta</span>`;
        // marquinha na barra mostrando onde fica a meta
        const marcaMeta = temMeta && meta < 100
            ? `<div title="Meta ${meta}%" style="position: absolute; top: -3px; bottom: -3px; left: ${meta}%; width: 2px; background: #1b1b1b;"></div>`
            : '';
        return `
            <div class="flex-fill" style="min-width: 150px;">
                <div class="d-flex justify-content-between align-items-baseline">
                    <span class="small text-muted">${rotulo}</span>
                    <span>
                        <span class="fw-bold" style="font-size: 1.25rem; color: ${cor};">${pct.toFixed(1).replace('.', ',')}%</span>
                        ${temMeta ? `<span class="small text-muted ms-1">/ meta ${meta}%</span>` : ''}
                    </span>
                </div>
                <div style="position: relative;">
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar" role="progressbar" style="width: ${Math.min(pct, 100)}%; background-color: ${cor};"></div>
                    </div>
                    ${marcaMeta}
                </div>
                <div class="d-flex justify-content-between flex-wrap gap-2 small mt-1">
                    <span class="text-muted">${t.insp.toLocaleString('pt-BR')} de ${t.prod.toLocaleString('pt-BR')} peças inspecionadas</span>
                    ${linhaMeta}
                </div>
            </div>`;
    }

    async function renderizar(container, setores) {
        const hoje = new Date();
        const hojeIso = isoLocal(hoje);
        const inicioMes = isoLocal(new Date(hoje.getFullYear(), hoje.getMonth(), 1));

        const mes = hoje.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }).replace(' de ', '/');
        const rotuloMes = mes.charAt(0).toUpperCase() + mes.slice(1);

        const blocos = await Promise.all(setores.map(async (setor) => {
            const tMes = await totaisPeriodo(setor, inicioMes, hojeIso).catch((e) => { console.error(e); return null; });
            const rotulo = setores.length > 1 ? `${setor.titulo} · ${rotuloMes}` : rotuloMes;
            return blocoPeriodo(rotulo, tMes, Number(setor.meta));
        }));

        container.innerHTML = `
            <div class="card mb-3">
                <div class="card-body py-2">
                    <div class="mb-2">
                        <span class="fw-bold text-uppercase small" style="letter-spacing: 1px;">Percentual de inspeção</span>
                    </div>
                    <div class="d-flex gap-4 flex-wrap">${blocos.join('<div class="vr d-none d-md-block"></div>')}</div>
                </div>
            </div>`;
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-pct-inspecao]').forEach((container) => {
            let setores;
            try {
                setores = JSON.parse(container.dataset.pctInspecao);
            } catch (e) {
                console.error('data-pct-inspecao invalido', e);
                return;
            }
            container.innerHTML = `<div class="card mb-3"><div class="card-body py-2 small text-muted">
                <span class="spinner-border spinner-border-sm me-2"></span>Carregando percentual de inspeção...</div></div>`;
            renderizar(container, setores);
            setInterval(() => renderizar(container, setores), ATUALIZAR_A_CADA_MS);
        });
    });
})();
