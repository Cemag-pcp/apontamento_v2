// Modal "Inspecionar Pintura": checklist OK / Ñ OK por unidade inspecionada,
// no mesmo formato da inspeção da montagem (inspecao/static/js/montagem/inspecionar).
// Itens do checklist: 3 grupos (GRUPOS_PINTURA). Cada grupo lista as
// principais falhas, sempre à mostra mas só habilitadas quando o grupo é
// marcado "Ñ OK"; aí o inspetor escolhe uma ou mais e anexa a foto.
let GRUPOS_PINTURA = [];
try {
    const elCausas = document.getElementById("causas-pintura-data");
    const dadosCausas = elCausas ? JSON.parse(elCausas.textContent) : {};
    GRUPOS_PINTURA = dadosCausas.grupos || [];
} catch (e) {
    console.error("Erro ao carregar causas de pintura:", e);
}

// Respostas exigidas por unidade: uma por grupo
function totalItensChecklistPintura() {
    return GRUPOS_PINTURA.length;
}

function escaparHtmlPintura(texto) {
    const div = document.createElement("div");
    div.textContent = texto ?? "";
    return div.innerHTML;
}

function construirChecklistUnidadePintura(indiceUnidade) {
    const itensGrupos = GRUPOS_PINTURA.map((grupo, indiceGrupo) => {
        const nomeGrupo = escaparHtmlPintura(grupo.nome);
        const chave = `${indiceUnidade}-g${indiceGrupo + 1}`;
        const falhas = grupo.causas.map((causa) => `
            <div class="form-check">
                <input class="form-check-input outros-causa-check" type="checkbox" value="${causa.id}" data-causa-nome="${escaparHtmlPintura(causa.nome)}" id="falha-pintura-${chave}-${causa.id}" disabled>
                <label class="form-check-label small" for="falha-pintura-${chave}-${causa.id}">${escaparHtmlPintura(causa.nome)}</label>
            </div>`).join("");
        return `
        <div class="checklist-causa-item" data-grupo="1" data-causa-nome="${nomeGrupo}" data-chave="${chave}">
            <div class="d-flex justify-content-between align-items-center checklist-causa-header">
                <span class="checklist-causa-label">${nomeGrupo}</span>
                <div class="btn-group btn-group-sm" role="group">
                    <input type="radio" class="btn-check causa-status-ok" name="status-causa-pintura-${chave}" id="ok-causa-pintura-${chave}" value="ok" autocomplete="off">
                    <label class="btn btn-outline-success" for="ok-causa-pintura-${chave}" title="OK">OK</label>

                    <input type="radio" class="btn-check causa-status-nok" name="status-causa-pintura-${chave}" id="nok-causa-pintura-${chave}" value="nok" data-causa-nome="${nomeGrupo}" autocomplete="off">
                    <label class="btn btn-outline-danger" for="nok-causa-pintura-${chave}" title="Não OK" aria-label="Não OK">Ñ OK</label>
                </div>
            </div>
            <div class="checklist-falhas-grupo">
                <span class="label-modal-sm">Principais falhas a serem observadas:</span>
                <div class="outros-causas-lista">${falhas}</div>
                <div class="text-danger small outros-causas-erro" style="display:none;">Selecione ao menos uma falha.</div>
            </div>
            <div class="checklist-causa-detalhes" style="display:none;">
                <label class="label-modal">Imagem (obrigatória):<span class="text-danger"> *</span></label>
                <div class="fotos-salvas small mb-1"></div>
                <input class="form-control form-control-sm causa-imagens" type="file" accept="image/*" multiple>
                <div class="invalid-feedback">Anexe ao menos uma foto desta não conformidade.</div>
            </div>
        </div>`;
    }).join("");

    return `
        <div class="unidade-checklist-card" data-unidade="${indiceUnidade}">
            <div class="unidade-checklist-header" data-bs-toggle="collapse" data-bs-target="#unidade-checklist-pintura-body-${indiceUnidade}">
                <span class="unidade-checklist-titulo">Unidade ${indiceUnidade}</span>
                <span class="unidade-status-badge badge bg-secondary">Pendente</span>
            </div>
            <div class="collapse" id="unidade-checklist-pintura-body-${indiceUnidade}">
                <div class="checklist-causas-montagem">
                    ${itensGrupos}
                </div>
            </div>
        </div>
    `;
}

