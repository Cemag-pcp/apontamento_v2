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
        if (event.target.classList.contains('iniciar-reinspecao')) {

            document.getElementById("form-reinspecao").reset();
            $('.select2').val(null).trigger('change');
            
            const causasContainerEstanqueidade = document.getElementById('causasContainerEstanqueidade');
            const motivoFichaRetrabalhoEstanqueidade = document.getElementById('motivo_ficha_retrabalho_estanqueidade');
            const addRemoveCauseReteste = document.getElementById('addRemoveContainerReteste');
            const naoConformidadeTubos = document.getElementById('nao_conformidade_tubos');

            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const tipoInspecao = event.target.getAttribute("data-tipo");
            const naoConformidade = event.target.getAttribute("data-nao-conformidade");
            const naoConformidadeRefugo = event.target.getAttribute("data-nao-conformidade-refugo");
            let totalReinspecao;

            if(!naoConformidadeRefugo) {
                totalReinspecao = parseInt(naoConformidade);
            } else {
                totalReinspecao = parseInt(naoConformidade) + parseInt(naoConformidadeRefugo);
            }
            
            document.getElementById("cabecalho-reteste-estanqueidade").textContent = `Reteste - ${tipoInspecao}`
            document.getElementById("inspecao_id").value = id;
            document.getElementById("data_inspecao_estanqueidade").value = data;
            document.getElementById("tipo_inspecao_estanqueidade").value = tipoInspecao;
            document.getElementById("qnt_reinspecao").value = totalReinspecao;
            causasContainerEstanqueidade.style.display = "none";
            motivoFichaRetrabalhoEstanqueidade.style.display = "none";
            addRemoveCauseReteste.style.display = "none";
            naoConformidadeTubos.innerHTML = "";

            const modal = new bootstrap.Modal(document.getElementById("modal-reteste-estanqueidade"));
            modal.show();
        }   
    })

    const containerInspecao = document.getElementById("causasContainerEstanqueidade");
    const addButton = document.getElementById("add-reinspecao-tubos-cilindros");
    const removeButton = document.getElementById("remove-reinspecao-tubos-cilindros");

    addButton.addEventListener("click", () => {

        const lastContainer = containerInspecao.lastElementChild;

        destroySelect2($(lastContainer).find("select.select2"));

        const newContainer = lastContainer.cloneNode(true);

        const span = newContainer.querySelector("span.label-modal");
        const currentCount = containerInspecao.children.length + 1;
        span.textContent = `${currentCount}ª Causa`;

        newContainer.querySelector("select").value = "";
        newContainer.querySelector("select").name = `causas_reinspecao_${currentCount}`;
        newContainer.querySelector("input[type='number']").value = "";
        newContainer.querySelector("input[type='file']").value = "";
        newContainer.querySelector("input[type='file']").name = `imagens_reinspecao_${currentCount}`;

        containerInspecao.appendChild(newContainer);

        initModalSelects(newContainer);
    });


    removeButton.addEventListener("click", () => {
        if (containerInspecao.children.length > 1) {
            containerInspecao.removeChild(containerInspecao.lastElementChild);
        }
    });

    initModalSelects(document);
});
