document.getElementById("form-inspecao").addEventListener("submit", async function (event) {
    event.preventDefault();

    const modal = document.getElementById('modal-inspecionar-pintura');
    const modalInstance = bootstrap.Modal.getInstance(modal);
    let buttonInspecionarPintura = document.getElementById("submit-inspecionar-pintura");
    buttonInspecionarPintura.disabled = true;
    buttonInspecionarPintura.querySelector(".spinner-border").style.display = "flex";

    // Criar FormData e adicionar dados básicos
    const formData = new FormData(this);
    const naoConformidade = document.getElementById("nao-conformidade-inspecao-pintura").value;
    formData.append("nao-conformidade-inspecao-pintura", naoConformidade);

    let totalQuantidadeInput = 0;
    const selectContainerInspecao = document.querySelectorAll(".selectContainerInspecao");

    // Processar causas, quantidades e imagens
    for (const container of selectContainerInspecao) {
        const index = Array.from(selectContainerInspecao).indexOf(container) + 1;
        const causaSelect = container.querySelector('select');
        const quantidadeInput = container.querySelector('input[type="number"]');
        const imagensInput = container.querySelector('input[type="file"]');
        
        totalQuantidadeInput += parseFloat(quantidadeInput.value);

        // Adicionar causas selecionadas
        Array.from(causaSelect.selectedOptions).forEach((option, i) => {
            formData.append(`causas_${index}[${i}]`, option.value);
        });

        // Adicionar quantidade
        formData.append(`quantidade_${index}`, quantidadeInput.value);

        // Processar imagens (com compressão)
        const imageFiles = Array.from(imagensInput.files);
        for (let i = 0; i < imageFiles.length; i++) {
            try {
                let compressedFile = await compressImage(imageFiles[i]);
                
                // Verifica se ainda está grande (>2MB) e recompressa se necessário
                if (compressedFile.size > 2 * 1024 * 1024) {
                    compressedFile = await compressImage(imageFiles[i], 800, 800, 0.5);
                    console.warn(`Imagem ${imageFiles[i].name} comprimida novamente para ${Math.round(compressedFile.size / 1024)}KB`);
                }
                
                formData.append(`imagens_${index}[${i}]`, compressedFile, `img_${Date.now()}_${i}.jpg`);
            } catch (error) {
                console.error("Erro ao comprimir imagem:", error);
                // Fallback: envia a imagem original se a compressão falhar
                formData.append(`imagens_${index}[${i}]`, imageFiles[i]);
            }
        }
    }

    // Validação de não conformidade
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
            buttonInspecionarPintura.disabled = false;
            buttonInspecionarPintura.querySelector(".spinner-border").style.display = "none";
            return;
        }
    }

    formData.append("quantidade-total-causas", selectContainerInspecao.length);

    // Envio para o backend
    fetch("/inspecao/api/envio-inspecao-pintura/", {
        method: "POST",
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData,
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || "Erro no servidor"); });
        }
        return response.json();
    })
    .then(data => {
        if (modalInstance) modalInstance.hide();
        Swal.fire({
            toast: true,
            position: "bottom-end",
            icon: "success",
            title: "Inspeção realizada com sucesso",
            showConfirmButton: false,
            timer: 3000
        });
        // Atualiza listagens (supondo que essas funções existam)
        buscarItensInspecao(1);
        buscarItensReinspecao(1);
        buscarItensInspecionados(1);
    })
    .catch(error => {
        console.error("Erro completo:", error);
        Swal.fire({
            icon: 'error',
            title: 'Erro no envio',
            text: error.message || "Erro desconhecido",
        });
    })
    .finally(() => {
        buttonInspecionarPintura.disabled = false;
        buttonInspecionarPintura.querySelector(".spinner-border").style.display = "none";
    });
});

/**
 * Função de compressão de imagens (adicione ao seu código)
 */
async function compressImage(file, maxWidth = 1024, maxHeight = 1024, quality = 0.7) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;

                // Redimensionamento proporcional
                if (width > maxWidth || height > maxHeight) {
                    const ratio = Math.min(maxWidth / width, maxHeight / height);
                    width = Math.floor(width * ratio);
                    height = Math.floor(height * ratio);
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                // Conversão para JPEG (ou PNG se tiver transparência)
                const mimeType = file.type.includes('png') ? 'image/png' : 'image/jpeg';
                canvas.toBlob(
                    (blob) => {
                        if (!blob) reject(new Error("Falha na geração do blob"));
                        resolve(new File([blob], file.name, { type: mimeType }));
                    },
                    mimeType,
                    quality
                );
            };
            img.onerror = () => reject(new Error("Falha ao carregar imagem"));
            img.src = event.target.result;
        };
        reader.onerror = () => reject(new Error("Falha ao ler arquivo"));
        reader.readAsDataURL(file);
    });
}