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
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="mb-2">
                                <a href="https://drive.google.com/drive/u/0/search?q=${googleSearch}"
                                   target="_blank" rel="noopener noreferrer">
                                   ${item.peca || "-"}
                                </a>
                            </h5>

                            <p class="mb-2">Ordem #${item.ordem_numero || "-"}</p>

                            <p class="mb-0">
                                <strong>📅 Data da inspeção:</strong> ${item.data_inspecao || "-"}<br>
                                <strong>📍 Máquina:</strong> ${item.conjunto || "-"}
                            </p>
                        </div>
                        <button class="btn btn-sm btn-outline-danger btn-desfazer-inspecao" data-peca-id="${item.peca_id}" title="Desfazer inspeção" style="display: none;">
                            <i class="bi bi-trash"></i>
                        </button>
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
                // Adicionar evento para o botão de desfazer inspeção
                const btnDesfazer = card.querySelector(".btn-desfazer-inspecao");
                if (btnDesfazer && podeDesfazerInspecao) {
                    btnDesfazer.style.display = 'block';
                    btnDesfazer.addEventListener("click", async (e) => {
                        e.stopPropagation();
                        await desfazerInspecaoCorte(item.peca_id, item.peca);
                    });
                }
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

function escaparHtmlCorte(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function campoFichaCorte(label, value) {
    return `
        <div class="ficha-field">
            <span class="ficha-field-label">${escaparHtmlCorte(label)}</span>
            <span class="ficha-field-value">${escaparHtmlCorte(value || "-")}</span>
        </div>`;
}

function montarTabelaNaoConformidadesCorte(naoConformidades) {
    if (!Array.isArray(naoConformidades) || !naoConformidades.length) return "";

    const linhas = naoConformidades.map((nc, index) => {
        const causas = Array.isArray(nc.causas) && nc.causas.length ? nc.causas.join(", ") : "-";
        const imagens = Array.isArray(nc.imagens) && nc.imagens.length
            ? `<div class="ficha-nc-gallery">${nc.imagens.map((url) => `
                <a href="${escaparHtmlCorte(url)}" target="_blank" rel="noopener noreferrer">
                    <img src="${escaparHtmlCorte(url)}" alt="Nao conformidade ${index + 1}">
                </a>`).join("")}</div>`
            : "-";

        return `
            <tr>
                <td>${index + 1}</td>
                <td>${escaparHtmlCorte(causas)}</td>
                <td>${escaparHtmlCorte(nc.quantidade ?? 0)}</td>
                <td>${escaparHtmlCorte(nc.destino || "-")}</td>
                <td>${imagens}</td>
            </tr>`;
    }).join("");

    return `
        <div class="ficha-section">
            <div class="ficha-section-title">Nao conformidades</div>
            <div class="ficha-table-wrap">
                <table class="ficha-unidades-table">
                    <thead><tr><th>#</th><th>Causas</th><th>Quantidade</th><th>Destino</th><th>Imagens</th></tr></thead>
                    <tbody>${linhas}</tbody>
                </table>
            </div>
        </div>`;
}

function montarFichaInspecaoCorte(data) {
    const naoConformeQtd = Number(data.nao_conformidade ?? 0);
    const resultado = naoConformeQtd > 0 ? "Nao conforme" : "Conforme";
    const resultClass = naoConformeQtd > 0 ? "nao-conforme" : "conforme";
    const geradoEm = new Date().toLocaleString("pt-BR");
    const dadosPeca = [
        ["Peca", data.peca],
        ["Ordem", data.ordem],
        ["Maquina", data.conjunto],
        ["Qtd planejada", data.qtd_planejada],
        ["Qtd cortada", data.qtd_boa],
        ["Qtd morta", data.qtd_morta],
    ].map(([label, value]) => campoFichaCorte(label, value)).join("");
    const dadosInspecao = [
        ["Data da inspecao", data.data_inspecao],
        ["Inspetor", data.inspetor],
        ["Conformes", data.conformidade ?? 0],
        ["Nao conformes", naoConformeQtd],
    ].map(([label, value]) => campoFichaCorte(label, value)).join("");
    const ficha100 = data.ficha_100_url
        ? `<div class="ficha-section">
               <div class="ficha-section-title">Ficha Inspecao 100%</div>
               <a href="${escaparHtmlCorte(data.ficha_100_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary">
                   <i class="bi bi-file-earmark-text"></i> Visualizar ficha
               </a>
           </div>`
        : "";

    return `
        <div class="ficha-doc-header">
            <div>
                <div class="ficha-doc-title">Ficha de Inspecao de Corte</div>
                <div class="ficha-doc-subtitle">Controle de qualidade - plasma</div>
            </div>
            <div class="ficha-doc-id">
                <strong>#${escaparHtmlCorte(data.inspecao_id || "-")}</strong>
                Emitido em ${escaparHtmlCorte(geradoEm)}
            </div>
        </div>
        <div class="ficha-section">
            <div class="ficha-section-title">Dados da peca</div>
            <div class="ficha-fields">${dadosPeca}</div>
        </div>
        <div class="ficha-section">
            <div class="ficha-section-title">Resultado da inspecao</div>
            <div class="ficha-resultado-box ${resultClass}">
                <span class="ficha-resultado-pill ${resultClass}">${resultado}</span>
                <div class="ficha-fields flex-grow-1">${dadosInspecao}</div>
            </div>
            ${data.observacao ? `<div class="ficha-resultado-obs mt-2"><i class="bi bi-chat-left-text me-1"></i>${escaparHtmlCorte(data.observacao)}</div>` : ""}
        </div>
        ${montarTabelaNaoConformidadesCorte(data.nao_conformidades)}
        ${ficha100}
        <div class="ficha-doc-footer">
            <span>Inspecao de Corte - sistema de qualidade</span>
            <span>Registro #${escaparHtmlCorte(data.inspecao_id || "-")} - ${escaparHtmlCorte(geradoEm)}</span>
        </div>`;
}

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

        const container = document.getElementById("lista-historico-pecas-corte");
        container.innerHTML = montarFichaInspecaoCorte(data);

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

async function desfazerInspecaoCorte(pecaId, pecaNome) {
    try {
        const result = await Swal.fire({
            icon: "warning",
            title: "Confirmar Exclusão",
            html: `Tem certeza que deseja desfazer a inspeção da peça <strong>${pecaNome || pecaId}</strong>?<br><br>Esta ação não pode ser desfeita.`,
            showCancelButton: true,
            confirmButtonColor: "#dc3545",
            cancelButtonColor: "#6c757d",
            confirmButtonText: "Sim, desfazer",
            cancelButtonText: "Cancelar"
        });

        if (!result.isConfirmed) {
            return;
        }

        // Mostrar loading
        Swal.fire({
            title: "Processando...",
            text: "Desfazendo inspeção",
            allowOutsideClick: false,
            allowEscapeKey: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
        const response = await fetch("/inspecao/api/desfazer-inspecao-corte/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            credentials: "same-origin",
            body: JSON.stringify({ peca_id: pecaId })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Erro ao desfazer inspeção");
        }

        // Sucesso
        await Swal.fire({
            icon: "success",
            title: "Sucesso!",
            text: "Inspeção desfeita com sucesso",
            timer: 2000,
            showConfirmButton: false
        });

        // Recarregar a lista de inspecionados e pendências
        await buscarInspecionados(1);
        
        // Verificar se a função buscarPendencias existe (do arquivo a-inspecionar-corte.js)
        if (typeof buscarPendencias === 'function') {
            await buscarPendencias(1);
        }

    } catch (error) {
        console.error("Erro ao desfazer inspeção:", error);
        Swal.fire({
            icon: "error",
            title: "Erro",
            text: error.message || "Erro ao desfazer inspeção"
        });
    }
}




