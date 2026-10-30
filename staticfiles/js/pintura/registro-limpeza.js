// Registro de limpeza da pintura: modal de novo registro + tabela de histórico

const modalRegistroLimpeza = document.getElementById("modal-registro-limpeza");
const formRegistroLimpeza = document.getElementById("form-registro-limpeza");

function csrfTokenLimpeza() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

function escaparHtmlLimpeza(texto) {
    const div = document.createElement("div");
    div.textContent = texto ?? "";
    return div.innerHTML;
}

// "AAAA-MM-DDTHH:MM" no horário local, para o datetime-local
function agoraLocalLimpeza() {
    const agora = new Date();
    agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset());
    return agora.toISOString().slice(0, 16);
}

// Fundo do badge na cor da peça (tons claros para o texto preto ficar legível)
const FUNDO_COR_LIMPEZA = {
    amarelo: "#ffd84d",
    azul: "#7fb2ff",
    cinza: "#c8c8c8",
    laranja: "#ffaa55",
    verde: "#7ed69a",
    vermelho: "#ff8080",
};

// Cor e data de carga em que a peça está programada, ao lado do nome
function detalhesPecaLimpeza(opcao) {
    const cor = opcao.cor ? escaparHtmlLimpeza(opcao.cor) : "Sem cor";
    const fundo = FUNDO_COR_LIMPEZA[(opcao.cor || "").trim().toLowerCase()] || "#f8f9fa";
    const carga = opcao.data_carga_br ? `Carga ${escaparHtmlLimpeza(opcao.data_carga_br)}` : "Sem data de carga";
    const ordem = opcao.ordem ? `<span class="badge bg-light text-dark border">Ordem ${escaparHtmlLimpeza(String(opcao.ordem))}</span>` : "";
    return `${ordem}
            <span class="badge text-dark border" style="background-color: ${fundo};">${cor}</span>
            <span class="badge bg-light text-dark border"><i class="bi bi-calendar-event"></i> ${carga}</span>`;
}

// Material: peças da pintura (já pintadas ou não), uma opção por peça + cor
// + data de carga, buscadas no servidor
$("#limpeza-peca").select2({
    theme: "bootstrap-5",
    width: "100%",
    dropdownParent: $(modalRegistroLimpeza),
    placeholder: "Selecione a peça",
    templateResult: (opcao) => {
        if (!opcao.peca) return opcao.text; // "Buscando..." etc.
        return $(`<div>
            <div class="fw-semibold">${escaparHtmlLimpeza(opcao.peca)}</div>
            <div class="d-flex gap-1 mt-1 small">${detalhesPecaLimpeza(opcao)}</div>
        </div>`);
    },
    templateSelection: (opcao) => {
        if (!opcao.peca) return opcao.text;
        return $(`<span>${escaparHtmlLimpeza(opcao.peca)} ${detalhesPecaLimpeza(opcao)}</span>`);
    },
    language: {
        inputTooShort: () => "Digite para buscar",
        noResults: () => "Nenhuma peça encontrada",
        searching: () => "Buscando...",
    },
    ajax: {
        url: "/inspecao/api/registro-limpeza-pintura/pecas/",
        dataType: "json",
        delay: 300,
        data: (params) => ({ q: params.term || "" }),
        processResults: (data) => data,
    },
});

// ------------------------------------------------- etapas da não conformidade
// Etapa 0 = inspeção (campo "Limpeza"); 1, 2... = reinspeções. Não conforme
// pede a foto dos trapos e "Direcionar para nova limpeza"; "Sim" abre a
// próxima reinspeção, e assim por diante até a reinspeção ficar conforme
// (foto dos trapos conformes) ou a resposta ser "Não". Os nomes dos campos
// (etapa_<n>_...) são os que o servidor lê em _etapas_registro_limpeza.
const containerEtapasLimpeza = document.getElementById("limpeza-etapas");

function campoFotoLimpeza(numero, conforme) {
    const id = `limpeza-etapa-${numero}-imagem`;
    return `
        <label class="form-label" for="${id}">Registro dos trapos ${conforme ? "conforme" : "não conforme"} <span class="text-danger">*</span></label>
        <input class="form-control" type="file" name="etapa_${numero}_imagem" id="${id}" accept="image/*" required>`;
}

