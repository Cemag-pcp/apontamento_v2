function escaparHtmlPintura(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function campoFichaPintura(label, value) {
    return `
        <div class="ficha-field">
            <span class="ficha-field-label">${escaparHtmlPintura(label)}</span>
            <span class="ficha-field-value">${escaparHtmlPintura(value ?? "-")}</span>
        </div>`;
}

function montarTabelaCausasPintura(causas) {
    if (!Array.isArray(causas) || !causas.length) return "";

    const linhas = causas.map((causa, index) => {
        const imagens = Array.isArray(causa.imagens) && causa.imagens.length
            ? `<div class="ficha-nc-gallery">${causa.imagens.map((imagem) => `
                <a href="${escaparHtmlPintura(imagem.url)}" target="_blank" rel="noopener noreferrer">
                    <img src="${escaparHtmlPintura(imagem.url)}" alt="Não conformidade ${index + 1}">
                </a>`).join("")}</div>`
            : "-";

        return `
            <tr>
                <td>${index + 1}</td>
                <td>${escaparHtmlPintura((causa.nomes || []).join(", ") || "-")}</td>
                <td>${escaparHtmlPintura(causa.quantidade ?? 0)}</td>
                <td>${escaparHtmlPintura(causa.setor || "-")}</td>
                <td>${imagens}</td>
            </tr>`;
    }).join("");

    return `
        <div class="ficha-section mt-3 mb-0">
            <div class="ficha-section-title">Causas da não conformidade</div>
            <div class="ficha-table-wrap${causas.length > 10 ? " is-scrollable-y" : ""}">
                <table class="ficha-unidades-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Causas</th>
                            <th>Quantidade</th>
                            <th>Setor</th>
                            <th>Imagens</th>
                        </tr>
                    </thead>
                    <tbody>${linhas}</tbody>
                </table>
            </div>
        </div>`;
}

function montarGaleriaConformidadePintura(imagens) {
    if (!Array.isArray(imagens) || !imagens.length) return "";

    return `
        <div class="ficha-section mt-3 mb-0">
            <div class="ficha-section-title">Evidências de conformidade</div>
            <div class="ficha-nc-gallery">
                ${imagens.map((imagem) => `
                    <a href="${escaparHtmlPintura(imagem.url)}" target="_blank" rel="noopener noreferrer">
                        <img src="${escaparHtmlPintura(imagem.url)}" alt="Evidência de conformidade">
                    </a>`).join("")}
            </div>
        </div>`;
}

function montarExecucaoPintura(element, index, total) {
    const isFirstItem = index === 0;
    const naoConformeQtd = Number(element.nao_conformidade ?? 0);
    const resultado = naoConformeQtd > 0 ? "Não conforme" : "Conforme";
    const resultClass = naoConformeQtd > 0 ? "nao-conforme" : "conforme";
    const titulo = element.num_execucao === 0 ? "Inspeção" : "Reinspeção";
    const trashIcon = isFirstItem
        ? `<i class="bi bi-trash trash-history-last-execution"
                data-id="${escaparHtmlPintura(element.id)}"
                data-id-inspecao="${escaparHtmlPintura(element.id_inspecao)}"
                data-nao-conformidade="${escaparHtmlPintura(element.nao_conformidade)}"
                data-conformidade="${escaparHtmlPintura(element.conformidade)}"
                data-data="${escaparHtmlPintura(element.data_execucao)}"
                data-primeira-execucao="${total - 1}"
                data-bs-toggle="tooltip"
                data-bs-placement="top"
                data-bs-custom-class="custom-tooltip"
                data-bs-title="Deseja excluir esta execução?"></i>`
        : `<i class="bi bi-trash trash-history-others-execution"
                data-bs-toggle="tooltip"
                data-bs-placement="top"
                data-bs-custom-class="custom-tooltip"
                data-bs-title="Exclua a última execução para conseguir excluir a execução #${escaparHtmlPintura(element.num_execucao)}"></i>`;

    return `
        <div class="ficha-execucao-card">
            <div class="ficha-execucao-header">
                <h6 class="ficha-execucao-title">${titulo} #${escaparHtmlPintura(element.num_execucao)}</h6>
                ${trashIcon}
            </div>
            <div class="ficha-execucao-body">
                <div class="ficha-resultado-box ${resultClass}">
                    <span class="ficha-resultado-pill ${resultClass}">${resultado}</span>
                    <div class="ficha-fields flex-grow-1">
                        ${campoFichaPintura("Data da execução", element.data_execucao)}
                        ${campoFichaPintura("Inspetor", element.inspetor)}
                        ${campoFichaPintura("Conformidade", element.conformidade)}
                        ${campoFichaPintura("Não conformidade", element.nao_conformidade)}
                    </div>
                </div>
                ${montarTabelaCausasPintura(element.causas)}
                ${montarGaleriaConformidadePintura(element.imagens_conformidade)}
            </div>
        </div>`;
}

function montarFichaPintura(data, button) {
    const history = Array.isArray(data.history) ? data.history : [];
    const ultima = history[0] || {};
    const pecaInfo = data.peca_info || {};
    const naoConformeQtd = Number(ultima.nao_conformidade ?? 0);
    const resultado = naoConformeQtd > 0 ? "Não conforme" : "Conforme";
    const resultClass = naoConformeQtd > 0 ? "nao-conforme" : "conforme";
    const geradoEm = new Date().toLocaleString("pt-BR");
    const registroId = button.dataset.id || "";

    const dadosItem = [
        ["Peça", pecaInfo.peca],
        ["Ordem", pecaInfo.ordem],
        ["Máquina", pecaInfo.maquina],
        ["Cor", pecaInfo.cor],
        ["Tipo", pecaInfo.tipo],
        ["Qtd. planejada", pecaInfo.qtd_planejada],
        ["Qtd. boa", pecaInfo.qtd_boa],
        ["Qtd. morta", pecaInfo.qtd_morta],
        ["Data de carga", pecaInfo.data_carga],
        ["Operador final", pecaInfo.operador_fim],
    ].map(([label, value]) => campoFichaPintura(label, value)).join("");

    return `
        <div class="ficha-doc-header">
            <div>
                <div class="ficha-doc-title">Ficha de Inspeção de Pintura</div>
                <div class="ficha-doc-subtitle">Controle de qualidade - pintura</div>
            </div>
            <div class="ficha-doc-id">
                <strong>#${escaparHtmlPintura(registroId || "-")}</strong>
                Emitido em ${escaparHtmlPintura(geradoEm)}
            </div>
        </div>

        <div class="ficha-section">
            <div class="ficha-section-title">Dados do item</div>
            <div class="ficha-fields">${dadosItem}</div>
        </div>

        <div class="ficha-section">
            <div class="ficha-section-title">Resultado da inspeção</div>
            <div class="ficha-resultado-box ${resultClass}">
                <span class="ficha-resultado-pill ${resultClass}">${resultado}</span>
                <div class="ficha-fields flex-grow-1">
                    ${campoFichaPintura("Data da inspeção", ultima.data_execucao)}
                    ${campoFichaPintura("Inspetor", ultima.inspetor)}
                    ${campoFichaPintura("Conformidade", ultima.conformidade)}
                    ${campoFichaPintura("Não conformidade", ultima.nao_conformidade)}
                </div>
            </div>
        </div>

        <div class="ficha-section">
            <div class="ficha-section-title">Histórico de execuções</div>
            ${history.length
                ? history.map((element, index) => montarExecucaoPintura(element, index, history.length)).join("")
                : `<p class="text-muted mb-0">Nenhuma execução encontrada.</p>`}
        </div>

        <div class="ficha-doc-footer">
            <span>Inspeção de Pintura - sistema de qualidade</span>
            <span>Registro #${escaparHtmlPintura(registroId || "-")} - ${escaparHtmlPintura(geradoEm)}</span>
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
        const containerFicha = document.getElementById("ficha-doc-pintura");
        const id = button.getAttribute("data-id");

        containerFicha.innerHTML = "";

        fetch(`/inspecao/api/historico-pintura/${id}`, {
            method: "GET",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro na requisição HTTP. Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            containerFicha.innerHTML = montarFichaPintura(data, button);

            const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltips.forEach(t => new bootstrap.Tooltip(t));
            const modal = new bootstrap.Modal(document.getElementById("modal-historico-pintura"));
            modal.show();
        })
        .catch(error => {
            console.error(error);
        })
        .finally(() => {
            buttonSeeDetails.forEach((detailsButton) => {
                detailsButton.disabled = false;
            });
            button.querySelector(".spinner-border").style.display = "none";
        });
    });

    document.addEventListener("click", function(event) {
        if (!event.target.closest('.bi-trash')) return;
        if (event.target.classList.contains('trash-history-last-execution')) {
            const confirmModal = bootstrap.Modal.getInstance(document.getElementById("modal-historico-pintura"));
            confirmModal.hide();

            const id = event.target.getAttribute('data-id');
            const idInspecao = event.target.getAttribute('data-id-inspecao');
            const conformidade = event.target.getAttribute('data-conformidade');
            const naoConformidade = event.target.getAttribute('data-nao-conformidade');
            const dataExecucao = event.target.getAttribute('data-data');
            const indexItem = event.target.getAttribute('data-primeira-execucao');

            let textDescricao;
            if (parseInt(indexItem) !== 0) {
                textDescricao = "Tem certeza que deseja excluir esta execução? Ao excluir o item será retornado para 'Itens a Reinspecionar'";
            } else {
                textDescricao = "Tem certeza que deseja excluir esta execução? Ao excluir o item será retornado para 'Itens a Inspecionar'";
            }

            // Preenche o modal com os dados
            document.getElementById('modal-execucao-conformidade').textContent = conformidade;
            document.getElementById('modal-execucao-nao-conformidade').textContent = naoConformidade;
            document.getElementById('modal-execucao-data').textContent = dataExecucao;
            document.getElementById('descricao-exclusao').textContent = textDescricao;

            document.getElementById('confirmar-exclusao').setAttribute('data-execucao-id', id);
            document.getElementById('confirmar-exclusao').setAttribute('data-inspecao-id', idInspecao);
            document.getElementById('confirmar-exclusao').setAttribute('primeira-execucao', parseInt(indexItem) === 0);

            const modalExcluirExecution = new bootstrap.Modal(document.getElementById("modal-excluir-execucao"));
            modalExcluirExecution.show();
        }
    });
});
