const toastExcluirInspecaoTanque = Swal.mixin({
    toast: true,
    position: "bottom-end",
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.onmouseenter = Swal.stopTimer;
        toast.onmouseleave = Swal.resumeTimer;
    }
});

function obterInspecoesTanqueSelecionadas() {
    return Array.from(
        document.querySelectorAll(".checkbox-excluir-inspecao-tanque:checked")
    ).map((checkbox) => ({
        id: Number(checkbox.value),
        peca: checkbox.dataset.peca || "",
        data: checkbox.dataset.data || "",
    }));
}

function atualizarEstadoExclusaoInspecaoTanque() {
    const selecionadas = obterInspecoesTanqueSelecionadas();
    const botao = document.getElementById("btn-abrir-exclusao-tanque");

    if (!botao) {
        return;
    }

    botao.disabled = selecionadas.length === 0;
    botao.innerHTML = `<i class="bi bi-trash"></i> Excluir selecionadas (${selecionadas.length})`;
}

function injetarCheckboxesInspecaoTanque() {
    const cards = document.querySelectorAll("#cards-inspecionados .card");

    cards.forEach((card) => {
        if (card.querySelector(".checkbox-excluir-inspecao-tanque")) {
            return;
        }

        const botaoHistorico = card.querySelector(".historico-inspecao");
        const topoCard = card.querySelector(".d-flex.justify-content-between");

        if (!botaoHistorico || !topoCard) {
            return;
        }

        const checkboxWrapper = document.createElement("div");
        checkboxWrapper.className = "form-check me-2";
        checkboxWrapper.innerHTML = `
            <input
                class="form-check-input checkbox-excluir-inspecao-tanque"
                type="checkbox"
                value="${botaoHistorico.dataset.id}"
                data-peca="${botaoHistorico.dataset.peca || ""}"
                data-data="${botaoHistorico.dataset.data || ""}"
                title="Selecionar inspeção para exclusão"
            >
        `;

        topoCard.insertBefore(checkboxWrapper, topoCard.firstElementChild);
    });

    atualizarEstadoExclusaoInspecaoTanque();
}

document.addEventListener("DOMContentLoaded", () => {
    const cardsContainer = document.getElementById("cards-inspecionados");
    const botaoAbrirModal = document.getElementById("btn-abrir-exclusao-tanque");
    const botaoConfirmar = document.getElementById("confirmar-exclusao-inspecao-tanque");

    if (!cardsContainer || !botaoAbrirModal || !botaoConfirmar) {
        return;
    }

    const observer = new MutationObserver(() => {
        injetarCheckboxesInspecaoTanque();
    });

    observer.observe(cardsContainer, { childList: true, subtree: true });
    injetarCheckboxesInspecaoTanque();

    document.addEventListener("change", (event) => {
        if (event.target.classList.contains("checkbox-excluir-inspecao-tanque")) {
            atualizarEstadoExclusaoInspecaoTanque();
        }
    });

    botaoAbrirModal.addEventListener("click", () => {
        const selecionadas = obterInspecoesTanqueSelecionadas();

        if (selecionadas.length === 0) {
            return;
        }

        document.getElementById("qtd-inspecoes-excluir-tanque").textContent = selecionadas.length;
        document.getElementById("lista-inspecoes-excluir-tanque").innerHTML = selecionadas
            .map((item) => `<div>${item.peca} <span class="text-muted">(${item.data})</span></div>`)
            .join("");

        new bootstrap.Modal(document.getElementById("modal-excluir-inspecao-tanque")).show();
    });

    botaoConfirmar.addEventListener("click", async function () {
        const selecionadas = obterInspecoesTanqueSelecionadas();
        const spinner = this.querySelector(".spinner-border");

        if (selecionadas.length === 0) {
            toastExcluirInspecaoTanque.fire({
                icon: "warning",
                title: "Selecione ao menos uma inspeção"
            });
            return;
        }

        this.disabled = true;
        spinner.style.display = "inline-flex";

        try {
            const response = await fetch("/inspecao/api/excluir-inspecao-tanque/", {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                },
                body: JSON.stringify({
                    ids: selecionadas.map((item) => item.id),
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Erro ao excluir inspeção");
            }

            bootstrap.Modal.getInstance(
                document.getElementById("modal-excluir-inspecao-tanque")
            ).hide();

            toastExcluirInspecaoTanque.fire({
                icon: "success",
                title: data.message || "Inspeção excluída com sucesso"
            });

            if (typeof buscarItensInspecionadosEstanqueidadeTanque === "function") {
                buscarItensInspecionadosEstanqueidadeTanque(1);
            }

            if (typeof buscarItensReinspecaoEstanqueidadeTanque === "function") {
                buscarItensReinspecaoEstanqueidadeTanque(1);
            }
        } catch (error) {
            toastExcluirInspecaoTanque.fire({
                icon: "error",
                title: error.message || "Falha ao excluir inspeção"
            });
        } finally {
            this.disabled = false;
            spinner.style.display = "none";
        }
    });
});