function blocoNaoConformeLimpeza(numero) {
    const titulo = numero === 0 ? "Não conforme" : `Não conforme - ${numero}ª reinspeção`;
    return `
        <div class="border border-danger-subtle rounded p-3 mt-3" data-etapa="${numero}" data-tipo="nao-conforme">
            <h6 class="text-danger mb-3">${titulo}</h6>
            <div class="mb-3">${campoFotoLimpeza(numero, false)}</div>
            <label class="form-label d-block">Direcionar para nova limpeza <span class="text-danger">*</span></label>
            <div class="btn-group w-100" role="group" aria-label="Direcionar para nova limpeza">
                <input type="radio" class="btn-check" name="etapa_${numero}_nova_limpeza" id="limpeza-etapa-${numero}-nova-sim" value="sim" autocomplete="off" required data-numero="${numero}">
                <label class="btn btn-outline-dark" for="limpeza-etapa-${numero}-nova-sim">Sim</label>
                <input type="radio" class="btn-check" name="etapa_${numero}_nova_limpeza" id="limpeza-etapa-${numero}-nova-nao" value="nao" autocomplete="off" data-numero="${numero}">
                <label class="btn btn-outline-dark" for="limpeza-etapa-${numero}-nova-nao">Não</label>
            </div>
        </div>`;
}

function blocoReinspecaoLimpeza(numero) {
    return `
        <div class="border border-warning-subtle rounded p-3 mt-3" data-etapa="${numero}" data-tipo="reinspecao">
            <h6 class="mb-3">Reinspeção da limpeza${numero > 1 ? ` (${numero}ª)` : ""}</h6>
            <label class="form-label d-block">Limpeza - Reinspeção <span class="text-danger">*</span></label>
            <div class="btn-group w-100" role="group" aria-label="Limpeza - Reinspeção">
                <input type="radio" class="btn-check" name="etapa_${numero}_resultado" id="limpeza-etapa-${numero}-conforme" value="conforme" autocomplete="off" required data-numero="${numero}">
                <label class="btn btn-outline-success" for="limpeza-etapa-${numero}-conforme"><i class="bi bi-check-lg"></i> Conforme</label>
                <input type="radio" class="btn-check" name="etapa_${numero}_resultado" id="limpeza-etapa-${numero}-nao-conforme" value="nao_conforme" autocomplete="off" data-numero="${numero}">
                <label class="btn btn-outline-danger" for="limpeza-etapa-${numero}-nao-conforme"><i class="bi bi-x-lg"></i> Não conforme</label>
            </div>
            <div class="foto-conforme-limpeza"></div>
        </div>`;
}

// Remove o que vem depois da resposta alterada (as etapas seguintes)
function removerEtapasLimpezaDepoisDe(numero, incluirNaoConformeDaEtapa = false) {
    containerEtapasLimpeza.querySelectorAll("[data-etapa]").forEach((bloco) => {
        const etapa = parseInt(bloco.dataset.etapa, 10);
        if (etapa > numero || (incluirNaoConformeDaEtapa && etapa === numero && bloco.dataset.tipo === "nao-conforme")) {
            bloco.remove();
        }
    });
}

function resultadoEtapaLimpezaAlterado(numero, conforme) {
    removerEtapasLimpezaDepoisDe(numero, true);
    if (numero === 0) {
        if (!conforme) containerEtapasLimpeza.insertAdjacentHTML("beforeend", blocoNaoConformeLimpeza(0));
        return;
    }
    const reinspecao = containerEtapasLimpeza.querySelector(`[data-etapa="${numero}"][data-tipo="reinspecao"]`);
    const slotFoto = reinspecao.querySelector(".foto-conforme-limpeza");
    slotFoto.innerHTML = "";
    if (conforme) {
        slotFoto.innerHTML = `<div class="mt-3"><h6 class="text-success mb-2">Conforme</h6>${campoFotoLimpeza(numero, true)}</div>`;
    } else {
        containerEtapasLimpeza.insertAdjacentHTML("beforeend", blocoNaoConformeLimpeza(numero));
    }
}

