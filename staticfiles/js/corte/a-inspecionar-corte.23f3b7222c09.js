const pendenciasConfig = {
    containerId: "cards-pendencias-corte",
    totalId: "qtd-pendente-corte",
    totalFiltradoId: "qtd-filtrada-pendencias",
    filtroDataId: "filtro-pendencias-data",
    filtroPesquisaId: "filtro-pendencias-pesquisa",
    paginacaoId: "paginacao-pendencias-corte",
    inputPesquisaId: "pesquisar-ordem-pendencias",
    inputDataInicioId: "data-inicio-pendencias",
    inputDataFimId: "data-fim-pendencias",
    btnFiltrarId: "btn-filtrar-pendencias",
    btnLimparId: "btn-limpar-pendencias",
    templateId: "template-card-pendencia-corte",
    endpoint: "/inspecao/api/itens-inspecao-corte/",
};

function getInputValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = text;
    }
}

function setVisible(id, visible, text) {
    const el = document.getElementById(id);
    if (!el) {
        return;
    }
    el.style.display = visible ? "inline-block" : "none";
    if (text !== undefined) {
        el.textContent = text;
    }
}

function montarParametrosPendencias(pagina) {
    const params = new URLSearchParams();
    const pesquisa = getInputValue(pendenciasConfig.inputPesquisaId).trim();
    const dataInicio = getInputValue(pendenciasConfig.inputDataInicioId);
    const dataFim = getInputValue(pendenciasConfig.inputDataFimId);

    if (pesquisa) {
        params.append("pesquisar", pesquisa);
        setVisible(pendenciasConfig.filtroPesquisaId, true, `Pesquisa: ${pesquisa}`);
    } else {
        setVisible(pendenciasConfig.filtroPesquisaId, false);
    }

    if (dataInicio) {
        params.append("data_inicio", dataInicio);
    }
    if (dataFim) {
        params.append("data_fim", dataFim);
    }

    if (dataInicio || dataFim) {
        const faixa = dataFim && dataInicio ? `${dataInicio} ate ${dataFim}` : (dataInicio || dataFim);
        setVisible(pendenciasConfig.filtroDataId, true, `Data: ${faixa}`);
    } else {
        setVisible(pendenciasConfig.filtroDataId, false);
    }

    params.append("pagina", pagina);

    return params;
}

function renderizarPaginacao(containerId, paginaAtual, totalPaginas, onClick) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }

    if (totalPaginas <= 1) {
        container.innerHTML = "";
        return;
    }

    const nav = document.createElement("nav");
    const ul = document.createElement("ul");
    ul.className = "pagination justify-content-center";

    for (let i = 1; i <= totalPaginas; i += 1) {
        const li = document.createElement("li");
        li.className = `page-item ${i === paginaAtual ? "active" : ""}`;

        const a = document.createElement("a");
        a.className = "page-link";
        a.href = "#";
        a.textContent = i;
        a.addEventListener("click", (event) => {
            event.preventDefault();
            onClick(i);
        });

        li.appendChild(a);
        ul.appendChild(li);
    }

    nav.appendChild(ul);
    container.innerHTML = "";
    container.appendChild(nav);
}

function renderizarPeca(peca, ordemId, index) {
    const template = document.getElementById("template-peca-corte");
    if (!template) {
        return null;
    }

    const clone = template.content.cloneNode(true);
    const uniqueId = `ordem-${ordemId}-peca-${index}`;

    const header = clone.querySelector(".accordion-header");
    const button = clone.querySelector(".accordion-button");
    const collapse = clone.querySelector(".accordion-collapse");
    const nomePeca = clone.querySelector(".peca-nome");
    const qtdPeca = clone.querySelector(".peca-qtd");
    const inputPeca = clone.querySelector(".peca-nome-input");
    const form = clone.querySelector(".form-inspecao-peca-corte");

    if (header) {
        header.id = `heading-${uniqueId}`;
    }

    if (button) {
        button.setAttribute("data-bs-target", `#collapse-${uniqueId}`);
        button.setAttribute("aria-controls", `collapse-${uniqueId}`);
    }

    if (collapse) {
        collapse.id = `collapse-${uniqueId}`;
        collapse.setAttribute("aria-labelledby", `heading-${uniqueId}`);
        collapse.setAttribute("data-bs-parent", "#lista-pecas-corte");
    }

    if (nomePeca) {
        nomePeca.textContent = peca.peca || "-";
    }

    if (qtdPeca) {
        qtdPeca.textContent = peca.qtd_boa ?? 0;
    }

    if (inputPeca) {
        inputPeca.value = peca.peca || "";
    }

    if (form) {
        form.dataset.ordemId = ordemId;
        form.dataset.pecaId = peca.id;
        form.dataset.qtdPeca = peca.qtd_boa ?? 0;
    }

    const radios = clone.querySelectorAll('input[type="radio"][name^="conformidade-"]');
    radios.forEach((radio) => {
        const parts = radio.name.split("-");
        const rowId = parts[1] || "1";
        radio.name = `conformidade-${uniqueId}-${rowId}`;
    });

    return clone;
}

