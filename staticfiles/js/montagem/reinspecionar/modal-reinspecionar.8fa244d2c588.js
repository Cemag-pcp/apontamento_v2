// Mesmo checklist em 3 grupos da inspeção (construirGruposChecklistMontagem
// e demais funções vêm de inspecionar/modal-inspecionar.js)
function construirChecklistUnidadeReinspecaoMontagem(indiceUnidade) {
    return `
        <div class="unidade-checklist-card" data-unidade="${indiceUnidade}">
            <div class="unidade-checklist-header" data-bs-toggle="collapse" data-bs-target="#unidade-checklist-reinsp-body-${indiceUnidade}">
                <span class="unidade-checklist-titulo">Unidade ${indiceUnidade}</span>
                <span class="unidade-status-badge badge bg-secondary">Pendente</span>
            </div>
            <div class="collapse" id="unidade-checklist-reinsp-body-${indiceUnidade}">
                <div class="checklist-causas-montagem">
                    ${construirGruposChecklistMontagem(indiceUnidade, "reinsp", false)}
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
    aplicarStatusGrupoMontagem(item, item.querySelector(".causa-status-nok").checked);
}

function atualizarContadoresConformidadeReinspecaoMontagem() {
    const totalCausas = totalItensChecklistMontagem();
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
        if (event.target.classList.contains("outros-causa-check")) {
            const erro = event.target.closest(".checklist-causa-item").querySelector(".outros-causas-erro");
            if (erro) erro.style.display = "none";
        }
    });
})