formRegistroLimpeza.addEventListener("change", (event) => {
    const campo = event.target;
    if (campo.name === "limpeza") {
        resultadoEtapaLimpezaAlterado(0, campo.value === "conforme");
    } else if (/^etapa_\d+_resultado$/.test(campo.name)) {
        resultadoEtapaLimpezaAlterado(parseInt(campo.dataset.numero, 10), campo.value === "conforme");
    } else if (/^etapa_\d+_nova_limpeza$/.test(campo.name)) {
        const numero = parseInt(campo.dataset.numero, 10);
        removerEtapasLimpezaDepoisDe(numero);
        if (campo.value === "sim") {
            containerEtapasLimpeza.insertAdjacentHTML("beforeend", blocoReinspecaoLimpeza(numero + 1));
            containerEtapasLimpeza.lastElementChild.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }
});

// Campo obrigatório vazio: os botões (btn-check) escondem o aviso nativo do
// navegador, então avisa e leva até o primeiro campo pendente
let avisoCampoLimpezaPendente = false;
formRegistroLimpeza.addEventListener("invalid", (event) => {
    if (avisoCampoLimpezaPendente) return;
    avisoCampoLimpezaPendente = true;
    setTimeout(() => { avisoCampoLimpezaPendente = false; }, 0);
    const grupo = event.target.closest(".mb-3, .mb-1, [data-etapa]") || event.target;
    const rotulo = grupo.querySelector(".form-label")?.textContent.replace("*", "").trim();
    grupo.scrollIntoView({ behavior: "smooth", block: "center" });
    Swal.fire({ icon: "error", title: "Campo obrigatório", text: rotulo ? `Preencha: ${rotulo}` : "Preencha todos os campos obrigatórios." });
}, true);

// Foto reduzida (máx. 1280px, JPEG) antes do envio; se falhar, vai a original
function comprimirImagemLimpeza(arquivo) {
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
                (blob) => resolve(blob ? new File([blob], `trapos_${Date.now()}.jpg`, { type: "image/jpeg" }) : arquivo),
                "image/jpeg",
                0.7
            );
        };
        img.onerror = () => { URL.revokeObjectURL(url); resolve(arquivo); };
        img.src = url;
    });
}

// Registro salvo parcialmente a reabrir no modal ("Continuar" no histórico)
let registroLimpezaParaContinuar = null;

modalRegistroLimpeza.addEventListener("show.bs.modal", () => {
    const inspetor = document.getElementById("limpeza-inspetor");
    const inspetorAnterior = inspetor.value;
    formRegistroLimpeza.reset();
    inspetor.value = inspetorAnterior || inspetor.value; // mantém o inspetor entre registros
    $("#limpeza-peca").val(null).trigger("change");
    document.getElementById("limpeza-data").value = agoraLocalLimpeza();
    document.getElementById("limpeza-quantidade").value = 1;
    document.getElementById("limpeza-registro-id").value = "";
    document.getElementById("limpeza-info-parcial").textContent = "";
    document.getElementById("modal-registro-limpeza-label").textContent = "Registrar limpeza";
    containerEtapasLimpeza.innerHTML = "";

    if (registroLimpezaParaContinuar) {
        preencherRegistroLimpeza(registroLimpezaParaContinuar);
        registroLimpezaParaContinuar = null;
    }
});

function marcarRadioLimpeza(nome, valor) {
    const radio = formRegistroLimpeza.querySelector(`input[name="${nome}"][value="${valor}"]`);
    if (!radio) return;
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
}

// Foto já salva na etapa: mostra o link e deixa o campo opcional (só para trocar)
function marcarFotoSalvaLimpeza(numero, url) {
    const input = formRegistroLimpeza.querySelector(`input[name="etapa_${numero}_imagem"]`);
    if (!input || !url) return;
    input.required = false;
    input.insertAdjacentHTML("afterend", `
        <div class="form-text text-success">
            <i class="bi bi-check-circle"></i> Foto já salva -
            <a href="${escaparHtmlLimpeza(url)}" target="_blank" rel="noopener noreferrer">ver</a>
            (anexe outra só se quiser trocar)
        </div>`);
}

