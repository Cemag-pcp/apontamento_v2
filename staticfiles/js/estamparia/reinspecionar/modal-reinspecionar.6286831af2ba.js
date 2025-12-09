document.addEventListener("DOMContentLoaded", async function () {
    const pecasProduzidasInput = document.getElementById("pecasProduzidasReinspecao");
    const qtdConformidadeInput = document.getElementById("qtdConformidadeReinspecao");
    const qtdNaoConformidadeInput = document.getElementById("qtdNaoConformidadeReinspecao");
    const nonConformitySection = document.getElementById("nonConformitySectionReinspecao");
    const causasContainer = document.getElementById("causasContainerReinspecao");

    // Desabilita o campo de não conformidades
    qtdNaoConformidadeInput.disabled = true;

    // Atualiza quantidade de não conformidades e mostra/oculta seção
    function updateNaoConformidades() {
        const produzidas = parseInt(pecasProduzidasInput.value) || 0;
        const conformes = parseInt(qtdConformidadeInput.value) || 0;
        const naoConformes = Math.max(produzidas - conformes, 0);

        qtdNaoConformidadeInput.value = naoConformes;

        nonConformitySection.style.display = naoConformes > 0 ? "block" : "none";
    }

    qtdConformidadeInput.addEventListener("input", updateNaoConformidades);
    updateNaoConformidades();

    // Busca os motivos/causas e preenche o container
    async function buscarMotivosCausasReinspecao() {
        try {
            const response = await fetch('/inspecao/api/motivos-causas/estamparia', {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            console.log(data)
            // Adiciona os checkboxes ao container
            data.motivos.forEach((causa, index) => {
                const checkbox = document.createElement('div');
                checkbox.classList.add("form-check", "mb-1");
                checkbox.innerHTML = `
                    <input class="form-check-input" type="checkbox" value="${causa.id}" name="causasReinspecao[]">
                    <label class="form-check-label">
                        ${causa.nome}
                    </label>
                `;
                causasContainer.appendChild(checkbox);
            });

        } catch (error) {
            console.error("Erro ao buscar motivos/causas:", error);
        }
    }

    // Chama a função ao carregar
    await buscarMotivosCausasReinspecao();
});

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-reinspecao')) {
            document.getElementById('reinspectionForm').reset()
            document.getElementById("nonConformitySectionReinspecao").style.display = "none";

            const btn = event.target;
            const containerImagem = document.getElementById('imagePreviewReinspection');
            containerImagem.innerHTML = "";

            const itemId = btn.getAttribute('data-id');
            const itemData = btn.getAttribute('data-data');
            const itemQtd = btn.getAttribute('data-conformidade');
            const itemPeca = btn.getAttribute('data-peca');
            const itemMaquina = btn.getAttribute('data-maquina');
            const itemPecasBoas = btn.getAttribute('data-qtd-total');
            
            const modalInspecao = document.getElementById('reinspectionModal');
            
            // Pegar a data atual formatada
            const currentDate = new Date();
            const formattedDate = currentDate.toISOString().split('T')[0];
            
            modalInspecao.querySelector('#dataReinspecao').value = formattedDate;
            modalInspecao.querySelector('#conjuntoNameReinspecao').value = itemPeca;
            modalInspecao.querySelector('#maquinaReinspecao').value = itemMaquina;
            modalInspecao.querySelector('#pecasProduzidasReinspecao').value = itemPecasBoas;
            modalInspecao.querySelector('#id-reinspecao').value = itemId;

            // Desabilitar campos para edição
            modalInspecao.querySelector('#maquinaReinspecao').disabled = true;
            modalInspecao.querySelector('#pecasProduzidasReinspecao').disabled = true;
            modalInspecao.querySelector('#dataReinspecao').disabled = true;
            modalInspecao.querySelector('#conjuntoNameReinspecao').disabled = true;
            modalInspecao.querySelector('#qtdNaoConformidadeReinspecao').disabled = true;

            // Mostrar o modal
            new bootstrap.Modal(modalInspecao).show();
        }
    })
})

function addNonConformityItemReinspecao() {
    const originalContainer = document.querySelector('.containerNonConformityItemsReinspecao');
    const clonedContainer = originalContainer.cloneNode(true);

    // Gera um ID único baseado em timestamp
    const uniqueId = `fotoNaoConformidade_${Date.now()}`;

    // Atualiza o input de imagem
    const fileInput = clonedContainer.querySelector('input[type="file"]');
    fileInput.id = uniqueId;
    fileInput.value = ""; // limpa arquivos anteriores

    // Atualiza o label para apontar para o novo input
    const fileLabel = clonedContainer.querySelector('label.custom-file-upload');
    fileLabel.setAttribute('for', uniqueId);

    // Atualiza o label de cima também se quiser
    const labelText = clonedContainer.querySelector('label.form-label[for="fotoNaoConformidade"]');
    if (labelText) labelText.setAttribute('for', uniqueId);

    // Limpa a imagem anterior
    const imagePreview = clonedContainer.querySelector('.image-preview');
    imagePreview.innerHTML = '';

    // Reseta campos
    clonedContainer.querySelector('input[type="number"]').value = '';
    clonedContainer.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.checked = false;
    });

    // Evento do input
    fileInput.addEventListener('change', function(e) {
        handleImageUpload(e, imagePreview);
    });

    // Remove
    clonedContainer.querySelector('.btn-remove-nonconformity').addEventListener('click', function () {
        clonedContainer.remove();
    });

    originalContainer.parentNode.insertBefore(clonedContainer, originalContainer.nextSibling);
}


function handleImageUpload(event, previewContainer) {
    previewContainer.innerHTML = '';
    
    Array.from(event.target.files).forEach(file => {
        if (file.type.match('image.*')) {
            const reader = new FileReader();
            
            reader.onload = function(e) {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.style.maxWidth = '100px';
                img.style.maxHeight = '100px';
                img.classList.add('img-thumbnail');
                previewContainer.appendChild(img);
            };
            
            reader.readAsDataURL(file);
        }
    });
}

// Configuração inicial
document.addEventListener('DOMContentLoaded', function() {
    // Configura o container original
    const originalContainer = document.querySelector('.containerNonConformityItemsReinspecao');
    const originalFileInput = originalContainer.querySelector('.foto-nao-conformidade');
    const originalImagePreview = originalContainer.querySelector('.image-preview');
    
    originalFileInput.addEventListener('change', function(e) {
        handleImageUpload(e, originalImagePreview);
    });

    // Impede remoção do container original
    originalContainer.querySelector('.btn-remove-nonconformity').addEventListener('click', function(e) {
        e.preventDefault();
        Toast.fire({
            icon: "error",
            title: "Você não pode remover o container original de não conformidade."
        });
    });

    document.querySelectorAll('.containerNonConformityItemsReinspecao').forEach(container => {
        const label = container.querySelector('.trigger-file-upload');
        const fileInput = container.querySelector('.foto-nao-conformidade');

        label.addEventListener('click', function () {
            fileInput.click();
        });
    });
});