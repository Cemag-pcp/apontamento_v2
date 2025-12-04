document.addEventListener('DOMContentLoaded', function() {
    const retesteStatusEstanqueidade = document.getElementById('reteste_status_estanqueidade');
    const causasContainerEstanqueidade = document.getElementById('causasContainerEstanqueidade');
    const motivoFichaRetrabalhoEstanqueidade = document.getElementById('motivo_ficha_retrabalho_estanqueidade');
    const addRemoveCauseReteste = document.getElementById('addRemoveContainerReteste');
    const addRemoveCauseCilindro = document.getElementById('addRemoveContainerCilindro');
    const addRemoveCauseTubo = document.getElementById('addRemoveContainerTubo');
    const naoConformidadeTubos = document.getElementById('nao_conformidade_tubos');
    const tipoInspecaoEstanqueidade = document.getElementById('tipo_inspecao_estanqueidade');
    const naoConformidadeCilindro = document.getElementById('nao-conformidade-inspecao-cilindro');
    const containerInspecaoCilindro = document.getElementById('containerInspecaoCilindro');
    const causasCilindro = document.querySelectorAll('.causas_cilindro, .quantidade_causas_cilindro');
    const naoConformidadeRetrabalhoTubo = document.getElementById('nao-conformidade-retrabalho-inspecao-tubo');
    const naoConformidadeRefugoTubo = document.getElementById('nao-conformidade-refugo-inspecao-tubo');
    const causasContainerEstanqueidadeTubo = document.getElementById('containerInspecaoTubo');
    const causasTubos = document.querySelectorAll('.causas_tubo, .quantidade_causas_tubo');

    if (retesteStatusEstanqueidade) {
        retesteStatusEstanqueidade.addEventListener('change', function() {
            const causasEstanqueidadeSelects = document.querySelectorAll('.causas_reteste, .quantidade_causas_reteste, #motivo_reteste_estanqueidade');
            if (this.value === "Não Conforme") {
                causasContainerEstanqueidade.style.display = "block";
                motivoFichaRetrabalhoEstanqueidade.style.display = "flex";
                addRemoveCauseReteste.style.display = "flex";

                causasEstanqueidadeSelects.forEach(element => {
                    element.setAttribute('required', true);
                });

                if (tipoInspecaoEstanqueidade.value === 'tubo') {
                    naoConformidadeTubos.innerHTML = `
                        <div class="col-sm-6 mb-4">
                            <label class="label-modal">Não conforme retrabalho</label>
                            <input type="number" class="form-control" name="nao-conformidade-tubo-retrabalho" id="nao-conformidade-tubo-retrabalho" min=0 required> 
                        </div>
                        <div class="col-sm-6 mb-4">
                            <label class="label-modal">Não conforme refugo</label>
                            <input type="number" class="form-control" name="nao-conformidade-tubo-refugo" id="nao-conformidade-tubo-refugo" min=0 required> 
                        </div>
                    `;
                }
            } else {
                naoConformidadeTubos.innerHTML = '';
                causasContainerEstanqueidade.style.display = "none";
                motivoFichaRetrabalhoEstanqueidade.style.display = "none";
                addRemoveCauseReteste.style.display = "none";

                causasEstanqueidadeSelects.forEach(element => {
                    element.removeAttribute('required');
                });
            }
        });
    }

    if (naoConformidadeCilindro) {
        naoConformidadeCilindro.addEventListener('input', function() {
            if (parseInt(this.value) === 0) {
                containerInspecaoCilindro.style.display = "none";
                addRemoveCauseCilindro.style.display = "none";
                causasCilindro.forEach(element => {
                    element.removeAttribute('required');
                });
            } else {
                containerInspecaoCilindro.style.display = "block";
                addRemoveCauseCilindro.style.display = "flex";
                causasCilindro.forEach(element => {
                    element.setAttribute('required', true);
                });
            }
        });
    }

    if (naoConformidadeRetrabalhoTubo) {
        naoConformidadeRetrabalhoTubo.addEventListener('input', function() {
            const total = parseInt(this.value) + parseInt(naoConformidadeRefugoTubo.value);
            if (total === 0) {
                causasContainerEstanqueidadeTubo.style.display = "none";
                addRemoveCauseTubo.style.display = "none";
                causasTubos.forEach(element => {
                    element.removeAttribute('required');
                });
            } else {
                causasContainerEstanqueidadeTubo.style.display = "block";
                addRemoveCauseTubo.style.display = "flex";
                causasTubos.forEach(element => {
                    element.setAttribute('required', true);
                });
            }
        });
    }

    if (naoConformidadeRefugoTubo) {
        naoConformidadeRefugoTubo.addEventListener('input', function() {
            const total = parseInt(this.value) + parseInt(naoConformidadeRetrabalhoTubo.value);
            if (total === 0) {
                causasContainerEstanqueidadeTubo.style.display = "none";
                addRemoveCauseTubo.style.display = "none";
                causasTubos.forEach(element => {
                    element.removeAttribute('required');
                });
            } else {
                causasContainerEstanqueidadeTubo.style.display = "block";
                addRemoveCauseTubo.style.display = "flex";
                causasTubos.forEach(element => {
                    element.setAttribute('required', true);
                });
            }
        });
    }
});