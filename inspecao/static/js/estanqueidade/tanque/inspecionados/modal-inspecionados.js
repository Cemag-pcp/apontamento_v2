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
                    // Renderiza em tabela (substitui carrossel)
                    const execucoesOrdenadas = [...data.history].sort(
                        (a, b) => b.num_execucao - a.num_execucao
                    );

                    const linhas = execucoesOrdenadas.map((element) => {
                        const statusNc =
                            element.nao_conformidade === true ? "text-danger" : "text-success";
                        const textoNc = element.nao_conformidade === true ? "Não" : "Sim";
                        return `
                        <tr>
                            <td class="text-center">${element.num_execucao}</td>
                            <td>${element.data_execucao}</td>
                            <td>${element.inspetor || "N/A"}</td>
                            <td>${element.pressao_inicial || "N/A"}</td>
                            <td>${element.pressao_final || "N/A"}</td>
                            <td>${element.tipo_teste || "N/A"}</td>
                            <td>${element.tempo_execucao || "N/A"}</td>
                            <td class="${statusNc} fw-semibold">${textoNc}</td>
                        </tr>
                    `;
                    });

                    listaTimeline.innerHTML = `
                    <div class="table-responsive">
                        <table class="table table-sm align-middle">
                            <thead>
                                <tr>
                                    <th class="text-center">Execução</th>
                                    <th>Data</th>
                                    <th>Inspetor</th>
                                    <th>Pressão Inicial</th>
                                    <th>Pressão Final</th>
                                    <th>Tipo de Teste</th>
                                    <th>Tempo Execução</th>
                                    <th>Conforme?</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${linhas.join("")}
                            </tbody>
                        </table>
                    </div>
                `;

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
