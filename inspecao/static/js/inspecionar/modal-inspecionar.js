document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-inspecao')) {

            document.getElementById("form-inspecao").reset();
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
    })
    document.getElementById("conformidade-inspecao-pintura").addEventListener("input", function() {
        const qtdInspecao = parseFloat(document.getElementById("qtd-inspecao-pintura").value) || 0;
        const conformidade = parseFloat(this.value) || 0;
        const naoConformidade = qtdInspecao - conformidade;

        document.getElementById("nao-conformidade-inspecao-pintura").value = naoConformidade;
    });

    const containerInspecao = document.getElementById("containerInspecao");
    const addButton = document.getElementById("addButtonPintura");
    const removeButton = document.getElementById("removeButtonPintura");

    addButton.addEventListener("click", () => {
        const lastContainer = containerInspecao.lastElementChild;

        $(lastContainer).find('select.select2').select2('destroy');

        const newContainer = lastContainer.cloneNode(true);

        const span = newContainer.querySelector("span.label-modal");
        const currentCount = containerInspecao.children.length + 1;
        span.textContent = `${currentCount}ª Causa`;

        newContainer.querySelector("select").value = "";
        newContainer.querySelector("input[type='number']").value = "";
        newContainer.querySelector("input[type='file']").value = "";

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