// Falhas do grupo: habilitadas só com o grupo em "Ñ OK"
function habilitarFalhasGrupoPintura(item, habilitar) {
    item.querySelectorAll(".outros-causa-check").forEach((check) => { check.disabled = !habilitar; });
}

function renderizarUnidadesChecklistPintura(quantidade) {
    const container = document.getElementById("unidades-checklist-pintura");
    let html = "";
    for (let i = 1; i <= quantidade; i++) {
        html += construirChecklistUnidadePintura(i);
    }
    container.innerHTML = html;
    atualizarContadoresConformidadePintura();
}

function alternarDetalhesCausaPintura(radio) {
    const item = radio.closest(".checklist-causa-item");
    const detalhes = item.querySelector(".checklist-causa-detalhes");
    const marcadoComoNaoOk = item.querySelector(".causa-status-nok").checked;

    habilitarFalhasGrupoPintura(item, marcadoComoNaoOk);
    if (marcadoComoNaoOk) {
        detalhes.style.display = "block";
    } else {
        detalhes.style.display = "none";
        item.querySelector(".causa-imagens").value = "";
        item.querySelector(".causa-imagens").classList.remove("is-invalid");
        // grupo voltou para OK: desmarca as falhas escolhidas
        item.querySelectorAll(".outros-causa-check").forEach((check) => { check.checked = false; });
        const erro = item.querySelector(".outros-causas-erro");
        if (erro) erro.style.display = "none";
        // fotos já salvas deste item deixam de valer (somem no próximo salvar/enviar)
        fotosSalvasDoItemPintura(item).forEach((foto) => RASCUNHO_PINTURA.removidas.add(String(foto.id)));
        renderizarFotosSalvasPintura();
    }
}

// ===== "Salvar parcial" (lote que chega em partes) =====
// Respostas e fotos ficam no servidor; RASCUNHO_PINTURA guarda as fotos já
// salvas da inspeção aberta e as marcadas para remover.
const RASCUNHO_PINTURA = { fotos: [], removidas: new Set() };

function urlRascunhoPintura(idInspecao) {
    return `/inspecao/api/rascunho-inspecao-pintura/${idInspecao}/`;
}

function fotosSalvasDoItemPintura(item) {
    return RASCUNHO_PINTURA.fotos.filter(
        (foto) => foto.chave === item.dataset.chave && !RASCUNHO_PINTURA.removidas.has(String(foto.id))
    );
}

function renderizarFotosSalvasPintura() {
    document.querySelectorAll("#unidades-checklist-pintura .checklist-causa-item").forEach((item) => {
        const alvo = item.querySelector(".fotos-salvas");
        const fotos = fotosSalvasDoItemPintura(item);
        alvo.innerHTML = fotos.map((foto, i) => `
            <span class="badge text-bg-light border me-1 mb-1">
                <a href="${foto.url}" target="_blank" rel="noopener">Foto salva ${i + 1}</a>
                <button type="button" class="btn btn-link btn-sm p-0 ms-1 text-danger remover-foto-rascunho" data-foto-id="${foto.id}" title="Remover foto">&times;</button>
            </span>`).join("");
    });
}

function coletarDadosRascunhoPintura() {
    const itens = {};
    document.querySelectorAll("#unidades-checklist-pintura .checklist-causa-item").forEach((item) => {
        const ok = item.querySelector(".causa-status-ok").checked;
        const nok = item.querySelector(".causa-status-nok").checked;
        if (!ok && !nok) return;
        itens[item.dataset.chave] = {
            status: ok ? "ok" : "nok",
            causas: Array.from(item.querySelectorAll(".outros-causa-check:checked")).map((c) => c.value),
        };
    });
    return {
        data_inspecao: document.getElementById("data-inspecao-pintura").value,
        inspetor: document.getElementById("inspetor").value,
        itens,
    };
}

