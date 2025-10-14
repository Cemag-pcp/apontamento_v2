document.getElementById("form-inspecao").addEventListener("submit", function (event) {
    event.preventDefault();

    const modal = document.getElementById('modal-inspecionar-solda-tanque');
    const modalInstance = bootstrap.Modal.getInstance(modal);
    let buttonInspecionarSoldaTanque = document.getElementById("submit-inspecionar-solda-tanque");
    buttonInspecionarSoldaTanque.disabled = true;
    buttonInspecionarSoldaTanque.querySelector(".spinner-border").style.display = "flex";

    // Criar um objeto FormData para enviar os arquivos
    const formData = new FormData(this);

    // Adicionar os dados básicos ao FormData
    const naoConformidade = document.getElementById("nao-conformidade-inspecao-solda-tanque").value;
    const qtdProduzida = document.getElementById("qtd-produzida-solda-tanque").value;
    formData.append("nao-conformidade-inspecao-solda-tanque", naoConformidade);

    let totalQuantidadeInput = 0;
    // Adicionar causas, quantidades e imagens ao FormData
    const selectContainerInspecao = document.querySelectorAll(".selectContainerInspecao");
    selectContainerInspecao.forEach((container, index) => {
        const causaSelect = container.querySelector('select');
        const quantidadeInput = container.querySelector('input[type="number"]');
        const imagensInput = container.querySelector('input[type="file"]');
        totalQuantidadeInput += parseFloat(quantidadeInput.value || 0);

        // Adicionar causas
        Array.from(causaSelect.selectedOptions).forEach((option, i) => {
            formData.append(`causas_${index + 1}[${i}]`, option.value);
        });

        // Adicionar quantidade
        formData.append(`quantidade_${index + 1}`, quantidadeInput.value);

        // Adicionar arquivos de imagem
        Array.from(imagensInput.files).forEach((file, i) => {
            formData.append(`imagens_${index + 1}[${i}]`, file);
        });
    });

    const naoConformidadeNum = parseFloat(naoConformidade);

    // Validação: soma das quantidades de causas deve ser igual às não conformidades
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
    
            buttonInspecionarSoldaTanque.disabled = false;
            buttonInspecionarSoldaTanque.querySelector(".spinner-border").style.display = "none";
            return;
        }
    }

    formData.append("quantidade-total-causas", selectContainerInspecao.length);

    for (let [key, value] of formData.entries()) {
        console.log(key, value);
    }

    // Enviar os dados para o endpoint de solda e tanque
    fetch("/inspecao/api/envio-inspecao-solda-tanque/", {
        method: "POST",
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData,
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
            title: "Inspeção de solda/tanque realizada com sucesso"
          });
        
        buscarItensInspecionadosEstanqueidadeTanque(1);
    })
    .catch(error => {
        console.error(error);
        Swal.fire({
            icon: 'error',
            title: 'Erro no envio da inspeção de solda/tanque',
            text: error.message,
        });
    })
    .finally(() => {
        buttonInspecionarSoldaTanque.disabled = false;
        buttonInspecionarSoldaTanque.querySelector(".spinner-border").style.display = "none";
    });
});