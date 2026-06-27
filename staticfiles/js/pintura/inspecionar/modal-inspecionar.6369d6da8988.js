document.addEventListener("DOMContentLoaded", () => {
    const modalSelector = "#modal-inspecionar-pintura";
    const mobileQuery = window.matchMedia("(max-width: 768px), (pointer: coarse)");

    function isMobileLayout() {
        return mobileQuery.matches;
    }

    function destroySelect2($select) {
        if ($select.hasClass("select2-hidden-accessible")) {
            $select.select2("destroy");
        }
    }

    function getSelects(context = document) {
        const $context = $(context);
        return $context.find("select.select2").addBack("select.select2");
    }

    function initCauseSelects(context = document) {
        const $selects = getSelects(context);

        $selects.each(function() {
            const $select = $(this);
            destroySelect2($select);

            if (isMobileLayout()) {
                this.setAttribute("size", "6");
                return;
            }

            this.removeAttribute("size");
            $select.select2({
                dropdownParent: $(modalSelector).find(".modal-content"),
                width: "100%"
            });

            $select.off("select2:open.select2ModalFix");
            $select.off("select2:close.select2ModalFix");

            $select.on("select2:open.select2ModalFix", function() {
                const modalBody = this.closest(".modal-content")?.querySelector(".modal-body");
                if (modalBody) {
                    modalBody.dataset.previousOverflow = modalBody.style.overflowY || "";
                    modalBody.style.overflowY = "visible";
                }

                const searchField = document.querySelector(".select2-container--open .select2-search__field");
                if (searchField) {
                    searchField.focus({ preventScroll: true });
                }
            });

            $select.on("select2:close.select2ModalFix", function() {
                const modalBody = this.closest(".modal-content")?.querySelector(".modal-body");
                if (modalBody) {
                    modalBody.style.overflowY = modalBody.dataset.previousOverflow || "auto";
                    delete modalBody.dataset.previousOverflow;
                }
            });
        });
    }

    document.addEventListener("click", function(event) {
        if (event.target.classList.contains("iniciar-inspecao")) {
            document.getElementById("form-inspecao").reset();
            $(".select2").val(null).trigger("change");

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
            document.getElementById("qtd-inspecao-pintura").value = apontada;

            const modal = new bootstrap.Modal(document.getElementById("modal-inspecionar-pintura"));
            modal.show();
        }
    });

    document.getElementById("conformidade-inspecao-pintura").addEventListener("input", function() {
        const qtdInspecao = parseFloat(document.getElementById("qtd-inspecao-pintura").value) || 0;
        const conformidade = parseFloat(this.value) || 0;
        const naoConformidade = qtdInspecao - conformidade;
        const containerInspecao = document.getElementById("containerInspecao");
        const addRemoveContainer = document.getElementById("addRemoveContainer");

        document.getElementById("nao-conformidade-inspecao-pintura").value = naoConformidade;

        if (naoConformidade <= 0) {
            containerInspecao.style.display = "none";
            addRemoveContainer.style.display = "none";

            const inputs = containerInspecao.querySelectorAll("input");
            const selects = containerInspecao.querySelectorAll("select");

            inputs.forEach(input => {
                if (input.type !== "file") {
                    input.removeAttribute("required");
                }
                input.value = "";
            });

            selects.forEach(select => {
                select.value = "";
                select.removeAttribute("required");
            });
        } else {
            containerInspecao.style.display = "block";
            addRemoveContainer.style.display = "flex";

            const inputs = containerInspecao.querySelectorAll("input");
            const selects = containerInspecao.querySelectorAll("select");

            inputs.forEach(input => {
                if (input.type !== "file") {
                    input.setAttribute("required", "required");
                }
            });

            selects.forEach(select => select.setAttribute("required", "required"));
        }
    });

    const containerInspecao = document.getElementById("containerInspecao");
    const addButton = document.getElementById("addButtonPintura");
    const removeButton = document.getElementById("removeButtonPintura");

    addButton.addEventListener("click", () => {
        const lastContainer = containerInspecao.lastElementChild;
        destroySelect2($(lastContainer).find("select.select2"));

        const newContainer = lastContainer.cloneNode(true);

        const span = newContainer.querySelector("span.label-modal");
        const currentCount = containerInspecao.children.length + 1;
        span.textContent = `${currentCount}ª Causa`;

        const select = newContainer.querySelector("select");
        select.value = "";
        select.name = `causas_${currentCount}`;

        newContainer.querySelector("input[type='number']").value = "";
        newContainer.querySelector("input[type='file']").value = "";
        newContainer.querySelector("input[type='file']").name = `imagens_${currentCount}`;

        containerInspecao.appendChild(newContainer);
        initCauseSelects(lastContainer);
        initCauseSelects(newContainer);
    });

    removeButton.addEventListener("click", () => {
        if (containerInspecao.children.length > 1) {
            containerInspecao.removeChild(containerInspecao.lastElementChild);
        }
    });

    initCauseSelects(document);
});
