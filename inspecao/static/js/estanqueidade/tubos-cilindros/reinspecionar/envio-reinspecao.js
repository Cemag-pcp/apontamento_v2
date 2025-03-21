document.getElementById("form-reinspecao").addEventListener("submit", function (event) {
    event.preventDefault();

    let modal = document.getElementById('modal-reteste-estanqueidade');
    let inspecao_id = document.getElementById('inspecao_id').value;
    let modalInstance = bootstrap.Modal.getInstance(modal); // Obter a instância existente
    let buttonReinspecionarTubosCilindros = document.getElementById("submit-reinspecionar-tubos-cilindros");
    let tipoInspecaoEstanqueidade = document.getElementById("tipo_inspecao_estanqueidade").value;
    let quantidadeReinspecao = document.getElementById("qnt_reinspecao").value;
    let dataReinspecao = document.getElementById("data_reinspecao_estanqueidade").value;
    buttonReinspecionarTubosCilindros.disabled = true;
    buttonReinspecionarTubosCilindros.querySelector(".spinner-border").style.display = "flex";

    // Criar um objeto FormData para enviar os arquivos
    const formData = new FormData(this); // Usar o formulário diretamente

    let totalNaoConformidadeCilindro = 0;
    // Adicionar causas, quantidades e imagens ao FormData
    const selectContainerInspecao = document.querySelectorAll(".selectContainerInspecaoReteste");
    selectContainerInspecao.forEach((container, index) => {
        const causaSelect = container.querySelector('select');
        const quantidadeInput = container.querySelector('input[type="number"]');
        const imagensInput = container.querySelector('input[type="file"]');
        totalNaoConformidadeCilindro += parseFloat(quantidadeInput.value);

        // Adicionar causas
        Array.from(causaSelect.selectedOptions).forEach((option, i) => {
            formData.append(`causas_reinspecao_${index + 1}[${i}]`, option.value);
        });

        // Adicionar quantidade
        formData.append(`quantidade_reinspecao_${index + 1}`, quantidadeInput.value);

        // Adicionar arquivos de imagem
        Array.from(imagensInput.files).forEach((file, i) => {
            formData.append(`imagens_reinspecao_${index + 1}[${i}]`, file); // Anexar o arquivo diretamente
        });
    });

    let naoConformidadeNum = 0;

    if (tipoInspecaoEstanqueidade == "tubo" && tipoInspecaoEstanqueidade == "Não Conforme") {
        const naoConformidadeRetrabalho = document.getElementById("nao-conformidade-tubo-retrabalho").value;
        const naoConformidadeRefugo = document.getElementById("nao-conformidade-tubo-refugo").value;
        
        naoConformidadeNum = parseFloat(naoConformidadeRetrabalho) + parseFloat(naoConformidadeRefugo);
    } else {
        naoConformidadeNum = totalNaoConformidadeCilindro;
    }

    if (naoConformidadeNum !== 0) {
        const erroMensagem = naoConformidadeNum > 0 && totalNaoConformidadeCilindro !== naoConformidadeNum
            ? 'Verifique se a soma dos campos de "Quantidade" está igual ao valor de "N° total de não conformidade Refugo" + "N° total de não conformidade Retrabalho"'
            : naoConformidadeNum < 0 || quantidadeReinspecao < naoConformidadeNum
            ? 'Verifique se o número de não conformidades está com o valor correto'
            : null;
    
        if (erroMensagem) {
            Swal.fire({
                icon: 'error',
                title: erroMensagem,
            });
    
            buttonReinspecionarTubosCilindros.disabled = false;
            buttonReinspecionarTubosCilindros.querySelector(".spinner-border").style.display = "none";
            return;
        }
    }

    if(totalNaoConformidadeCilindro > 0) {
        formData.append("nao-conformidade-reinspecao-cilindro", totalNaoConformidadeCilindro);
    } 
    
    formData.append("quantidade-total-causas", selectContainerInspecao.length)

    formData.append("inspecao_id", inspecao_id)

    formData.append("tipo_inspecao_estanqueidade", tipoInspecaoEstanqueidade)

    formData.append("quantidade_reinspecionada", quantidadeReinspecao)

    formData.append("data_reinspecao", dataReinspecao)

    // Enviar os dados para o backend
    fetch("/inspecao/api/envio-reinspecao-tubos-cilindros/", {
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
        buscarItensInspecionadosEstanqueidade(1);
        buscarItensReinspecaoEstanqueidade(1);
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
        buttonReinspecionarTubosCilindros.disabled = false;
        buttonReinspecionarTubosCilindros.querySelector(".spinner-border").style.display = "none";
    });
});