document.addEventListener("DOMContentLoaded", () => {
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

    function initModalSelects(context = document) {
        const $selects = getSelects(context);

        $selects.each(function() {
            const $select = $(this);
            destroySelect2($select);

            if (isMobileLayout()) {
                if (this.multiple) {
                    this.setAttribute("size", "6");
                } else {
                    this.removeAttribute("size");
                }
                return;
            }

            this.removeAttribute("size");

            const $modalContent = $select.closest(".modal-content");
            $select.select2({
                dropdownParent: $modalContent,
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

    document.addEventListener("click", function (event) {
        if (event.target.id === "button-inspecao-tubos") {
            const modal = new bootstrap.Modal(document.getElementById("modal-inspecao-tubo"));
            modal.show();
        } else if(event.target.id ===  "button-inspecao-cilindros") {
            const modal = new bootstrap.Modal(document.getElementById("modal-inspecao-cilindro"));
            modal.show();
        }
    })

    const containerInspecaoTubo = document.getElementById("containerInspecaoTubo");
    const containerInspecaoCilindro = document.getElementById("containerInspecaoCilindro");

    const addButtonTubo = document.getElementById("add-causas-tubos");
    const removeButtonTubo = document.getElementById("remove-causas-tubos");

    const addButtonCilindro = document.getElementById("add-causas-cilindros");
    const removeButtonCilindro = document.getElementById("remove-causas-cilindros");

    if (addButtonTubo && removeButtonTubo && containerInspecaoTubo) {
        setupContainerActions(addButtonTubo, removeButtonTubo, containerInspecaoTubo);
    }

    if (addButtonCilindro && removeButtonCilindro && containerInspecaoCilindro) {
        setupContainerActions(addButtonCilindro, removeButtonCilindro, containerInspecaoCilindro);
    }

    function setupContainerActions(addButton, removeButton, container) {
        addButton.addEventListener("click", () => addContainer(container));
        removeButton.addEventListener("click", () => removeContainer(container));
    }

    function addContainer(container) {
        const lastContainer = container.lastElementChild;

        if (!lastContainer) return;

        destroySelect2($(lastContainer).find("select.select2"));

        const newContainer = lastContainer.cloneNode(true);

        const span = newContainer.querySelector("span.label-modal");
        const currentCount = container.children.length + 1;
        span.textContent = `${currentCount}ª Causa`;

        const select = newContainer.querySelector("select");
        const inputNumber = newContainer.querySelector("input[type='number']");
        const inputFile = newContainer.querySelector("input[type='file']");

        if (select) {
            select.value = "";
            select.name = `causas_reinspecao_${currentCount}`;
        }

        if (inputNumber) {
            inputNumber.value = "";
        }

        if (inputFile) {
            inputFile.value = "";
            inputFile.name = `imagens_reinspecao_${currentCount}`;
        }

        container.appendChild(newContainer);

        initModalSelects(newContainer);
    }

    function removeContainer(container) {
        if (container.children.length > 1) {
            container.removeChild(container.lastElementChild);
        }
    }
    initModalSelects(document);
});
