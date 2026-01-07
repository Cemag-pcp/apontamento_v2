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
    if (!cardsContainer) return;

    // container em grid (2 col no md+, 1 col no mobile)
    cardsContainer.classList.add("row", "g-3");
    cardsContainer.innerHTML = `
        <div class="col-12 text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;

    const params = montarParametrosInspecionados(pagina);

    try {
        const response = await fetch(`${inspecionadosConfig.endpoint}?${params.toString()}`, {
            method: "GET",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin"
        });

        if (!response.ok) throw new Error(`Erro HTTP! Status: ${response.status}`);

        const data = await response.json();

        const totalSpan = document.getElementById(inspecionadosConfig.totalId);
        const totalFiltradoSpan = document.getElementById(inspecionadosConfig.totalFiltradoId);

        if (totalSpan) totalSpan.textContent = `${data.total} inspecionados`;

        if (totalFiltradoSpan) {
            if (params.size > 1) {
                totalFiltradoSpan.style.display = "inline-block";
                totalFiltradoSpan.textContent = `${data.total_filtrado} filtrados`;
            } else {
                totalFiltradoSpan.style.display = "none";
            }
        }

        cardsContainer.innerHTML = "";

        if (!data.dados.length) {
            cardsContainer.classList.remove("row", "g-3");
            cardsContainer.innerHTML = '<p class="text-muted">Sem inspecionados para exibir.</p>';
        } else {
            data.dados.forEach(item => {
                const col = document.createElement("div");
                col.className = "col-12 col-md-6 col-lg-4"; // 1 por linha no mobile, 2 no md, 3 no lg
                console.log(item);
                const card = document.createElement("div");
                card.className = "card p-3 border-undefined h-100";
                card.style.minHeight = "300px";
                card.style.display = "flex";
                card.style.flexDirection = "column";
                card.style.justifyContent = "space-between";

                const googleSearch = encodeURIComponent(item.peca || "");

                card.innerHTML = `
                    <div>
                        <h5 class="mb-2">
                            <a href="https://drive.google.com/drive/u/0/search?q=${googleSearch}"
                               target="_blank" rel="noopener noreferrer">
                               ${item.peca || "-"}
                            </a>
                        </h5>

                        <p class="mb-2">Ordem #${item.ordem_numero || "-"}</p>

                        <p class="mb-0">
                            <strong>📅 Data da última inspeção:</strong> ${item.data_inspecao || "-"}<br>
                            <strong>📍 Máquina:</strong> ${item.conjunto || "-"}
                        </p>
                    </div>

                    <hr class="my-3">

                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-baseline gap-2">
                            <span class="badge rounded-pill ${item.nao_conformidade === 0 ? 'bg-success' : 'bg-danger'}">
                                <i class="bi ${item.nao_conformidade === 0 ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} me-1"></i>
                                ${item.nao_conformidade === 0 ? 'Conforme' : 'Não conforme'}
                            </span>
                        </div>

                        <button class="btn btn-white w-50 d-flex justify-content-center align-items-center gap-2 btn-ver-peca">
                            <span class="spinner-border spinner-border-sm" style="display:none"></span>
                            Ver detalhes
                        </button>
                    </div>
                `;

                const btnVer = card.querySelector(".btn-ver-peca");
                btnVer.innerHTML = `
                    <span class="spinner-border spinner-border-sm me-2" style="display:none"></span>
                    <span class="btn-text">Ver detalhes</span>
                `;

                btnVer.addEventListener("click", async () => {
                    const spinner = btnVer.querySelector(".spinner-border");
                    const text = btnVer.querySelector(".btn-text");

                    // Disable all btn-ver-peca buttons
                    const allBtns = document.querySelectorAll(".btn-ver-peca");
                    allBtns.forEach(btn => btn.disabled = true);

                    spinner.style.display = "inline-block";
                    text.textContent = "Carregando...";

                    try {
                        await abrirModalPeca(item.peca_id);
                    } finally {
                        spinner.style.display = "none";
                        text.textContent = "Ver detalhes";

                        // Re-enable all btn-ver-peca buttons
                        allBtns.forEach(btn => btn.disabled = false);
                    }
                });

                col.appendChild(card);
                cardsContainer.appendChild(col);
            });
        }

        renderizarPaginacaoInspecionados(
            inspecionadosConfig.paginacaoId,
            data.pagina_atual,
            data.total_paginas,
            buscarInspecionados
        );

    } catch (error) {
        cardsContainer.classList.remove("row", "g-3");
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

async function abrirModalPeca(pecaId) {
    try {
        const response = await fetch(`/inspecao/api/detalhes-inspecao-corte/${pecaId}/`, {
            method: "GET",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin"
        });

        if (response.status === 401) {
            window.location.href = `/core/login/?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
            return;
        }

        if (!response.ok) {
            throw new Error(`Erro HTTP! Status: ${response.status}`);
        }

        const data = await response.json();
        
        console.log(data);

        const container = document.getElementById("lista-historico-pecas-corte");
        container.innerHTML = "";

        const section = document.createElement("section");
        section.className = "py-3";

        const timeline = document.createElement("ul");
        timeline.className = "timeline";

        const item = document.createElement("li");
        item.className = "timeline-item";

        const naoConformeQtd = Number(data.nao_conformidade ?? 0);
        const iconClass = naoConformeQtd > 0 ? "bi-x-circle-fill" : "bi-check-circle-fill";
        const statusClass = naoConformeQtd > 0 ? "danger" : "success";

        item.innerHTML = `
            <span class="timeline-icon ${statusClass}">
                <i class="bi ${iconClass}"></i>
            </span>

            <div class="timeline-content">
                <div class="d-flex justify-content-between">
                    <h5>Inspeção #${data.inspecao_id ?? "-"}</h5>
                </div>
                <p><strong>Ordem: ${data.ordem}</strong>
                <p><strong>${data.peca}</strong>
                <p class="date">${data.data_inspecao ?? "-"}</p>
                <p><strong>Qtd cortada:</strong> ${data.qtd_boa ?? "-"}</p>
                <p><strong>Máquina:</strong> ${data.conjunto ?? "-"}</p>
                <p><strong>Inspetor:</strong> ${data.inspetor ?? "-"}</p>

                <p class="text-muted">
                    <strong>Conformidade:</strong> ${data.conformidade ?? 0}
                </p>

                ${
                    naoConformeQtd > 0
                        ? `<p class="text-danger"><strong>Não Conformidade:</strong> ${naoConformeQtd}</p>`
                        : ""
                }

                ${
                    data.observacao
                        ? `<div class="mt-3">
                               <h6 class="mb-2">Observações:</h6>
                               <p class="mb-0">${data.observacao}</p>
                           </div>`
                        : ""
                }

                ${
                    data.nao_conformidades?.length > 0
                        ? `<div class="mt-3">
                               <h6 class="mb-2">Não Conformidades:</h6>
                               <ul class="list-unstyled mb-0">
                                   ${data.nao_conformidades.map(nc => `
                                       <li class="mb-2">
                                           <strong>Causas:</strong> ${(nc.causas || []).join(", ")}<br>
                                           <strong>Quantidade:</strong> ${nc.quantidade ?? 0}<br>
                                           <strong>Destino:</strong> ${nc.destino ?? "-"}
                                       </li>
                                   `).join("")}
                               </ul>
                           </div>`
                        : ""
                }
            </div>
        `;

        timeline.appendChild(item);
        section.appendChild(timeline);
        container.appendChild(section);

        const modal = bootstrap.Modal.getOrCreateInstance(
            document.getElementById("modal-historico-ordem-corte")
        );
        modal.show();

    } catch (error) {
        console.error("Erro ao abrir modal da peça:", error);

        Swal.fire({
            icon: "error",
            title: "Erro",
            text: "Erro ao carregar detalhes da inspeção."
        });
    }
}




