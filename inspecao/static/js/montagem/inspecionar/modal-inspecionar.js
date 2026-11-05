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
        <div class="checklist-causa-item" data-causa-nome="${causa.nome}" data-chave="${indiceUnidade}-${causa.id}">
            <div class="d-flex justify-content-between align-items-center checklist-causa-header">
                <span class="checklist-causa-label">${causa.nome}</span>
                <div class="btn-group btn-group-sm" role="group">
                    <input type="radio" class="btn-check causa-status-ok" name="status-causa-${indiceUnidade}-${causa.id}" id="ok-causa-${indiceUnidade}-${causa.id}" value="ok" autocomplete="off">
                    <label class="btn btn-outline-success" for="ok-causa-${indiceUnidade}-${causa.id}" title="OK">OK</label>

                    <input type="radio" class="btn-check causa-status-nok" name="status-causa-${indiceUnidade}-${causa.id}" id="nok-causa-${indiceUnidade}-${causa.id}" value="${causa.id}" data-causa-id="${causa.id}" data-causa-nome="${causa.nome}" autocomplete="off">
                    <label class="btn btn-outline-danger" for="nok-causa-${indiceUnidade}-${causa.id}" title="Não OK" aria-label="Não OK">Ñ OK</label>
                </div>
            </div>
            <div class="checklist-causa-detalhes" style="display:none;">
                <label class="label-modal">Imagem (obrigatória):<span class="text-danger"> *</span></label>
                <div class="fotos-salvas small mb-1"></div>
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

// Muda a quantidade de unidades sem perder o que já foi respondido nelas
// (as respostas ficam no DOM; só as unidades acima da nova quantidade saem)
function renderizarUnidadesChecklistMontagem(quantidade) {
    const container = document.getElementById("unidades-checklist-montagem");
    const cards = container.querySelectorAll(".unidade-checklist-card");
    for (let i = cards.length; i > quantidade; i--) {
        // fotos já salvas de unidades removidas deixam de valer
        cards[i - 1].querySelectorAll(".checklist-causa-item").forEach((item) => {
            fotosSalvasDoItemMontagem(item).forEach((foto) => RASCUNHO_MONTAGEM.removidas.add(String(foto.id)));
        });
        cards[i - 1].remove();
    }
    let html = "";
    for (let i = cards.length + 1; i <= quantidade; i++) {
        html += construirChecklistUnidadeMontagem(i);
    }
    container.insertAdjacentHTML("beforeend", html);
    renderizarFotosSalvasMontagem();
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
        // fotos já salvas deste item deixam de valer (somem no próximo salvar/enviar)
        fotosSalvasDoItemMontagem(item).forEach((foto) => RASCUNHO_MONTAGEM.removidas.add(String(foto.id)));
        renderizarFotosSalvasMontagem();
    }
}

// ===== "Salvar parcial" =====
// Respostas e fotos ficam no servidor (mesma API da pintura); RASCUNHO_MONTAGEM
// guarda as fotos já salvas da inspeção aberta e as marcadas para remover.
const RASCUNHO_MONTAGEM = { fotos: [], removidas: new Set() };

function urlRascunhoMontagem(idInspecao) {
    return `/inspecao/api/rascunho-inspecao-montagem/${idInspecao}/`;
}

// itens sem data-chave (checklist da reinspeção) não têm rascunho
function fotosSalvasDoItemMontagem(item) {
    if (!item.dataset.chave) return [];
    return RASCUNHO_MONTAGEM.fotos.filter(
        (foto) => foto.chave === item.dataset.chave && !RASCUNHO_MONTAGEM.removidas.has(String(foto.id))
    );
}

