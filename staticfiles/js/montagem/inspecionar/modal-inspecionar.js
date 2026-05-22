document.addEventListener("DOMContentLoaded", () => {
    function destroySelect2($select) {
        if ($select.hasClass("select2-hidden-accessible")) {
            $select.select2("destroy");
        }
    }

    function initSelect2InModal(context = document) {
        const $context = $(context);
        const $selects = $context.find("select.select2").addBack("select.select2");

        $selects.each(function() {
            const $select = $(this);
            const $modalContent = $select.closest(".modal-content");

            destroySelect2($select);

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
        if (event.target.classList.contains('iniciar-inspecao')) {

            document.getElementById("form-inspecao").reset();
            $("#modal-inspecionar-montagem .select2").val(null).trigger("change");

            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const apontada = event.target.getAttribute("data-qtd");

            document.getElementById("id-inspecao-montagem").value = id;
            document.getElementById("data-finalizada-inspecao-montagem").value = data;
            document.getElementById("peca-inspecao-montagem").value = peca;
            document.getElementById("qtd-produzida-montagem").value = apontada;

            const modal = new bootstrap.Modal(document.getElementById("modal-inspecionar-montagem"));
            modal.show();
        }
    })
    document.getElementById("conformidade-inspecao-montagem").addEventListener("input", function() {
        const qtdInspecao = parseFloat(document.getElementById("qtd-inspecao-montagem").value) || 0;
        const conformidade = parseFloat(this.value) || 0;
        const naoConformidade = qtdInspecao - conformidade;
        const containerInspecao = document.getElementById("containerInspecao");
        const addRemoveContainer = document.getElementById("addRemoveContainer");
    
        
        document.getElementById("nao-conformidade-inspecao-montagem").value = naoConformidade;
        
        if (naoConformidade <= 0) {
            containerInspecao.style.display = "none";
            addRemoveContainer.style.display = "none";
    
            // Remove o atributo 'required' de todos os inputs (exceto file) e selects dentro do containerInspecao
            const inputs = containerInspecao.querySelectorAll('input');
            const selects = containerInspecao.querySelectorAll('select');

            inputs.forEach(input => {
                if (input.type !== 'file') { // Ignora inputs do tipo file
                    input.removeAttribute('required');
                }
                input.value = "";
            });
            selects.forEach(select => {
                select.value = "";
                select.removeAttribute('required');
            });
        } else {
            containerInspecao.style.display = "block";
            addRemoveContainer.style.display = "flex";
    
            // Adiciona o atributo 'required' de volta a todos os inputs (exceto file) e selects dentro do containerInspecao
            const inputs = containerInspecao.querySelectorAll('input');
            const selects = containerInspecao.querySelectorAll('select');
    
            inputs.forEach(input => {
                if (input.type !== 'file') { // Ignora inputs do tipo file
                    input.setAttribute('required', 'required');
                }
            });
            selects.forEach(select => select.setAttribute('required', 'required'));
        }
    });

    document.getElementById("qtd-inspecao-montagem").addEventListener("input", function() {
        const qtdInspecao = parseFloat(this.value) || 0;
        const conformidade = parseFloat(document.getElementById("conformidade-inspecao-montagem").value) || 0;
        const naoConformidade = qtdInspecao - conformidade;
        const containerInspecao = document.getElementById("containerInspecao");
        const addRemoveContainer = document.getElementById("addRemoveContainer");
    
        
        document.getElementById("nao-conformidade-inspecao-montagem").value = naoConformidade;
        
        if (naoConformidade <= 0) {
            containerInspecao.style.display = "none";
            addRemoveContainer.style.display = "none";
    
            // Remove o atributo 'required' de todos os inputs (exceto file) e selects dentro do containerInspecao
            const inputs = containerInspecao.querySelectorAll('input');
            const selects = containerInspecao.querySelectorAll('select');

            inputs.forEach(input => {
                if (input.type !== 'file') { // Ignora inputs do tipo file
                    input.removeAttribute('required');
                }
                input.value = "";
            });
            selects.forEach(select => {
                select.value = "";
                select.removeAttribute('required');
            });
        } else {
            containerInspecao.style.display = "block";
            addRemoveContainer.style.display = "flex";
    
            // Adiciona o atributo 'required' de volta a todos os inputs (exceto file) e selects dentro do containerInspecao
            const inputs = containerInspecao.querySelectorAll('input');
            const selects = containerInspecao.querySelectorAll('select');
    
            inputs.forEach(input => {
                if (input.type !== 'file') { // Ignora inputs do tipo file
                    input.setAttribute('required', 'required');
                }
            });
            selects.forEach(select => select.setAttribute('required', 'required'));
        }
    });

    const containerInspecao = document.getElementById("containerInspecao");
    const addButton = document.getElementById("addButtonmontagem");
    const removeButton = document.getElementById("removeButtonmontagem");

    addButton.addEventListener("click", () => {
        const lastContainer = containerInspecao.lastElementChild;

        destroySelect2($(lastContainer).find("select.select2"));

        const newContainer = lastContainer.cloneNode(true);

        const span = newContainer.querySelector("span.label-modal");
        const currentCount = containerInspecao.children.length + 1;
        span.textContent = `${currentCount}ª Causa`;

        newContainer.querySelector("select").value = "";
        newContainer.querySelector("select").name = `causas_${currentCount}`;
        newContainer.querySelector("input[type='number']").value = "";
        newContainer.querySelector("input[type='file']").value = "";
        newContainer.querySelector("input[type='file']").name = `imagens_${currentCount}`;


        containerInspecao.appendChild(newContainer);
        initSelect2InModal(newContainer);
    });


    removeButton.addEventListener("click", () => {

        if (containerInspecao.children.length > 1) {
            containerInspecao.removeChild(containerInspecao.lastElementChild);
        }
    });
    initSelect2InModal(document.getElementById("modal-inspecionar-montagem"));
});