async function abrirModalOrdem(ordemData) {
    const ordemId = ordemData.ordem_id;
    const modalOrdem = document.getElementById("modal-ordem-corte");

    if (!modalOrdem) {
        return;
    }

    const inputNumero = document.getElementById("modal-ordem-corte-numero");
    const inputConjunto = document.getElementById("modal-ordem-corte-conjunto");
    const inputQtd = document.getElementById("modal-ordem-corte-qtd");

    if (inputNumero) {
        inputNumero.value = ordemData.ordem_numero || "-";
    }
    if (inputConjunto) {
        inputConjunto.value = ordemData.conjunto || "-";
    }
    if (inputQtd) {
        inputQtd.value = ordemData.qtd_boa || 0;
    }

    const lista = document.getElementById("lista-pecas-corte");
    if (lista) {
        lista.innerHTML = '<div class="text-center py-3"><span class="spinner-border" role="status" aria-hidden="true"></span></div>';
    }

    try {
        const response = await fetch(`/inspecao/api/ordem-corte/${ordemId}/`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            throw new Error(`Erro HTTP! Status: ${response.status}`);
        }

        const payload = await response.json();
        const pecas = payload.pecas || [];

        if (lista) {
            lista.innerHTML = "";
        }

        if (!pecas.length) {
            if (lista) {
                lista.innerHTML = '<p class="text-muted mb-0">Nenhuma peca encontrada para esta ordem.</p>';
            }
            return;
        }

        pecas.forEach((peca, index) => {
            const item = renderizarPeca(peca, ordemId, index + 1);
            if (item && lista) {
                lista.appendChild(item);
            }
        });
    } catch (error) {
        if (lista) {
            lista.innerHTML = '<p class="text-danger mb-0">Erro ao carregar pecas da ordem.</p>';
        }
        console.error(error);
    }
}

async function buscarPendencias(pagina) {
    const cardsContainer = document.getElementById(pendenciasConfig.containerId);
    if (!cardsContainer) {
        return;
    }

    cardsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';

    const params = montarParametrosPendencias(pagina);

    try {
        const response = await fetch(`${pendenciasConfig.endpoint}?${params.toString()}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            throw new Error(`Erro HTTP! Status: ${response.status}`);
        }

        const data = await response.json();

        setText(pendenciasConfig.totalId, `${data.total} pendencias`);
        if (params.size > 1) {
            setVisible(pendenciasConfig.totalFiltradoId, true, `${data.total_filtrado} filtrados`);
        } else {
            setVisible(pendenciasConfig.totalFiltradoId, false);
        }

        cardsContainer.innerHTML = "";
        const template = document.getElementById(pendenciasConfig.templateId);

        if (!template || !data.dados.length) {
            cardsContainer.innerHTML = '<p class="text-muted">Sem pendencias para exibir.</p>';
        } else {
            data.dados.forEach((item) => {
                console.log(item);
                
                const clone = template.content.cloneNode(true);
                const conjunto = clone.querySelector(".ordem-conjunto");
                const qtd = clone.querySelector(".ordem-qtd");
                const dataSpan = clone.querySelector(".ordem-data");
                const numero = clone.querySelector(".ordem-numero");
                const botao = clone.querySelector(".btn-ver-ordem");

                if (conjunto) {
                    conjunto.textContent = item.conjunto || "-";
                }
                if (qtd) {
                    qtd.textContent = item.qtd_boa ?? 0;
                }
                if (dataSpan) {
                    dataSpan.textContent = item.data ?? "-";
                }
                if (numero) {
                    numero.textContent = item.ordem_numero;
                }
                if (botao) {
                    botao.addEventListener("click", () => abrirModalOrdem(item));
                }

                cardsContainer.appendChild(clone);
            });
        }

        renderizarPaginacao(
            pendenciasConfig.paginacaoId,
            data.pagina_atual,
            data.total_paginas,
            buscarPendencias
        );
    } catch (error) {
        cardsContainer.innerHTML = '<p class="text-danger">Erro ao carregar pendencias.</p>';
        console.error(error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const btnFiltrar = document.getElementById(pendenciasConfig.btnFiltrarId);
    const btnLimpar = document.getElementById(pendenciasConfig.btnLimparId);

    if (btnFiltrar) {
        btnFiltrar.addEventListener("click", (event) => {
            event.preventDefault();
            buscarPendencias(1);
        });
    }

    if (btnLimpar) {
        btnLimpar.addEventListener("click", (event) => {
            event.preventDefault();
            const form = document.getElementById("form-filtrar-pendencias-corte");
            if (form) {
                form.querySelectorAll("input").forEach((input) => {
                    input.value = "";
                });
            }
            buscarPendencias(1);
        });
    }

    buscarPendencias(1);
});
