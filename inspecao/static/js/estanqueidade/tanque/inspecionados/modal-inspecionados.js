document.addEventListener("DOMContentLoaded", () => {
    const dataInspecao = document.getElementById("data-inspecao-solda-tanque");
    const hoje = new Date().toISOString().split("T")[0];
    dataInspecao.value = hoje;

    document.addEventListener("click", function (event) {
        if (event.target.classList.contains("historico-inspecao")) {
            const buttonSeeDetails = document.querySelectorAll(".historico-inspecao");
            const button = event.target;
            buttonSeeDetails.forEach((detailsButton) => {
                detailsButton.disabled = true;
            });
            button.querySelector(".spinner-border").style.display = "flex";

            const listaTimeline = document.querySelector(".timeline");
            const id = event.target.getAttribute("data-id");

            listaTimeline.innerHTML = "";

            fetch(`/inspecao/api/${id}/historico-tanque/`, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                },
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error(`Erro na requisição HTTP. Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then((data) => {
                    listaTimeline.innerHTML = renderizarTimelineTanque(data.eventos || []);

                    const modal = new bootstrap.Modal(
                        document.getElementById("modal-historico-tanque")
                    );
                    modal.show();
                })
                .catch((error) => {
                    console.error(error);
                })
                .finally(() => {
                    buttonSeeDetails.forEach((detailsButton) => {
                        detailsButton.disabled = false;
                    });
                    button.querySelector(".spinner-border").style.display = "none";
                });
        }
    });
});

function escaparHtmlHistoricoTanque(texto) {
    const div = document.createElement("div");
    div.textContent = texto ?? "";
    return div.innerHTML;
}

function renderizarTimelineTanque(eventos) {
    if (!eventos.length) {
        return `<li class="timeline-item text-center text-muted">Nenhum registro encontrado para este tanque.</li>`;
    }

    return eventos.map((evento) => {
        if (evento.categoria === "solda") {
            return renderizarEventoSoldaTanque(evento);
        }
        return renderizarEventoEstanqueidadeTanque(evento);
    }).join("");
}

function renderizarEventoEstanqueidadeTanque(evento) {
    const iconeClasse = evento.possui_nao_conformidade ? "danger" : "success";
    const icone = evento.possui_nao_conformidade ? "bi-exclamation-triangle-fill" : "bi-check-lg";

    const linhasTestes = evento.testes.map((teste) => {
        const statusTeste = teste.nao_conformidade
            ? '<span class="text-danger fw-semibold"><i class="bi bi-x-circle-fill"></i> Não conforme</span>'
            : '<span class="text-success fw-semibold"><i class="bi bi-check-circle-fill"></i> Conforme</span>';
        return `
            <tr>
                <td>${escaparHtmlHistoricoTanque(teste.tipo_teste)}</td>
                <td>${teste.pressao_inicial ?? "N/A"}</td>
                <td>${teste.pressao_final ?? "N/A"}</td>
                <td>${teste.tempo_execucao || "N/A"}</td>
                <td>${statusTeste}</td>
            </tr>
        `;
    }).join("");

    return `
        <li class="timeline-item">
            <div class="timeline-icon ${iconeClasse}"><i class="bi ${icone}"></i></div>
            <div class="timeline-content">
                <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <span class="title">
                        <span class="badge bg-primary-subtle text-primary-emphasis me-1">Estanqueidade</span>
                        ${escaparHtmlHistoricoTanque(evento.titulo)}
                    </span>
                    <span class="date">${evento.data}</span>
                </div>
                <p class="mb-2 mt-1 text-muted">Inspetor: ${escaparHtmlHistoricoTanque(evento.inspetor || "N/A")}</p>
                <div class="table-responsive">
                    <table class="table table-sm align-middle mb-0">
                        <thead>
                            <tr>
                                <th>Teste</th>
                                <th>Pressão inicial</th>
                                <th>Pressão final</th>
                                <th>Tempo</th>
                                <th>Resultado</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${linhasTestes}
                        </tbody>
                    </table>
                </div>
            </div>
        </li>
    `;
}

function renderizarEventoSoldaTanque(evento) {
    const iconeClasse = evento.possui_nao_conformidade ? "danger" : "success";
    const icone = evento.possui_nao_conformidade ? "bi-exclamation-triangle-fill" : "bi-check-lg";

    const causasHtml = evento.causas.length ? evento.causas.map((causa) => {
        const imagensHtml = causa.imagens.length ? `
            <div class="d-flex flex-wrap gap-2 mt-2">
                ${causa.imagens.map((img) => `
                    <img src="${img.url}" class="img-thumbnail modal-image-trigger"
                        style="width: 70px; height: 70px; object-fit: cover; cursor: pointer;"
                        alt="Imagem da causa" data-image-url="${img.url}">
                `).join("")}
            </div>
        ` : "";

        return `
            <div class="border rounded p-2 mb-2">
                <strong>${escaparHtmlHistoricoTanque(causa.nome)}</strong>
                <span class="text-muted"> — quantidade: ${causa.quantidade}</span>
                ${imagensHtml}
            </div>
        `;
    }).join("") : "";

    return `
        <li class="timeline-item">
            <div class="timeline-icon ${iconeClasse}"><i class="bi ${icone}"></i></div>
            <div class="timeline-content">
                <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <span class="title">
                        <span class="badge bg-dark-subtle text-dark-emphasis me-1">Solda</span>
                        ${escaparHtmlHistoricoTanque(evento.titulo)}
                    </span>
                    <span class="date">${evento.data || "N/A"}</span>
                </div>
                <p class="mb-2 mt-1 text-muted">Inspetor: ${escaparHtmlHistoricoTanque(evento.inspetor || "N/A")}</p>
                <p class="mb-2">
                    <span class="text-success fw-semibold me-3"><i class="bi bi-check-circle-fill"></i> Conforme: ${evento.conformidade}</span>
                    <span class="text-danger fw-semibold"><i class="bi bi-x-circle-fill"></i> Não conforme: ${evento.nao_conformidade}</span>
                </p>
                ${evento.observacao ? `<p class="mb-2"><strong>Observação:</strong> ${escaparHtmlHistoricoTanque(evento.observacao)}</p>` : ""}
                ${causasHtml}
            </div>
        </li>
    `;
}
