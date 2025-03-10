document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-reinspecao')) {

            document.getElementById("form-reinspecao").reset();
            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const peca = event.target.getAttribute("data-peca");
            const tipo = event.target.getAttribute("data-tipo");
            const cor = event.target.getAttribute("data-cor");
            const conformidade = event.target.getAttribute("data-conformidade");

            document.getElementById("id-reinspecao-pintura").value = id;
            document.getElementById("data-finalizada-reinspecao-pintura").value = data;
            document.getElementById("peca-reinspecao-pintura").value = peca;
            document.getElementById("cor-reinspecao-pintura").value = `${cor} - ${tipo}`;
            document.getElementById("qtd-reinspecao-pintura").value = conformidade;

            const modal = new bootstrap.Modal(document.getElementById("modal-reinspecionar-pintura"));
            modal.show();
        }
    })
    document.getElementById("conformidade-reinspecao-pintura").addEventListener("input", function() {
        const qtdInspecao = parseFloat(document.getElementById("qtd-reinspecao-pintura").value) || 0;
        const conformidade = parseFloat(this.value) || 0;
        const naoConformidade = qtdInspecao - conformidade;

        document.getElementById("nao-conformidade-reinspecao-pintura").value = naoConformidade;
    });

    const containerInspecao = document.getElementById("containerReinspecao");
    const addButton = document.getElementById("add-reinspecao-pintura");
    const removeButton = document.getElementById("remove-reinspecao-pintura");

    // Função para adicionar um novo contêiner
    addButton.addEventListener("click", () => {
        // Seleciona o último contêiner existente
        const lastContainer = containerInspecao.lastElementChild;

        // Remove a inicialização do Select2 antes de clonar
        $(lastContainer).find('select.select2').select2('destroy');

        // Clona o último contêiner existente
        const newContainer = lastContainer.cloneNode(true);

        // Atualiza o texto do span (ex: "2ª Causa", "3ª Causa", etc.)
        const span = newContainer.querySelector("span.label-modal");
        const currentCount = containerInspecao.children.length + 1;
        span.textContent = `${currentCount}ª Causa`;

        // Limpa os valores dos inputs e selects
        newContainer.querySelector("select").value = "";
        newContainer.querySelector("input[type='number']").value = "";
        newContainer.querySelector("input[type='file']").value = "";

        // Adiciona o novo contêiner ao DOM
        containerInspecao.appendChild(newContainer);

        // Reaplica o select2 nos selects clonados
        $('.select2').each(function() {
            $(this).select2({
                dropdownParent: $(this).closest('.modal'),
                width: '100%'
            });
        });
    });


    // Função para remover o último contêiner
    removeButton.addEventListener("click", () => {
        // Verifica se há mais de um contêiner para evitar remover o primeiro
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