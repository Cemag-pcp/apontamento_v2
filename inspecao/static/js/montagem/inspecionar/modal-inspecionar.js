document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-inspecao')) {

            document.getElementById("form-inspecao").reset();
            $('.select2').val(null).trigger('change');

            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const apontada = event.target.getAttribute("data-qtd");

            document.getElementById("id-inspecao-montagem").value = id;
            document.getElementById("data-finalizada-inspecao-montagem").value = data;
            document.getElementById("peca-inspecao-montagem").value = peca;
            document.getElementById("qtd-inspecao-montagem").value = apontada;

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

    const containerInspecao = document.getElementById("containerInspecao");
    const addButton = document.getElementById("addButtonmontagem");
    const removeButton = document.getElementById("removeButtonmontagem");

    addButton.addEventListener("click", () => {
        const lastContainer = containerInspecao.lastElementChild;

        $(lastContainer).find('select.select2').select2('destroy');

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