function aplicarRascunhoPintura(dados, fotos) {
    RASCUNHO_PINTURA.fotos = fotos || [];
    RASCUNHO_PINTURA.removidas = new Set();
    if (dados.data_inspecao) document.getElementById("data-inspecao-pintura").value = dados.data_inspecao;
    const inspetor = document.getElementById("inspetor");
    if (dados.inspetor && inspetor.querySelector(`option[value="${dados.inspetor}"]`)) inspetor.value = dados.inspetor;

    Object.entries(dados.itens || {}).forEach(([chave, resposta]) => {
        const item = document.querySelector(`#unidades-checklist-pintura .checklist-causa-item[data-chave="${chave}"]`);
        if (!item) return;
        const radio = item.querySelector(resposta.status === "ok" ? ".causa-status-ok" : ".causa-status-nok");
        radio.checked = true;
        item.querySelector(".checklist-causa-detalhes").style.display = resposta.status === "nok" ? "block" : "none";
        habilitarFalhasGrupoPintura(item, resposta.status === "nok");
        (resposta.causas || []).forEach((id) => {
            const check = item.querySelector(`.outros-causa-check[value="${id}"]`);
            if (check) check.checked = true;
        });
    });
    renderizarFotosSalvasPintura();
    atualizarContadoresConformidadePintura();
}

function carregarRascunhoPintura(idInspecao) {
    const info = document.getElementById("rascunho-pintura-info");
    info.textContent = "";
    fetch(urlRascunhoPintura(idInspecao))
        .then((r) => (r.ok ? r.json() : { existe: false }))
        .catch(() => ({ existe: false }))
        .then((resposta) => {
            // o modal pode ter sido aberto em outra inspeção enquanto buscava
            if (document.getElementById("id-inspecao-pintura").value !== String(idInspecao) || !resposta.existe) return;
            aplicarRascunhoPintura(resposta.dados || {}, resposta.fotos);
            info.textContent = `Rascunho salvo${resposta.usuario ? ` por ${resposta.usuario}` : ""} em ${resposta.atualizado_em}`;
        });
}

