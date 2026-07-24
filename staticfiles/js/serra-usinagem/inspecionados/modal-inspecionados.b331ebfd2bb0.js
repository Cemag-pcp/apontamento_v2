function escaparHtmlSerraUsinagem(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function campoFichaSerraUsinagem(label, value) {
    return `
        <div class="ficha-field">
            <span class="ficha-field-label">${escaparHtmlSerraUsinagem(label)}</span>
            <span class="ficha-field-value">${escaparHtmlSerraUsinagem(value || "-")}</span>
        </div>`;
}

function montarTabelaMedidasSerraUsinagem(medidasPorProcesso) {
    if (!medidasPorProcesso || !Object.keys(medidasPorProcesso).length) return "";

    const linhas = [];
    Object.entries(medidasPorProcesso).forEach(([tipoProcesso, detalhes]) => {
        const detalhesPorAmostra = {};
        detalhes.forEach((detalhe) => {
            if (!detalhesPorAmostra[detalhe.amostra]) detalhesPorAmostra[detalhe.amostra] = [];
            detalhesPorAmostra[detalhe.amostra].push(detalhe);
        });

        Object.entries(detalhesPorAmostra).forEach(([amostra, detalhesAmostra]) => {
            detalhesAmostra.forEach((detalhe) => {
                linhas.push(`
                    <tr>
                        <td>${escaparHtmlSerraUsinagem(tipoProcesso)}</td>
                        <td>${escaparHtmlSerraUsinagem(amostra)}</td>
                        <td>${escaparHtmlSerraUsinagem(detalhe.cabecalho)}</td>
                        <td>${escaparHtmlSerraUsinagem(detalhe.valor)}mm</td>
                        <td class="${detalhe.conforme ? "text-success" : "text-danger"}">${detalhe.conforme ? "Sim" : "Nao"}</td>
                    </tr>`);
            });
        });
    });

    if (!linhas.length) return "";

    return `
        <div class="ficha-table-wrap mt-3${linhas.length > 10 ? " is-scrollable-y" : ""}">
            <table class="ficha-unidades-table">
                <thead>
                    <tr>
                        <th>Processo</th>
                        <th>Amostra</th>
                        <th>Cabecalho</th>
                        <th>Valor</th>
                        <th>Conforme</th>
                    </tr>
                </thead>
                <tbody>${linhas.join("")}</tbody>
            </table>
        </div>`;
}

function montarTabelaCausasSerraUsinagem(causas) {
    if (!Array.isArray(causas) || !causas.length) return "";

    const linhas = causas.map((causa, index) => {
        const imagens = Array.isArray(causa.imagens) && causa.imagens.length
            ? `<div class="ficha-nc-gallery">${causa.imagens.map((imagem) => `
                <a href="${escaparHtmlSerraUsinagem(imagem.url)}" target="_blank" rel="noopener noreferrer">
                    <img src="${escaparHtmlSerraUsinagem(imagem.url)}" alt="Nao conformidade ${index + 1}">
                </a>`).join("")}</div>`
            : "-";

        return `
            <tr>
                <td>${index + 1}</td>
                <td>${escaparHtmlSerraUsinagem((causa.nomes || []).join(", ") || "-")}</td>
                <td>${escaparHtmlSerraUsinagem(causa.quantidade ?? 0)}</td>
                <td>${escaparHtmlSerraUsinagem(causa.destino || "-")}</td>
                <td>${imagens}</td>
            </tr>`;
    }).join("");

    return `
        <div class="ficha-section mt-3 mb-0">
            <div class="ficha-section-title">Causas da nao conformidade</div>
            <div class="ficha-table-wrap">
                <table class="ficha-unidades-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Causas</th>
                            <th>Quantidade</th>
                            <th>Destino</th>
                            <th>Imagens</th>
                        </tr>
                    </thead>
                    <tbody>${linhas}</tbody>
                </table>
            </div>
        </div>`;
}

function montarInfoAdicionaisSerraUsinagem(infoAdicionais) {
    if (!infoAdicionais) return "";

    return `
        <div class="ficha-section">
            <div class="ficha-section-title">Informacoes adicionais</div>
            <div class="ficha-fields">
                ${campoFichaSerraUsinagem("Inspecao completa", infoAdicionais.inspecao_completa ? "Sim" : "Nao")}
                ${infoAdicionais.ficha_url
                    ? `<div class="ficha-field">
                        <span class="ficha-field-label">Ficha</span>
                        <span class="ficha-field-value">
                            <a href="${escaparHtmlSerraUsinagem(infoAdicionais.ficha_url)}" target="_blank" rel="noopener noreferrer">Ver imagem</a>
                        </span>
                    </div>`
                    : ""}
            </div>
        </div>`;
}

function montarExecucaoSerraUsinagem(element, index, total) {
    const isFirstItem = index === 0;
    const naoConformeQtd = Number(element.nao_conformidade ?? 0);
    const resultado = naoConformeQtd > 0 ? "Nao conforme" : "Conforme";
    const resultClass = naoConformeQtd > 0 ? "nao-conforme" : "conforme";
    const titulo = element.num_execucao === 0 ? "Inspecao" : "Reinspecao";
    const trashIcon = isFirstItem
        ? `<i class="bi bi-trash trash-history-last-execution"
                data-id="${escaparHtmlSerraUsinagem(element.id)}"
                data-id-inspecao="${escaparHtmlSerraUsinagem(element.id_inspecao)}"
                data-nao-conformidade="${escaparHtmlSerraUsinagem(element.nao_conformidade)}"
                data-conformidade="${escaparHtmlSerraUsinagem(element.conformidade)}"
                data-data="${escaparHtmlSerraUsinagem(element.data_execucao)}"
                data-primeira-execucao="${total - 1}"
                data-bs-toggle="tooltip"
                data-bs-placement="top"
                data-bs-custom-class="custom-tooltip"
                data-bs-title="Deseja excluir esta execucao?"></i>`
        : `<i class="bi bi-trash trash-history-others-execution"
                data-bs-toggle="tooltip"
                data-bs-placement="top"
                data-bs-custom-class="custom-tooltip"
                data-bs-title="Exclua a ultima execucao para conseguir excluir a execucao #${escaparHtmlSerraUsinagem(element.num_execucao)}"></i>`;

    return `
        <div class="ficha-execucao-card" data-id="${escaparHtmlSerraUsinagem(element.id)}" data-nao-conformidade="${escaparHtmlSerraUsinagem(element.nao_conformidade)}" data-data="${escaparHtmlSerraUsinagem(element.data_execucao)}">
            <div class="ficha-execucao-header">
                <h6 class="ficha-execucao-title">${titulo} #${escaparHtmlSerraUsinagem(element.num_execucao)}</h6>
                ${trashIcon}
            </div>
            <div class="ficha-execucao-body">
                <div class="ficha-resultado-box ${resultClass}">
                    <span class="ficha-resultado-pill ${resultClass}">${resultado}</span>
                    <div class="ficha-fields flex-grow-1">
                        ${campoFichaSerraUsinagem("Data da execucao", element.data_execucao)}
                        ${campoFichaSerraUsinagem("Inspetor", element.inspetor)}
                        ${campoFichaSerraUsinagem("Conformidade", element.conformidade)}
                        ${campoFichaSerraUsinagem("Nao conformidade", element.nao_conformidade)}
                    </div>
                </div>
                ${montarTabelaCausasSerraUsinagem(element.causas)}
                ${montarInfoAdicionaisSerraUsinagem(element.info_adicionais)}
                ${montarTabelaMedidasSerraUsinagem(element.medidas_por_processo)}
            </div>
        </div>`;
}

function carregarCausasDaExecucaoSerraUsinagem(element) {
    const naoConformeQtd = Number(element.nao_conformidade ?? 0);
    if (naoConformeQtd <= 0) return Promise.resolve({ ...element, causas: [] });

    return fetch(`/inspecao/api/historico-causas-serra-usinagem/${element.id}`, {
        method: "GET",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
        },
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro na requisicao HTTP. Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => ({ ...element, causas: data.causas || [] }));
}

function montarFichaSerraUsinagem(data, button) {
    const history = Array.isArray(data.history) ? data.history : [];
    const ultima = history[0] || {};
    const naoConformeQtd = Number(ultima.nao_conformidade ?? button.dataset.naoConformidade ?? 0);
    const resultado = naoConformeQtd > 0 ? "Nao conforme" : "Conforme";
    const resultClass = naoConformeQtd > 0 ? "nao-conforme" : "conforme";
    const geradoEm = new Date().toLocaleString("pt-BR");
    const registroId = button.dataset.id || "";

    const dadosItem = [
        ["Peca", button.dataset.peca],
        ["Tipo", button.dataset.tipo],
        ["Maquina", button.dataset.maquina],
        ["Data da ultima inspecao", button.dataset.data],
        ["Conformidade", button.dataset.conformidade],
        ["Nao conformidade", button.dataset.naoConformidade],
    ].map(([label, value]) => campoFichaSerraUsinagem(label, value)).join("");

    return `
        <div class="ficha-doc-header">
            <div>
                <div class="ficha-doc-title">Ficha de Inspecao de Serra e Usinagem</div>
                <div class="ficha-doc-subtitle">Controle de qualidade - serra e usinagem</div>
            </div>
            <div class="ficha-doc-id">
                <strong>#${escaparHtmlSerraUsinagem(registroId || "-")}</strong>
                Emitido em ${escaparHtmlSerraUsinagem(geradoEm)}
            </div>
        </div>

        <div class="ficha-section">
            <div class="ficha-section-title">Dados do item</div>
            <div class="ficha-fields">${dadosItem}</div>
        </div>

        <div class="ficha-section">
            <div class="ficha-section-title">Resultado da inspecao</div>
            <div class="ficha-resultado-box ${resultClass}">
                <span class="ficha-resultado-pill ${resultClass}">${resultado}</span>
                <div class="ficha-fields flex-grow-1">
                    ${campoFichaSerraUsinagem("Data da inspecao", ultima.data_execucao || button.dataset.data)}
                    ${campoFichaSerraUsinagem("Inspetor", ultima.inspetor)}
                    ${campoFichaSerraUsinagem("Conformidade", ultima.conformidade ?? button.dataset.conformidade)}
                    ${campoFichaSerraUsinagem("Nao conformidade", ultima.nao_conformidade ?? button.dataset.naoConformidade)}
                </div>
            </div>
        </div>

        <div class="ficha-section">
            <div class="ficha-section-title">Historico de execucoes</div>
            ${history.length
                ? history.map((element, index) => montarExecucaoSerraUsinagem(element, index, history.length)).join("")
                : `<p class="text-muted mb-0">Nenhuma execucao encontrada.</p>`}
        </div>

        <div class="ficha-doc-footer">
            <span>Inspecao de Serra e Usinagem - sistema de qualidade</span>
            <span>Registro #${escaparHtmlSerraUsinagem(registroId || "-")} - ${escaparHtmlSerraUsinagem(geradoEm)}</span>
        </div>`;
}

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        const button = event.target.closest(".historico-inspecao");
        if (!button) return;

        const buttonSeeDetails = document.querySelectorAll(".historico-inspecao");
        buttonSeeDetails.forEach((detailsButton) => {
            detailsButton.disabled = true;
        });
        button.querySelector(".spinner-border").style.display = "flex";
        const containerFicha = document.getElementById("ficha-doc-serra-usinagem");
        const id = button.getAttribute("data-id");

        containerFicha.innerHTML = "";

        fetch(`/inspecao/api/historico-serra-usinagem/${id}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
            },
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro na requisicao HTTP. Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const history = Array.isArray(data.history) ? data.history : [];
            return Promise.all(history.map(carregarCausasDaExecucaoSerraUsinagem))
                .then(historyComCausas => ({ ...data, history: historyComCausas }));
        })
        .then(data => {
            containerFicha.innerHTML = montarFichaSerraUsinagem(data, button);

            const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltips.forEach(t => new bootstrap.Tooltip(t));
            const modal = new bootstrap.Modal(document.getElementById("modal-historico-serra-usinagem"));
            modal.show();
        })
        .catch(error => {
            console.error(error);
            Swal.fire({
                icon: "error",
                title: "Erro",
                text: "Ocorreu um erro ao carregar o historico de inspecao.",
                confirmButtonText: "OK"
            });
        })
        .finally(() => {
            buttonSeeDetails.forEach((detailsButton) => {
                detailsButton.disabled = false;
            });
            button.querySelector(".spinner-border").style.display = "none";
        });
    });

    document.addEventListener("click", function(event) {
        if (event.target.closest(".bi-trash")) {
            if(event.target.classList.contains("trash-history-last-execution")) {
                const confirmModal = bootstrap.Modal.getInstance(document.getElementById("modal-historico-serra-usinagem"));
                confirmModal.hide();

                const id = event.target.getAttribute("data-id");
                const idInspecao = event.target.getAttribute("data-id-inspecao");
                const conformidade = event.target.getAttribute("data-conformidade");
                const naoConformidade = event.target.getAttribute("data-nao-conformidade");
                const dataExecucao = event.target.getAttribute("data-data");
                const indexItem = event.target.getAttribute("data-primeira-execucao");

                let textDescricao;
                if (parseInt(indexItem) !== 0) {
                    textDescricao = "Tem certeza que deseja excluir esta execucao? Ao excluir o item sera retornado para 'Itens a Reinspecionar'";
                } else {
                    textDescricao = "Tem certeza que deseja excluir esta execucao? Ao excluir o item sera retornado para 'Itens a Inspecionar'";
                }

                document.getElementById("modal-execucao-conformidade").textContent = conformidade;
                document.getElementById("modal-execucao-nao-conformidade").textContent = naoConformidade;
                document.getElementById("modal-execucao-data").textContent = dataExecucao;
                document.getElementById("descricao-exclusao").textContent = textDescricao;

                document.getElementById("confirmar-exclusao").setAttribute("data-execucao-id", id);
                document.getElementById("confirmar-exclusao").setAttribute("data-inspecao-id", idInspecao);
                document.getElementById("confirmar-exclusao").setAttribute("primeira-execucao", parseInt(indexItem) === 0);

                const modalExcluirExecution = new bootstrap.Modal(document.getElementById("modal-excluir-execucao"));
                modalExcluirExecution.show();
            }
            return;
        }

    });
});
