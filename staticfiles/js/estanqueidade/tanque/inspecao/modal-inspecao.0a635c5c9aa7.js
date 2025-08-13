document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function (event) {
        if (event.target.id === "button-inspecao-tanque") {
            const modal = new bootstrap.Modal(document.getElementById("modal-inspecao-tanque"));
            modal.show();
        } 
    })

    const containerInspecaoTanque = document.getElementById("containerInspecaoTanque");

    const addButtonTanque = document.getElementById("add-causas-tanques");
    const removeButtonTanque = document.getElementById("remove-causas-tanques");

    if (addButtonTanque && removeButtonTanque && containerInspecaoTanque) {
        setupContainerActions(addButtonTanque, removeButtonTanque, containerInspecaoTanque);
    }

    function setupContainerActions(addButton, removeButton, container) {
        addButton.addEventListener("click", () => addContainer(container));
        removeButton.addEventListener("click", () => removeContainer(container));
    }

    function addContainer(container) {
        const lastContainer = container.lastElementChild;

        if (!lastContainer) return;

        $(lastContainer).find('select.select2').select2('destroy');

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

        $('.select2').each(function() {
            $(this).select2({
                dropdownParent: $(this).closest('.modal'),
                width: '100%'
            });
        });
    }

    function removeContainer(container) {
        if (container.children.length > 1) {
            container.removeChild(container.lastElementChild);
        }
    }
})


$(document).ready(function() {
    $('.select2').each(function() {
        $(this).select2({
            dropdownParent: $(this).closest('.modal'),
            width: '100%'
        });
    });
});