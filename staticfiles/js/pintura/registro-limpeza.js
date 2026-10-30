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

modalRegistroLimpeza.addEventListener("show.bs.modal", () => {
    const inspetor = document.getElementById("limpeza-inspetor");
    const inspetorAnterior = inspetor.value;
    formRegistroLimpeza.reset();
    inspetor.value = inspetorAnterior || inspetor.value; // mantém o inspetor entre registros
    $("#limpeza-peca").val(null).trigger("change");
    document.getElementById("limpeza-data").value = agoraLocalLimpeza();
    document.getElementById("limpeza-quantidade").value = 1;
});

formRegistroLimpeza.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!document.getElementById("limpeza-peca").value) {
        Swal.fire({ icon: "error", title: "Selecione o material (peça)." });
        return;
    }

    const botao = document.getElementById("btn-salvar-limpeza");
    const spinner = botao.querySelector(".spinner-border");
    botao.disabled = true;
    spinner.classList.remove("d-none");

    try {
        const response = await fetch("/inspecao/api/registro-limpeza-pintura/salvar/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfTokenLimpeza() },
            body: new FormData(formRegistroLimpeza),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Erro ao salvar o registro.");

        bootstrap.Modal.getInstance(modalRegistroLimpeza).hide();
        Swal.fire({
            toast: true,
            position: "bottom-end",
            icon: "success",
            title: "Registro de limpeza salvo",
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
});

// ---------------------------------------------------------------- histórico

function buscarRegistrosLimpeza(pagina) {
    const corpo = document.getElementById("registros-limpeza-body");
    const paginacao = document.getElementById("paginacao-registros-limpeza");
    const qtd = document.getElementById("qtd-registros-limpeza");

    corpo.innerHTML = `<tr><td colspan="9" class="text-center py-4"><span class="spinner-border spinner-border-sm"></span></td></tr>`;
    paginacao.innerHTML = "";

    const params = new URLSearchParams({ pagina });
    const filtros = {
        pesquisar: document.getElementById("filtro-limpeza-pesquisar").value.trim(),
        processo: document.getElementById("filtro-limpeza-processo").value,
        resultado: document.getElementById("filtro-limpeza-resultado").value,
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
                corpo.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">Nenhum registro encontrado.</td></tr>`;
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
                    <td class="text-center">${registro.conforme
                        ? '<span class="badge bg-success">Conforme</span>'
                        : '<span class="badge bg-danger">Não conforme</span>'}</td>
                </tr>`).join("");

            if (resposta.total_paginas > 1) {
                paginacao.innerHTML = montarPaginacaoLimpeza(resposta.pagina_atual, resposta.total_paginas);
            }
        })
        .catch((error) => {
            console.error(error);
            corpo.innerHTML = `<tr><td colspan="9" class="text-center text-danger py-4">Erro ao carregar os registros.</td></tr>`;
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