async function salvarParcialPintura() {
    const idInspecao = document.getElementById("id-inspecao-pintura").value;
    if (!idInspecao) return;
    const botao = document.getElementById("salvar-parcial-pintura");
    botao.disabled = true;
    botao.querySelector(".spinner-border").style.display = "flex";

    try {
        const formData = new FormData();
        formData.append("dados", JSON.stringify(coletarDadosRascunhoPintura()));
        RASCUNHO_PINTURA.removidas.forEach((id) => formData.append("remover_fotos", id));
        // fotos novas dos itens "Ñ OK" (comprimidas, como no envio)
        for (const item of document.querySelectorAll("#unidades-checklist-pintura .checklist-causa-item")) {
            if (!item.querySelector(".causa-status-nok").checked) continue;
            const arquivos = Array.from(item.querySelector(".causa-imagens").files);
            for (let i = 0; i < arquivos.length; i++) {
                formData.append(`foto__${item.dataset.chave}`, await comprimirImagemPintura(arquivos[i], i));
            }
        }

        const resposta = await fetch(urlRascunhoPintura(idInspecao), {
            method: "POST",
            headers: { "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value },
            body: formData,
        });
        const data = await resposta.json().catch(() => ({}));
        if (!resposta.ok) throw new Error(data.error || "Falha ao salvar a inspeção parcial.");

        // fotos agora estão no servidor: limpa os campos e mostra como "Foto salva"
        RASCUNHO_PINTURA.fotos = data.fotos || [];
        RASCUNHO_PINTURA.removidas = new Set();
        document.querySelectorAll("#unidades-checklist-pintura .causa-imagens").forEach((input) => {
            input.value = "";
            input.classList.remove("is-invalid");
        });
        renderizarFotosSalvasPintura();
        document.getElementById("rascunho-pintura-info").textContent = "Rascunho salvo agora";
        Swal.fire({ toast: true, position: "bottom-end", icon: "success", title: "Inspeção salva parcialmente", showConfirmButton: false, timer: 3000 });
        if (typeof buscarItensInspecao === "function") buscarItensInspecao(1);
    } catch (error) {
        Swal.fire({ icon: "error", title: "Erro ao salvar parcial", text: error.message });
    } finally {
        botao.disabled = false;
        botao.querySelector(".spinner-border").style.display = "none";
    }
}

// Grupo marcado como Ñ OK precisa de ao menos uma falha escolhida.
// Devolve a lista "Unidade N: Grupo" pra mensagem de erro e abre a primeira.
function validarOutrosChecklistPintura(container) {
    const pendencias = [];
    let primeiro = null;
    container.querySelectorAll('.checklist-causa-item[data-grupo="1"]').forEach((item) => {
        const erro = item.querySelector(".outros-causas-erro");
        const nok = item.querySelector(".causa-status-nok").checked;
        const escolhidas = item.querySelectorAll(".outros-causa-check:checked").length;
        const faltando = nok && escolhidas === 0;
        erro.style.display = faltando ? "block" : "none";
        if (faltando) {
            pendencias.push(`Unidade ${item.closest(".unidade-checklist-card").dataset.unidade}: ${item.dataset.causaNome}`);
            if (!primeiro) primeiro = item;
        }
    });
    if (primeiro) {
        const corpo = primeiro.closest(".collapse");
        if (corpo) bootstrap.Collapse.getOrCreateInstance(corpo, { toggle: false }).show();
        primeiro.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    return pendencias;
}

// Toda causa marcada como "Ñ OK" precisa de ao menos uma foto, em cada
// unidade. Marca os campos sem foto, abre a primeira unidade com pendencia e
// devolve a lista "Unidade N: Causa" pra mensagem de erro.
function validarImagensChecklistPintura(container) {
    const pendencias = [];
    let primeiroCampo = null;

    container.querySelectorAll(".unidade-checklist-card").forEach((card) => {
        card.querySelectorAll(".causa-status-nok:checked").forEach((radio) => {
            const item = radio.closest(".checklist-causa-item");
            const input = item.querySelector(".causa-imagens");
            // vale foto nova ou já salva no "Salvar parcial"
            if (input.files.length > 0 || fotosSalvasDoItemPintura(item).length > 0) {
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

// Quantidade produzida (apontada): na pintura é também a quantidade inspecionada
function maximoQtdInspecaoPintura() {
    const produzida = parseInt(document.getElementById("qtd-produzida-pintura").value, 10);
    return Math.max(Number.isFinite(produzida) ? produzida : 1, 1);
}

function atualizarContadoresConformidadePintura() {
    const totalCausas = totalItensChecklistPintura();
    const cards = document.querySelectorAll("#unidades-checklist-pintura .unidade-checklist-card");
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

    document.getElementById("conformidade-inspecao-pintura").value = conformes;
    document.getElementById("nao-conformidade-inspecao-pintura").value = naoConformes;
}

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains("iniciar-inspecao")) {
            document.getElementById("form-inspecao").reset();

            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const apontada = event.target.getAttribute("data-qtd");
            const tipo = event.target.getAttribute("data-tipo");
            const cor = event.target.getAttribute("data-cor");

            document.getElementById("id-inspecao-pintura").value = id;
            document.getElementById("data-finalizada-inspecao-pintura").value = data;
            document.getElementById("peca-inspecao-pintura").value = peca;
            document.getElementById("cor-inspecao-pintura").value = `${cor} - ${tipo}`;
            document.getElementById("qtd-produzida-pintura").value = apontada;

            // Pintura: inspeção 100% obrigatória - a quantidade inspecionada é
            // sempre a produzida (campo somente leitura)
            const qtdProduzida = maximoQtdInspecaoPintura();
            document.getElementById("qtd-inspecao-pintura").value = qtdProduzida;

            RASCUNHO_PINTURA.fotos = [];
            RASCUNHO_PINTURA.removidas = new Set();
            renderizarUnidadesChecklistPintura(qtdProduzida);
            carregarRascunhoPintura(id);

            const modal = new bootstrap.Modal(document.getElementById("modal-inspecionar-pintura"));
            modal.show();
        }

        // remover uma foto já salva no rascunho (sai de vez no próximo salvar/enviar)
        const botaoRemover = event.target.closest(".remover-foto-rascunho");
        if (botaoRemover) {
            RASCUNHO_PINTURA.removidas.add(String(botaoRemover.dataset.fotoId));
            renderizarFotosSalvasPintura();
        }
    });

    document.getElementById("salvar-parcial-pintura").addEventListener("click", salvarParcialPintura);

    document.getElementById("unidades-checklist-pintura").addEventListener("change", function(event) {
        if (event.target.classList.contains("causa-status-ok") || event.target.classList.contains("causa-status-nok")) {
            alternarDetalhesCausaPintura(event.target);
            atualizarContadoresConformidadePintura();
        }
        // Ao escolher a foto, tira o destaque de erro do campo
        if (event.target.classList.contains("causa-imagens") && event.target.files.length > 0) {
            event.target.classList.remove("is-invalid");
        }
        // Ao escolher uma falha do grupo, tira o aviso
        if (event.target.classList.contains("outros-causa-check") && event.target.checked) {
            const erro = event.target.closest(".checklist-causa-item").querySelector(".outros-causas-erro");
            if (erro) erro.style.display = "none";
        }
    });
});
