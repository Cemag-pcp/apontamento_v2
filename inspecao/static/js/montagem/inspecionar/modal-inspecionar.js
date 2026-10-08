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
                <label class="label-modal">Imagem (obrigatória):<span class="text-danger"> *</span></label>
                <input class="form-control form-control-sm causa-imagens" type="file" accept="image/*" multiple>
                <div class="invalid-feedback">Anexe ao menos uma foto desta não conformidade.</div>
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
        item.querySelector(".causa-imagens").classList.remove("is-invalid");
    }
}

// Toda causa marcada como "Não OK" precisa de ao menos uma foto, em cada
// unidade. Usada na inspecao e na reinspecao (envio-reinspecao.js).
// Marca os campos sem foto, abre a primeira unidade com pendencia e
// devolve a lista "Unidade N: Causa" pra mensagem de erro.
function validarImagensNaoConformidadeMontagem(container) {
    const pendencias = [];
    let primeiroCampo = null;

    container.querySelectorAll(".unidade-checklist-card").forEach((card) => {
        card.querySelectorAll(".causa-status-nok:checked").forEach((radio) => {
            const input = radio.closest(".checklist-causa-item").querySelector(".causa-imagens");
            if (input.files.length > 0) {
                input.classList.remove("is-invalid");
                return;
            }
            input.classList.add("is-invalid");
            pendencias.push(`Unidade ${card.dataset.unidade}: ${radio.dataset.causaNome}`);
            if (!primeiroCampo) primeiroCampo = input;
        });
    });

    if (primeiroCampo) {
        const corpo = primeiroCampo.closest(".collapse");
        if (corpo) bootstrap.Collapse.getOrCreateInstance(corpo, { toggle: false }).show();
        primeiroCampo.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    return pendencias;
}

// Ao escolher a foto, tira o destaque de erro do campo
document.addEventListener("change", (event) => {
    if (event.target.classList.contains("causa-imagens") && event.target.files.length > 0) {
        event.target.classList.remove("is-invalid");
    }
});

// Qtd. Inspecionada vai de 1 ate a quantidade produzida (apontada)
function maximoQtdInspecaoMontagem() {
    const produzida = parseInt(document.getElementById("qtd-produzida-montagem").value, 10);
    return Math.max(Number.isFinite(produzida) ? produzida : 1, 1);
}

function limitarQtdInspecaoMontagem(valor) {
    return Math.min(Math.max(parseInt(valor, 10) || 1, 1), maximoQtdInspecaoMontagem());
}

function atualizarContadoresConformidadeMontagem() {
    const totalCausas = CAUSAS_MONTAGEM.length;
    // so as unidades deste modal: o de reinspecao (mesma pagina) tambem tem
    // .unidade-checklist-card e entrava na conta
    const cards = document.querySelectorAll("#unidades-checklist-montagem .unidade-checklist-card");
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
            const campoQtd = document.getElementById("qtd-inspecao-montagem");
            const maximoQtd = maximoQtdInspecaoMontagem();
            campoQtd.max = maximoQtd;
            campoQtd.value = 1;
            document.getElementById("qtd-inspecao-montagem-limite").textContent = `Máximo: ${maximoQtd} (produzida)`;

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
        // acima da produzida volta na hora pro maximo
        const quantidade = limitarQtdInspecaoMontagem(this.value);
        if (parseInt(this.value, 10) !== quantidade) {
            this.value = quantidade;
        }
        renderizarUnidadesChecklistMontagem(quantidade);
    });

    document.getElementById("qtd-inspecao-montagem").addEventListener("blur", function() {
        const quantidade = limitarQtdInspecaoMontagem(this.value);
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
