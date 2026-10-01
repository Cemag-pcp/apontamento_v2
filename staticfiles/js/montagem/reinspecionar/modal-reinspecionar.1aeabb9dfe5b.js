function construirChecklistUnidadeReinspecaoMontagem(indiceUnidade) {
    const itensCausas = CAUSAS_MONTAGEM.map((causa) => `
        <div class="checklist-causa-item" data-causa-nome="${causa.nome}">
            <div class="d-flex justify-content-between align-items-center checklist-causa-header">
                <span class="checklist-causa-label">${causa.nome}</span>
                <div class="btn-group btn-group-sm" role="group">
                    <input type="radio" class="btn-check causa-status-ok" name="status-causa-reinsp-${indiceUnidade}-${causa.id}" id="ok-causa-reinsp-${indiceUnidade}-${causa.id}" value="ok" autocomplete="off">
                    <label class="btn btn-outline-success" for="ok-causa-reinsp-${indiceUnidade}-${causa.id}" title="OK" aria-label="OK"><i class="bi bi-check-lg"></i></label>

                    <input type="radio" class="btn-check causa-status-nok" name="status-causa-reinsp-${indiceUnidade}-${causa.id}" id="nok-causa-reinsp-${indiceUnidade}-${causa.id}" value="${causa.id}" data-causa-id="${causa.id}" data-causa-nome="${causa.nome}" autocomplete="off">
                    <label class="btn btn-outline-danger" for="nok-causa-reinsp-${indiceUnidade}-${causa.id}" title="Não OK" aria-label="Não OK"><i class="bi bi-x-lg"></i></label>
                </div>
            </div>
            <div class="checklist-causa-detalhes" style="display:none;">
                <label class="label-modal">Imagem (obrigatória):<span class="text-danger"> *</span></label>
                <input class="form-control form-control-sm causa-imagens" type="file" accept="image/*" multiple>
                <div class="invalid-feedback">Anexe ao menos uma foto desta não conformidade.</div>
            </div>
        </div>
    `).join("");

    return `
        <div class="unidade-checklist-card" data-unidade="${indiceUnidade}">
            <div class="unidade-checklist-header" data-bs-toggle="collapse" data-bs-target="#unidade-checklist-reinsp-body-${indiceUnidade}">
                <span class="unidade-checklist-titulo">Unidade ${indiceUnidade}</span>
                <span class="unidade-status-badge badge bg-secondary">Pendente</span>
            </div>
            <div class="collapse" id="unidade-checklist-reinsp-body-${indiceUnidade}">
                <div class="checklist-causas-montagem">
                    ${itensCausas}
                </div>
            </div>
        </div>
    `;
}

function renderizarUnidadesChecklistReinspecaoMontagem(quantidade) {
    const container = document.getElementById("unidades-checklist-reinspecao-montagem");
    let html = "";
    for (let i = 1; i <= quantidade; i++) {
        html += construirChecklistUnidadeReinspecaoMontagem(i);
    }
    container.innerHTML = html;
    atualizarContadoresConformidadeReinspecaoMontagem();
}

function alternarDetalhesCausaReinspecaoMontagem(radio) {
    const item = radio.closest(".checklist-causa-item");
    const detalhes = item.querySelector(".checklist-causa-detalhes");
    const marcadoComoNaoOk = item.querySelector(".causa-status-nok").checked;

    if (marcadoComoNaoOk) {
        detalhes.style.display = "block";
    } else {
        detalhes.style.display = "none";
        item.querySelector(".causa-imagens").value = "";
        item.querySelector(".causa-imagens").classList.remove("is-invalid");
    }
}

function atualizarContadoresConformidadeReinspecaoMontagem() {
    const totalCausas = CAUSAS_MONTAGEM.length;
    const cards = document.querySelectorAll("#unidades-checklist-reinspecao-montagem .unidade-checklist-card");
    let conformes = 0;
    let naoConformes = 0;

    cards.forEach((card) => {
        const okCount = card.querySelectorAll(".causa-status-ok:checked").length;
        const nokCount = card.querySelectorAll(".causa-status-nok:checked").length;
        const respondidos = okCount + nokCount;
        const badge = card.querySelector(".unidade-status-badge");

        if (respondidos < totalCausas) {
            badge.textContent = "Pendente";
            badge.className = "unidade-status-badge badge bg-secondary";
        } else if (nokCount > 0) {
            naoConformes++;
            badge.textContent = "Não conforme";
            badge.className = "unidade-status-badge badge bg-danger";
        } else {
            conformes++;
            badge.textContent = "Conforme";
            badge.className = "unidade-status-badge badge bg-success";
        }
    });

    document.getElementById("conformidade-reinspecao-montagem").value = conformes;
    document.getElementById("nao-conformidade-reinspecao-montagem").value = naoConformes;
}

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-reinspecao')) {

            document.getElementById("form-reinspecao").reset();

            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const totalReinspecao = event.target.getAttribute("data-nao-conformidade");

            document.getElementById("id-reinspecao-montagem").value = id;
            document.getElementById("data-finalizada-reinspecao-montagem").value = data;
            document.getElementById("peca-reinspecao-montagem").value = peca;
            document.getElementById("qtd-reinspecao-montagem").value = totalReinspecao;

            renderizarUnidadesChecklistReinspecaoMontagem(Math.max(parseInt(totalReinspecao, 10) || 1, 1));

            const modal = new bootstrap.Modal(document.getElementById("modal-reinspecionar-montagem"));
            modal.show();
        }
    })

    document.getElementById("unidades-checklist-reinspecao-montagem").addEventListener("change", function(event) {
        if (event.target.classList.contains("causa-status-ok") || event.target.classList.contains("causa-status-nok")) {
            alternarDetalhesCausaReinspecaoMontagem(event.target);
            atualizarContadoresConformidadeReinspecaoMontagem();
        }
    });
})
