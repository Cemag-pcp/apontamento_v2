document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-reinspecao')) {

            document.getElementById("form-reinspecao").reset();
            
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