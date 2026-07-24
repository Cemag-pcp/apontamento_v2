function escaparHtmlEstamparia(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function campoFichaEstamparia(label, value) {
    return `
        <div class="ficha-field">
            <span class="ficha-field-label">${escaparHtmlEstamparia(label)}</span>
            <span class="ficha-field-value">${escaparHtmlEstamparia(value || "-")}</span>
        </div>`;
}

function montarTabelaMedidasEstamparia(medidas) {
    if (!Array.isArray(medidas) || !medidas.length) return "";

    const linhas = medidas.map((medida, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escaparHtmlEstamparia(medida.cabecalhoMedidaA || "-")}</td>
            <td>${escaparHtmlEstamparia(medida.medidaA || "-")}</td>
            <td>${escaparHtmlEstamparia(medida.cabecalhoMedidaB || "-")}</td>
            <td>${escaparHtmlEstamparia(medida.medidaB || "-")}</td>
            <td>${escaparHtmlEstamparia(medida.cabecalhoMedidaC || "-")}</td>
            <td>${escaparHtmlEstamparia(medida.medidaC || "-")}</td>
            <td>${escaparHtmlEstamparia(medida.cabecalhoMedidaD || "-")}</td>
            <td>${escaparHtmlEstamparia(medida.medidaD || "-")}</td>
        </tr>`).join("");

    return `
        <div class="ficha-table-wrap mt-3${medidas.length > 10 ? " is-scrollable-y" : ""}">
            <table class="ficha-unidades-table">
                <thead>
                    <tr>
                        <th>Amostra</th>
                        <th>Cabecalho A</th>
                        <th>Medida A</th>
                        <th>Cabecalho B</th>
                        <th>Medida B</th>
                        <th>Cabecalho C</th>
                        <th>Medida C</th>
                        <th>Cabecalho D</th>
                        <th>Medida D</th>
                    </tr>
                </thead>
                <tbody>${linhas}</tbody>
            </table>
        </div>`;
}

function montarTabelaCausasEstamparia(causas) {
    if (!Array.isArray(causas) || !causas.length) return "";

    const linhas = causas.map((causa, index) => {
        const imagens = Array.isArray(causa.imagens) && causa.imagens.length
            ? `<div class="ficha-nc-gallery">${causa.imagens.map((imagem) => `
                <a href="${escaparHtmlEstamparia(imagem.url)}" target="_blank" rel="noopener noreferrer">
                    <img src="${escaparHtmlEstamparia(imagem.url)}" alt="Nao conformidade ${index + 1}">
                </a>`).join("")}</div>`
            : "-";

        return `
            <tr>
                <td>${index + 1}</td>
                <td>${escaparHtmlEstamparia((causa.nomes || []).join(", ") || "-")}</td>
                <td>${escaparHtmlEstamparia(causa.quantidade ?? 0)}</td>
                <td>${escaparHtmlEstamparia(causa.destino || "-")}</td>
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

function montarInfoAdicionaisEstamparia(infoAdicionais) {
    if (!infoAdicionais) return "";

    return `
        <div class="ficha-section">
            <div class="ficha-section-title">Informacoes adicionais</div>
            <div class="ficha-fields">
                ${campoFichaEstamparia("Inspecao completa", infoAdicionais.inspecao_completa ? "Sim" : "Nao")}
                ${campoFichaEstamparia("Qtd mortas", infoAdicionais.qtd_mortas ?? 0)}
                ${campoFichaEstamparia("Motivo mortas", (infoAdicionais.motivo_mortas || []).join(", ") || "-")}
                ${infoAdicionais.ficha_url
                    ? `<div class="ficha-field">
                        <span class="ficha-field-label">Ficha</span>
                        <span class="ficha-field-value">
                            <a href="${escaparHtmlEstamparia(infoAdicionais.ficha_url)}" target="_blank" rel="noopener noreferrer">Ver imagem</a>
                        </span>
                    </div>`
                    : ""}
            </div>
        </div>`;
}

function montarExecucaoEstamparia(element, index, total) {
    const isFirstItem = index === 0;
    const naoConformeQtd = Number(element.nao_conformidade ?? 0);
    const resultado = naoConformeQtd > 0 ? "Nao conforme" : "Conforme";
    const resultClass = naoConformeQtd > 0 ? "nao-conforme" : "conforme";
    const titulo = element.num_execucao === 0 ? "Inspecao" : "Reinspecao";
    const trashIcon = isFirstItem
        ? `<i class="bi bi-trash trash-history-last-execution"
                data-id="${escaparHtmlEstamparia(element.id)}"
                data-id-inspecao="${escaparHtmlEstamparia(element.id_inspecao)}"
                data-nao-conformidade="${escaparHtmlEstamparia(element.nao_conformidade)}"
                data-conformidade="${escaparHtmlEstamparia(element.conformidade)}"
                data-data="${escaparHtmlEstamparia(element.data_execucao)}"
                data-primeira-execucao="${total - 1}"
                data-bs-toggle="tooltip"
                data-bs-placement="top"
                data-bs-custom-class="custom-tooltip"
                data-bs-title="Deseja excluir esta execucao?"></i>`
        : `<i class="bi bi-trash trash-history-others-execution"
                data-bs-toggle="tooltip"
                data-bs-placement="top"
                data-bs-custom-class="custom-tooltip"
                data-bs-title="Exclua a ultima execucao para conseguir excluir a execucao #${escaparHtmlEstamparia(element.num_execucao)}"></i>`;

    return `
        <div class="ficha-execucao-card">
            <div class="ficha-execucao-header">
                <h6 class="ficha-execucao-title">${titulo} #${escaparHtmlEstamparia(element.num_execucao)}</h6>
                ${trashIcon}
            </div>
            <div class="ficha-execucao-body">
                <div class="ficha-resultado-box ${resultClass}">
                    <span class="ficha-resultado-pill ${resultClass}">${resultado}</span>
                    <div class="ficha-fields flex-grow-1">
                        ${campoFichaEstamparia("Data da execucao", element.data_execucao)}
                        ${campoFichaEstamparia("Inspetor", element.inspetor)}
                        ${campoFichaEstamparia("Conformidade", element.conformidade)}
                        ${campoFichaEstamparia("Nao conformidade", element.nao_conformidade)}
                    </div>
                </div>
                ${montarTabelaCausasEstamparia(element.causas)}
                ${montarInfoAdicionaisEstamparia(element.info_adicionais)}
                ${montarTabelaMedidasEstamparia(element.medidas_inspecao)}
            </div>
        </div>`;
}

function carregarCausasDaExecucaoEstamparia(element) {
    const naoConformeQtd = Number(element.nao_conformidade ?? 0);
    if (naoConformeQtd <= 0) return Promise.resolve({ ...element, causas: [] });

    return fetch(`/inspecao/api/historico-causas-estamparia/${element.id}`, {
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

function montarFichaEstamparia(data, button) {
    const history = Array.isArray(data.history) ? data.history : [];
    const ultima = history[0] || {};
    const naoConformeQtd = Number(ultima.nao_conformidade ?? button.dataset.naoConformidade ?? 0);
    const resultado = naoConformeQtd > 0 ? "Nao conforme" : "Conforme";
    const resultClass = naoConformeQtd > 0 ? "nao-conforme" : "conforme";
    const geradoEm = new Date().toLocaleString("pt-BR");
    const registroId = button.dataset.id || "";

    const dadosItem = [
        ["Peca", button.dataset.peca],
        ["Maquina", button.dataset.maquina],
        ["Data da ultima inspecao", button.dataset.data],
        ["Conformidade", ultima.conformidade ?? button.dataset.conformidade],
        ["Nao conformidade", ultima.nao_conformidade ?? button.dataset.naoConformidade],
    ].map(([label, value]) => campoFichaEstamparia(label, value)).join("");

    return `
        <div class="ficha-doc-header">
            <div>
                <div class="ficha-doc-title">Ficha de Inspecao de Estamparia</div>
                <div class="ficha-doc-subtitle">Controle de qualidade - estamparia</div>
            </div>
            <div class="ficha-doc-id">
                <strong>#${escaparHtmlEstamparia(registroId || "-")}</strong>
                Emitido em ${escaparHtmlEstamparia(geradoEm)}
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
                    ${campoFichaEstamparia("Data da inspecao", ultima.data_execucao || button.dataset.data)}
                    ${campoFichaEstamparia("Inspetor", ultima.inspetor)}
                    ${campoFichaEstamparia("Conformidade", ultima.conformidade ?? button.dataset.conformidade)}
                    ${campoFichaEstamparia("Nao conformidade", ultima.nao_conformidade ?? button.dataset.naoConformidade)}
                </div>
            </div>
        </div>

        <div class="ficha-section">
            <div class="ficha-section-title">Historico de execucoes</div>
            ${history.length
                ? history.map((element, index) => montarExecucaoEstamparia(element, index, history.length)).join("")
                : `<p class="text-muted mb-0">Nenhuma execucao encontrada.</p>`}
        </div>

        <div class="ficha-doc-footer">
            <span>Inspecao de Estamparia - sistema de qualidade</span>
            <span>Registro #${escaparHtmlEstamparia(registroId || "-")} - ${escaparHtmlEstamparia(geradoEm)}</span>
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
        const containerFicha = document.getElementById("ficha-doc-estamparia");
        const id = button.getAttribute("data-id");

        containerFicha.innerHTML = "";

        fetch(`/inspecao/api/historico-estamparia/${id}`, {
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
            return Promise.all(history.map(carregarCausasDaExecucaoEstamparia))
                .then(historyComCausas => ({ ...data, history: historyComCausas }));
        })
        .then(data => {
            containerFicha.innerHTML = montarFichaEstamparia(data, button);

            const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltips.forEach(t => new bootstrap.Tooltip(t));
            const modal = new bootstrap.Modal(document.getElementById("modal-historico-estamparia"));
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
        if (!event.target.closest(".bi-trash")) return;
        if(event.target.classList.contains("trash-history-last-execution")) {
            const confirmModal = bootstrap.Modal.getInstance(document.getElementById("modal-historico-estamparia"));
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
    });
});
