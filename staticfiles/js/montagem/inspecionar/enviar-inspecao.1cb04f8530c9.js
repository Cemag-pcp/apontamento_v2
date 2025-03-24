document.getElementById("form-inspecao").addEventListener("submit", function (event) {
    event.preventDefault();

    const modal = document.getElementById('modal-inspecionar-montagem');
    const modalInstance = bootstrap.Modal.getInstance(modal); // Obter a instância existente
    let buttonInspecionarMontagem = document.getElementById("submit-inspecionar-montagem");
    buttonInspecionarMontagem.disabled = true;
    buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "flex";

    // Criar um objeto FormData para enviar os arquivos
    const formData = new FormData(this); // Usar o formulário diretamente

    // Adicionar os dados básicos ao FormData
    const naoConformidade = document.getElementById("nao-conformidade-inspecao-montagem").value;
    formData.append("nao-conformidade-inspecao-montagem", naoConformidade);

    let totalQuantidadeInput = 0;
    // Adicionar causas, quantidades e imagens ao FormData
    const selectContainerInspecao = document.querySelectorAll(".selectContainerInspecao");
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
            ? 'Verifique se a soma dos campos de "Quantidade" está igual ao valor de "N° total de não conformidades"'
            : naoConformidadeNum < 0
            ? 'Verifique se o "N° total de conformidades" está com o valor correto'
            : null;
    
        if (erroMensagem) {
            Swal.fire({
                icon: 'error',
                title: erroMensagem,
            });
    
            buttonInspecionarMontagem.disabled = false;
            buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "none";
            return;
        }
    }

    formData.append("quantidade-total-causas", selectContainerInspecao.length)

    // Enviar os dados para o backend
    fetch("/inspecao/api/envio-inspecao-montagem/", {
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
        buscarItensInspecao(1);
        buscarItensReinspecao(1);
        buscarItensInspecionados(1);
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
        buttonInspecionarMontagem.disabled = false;
        buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "none";
    });
});