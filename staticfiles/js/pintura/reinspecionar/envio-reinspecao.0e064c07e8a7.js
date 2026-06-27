document.getElementById("form-reinspecao").addEventListener("submit", function (event) {
    event.preventDefault();

    let modal = document.getElementById('modal-reinspecionar-pintura');
    let modalInstance = bootstrap.Modal.getInstance(modal);
    let buttonInspecionarPintura = document.getElementById("submit-reinspecionar-pintura");
    buttonInspecionarPintura.disabled = true;
    buttonInspecionarPintura.querySelector(".spinner-border").style.display = "flex";

    const formData = new FormData(this);
    const naoConformidade = document.getElementById("nao-conformidade-reinspecao-pintura").value;
    const naoConformidadeNum = parseFloat(naoConformidade);

    formData.append('nao-conformidade-reinspecao-pintura', naoConformidade)

    // Limpamos campos que podem ter sido adicionados por engano
    formData.delete("quantidade-total-causas");

    // Lógica condicional para adicionar os dados corretos
    if (naoConformidadeNum > 0) {
        // --- LÓGICA PARA NÃO CONFORMIDADE ---
        let totalQuantidadeInput = 0;
        const selectContainerInspecao = document.querySelectorAll(".selectContainerReinspecao");
        
        selectContainerInspecao.forEach((container, index) => {
            const causaSelect = container.querySelector('select');
            const quantidadeInput = container.querySelector('input[type="number"]');
            const imagensInput = container.querySelector('input[type="file"]');
            
            if (quantidadeInput.value) {
                totalQuantidadeInput += parseFloat(quantidadeInput.value);
            }

            // Adicionar causas com '[]' no final do nome
            Array.from(causaSelect.selectedOptions).forEach(option => {
                formData.append(`causas_reinspecao_${index + 1}[]`, option.value);
            });

            // Adicionar quantidade
            formData.append(`quantidade_reinspecao_${index + 1}`, quantidadeInput.value);

            // Adicionar imagens com '[]' no final do nome
            Array.from(imagensInput.files).forEach(file => {
                formData.append(`imagens_reinspecao_${index + 1}[]`, file);
            });
        });

        // Validação da quantidade
        if (totalQuantidadeInput !== naoConformidadeNum) {
            Swal.fire({
                icon: 'error',
                title: 'A soma das quantidades não bate com o total de "Não Conformidades"!',
            });
            buttonInspecionarPintura.disabled = false;
            buttonInspecionarPintura.querySelector(".spinner-border").style.display = "none";
            return;
        }

        formData.append("quantidade-total-causas", selectContainerInspecao.length);

    } else {
        // --- LÓGICA PARA CONFORMIDADE ---
        const imagensConformidadeInput = document.querySelector('input[name="imagens_conformidade"]');
        
        // Adiciona os arquivos de conformidade ao FormData
        Array.from(imagensConformidadeInput.files).forEach(file => {
            formData.append('imagens_conformidade', file);
        });
    }

    if (naoConformidadeNum < 0) {
        Swal.fire({
            icon: 'error',
            title: 'O N° de conformidades não pode ser maior que o total a ser inspecionado.',
        });
        buttonInspecionarPintura.disabled = false;
        buttonInspecionarPintura.querySelector(".spinner-border").style.display = "none";
        return;
    }
    
    // O fetch continua o mesmo
    fetch("/inspecao/api/envio-reinspecao-pintura/", {
        method: "POST",
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData,
    })
    .then(response => {
        return response.json().then(data => {
            if (!response.ok) {
                throw new Error(data.error || `Erro HTTP. Status: ${response.status}`);
            }
            return data;
        });
    })
    .then(data => {
        if (modalInstance) {
            modalInstance.hide();
        }
        Swal.fire({
            toast: true,
            position: "bottom-end",
            icon: "success",
            title: "Reinspeção realizada com sucesso!",
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true
        });
        buscarItensInspecao(1);
        buscarItensReinspecao(1);
        buscarItensInspecionados(1);
        verificarPendenciasInspecao();
    })
    .catch(error => {
        console.error(error);
        Swal.fire({
            icon: 'error',
            title: 'Erro no envio da reinspeção',
            text: error.message,
        });
    })
    .finally(() => {
        buttonInspecionarPintura.disabled = false;
        buttonInspecionarPintura.querySelector(".spinner-border").style.display = "none";
    });
});