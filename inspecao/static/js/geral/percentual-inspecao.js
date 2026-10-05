// Percentual de inspecao no topo das telas de inspecao.
//
// Uso no template:
//   <div data-pct-inspecao='[{"titulo": "Pintura", "api": "/inspecao/pintura/api/...-resumo-analise-temporal/",
//                            "prod": "N° de peças produzidas", "insp": "N° de inspeções"}]'></div>
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

    function corPct(pct) {
        if (pct >= 95) return '#16a34a';
        if (pct >= 80) return '#f59e0b';
        return '#dc2626';
    }

    function blocoPeriodo(rotulo, t) {
        if (!t) {
            return `<div class="flex-fill"><div class="small text-muted">${rotulo}</div>
                    <div class="fw-bold text-muted">indisponível</div></div>`;
        }
        if (t.prod === 0) {
            return `<div class="flex-fill"><div class="small text-muted">${rotulo}</div>
                    <div class="fw-bold text-muted">sem produção</div></div>`;
        }
        const pct = (t.insp / t.prod) * 100;
        const cor = corPct(pct);
        return `
            <div class="flex-fill" style="min-width: 150px;">
                <div class="d-flex justify-content-between align-items-baseline">
                    <span class="small text-muted">${rotulo}</span>
                    <span class="fw-bold" style="font-size: 1.25rem; color: ${cor};">${pct.toFixed(1).replace('.', ',')}%</span>
                </div>
                <div class="progress" style="height: 6px;">
                    <div class="progress-bar" role="progressbar" style="width: ${Math.min(pct, 100)}%; background-color: ${cor};"></div>
                </div>
                <div class="small text-muted mt-1">${t.insp.toLocaleString('pt-BR')} de ${t.prod.toLocaleString('pt-BR')} peças inspecionadas</div>
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
            return blocoPeriodo(rotulo, tMes);
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
