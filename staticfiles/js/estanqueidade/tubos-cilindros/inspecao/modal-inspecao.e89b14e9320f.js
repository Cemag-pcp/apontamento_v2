document.addEventListener("DOMContentLoaded", () => {
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