// Reabre o fluxo como estava: cabeçalho, depois cada etapa na ordem, disparando
// os mesmos "change" do preenchimento à mão para montar os blocos
function preencherRegistroLimpeza(registro) {
    document.getElementById("modal-registro-limpeza-label").textContent = `Continuar limpeza #${registro.id}`;
    document.getElementById("limpeza-registro-id").value = registro.id;
    document.getElementById("limpeza-info-parcial").textContent =
        `Salvo parcialmente por ${registro.inspetor}`;

    const inspetor = document.getElementById("limpeza-inspetor");
    if (!inspetor.value && registro.inspetor_id) inspetor.value = registro.inspetor_id;
    document.getElementById("limpeza-data").value = registro.data_iso;
    marcarRadioLimpeza("processo", registro.processo_valor);
    if (registro.material) {
        $("#limpeza-peca").select2("trigger", "select", { data: registro.material });
    }

    registro.etapas.forEach((etapa) => {
        const numero = etapa.numero;
        if (etapa.conforme === null) return;
        const valor = etapa.conforme ? "conforme" : "nao_conforme";
        marcarRadioLimpeza(numero === 0 ? "limpeza" : `etapa_${numero}_resultado`, valor);
        marcarFotoSalvaLimpeza(numero, etapa.imagem);
        if (etapa.nova_limpeza !== null) {
            marcarRadioLimpeza(`etapa_${numero}_nova_limpeza`, etapa.nova_limpeza ? "sim" : "nao");
        }
    });
}

async function continuarRegistroLimpeza(id) {
    try {
        const response = await fetch(`/inspecao/api/registro-limpeza-pintura/${id}/`);
        if (!response.ok) throw new Error("Não foi possível carregar o registro.");
        registroLimpezaParaContinuar = await response.json();
        bootstrap.Modal.getOrCreateInstance(modalRegistroLimpeza).show();
    } catch (error) {
        Swal.fire({ icon: "error", title: "Erro", text: error.message });
    }
}

