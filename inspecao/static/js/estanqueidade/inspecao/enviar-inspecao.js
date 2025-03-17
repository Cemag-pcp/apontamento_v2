document.addEventListener("DOMContentLoaded", () => {

    document.getElementById("form-inspecao-tubo").addEventListener("submit", function (event) {
        event.preventDefault();

        const modal = document.getElementById('modal-inspecao-tubo');
        const modalInstance = bootstrap.Modal.getInstance(modal); // Obter a instância existente
        let buttonInspecionarTubo = document.getElementById("submit-inspecionar-tubo");
        buttonInspecionarTubo.disabled = true;
        buttonInspecionarTubo.querySelector(".spinner-border").style.display = "flex";

        // Criar um objeto FormData para enviar os arquivos
        const formData = new FormData(this); // Usar o formulário diretamente

        // Adicionar os dados básicos ao FormData
        const naoConformidadeRetrabalho = document.getElementById("nao-conformidade-retrabalho-inspecao-tubo").value;
        const naoConformidadeRefugo = document.getElementById("nao-conformidade-refugo-inspecao-tubo").value;

        let totalQuantidadeInput = 0;
        // Adicionar causas, quantidades e imagens ao FormData
        const selectContainerInspecao = document.querySelectorAll(".selectContainerInspecaoTubo");
        selectContainerInspecao.forEach((container, index) => {
            const causaSelect = container.querySelector('select');
            const quantidadeInput = container.querySelector('input[type="number"]');
            const imagensInput = container.querySelector('input[type="file"]');
            totalQuantidadeInput += parseFloat(quantidadeInput.value);
            console.log(totalQuantidadeInput)

            // Adicionar causas
            Array.from(causaSelect.selectedOptions).forEach((option, i) => {
                formData.append(`causas_${index + 1}[${i}]`, option.value);
            });

            // Adicionar quantidade
            formData.append(`quantidade_${index + 1}`, quantidadeInput.value);

            // Adicionar arquivos de imagem
            Array.from(imagensInput.files).forEach((file, i) => {
                formData.append(`imagens_${index + 1}[${i}]`, file); // Anexar o arquivo diretamente
            });
        });

        const naoConformidadeNum = parseFloat(naoConformidadeRetrabalho) + parseFloat(naoConformidadeRefugo);

        console.log(naoConformidadeNum)
        console.log(totalQuantidadeInput)

        if (naoConformidadeNum !== 0) {
            const erroMensagem = naoConformidadeNum > 0 && totalQuantidadeInput !== naoConformidadeNum
                ? 'Verifique se a soma dos campos de "Quantidade" está igual ao valor de "N° total de não conformidade Refugo" + "N° total de não conformidade Retrabalho"'
                : naoConformidadeNum < 0
                ? 'Verifique se o "N° total de conformidades" está com o valor correto'
                : null;
        
            if (erroMensagem) {
                Swal.fire({
                    icon: 'error',
                    title: erroMensagem,
                });
        
                buttonInspecionarTubo.disabled = false;
                buttonInspecionarTubo.querySelector(".spinner-border").style.display = "none";
                return;
            }
        }

        formData.append("quantidade-total-causas", selectContainerInspecao.length)

        // Enviar os dados para o backend
        fetch("/inspecao/api/envio-inspecao-tubos-cilindros/", {
            method: "POST",
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: formData, // Usar FormData em vez de JSON
        })
        .then(response => {
            return response.json().then(data => {
                if (!response.ok) {
                    throw new Error(data.error || `Erro na requisição HTTP. Status: ${response.status}`);
                }
                return data;
            });
        })
        .then(data => {
            if (modalInstance) {
                modalInstance.hide();
            }
            const Toast = Swal.mixin({
                toast: true,
                position: "bottom-end",
                showConfirmButton: false,
                timer: 3000,
                timerProgressBar: true,
                didOpen: (toast) => {
                toast.onmouseenter = Swal.stopTimer;
                toast.onmouseleave = Swal.resumeTimer;
                }
            });
            Toast.fire({
                icon: "success",
                title: "Inspeção realizada com sucesso"
            });
            buscarItensReinspecaoEstanqueidade(1);
            buscarItensInspecionadosEstanqueidade(1);
            this.reset();
        })
        .catch(error => {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Erro no envio da inspeção',
                text: error, // Exibe a mensagem do backend corretamente
            });
        })
        .finally(() => {
            buttonInspecionarTubo.disabled = false;
            buttonInspecionarTubo.querySelector(".spinner-border").style.display = "none";
        });
    });

    document.getElementById("form-inspecao-cilindro").addEventListener("submit", function (event) {
        event.preventDefault();

        const modal = document.getElementById('modal-inspecao-cilindro');
        const modalInstance = bootstrap.Modal.getInstance(modal); // Obter a instância existente
        let buttonInspecionarCilindro = document.getElementById("submit-inspecionar-cilindro");
        buttonInspecionarCilindro.disabled = true;
        buttonInspecionarCilindro.querySelector(".spinner-border").style.display = "flex";

        // Criar um objeto FormData para enviar os arquivos
        const formData = new FormData(this); // Usar o formulário diretamente

        // Adicionar os dados básicos ao FormData
        const naoConformidade = document.getElementById("nao-conformidade-inspecao-cilindro").value;

        let totalQuantidadeInput = 0;
        // Adicionar causas, quantidades e imagens ao FormData
        const selectContainerInspecao = document.querySelectorAll(".selectContainerInspecaoCilindro");
        selectContainerInspecao.forEach((container, index) => {
            const causaSelect = container.querySelector('select');
            const quantidadeInput = container.querySelector('input[type="number"]');
            const imagensInput = container.querySelector('input[type="file"]');
            totalQuantidadeInput += parseFloat(quantidadeInput.value);
            console.log(totalQuantidadeInput)

            // Adicionar causas
            Array.from(causaSelect.selectedOptions).forEach((option, i) => {
                formData.append(`causas_${index + 1}[${i}]`, option.value);
            });

            // Adicionar quantidade
            formData.append(`quantidade_${index + 1}`, quantidadeInput.value);

            // Adicionar arquivos de imagem
            Array.from(imagensInput.files).forEach((file, i) => {
                formData.append(`imagens_${index + 1}[${i}]`, file); // Anexar o arquivo diretamente
            });
        });

        const naoConformidadeNum = parseFloat(naoConformidade);

        if (naoConformidadeNum !== 0) {
            const erroMensagem = naoConformidadeNum > 0 && totalQuantidadeInput !== naoConformidadeNum
                ? 'Verifique se a soma dos campos de "Quantidade" está igual ao valor de "N° total de não conformidade Refugo" + "N° total de não conformidade Retrabalho"'
                : naoConformidadeNum < 0
                ? 'Verifique se o "N° total de conformidades" está com o valor correto'
                : null;
        
            if (erroMensagem) {
                Swal.fire({
                    icon: 'error',
                    title: erroMensagem,
                });
        
                buttonInspecionarCilindro.disabled = false;
                buttonInspecionarCilindro.querySelector(".spinner-border").style.display = "none";
                return;
            }
        }

        formData.append("quantidade-total-causas", selectContainerInspecao.length)

        // Enviar os dados para o backend
        fetch("/inspecao/api/envio-inspecao-tubos-cilindros/", {
            method: "POST",
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: formData, // Usar FormData em vez de JSON
        })
        .then(response => {
            return response.json().then(data => {
                if (!response.ok) {
                    throw new Error(data.error || `Erro na requisição HTTP. Status: ${response.status}`);
                }
                return data;
            });
        })
        .then(data => {
            if (modalInstance) {
                modalInstance.hide();
            }
            const Toast = Swal.mixin({
                toast: true,
                position: "bottom-end",
                showConfirmButton: false,
                timer: 3000,
                timerProgressBar: true,
                didOpen: (toast) => {
                toast.onmouseenter = Swal.stopTimer;
                toast.onmouseleave = Swal.resumeTimer;
                }
            });
            Toast.fire({
                icon: "success",
                title: "Inspeção realizada com sucesso"
            });
            buscarItensReinspecaoEstanqueidade(1);
            buscarItensInspecionadosEstanqueidade(1);
            this.reset();
        })
        .catch(error => {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Erro no envio da inspeção',
                text: error, // Exibe a mensagem do backend corretamente
            });
        })
        .finally(() => {
            buttonInspecionarCilindro.disabled = false;
            buttonInspecionarCilindro.querySelector(".spinner-border").style.display = "none";
        });
    });
});