function renderizarFotosSalvasMontagem() {
    document.querySelectorAll("#unidades-checklist-montagem .checklist-causa-item").forEach((item) => {
        const alvo = item.querySelector(".fotos-salvas");
        if (!alvo) return;
        const fotos = fotosSalvasDoItemMontagem(item);
        alvo.innerHTML = fotos.map((foto, i) => `
            <span class="badge text-bg-light border me-1 mb-1">
                <a href="${foto.url}" target="_blank" rel="noopener">Foto salva ${i + 1}</a>
                <button type="button" class="btn btn-link btn-sm p-0 ms-1 text-danger remover-foto-rascunho-montagem" data-foto-id="${foto.id}" title="Remover foto">&times;</button>
            </span>`).join("");
    });
}

function coletarDadosRascunhoMontagem() {
    const itens = {};
    document.querySelectorAll("#unidades-checklist-montagem .checklist-causa-item").forEach((item) => {
        const ok = item.querySelector(".causa-status-ok").checked;
        const nok = item.querySelector(".causa-status-nok").checked;
        if (!ok && !nok) return;
        itens[item.dataset.chave] = { status: ok ? "ok" : "nok" };
    });
    return {
        data_inspecao: document.getElementById("data-inspecao-montagem").value,
        inspetor: document.getElementById("inspetor-inspecao-montagem").value,
        observacao: document.getElementById("observacao-inspecao-montagem").value,
        qtd_inspecionada: document.getElementById("qtd-inspecao-montagem").value,
        itens,
    };
}

function aplicarRascunhoMontagem(dados, fotos) {
    RASCUNHO_MONTAGEM.fotos = fotos || [];
    RASCUNHO_MONTAGEM.removidas = new Set();
    if (dados.data_inspecao) document.getElementById("data-inspecao-montagem").value = dados.data_inspecao;
    const inspetor = document.getElementById("inspetor-inspecao-montagem");
    if (dados.inspetor && inspetor.querySelector(`option[value="${dados.inspetor}"]`)) inspetor.value = dados.inspetor;
    if (dados.observacao) document.getElementById("observacao-inspecao-montagem").value = dados.observacao;

    // quantidade inspecionada salva (dentro do limite da produzida)
    const quantidade = limitarQtdInspecaoMontagem(dados.qtd_inspecionada || 1);
    document.getElementById("qtd-inspecao-montagem").value = quantidade;
    renderizarUnidadesChecklistMontagem(quantidade);

    Object.entries(dados.itens || {}).forEach(([chave, resposta]) => {
        const item = document.querySelector(`#unidades-checklist-montagem .checklist-causa-item[data-chave="${chave}"]`);
        if (!item) return;
        item.querySelector(resposta.status === "ok" ? ".causa-status-ok" : ".causa-status-nok").checked = true;
        item.querySelector(".checklist-causa-detalhes").style.display = resposta.status === "nok" ? "block" : "none";
    });
    renderizarFotosSalvasMontagem();
    atualizarContadoresConformidadeMontagem();
}

function carregarRascunhoMontagem(idInspecao) {
    const info = document.getElementById("rascunho-montagem-info");
    info.textContent = "";
    fetch(urlRascunhoMontagem(idInspecao))
        .then((r) => (r.ok ? r.json() : { existe: false }))
        .catch(() => ({ existe: false }))
        .then((resposta) => {
            // o modal pode ter sido aberto em outra inspeção enquanto buscava
            if (document.getElementById("id-inspecao-montagem").value !== String(idInspecao) || !resposta.existe) return;
            aplicarRascunhoMontagem(resposta.dados || {}, resposta.fotos);
            info.textContent = `Rascunho salvo${resposta.usuario ? ` por ${resposta.usuario}` : ""} em ${resposta.atualizado_em}`;
        });
}

