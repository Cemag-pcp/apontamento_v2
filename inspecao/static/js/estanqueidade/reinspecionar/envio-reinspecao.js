document.getElementById("form-reinspecao").addEventListener("submit", function (event) {
    event.preventDefault();

    let modal = document.getElementById('modal-reinspecionar-tubos-cilindros');
    let modalInstance = bootstrap.Modal.getInstance(modal); // Obter a instância existente
    let buttonInspecionarTubosCilindros = document.getElementById("submit-reinspecionar-tubos-cilindros");
    buttonInspecionarTubosCilindros.disabled = true;
    buttonInspecionarTubosCilindros.querySelector(".spinner-border").style.display = "flex";

    // Criar um objeto FormData para enviar os arquivos
    const formData = new FormData(this); // Usar o formulário diretamente

    // Adicionar os dados básicos ao FormData
    const naoConformidade = document.getElementById("nao-conformidade-reinspecao-tubos-cilindros").value;
    formData.append("nao-conformidade-reinspecao-tubos-cilindros", naoConformidade);

    // Adicionar causas, quantidades e imagens ao FormData
    const selectContainerInspecao = document.querySelectorAll(".selectContainerReinspecao");
    selectContainerInspecao.forEach((container, index) => {
        const causaSelect = container.querySelector('select');
        const quantidadeInput = container.querySelector('input[type="number"]');
        const imagensInput = container.querySelector('input[type="file"]');

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

    formData.append("quantidade-total-causas", selectContainerInspecao.length)

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
        buttonInspecionarTubosCilindros.disabled = false;
        buttonInspecionarTubosCilindros.querySelector(".spinner-border").style.display = "none";
    });
});