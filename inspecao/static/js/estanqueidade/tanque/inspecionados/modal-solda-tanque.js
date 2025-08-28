document.addEventListener("DOMContentLoaded", () => {
    
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('inspecionar-solda')){
            
            // Reset do formulário e limpeza dos selects
            document.getElementById("form-inspecao").reset();
            $('.select2').val(null).trigger('change');

            const dataInspecao = document.getElementById('data-inspecao-solda-tanque');
            const hoje = new Date().toISOString().split('T')[0];
            dataInspecao.value = hoje;
            
            const modalSolda = new bootstrap.Modal(document.getElementById('modal-inspecionar-solda-tanque'));
            const nomeTanque = event.target.getAttribute('data-nome');
            const idTanque = event.target.getAttribute('data-id');
            
            document.getElementById("id-inspecao-solda-tanque").value = idTanque;
            document.getElementById('peca-inspecao-solda-tanque').value = nomeTanque;
            modalSolda.show();
        }
    });

    // Lógica para calcular não conformidades baseado na quantidade produzida e conformidades
    document.getElementById("conformidade-inspecao-solda-tanque").addEventListener("input", function() {
        const qtdProduzida = parseFloat(document.getElementById("qtd-produzida-solda-tanque").value) || 0;
        const conformidade = parseFloat(this.value) || 0;
        const naoConformidade = qtdProduzida - conformidade;
        const containerInspecao = document.getElementById("containerInspecao");
        const addRemoveContainer = document.getElementById("addRemoveContainer");
    
        
        document.getElementById("nao-conformidade-inspecao-solda-tanque").value = naoConformidade;
        
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

    // Lógica para adicionar/remover containers de causas
    const containerInspecao = document.getElementById("containerInspecao");
    const addButton = document.getElementById("addButtonsolda-tanque");
    const removeButton = document.getElementById("removeButtonsolda-tanque");

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
});

$(document).ready(function() {
    $('.select2').each(function() {
        $(this).select2({
            dropdownParent: $(this).closest('.modal'),
            width: '100%'
        });
    });
});