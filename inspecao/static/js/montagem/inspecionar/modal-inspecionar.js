let CAUSAS_MONTAGEM = [];
try {
    const elCausas = document.getElementById("causas-montagem-data");
    CAUSAS_MONTAGEM = elCausas ? JSON.parse(elCausas.textContent) : [];
} catch (e) {
    console.error("Erro ao carregar causas de montagem:", e);
    CAUSAS_MONTAGEM = [];
}

function construirChecklistUnidadeMontagem(indiceUnidade) {
    const itensCausas = CAUSAS_MONTAGEM.map((causa) => `
        <div class="checklist-causa-item" data-causa-nome="${causa.nome}">
            <div class="d-flex justify-content-between align-items-center checklist-causa-header">
                <span class="checklist-causa-label">${causa.nome}</span>
                <div class="btn-group btn-group-sm" role="group">
                    <input type="radio" class="btn-check causa-status-ok" name="status-causa-${indiceUnidade}-${causa.id}" id="ok-causa-${indiceUnidade}-${causa.id}" value="ok" autocomplete="off">
                    <label class="btn btn-outline-success" for="ok-causa-${indiceUnidade}-${causa.id}" title="OK" aria-label="OK"><i class="bi bi-check-lg"></i></label>

                    <input type="radio" class="btn-check causa-status-nok" name="status-causa-${indiceUnidade}-${causa.id}" id="nok-causa-${indiceUnidade}-${causa.id}" value="${causa.id}" data-causa-id="${causa.id}" data-causa-nome="${causa.nome}" autocomplete="off">
                    <label class="btn btn-outline-danger" for="nok-causa-${indiceUnidade}-${causa.id}" title="Não OK" aria-label="Não OK"><i class="bi bi-x-lg"></i></label>
                </div>
            </div>
            <div class="checklist-causa-detalhes" style="display:none;">
                <label class="label-modal">Imagem (opcional):</label>
                <input class="form-control form-control-sm causa-imagens" type="file" accept="image/*" multiple>
            </div>
        </div>
    `).join("");

    return `
        <div class="unidade-checklist-card" data-unidade="${indiceUnidade}">
            <div class="unidade-checklist-header" data-bs-toggle="collapse" data-bs-target="#unidade-checklist-body-${indiceUnidade}">
                <span class="unidade-checklist-titulo">Unidade ${indiceUnidade}</span>
                <span class="unidade-status-badge badge bg-secondary">Pendente</span>
            </div>
            <div class="collapse" id="unidade-checklist-body-${indiceUnidade}">
                <div class="checklist-causas-montagem">
                    ${itensCausas}
                </div>
            </div>
        </div>
    `;
}

function renderizarUnidadesChecklistMontagem(quantidade) {
    const container = document.getElementById("unidades-checklist-montagem");
    let html = "";
    for (let i = 1; i <= quantidade; i++) {
        html += construirChecklistUnidadeMontagem(i);
    }
    container.innerHTML = html;
    atualizarContadoresConformidadeMontagem();
}

function alternarDetalhesCausaMontagem(radio) {
    const item = radio.closest(".checklist-causa-item");
    const detalhes = item.querySelector(".checklist-causa-detalhes");
    const marcadoComoNaoOk = item.querySelector(".causa-status-nok").checked;

    if (marcadoComoNaoOk) {
        detalhes.style.display = "block";
    } else {
        detalhes.style.display = "none";
        item.querySelector(".causa-imagens").value = "";
    }
}

function atualizarContadoresConformidadeMontagem() {
    const totalCausas = CAUSAS_MONTAGEM.length;
    const cards = document.querySelectorAll(".unidade-checklist-card");
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

    document.getElementById("conformidade-inspecao-montagem").value = conformes;
    document.getElementById("nao-conformidade-inspecao-montagem").value = naoConformes;
}

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-inspecao')) {

            document.getElementById("form-inspecao").reset();

            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const apontada = event.target.getAttribute("data-qtd");

            document.getElementById("id-inspecao-montagem").value = id;
            document.getElementById("data-finalizada-inspecao-montagem").value = data;
            document.getElementById("peca-inspecao-montagem").value = peca;
            document.getElementById("qtd-produzida-montagem").value = apontada;
            document.getElementById("qtd-inspecao-montagem").value = 1;

            renderizarUnidadesChecklistMontagem(1);

            const modal = new bootstrap.Modal(document.getElementById("modal-inspecionar-montagem"));
            modal.show();
        }
    })

    document.getElementById("qtd-inspecao-montagem").addEventListener("input", function() {
        // Permite deixar o campo vazio enquanto o usuario esta digitando
        // (ex: apagando pra trocar o numero) - so corrige pro minimo (1) no blur.
        if (this.value === "") {
            return;
        }
        const quantidade = Math.max(parseInt(this.value, 10) || 1, 1);
        if (parseInt(this.value, 10) !== quantidade) {
            this.value = quantidade;
        }
        renderizarUnidadesChecklistMontagem(quantidade);
    });

    document.getElementById("qtd-inspecao-montagem").addEventListener("blur", function() {
        const quantidade = Math.max(parseInt(this.value, 10) || 1, 1);
        if (this.value === "" || parseInt(this.value, 10) !== quantidade) {
            this.value = quantidade;
            renderizarUnidadesChecklistMontagem(quantidade);
        }
    });

    document.getElementById("unidades-checklist-montagem").addEventListener("change", function(event) {
        if (event.target.classList.contains("causa-status-ok") || event.target.classList.contains("causa-status-nok")) {
            alternarDetalhesCausaMontagem(event.target);
            atualizarContadoresConformidadeMontagem();
        }
    });
})
