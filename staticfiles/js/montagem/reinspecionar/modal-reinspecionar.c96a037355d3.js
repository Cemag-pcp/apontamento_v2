document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-reinspecao')) {

            document.getElementById("form-reinspecao").reset();
            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const tipo = event.target.getAttribute("data-tipo");
            const cor = event.target.getAttribute("data-cor");
            const totalReinspecao = event.target.getAttribute("data-nao-conformidade");

            document.getElementById("id-reinspecao-montagem").value = id;
            document.getElementById("data-finalizada-reinspecao-montagem").value = data;
            document.getElementById("peca-reinspecao-montagem").value = peca;
            document.getElementById("cor-reinspecao-montagem").value = `${cor} - ${tipo}`;
            document.getElementById("qtd-reinspecao-montagem").value = totalReinspecao;

            const modal = new bootstrap.Modal(document.getElementById("modal-reinspecionar-montagem"));
            modal.show();
        }
    })
    document.getElementById("conformidade-reinspecao-montagem").addEventListener("input", function() {
        const qtdInspecao = parseFloat(document.getElementById("qtd-reinspecao-montagem").value) || 0;
        const conformidade = parseFloat(this.value) || 0;
        const naoConformidade = qtdInspecao - conformidade;
        const containerInspecao = document.getElementById("containerReinspecao");
        const addRemoveContainer = document.getElementById("addRemoveContainerReinspecao");


        document.getElementById("nao-conformidade-reinspecao-montagem").value = naoConformidade;

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

    const containerInspecao = document.getElementById("containerReinspecao");
    const addButton = document.getElementById("add-reinspecao-montagem");
    const removeButton = document.getElementById("remove-reinspecao-montagem");

    addButton.addEventListener("click", () => {

        const lastContainer = containerInspecao.lastElementChild;

        $(lastContainer).find('select.select2').select2('destroy');

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

        $('.select2').each(function() {
            $(this).select2({
                dropdownParent: $(this).closest('.modal'),
                width: '100%'
            });
        });
    });


    removeButton.addEventListener("click", () => {
        if (containerInspecao.children.length > 1) {
            containerInspecao.removeChild(containerInspecao.lastElementChild);
        }
    });
})

$(document).ready(function() {
    $('.select2').each(function() {
        $(this).select2({
            dropdownParent: $(this).closest('.modal'),
            width: '100%'
        });
    });
});