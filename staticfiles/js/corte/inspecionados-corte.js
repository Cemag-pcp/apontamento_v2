const inspecionadosConfig = {
    containerId: "cards-inspecionados-corte",
    totalId: "qtd-inspecionados-corte",
    totalFiltradoId: "qtd-filtrada-inspecionados",
    filtroDataId: "filtro-inspecionados-data",
    filtroPesquisaId: "filtro-inspecionados-pesquisa",
    paginacaoId: "paginacao-inspecionados-corte",
    inputPesquisaId: "pesquisar-ordem-inspecionados",
    inputDataInicioId: "data-inicio-inspecionados",
    inputDataFimId: "data-fim-inspecionados",
    btnFiltrarId: "btn-filtrar-inspecionados",
    btnLimparId: "btn-limpar-inspecionados",
    templateId: "template-card-inspecionado-corte",
    endpoint: "/inspecao/api/itens-inspecionados-corte/",
};

function montarParametrosInspecionados(pagina) {
    const params = new URLSearchParams();
    const pesquisa = document.getElementById(inspecionadosConfig.inputPesquisaId)?.value.trim() || "";
    const dataInicio = document.getElementById(inspecionadosConfig.inputDataInicioId)?.value || "";
    const dataFim = document.getElementById(inspecionadosConfig.inputDataFimId)?.value || "";

    if (pesquisa) {
        params.append("pesquisar", pesquisa);
        const filtroPesquisa = document.getElementById(inspecionadosConfig.filtroPesquisaId);
        if (filtroPesquisa) {
            filtroPesquisa.style.display = "inline-block";
            filtroPesquisa.textContent = `Pesquisa: ${pesquisa}`;
        }
    } else {
        const filtroPesquisa = document.getElementById(inspecionadosConfig.filtroPesquisaId);
        if (filtroPesquisa) {
            filtroPesquisa.style.display = "none";
        }
    }

    if (dataInicio) {
        params.append("data_inicio", dataInicio);
    }
    if (dataFim) {
        params.append("data_fim", dataFim);
    }

    const filtroData = document.getElementById(inspecionadosConfig.filtroDataId);
    if (filtroData) {
        if (dataInicio || dataFim) {
            const faixa = dataFim && dataInicio ? `${dataInicio} ate ${dataFim}` : (dataInicio || dataFim);
            filtroData.style.display = "inline-block";
            filtroData.textContent = `Data: ${faixa}`;
        } else {
            filtroData.style.display = "none";
        }
    }

    params.append("pagina", pagina);
    return params;
}

function renderizarPaginacaoInspecionados(containerId, paginaAtual, totalPaginas, onClick) {
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

async function buscarInspecionados(pagina) {
    const cardsContainer = document.getElementById(inspecionadosConfig.containerId);
    if (!cardsContainer) {
        return;
    }

    cardsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';

    const params = montarParametrosInspecionados(pagina);

    try {
        const response = await fetch(`${inspecionadosConfig.endpoint}?${params.toString()}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            throw new Error(`Erro HTTP! Status: ${response.status}`);
        }

        const data = await response.json();
        const totalSpan = document.getElementById(inspecionadosConfig.totalId);
        const totalFiltradoSpan = document.getElementById(inspecionadosConfig.totalFiltradoId);

        if (totalSpan) {
            totalSpan.textContent = `${data.total} inspecionados`;
        }

        if (totalFiltradoSpan) {
            if (params.size > 1) {
                totalFiltradoSpan.style.display = "inline-block";
                totalFiltradoSpan.textContent = `${data.total_filtrado} filtrados`;
            } else {
                totalFiltradoSpan.style.display = "none";
            }
        }

        cardsContainer.innerHTML = "";
        const template = document.getElementById(inspecionadosConfig.templateId);

        if (!template || !data.dados.length) {
            cardsContainer.innerHTML = '<p class="text-muted">Sem inspecionados para exibir.</p>';
        } else {
            data.dados.forEach((item) => {
                const clone = template.content.cloneNode(true);
                clone.querySelector(".ordem-numero").textContent = item.ordem_numero ?? "-";
                clone.querySelector(".ordem-conjunto").textContent = item.conjunto || "-";
                clone.querySelector(".ordem-data").textContent = item.data || "-";
                cardsContainer.appendChild(clone);
            });
        }

        renderizarPaginacaoInspecionados(
            inspecionadosConfig.paginacaoId,
            data.pagina_atual,
            data.total_paginas,
            buscarInspecionados
        );
    } catch (error) {
        cardsContainer.innerHTML = '<p class="text-danger">Erro ao carregar inspecionados.</p>';
        console.error(error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const btnFiltrar = document.getElementById(inspecionadosConfig.btnFiltrarId);
    const btnLimpar = document.getElementById(inspecionadosConfig.btnLimparId);

    if (btnFiltrar) {
        btnFiltrar.addEventListener("click", (event) => {
            event.preventDefault();
            buscarInspecionados(1);
        });
    }

    if (btnLimpar) {
        btnLimpar.addEventListener("click", (event) => {
            event.preventDefault();
            const form = document.getElementById("form-filtrar-inspecionados-corte");
            if (form) {
                form.querySelectorAll("input").forEach((input) => {
                    input.value = "";
                });
            }
            buscarInspecionados(1);
        });
    }

    buscarInspecionados(1);
});