// Foto reduzida (máx. 1280px, JPEG) antes de ir para o servidor; se falhar, vai a original
function comprimirImagemMontagem(arquivo) {
    return new Promise((resolve) => {
        const url = URL.createObjectURL(arquivo);
        const img = new Image();
        img.onload = () => {
            const escala = Math.min(1, 1280 / Math.max(img.width, img.height));
            const canvas = document.createElement("canvas");
            canvas.width = Math.round(img.width * escala);
            canvas.height = Math.round(img.height * escala);
            canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
            canvas.toBlob(
                (blob) => resolve(blob ? new File([blob], `img_${Date.now()}.jpg`, { type: "image/jpeg" }) : arquivo),
                "image/jpeg",
                0.7
            );
        };
        img.onerror = () => { URL.revokeObjectURL(url); resolve(arquivo); };
        img.src = url;
    });
}

async function salvarParcialMontagem() {
    const idInspecao = document.getElementById("id-inspecao-montagem").value;
    if (!idInspecao) return;
    const botao = document.getElementById("salvar-parcial-montagem");
    botao.disabled = true;
    botao.querySelector(".spinner-border").style.display = "flex";

    try {
        const formData = new FormData();
        formData.append("dados", JSON.stringify(coletarDadosRascunhoMontagem()));
        RASCUNHO_MONTAGEM.removidas.forEach((id) => formData.append("remover_fotos", id));
        // fotos novas dos itens "Ñ OK"
        for (const item of document.querySelectorAll("#unidades-checklist-montagem .checklist-causa-item")) {
            if (!item.querySelector(".causa-status-nok").checked) continue;
            for (const arquivo of item.querySelector(".causa-imagens").files) {
                formData.append(`foto__${item.dataset.chave}`, await comprimirImagemMontagem(arquivo));
            }
        }

        const resposta = await fetch(urlRascunhoMontagem(idInspecao), {
            method: "POST",
            headers: { "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value },
            body: formData,
        });
        const data = await resposta.json().catch(() => ({}));
        if (!resposta.ok) throw new Error(data.error || "Falha ao salvar a inspeção parcial.");

        // fotos agora estão no servidor: limpa os campos e mostra como "Foto salva"
        RASCUNHO_MONTAGEM.fotos = data.fotos || [];
        RASCUNHO_MONTAGEM.removidas = new Set();
        document.querySelectorAll("#unidades-checklist-montagem .causa-imagens").forEach((input) => {
            input.value = "";
            input.classList.remove("is-invalid");
        });
        renderizarFotosSalvasMontagem();
        document.getElementById("rascunho-montagem-info").textContent = "Rascunho salvo agora";
        Swal.fire({ toast: true, position: "bottom-end", icon: "success", title: "Inspeção salva parcialmente", showConfirmButton: false, timer: 3000 });
        if (typeof buscarItensInspecao === "function") buscarItensInspecao(1);
    } catch (error) {
        Swal.fire({ icon: "error", title: "Erro ao salvar parcial", text: error.message });
    } finally {
        botao.disabled = false;
        botao.querySelector(".spinner-border").style.display = "none";
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
            const item = radio.closest(".checklist-causa-item");
            const input = item.querySelector(".causa-imagens");
            // vale foto nova ou já salva no "Salvar parcial"
            if (input.files.length > 0 || fotosSalvasDoItemMontagem(item).length > 0) {
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

            RASCUNHO_MONTAGEM.fotos = [];
            RASCUNHO_MONTAGEM.removidas = new Set();
            document.getElementById("unidades-checklist-montagem").innerHTML = "";
            renderizarUnidadesChecklistMontagem(1);
            carregarRascunhoMontagem(id);

            const modal = new bootstrap.Modal(document.getElementById("modal-inspecionar-montagem"));
            modal.show();
        }

        // remover uma foto já salva no rascunho (sai de vez no próximo salvar/enviar)
        const botaoRemover = event.target.closest(".remover-foto-rascunho-montagem");
        if (botaoRemover) {
            RASCUNHO_MONTAGEM.removidas.add(String(botaoRemover.dataset.fotoId));
            renderizarFotosSalvasMontagem();
        }
    })

    document.getElementById("salvar-parcial-montagem").addEventListener("click", salvarParcialMontagem);

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