// parcial = true: grava o que já foi respondido (fica "Em andamento");
// false: "Finalizar", com o fluxo completo (o navegador confere os required)
async function enviarRegistroLimpeza(parcial) {
    if (parcial) {
        // no parcial só o cabeçalho é obrigatório
        const pendente = [
            [!document.getElementById("limpeza-inspetor").value, "Inspetor"],
            [!document.getElementById("limpeza-data").value, "Data"],
            [!formRegistroLimpeza.querySelector('input[name="processo"]:checked'), "Processo pintura"],
            [!document.getElementById("limpeza-peca").value, "Material"],
        ].find(([falta]) => falta);
        if (pendente) {
            Swal.fire({ icon: "error", title: "Campo obrigatório", text: `Preencha: ${pendente[1]}` });
            return;
        }
    } else if (!document.getElementById("limpeza-peca").value) {
        Swal.fire({ icon: "error", title: "Selecione o material (peça)." });
        return;
    }

    const formData = new FormData(formRegistroLimpeza);
    if (parcial) formData.set("parcial", "1");

    const botao = document.getElementById(parcial ? "btn-salvar-parcial-limpeza" : "btn-salvar-limpeza");
    const spinner = botao.querySelector(".spinner-border");
    botao.disabled = true;
    spinner.classList.remove("d-none");

    try {
        const camposFoto = [...formData.keys()].filter((campo) => /^etapa_\d+_imagem$/.test(campo));
        for (const campo of camposFoto) {
            const arquivo = formData.get(campo);
            if (arquivo instanceof File && arquivo.size) {
                formData.set(campo, await comprimirImagemLimpeza(arquivo));
            } else {
                formData.delete(campo); // vazio: mantém a foto já salva, se houver
            }
        }
        const response = await fetch("/inspecao/api/registro-limpeza-pintura/salvar/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfTokenLimpeza() },
            body: formData,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Erro ao salvar o registro.");

        bootstrap.Modal.getInstance(modalRegistroLimpeza).hide();
        Swal.fire({
            toast: true,
            position: "bottom-end",
            icon: "success",
            title: parcial ? "Registro salvo parcialmente" : "Registro de limpeza finalizado",
            showConfirmButton: false,
            timer: 3000,
        });
        buscarRegistrosLimpeza(1);
    } catch (error) {
        Swal.fire({ icon: "error", title: "Erro ao salvar", text: error.message });
    } finally {
        botao.disabled = false;
        spinner.classList.add("d-none");
    }
}

formRegistroLimpeza.addEventListener("submit", (event) => {
    event.preventDefault();
    enviarRegistroLimpeza(false);
});

document.getElementById("btn-salvar-parcial-limpeza").addEventListener("click", () => enviarRegistroLimpeza(true));

// ---------------------------------------------------------------- histórico

function badgeResultadoLimpeza(conforme) {
    return conforme
        ? '<span class="badge bg-success">Conforme</span>'
        : '<span class="badge bg-danger">Não conforme</span>';
}

// Coluna "Limpeza": resultado da inspeção e, se houve não conformidade, cada
// etapa (foto, nova limpeza, reinspeções) e o resultado final
function etapasRegistroLimpezaHtml(registro) {
    const etapas = registro.etapas || [];
    const andamento = registro.finalizado
        ? ""
        : '<div class="mb-1"><span class="badge bg-warning text-dark"><i class="bi bi-hourglass-split"></i> Em andamento</span></div>';
    // conforme já na primeira inspeção: só o selo
    if (registro.finalizado && registro.conforme) return badgeResultadoLimpeza(true);
    if (etapas.length === 0) return andamento || badgeResultadoLimpeza(registro.conforme);

    const linhas = etapas.map((etapa) => {
        const rotulo = etapa.numero === 0 ? "Inspeção" : `${etapa.numero}ª reinspeção`;
        const foto = etapa.imagem
            ? `<a href="${escaparHtmlLimpeza(etapa.imagem)}" target="_blank" rel="noopener noreferrer" class="ms-1" title="Foto dos trapos"><i class="bi bi-image"></i></a>`
            : "";
        const nova = etapa.nova_limpeza === null ? "" : ` · nova limpeza: ${etapa.nova_limpeza ? "Sim" : "Não"}`;
        const quem = `<div class="text-muted" style="font-size: 0.7rem;">${escaparHtmlLimpeza(etapa.inspetor)} · ${escaparHtmlLimpeza(etapa.data)}</div>`;
        return `<div class="small text-nowrap mb-1">${rotulo}: ${badgeResultadoLimpeza(etapa.conforme)}${foto}<span class="text-muted">${nova}</span>${quem}</div>`;
    }).join("");

    const final = registro.finalizado
        ? `<div class="small mt-1 pt-1 border-top"><strong>Final:</strong> ${badgeResultadoLimpeza(registro.conforme_final)}
               <span class="text-muted">(${registro.total_reinspecoes} reinspeç${registro.total_reinspecoes === 1 ? "ão" : "ões"})</span></div>`
        : "";
    return `<div class="text-start">${andamento}${linhas}${final}</div>`;
}

function acoesRegistroLimpezaHtml(registro) {
    if (registro.finalizado) return "";
    return `<button type="button" class="btn btn-sm btn-dark text-nowrap" data-continuar-limpeza="${registro.id}">
                <i class="bi bi-play-fill"></i> Continuar
            </button>`;
}

document.getElementById("registros-limpeza-body").addEventListener("click", (event) => {
    const botao = event.target.closest("[data-continuar-limpeza]");
    if (botao) continuarRegistroLimpeza(botao.dataset.continuarLimpeza);
});

function buscarRegistrosLimpeza(pagina) {
    const corpo = document.getElementById("registros-limpeza-body");
    const paginacao = document.getElementById("paginacao-registros-limpeza");
    const qtd = document.getElementById("qtd-registros-limpeza");

    corpo.innerHTML = `<tr><td colspan="10" class="text-center py-4"><span class="spinner-border spinner-border-sm"></span></td></tr>`;
    paginacao.innerHTML = "";

    const params = new URLSearchParams({ pagina });
    const filtros = {
        pesquisar: document.getElementById("filtro-limpeza-pesquisar").value.trim(),
        processo: document.getElementById("filtro-limpeza-processo").value,
        resultado: document.getElementById("filtro-limpeza-resultado").value,
        final: document.getElementById("filtro-limpeza-final").value,
        situacao: document.getElementById("filtro-limpeza-situacao").value,
        data_inicio: document.getElementById("filtro-limpeza-data-inicio").value,
        data_fim: document.getElementById("filtro-limpeza-data-fim").value,
    };
    Object.entries(filtros).forEach(([chave, valor]) => { if (valor) params.append(chave, valor); });

    fetch(`/inspecao/api/registro-limpeza-pintura/?${params.toString()}`)
        .then((response) => {
            if (!response.ok) throw new Error(`Erro HTTP! Status: ${response.status}`);
            return response.json();
        })
        .then((resposta) => {
            qtd.textContent = `${resposta.total_filtrado} registros`;

            if (resposta.dados.length === 0) {
                corpo.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-4">Nenhum registro encontrado.</td></tr>`;
                return;
            }

            corpo.innerHTML = resposta.dados.map((registro) => `
                <tr>
                    <td class="text-nowrap">${escaparHtmlLimpeza(registro.data)}</td>
                    <td>${escaparHtmlLimpeza(registro.inspetor)}</td>
                    <td>${escaparHtmlLimpeza(registro.processo)}</td>
                    <td>${escaparHtmlLimpeza(registro.peca)}</td>
                    <td>${escaparHtmlLimpeza(String(registro.ordem))}</td>
                    <td>${escaparHtmlLimpeza(registro.cor)}</td>
                    <td class="text-nowrap">${escaparHtmlLimpeza(registro.data_carga)}</td>
                    <td class="text-center">${registro.quantidade}</td>
                    <td class="text-center">${etapasRegistroLimpezaHtml(registro)}</td>
                    <td class="text-center">${acoesRegistroLimpezaHtml(registro)}</td>
                </tr>`).join("");

            if (resposta.total_paginas > 1) {
                paginacao.innerHTML = montarPaginacaoLimpeza(resposta.pagina_atual, resposta.total_paginas);
            }
        })
        .catch((error) => {
            console.error(error);
            corpo.innerHTML = `<tr><td colspan="10" class="text-center text-danger py-4">Erro ao carregar os registros.</td></tr>`;
        });
}

// Primeira, vizinhas da atual e última, com reticências (como nas outras telas)
function montarPaginacaoLimpeza(paginaAtual, totalPaginas) {
    const link = (i) => `
        <li class="page-item ${i === paginaAtual ? "active" : ""}">
            <a class="page-link" href="#" data-pagina="${i}">${i}</a>
        </li>`;
    const reticencias = `<li class="page-item disabled"><span class="page-link">...</span></li>`;

    let html = link(1);
    if (paginaAtual > 3) html += reticencias;
    for (let i = Math.max(2, paginaAtual - 1); i <= Math.min(totalPaginas - 1, paginaAtual + 1); i++) {
        html += link(i);
    }
    if (paginaAtual < totalPaginas - 2) html += reticencias;
    html += link(totalPaginas);

    return `<nav aria-label="Paginação"><ul class="pagination justify-content-center">${html}</ul></nav>`;
}

document.getElementById("paginacao-registros-limpeza").addEventListener("click", (event) => {
    const link = event.target.closest("[data-pagina]");
    if (!link) return;
    event.preventDefault();
    buscarRegistrosLimpeza(parseInt(link.dataset.pagina, 10));
});

document.getElementById("form-filtrar-limpeza").addEventListener("submit", (event) => {
    event.preventDefault();
    buscarRegistrosLimpeza(1);
});

document.getElementById("btn-limpar-filtro-limpeza").addEventListener("click", () => {
    document.getElementById("form-filtrar-limpeza").reset();
    buscarRegistrosLimpeza(1);
});

document.addEventListener("DOMContentLoaded", () => buscarRegistrosLimpeza(1));
