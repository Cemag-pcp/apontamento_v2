// Toda nao conformidade da pintura exige foto: cada bloco de causa precisa
// de ao menos uma imagem. Usada na inspecao e na reinspecao
// (envio-reinspecao.js). Marca os campos sem foto e devolve a lista
// "Nª causa (nomes)" pra mensagem de erro.
function validarImagensNaoConformidadePintura(containers) {
    const pendencias = [];
    let primeiroCampo = null;

    containers.forEach((container, index) => {
        const input = container.querySelector('input[type="file"]');
        if (input.files.length > 0) {
            input.classList.remove("is-invalid");
            return;
        }
        input.classList.add("is-invalid");
        const nomes = Array.from(container.querySelector("select").selectedOptions).map((o) => o.text.trim());
        pendencias.push(`${index + 1}ª causa${nomes.length ? ` (${nomes.join(", ")})` : ""}`);
        if (!primeiroCampo) primeiroCampo = input;
    });

    if (primeiroCampo) primeiroCampo.scrollIntoView({ behavior: "smooth", block: "center" });
    return pendencias;
}

// Ao escolher a foto, tira o destaque de erro do campo
document.addEventListener("change", (event) => {
    const input = event.target;
    if (input.type === "file" && input.classList.contains("is-invalid") && input.files.length > 0) {
        input.classList.remove("is-invalid");
    }
});

// Foto comprimida (>2MB comprime de novo); se falhar, vai a original
async function comprimirImagemPintura(file, indice) {
    try {
        let comprimida = await compressImage(file);
        if (comprimida.size > 2 * 1024 * 1024) {
            comprimida = await compressImage(file, 800, 800, 0.5);
        }
        return new File([comprimida], `img_${Date.now()}_${indice}.jpg`, { type: comprimida.type });
    } catch (error) {
        console.error("Erro ao comprimir imagem:", error);
        return file;
    }
}

// Envio do checklist OK / Ñ OK (modal-inspecionar.js), no formato que o
// backend ja recebe: um bloco por causa (causas_N, quantidade_N, imagens_N)
document.getElementById("form-inspecao").addEventListener("submit", async function (event) {
    event.preventDefault();

    const modal = document.getElementById('modal-inspecionar-pintura');
    const modalInstance = bootstrap.Modal.getInstance(modal);
    let buttonInspecionarPintura = document.getElementById("submit-inspecionar-pintura");
    buttonInspecionarPintura.disabled = true;
    buttonInspecionarPintura.querySelector(".spinner-border").style.display = "flex";

    function cancelarEnvio(mensagem, html) {
        Swal.fire({ icon: 'error', title: mensagem, html });
        buttonInspecionarPintura.disabled = false;
        buttonInspecionarPintura.querySelector(".spinner-border").style.display = "none";
    }

    const formData = new FormData(this);

    const qtdProduzida = document.getElementById("qtd-produzida-pintura").value;
    const qtdInspecionada = document.getElementById("qtd-inspecao-pintura").value;

    if (qtdInspecionada === "" || parseInt(qtdInspecionada, 10) < 1) {
        cancelarEnvio('Informe a quantidade inspecionada (mínimo 1).');
        return;
    }
    if (parseFloat(qtdInspecionada) > parseFloat(qtdProduzida)) {
        cancelarEnvio('Quantidade Inspecionada não pode ser maior que a quantidade Produzida');
        return;
    }

    const containerChecklist = document.getElementById("unidades-checklist-pintura");
    const cardsUnidades = containerChecklist.querySelectorAll(".unidade-checklist-card");
    const totalCausas = totalItensChecklistPintura();

    if (cardsUnidades.length !== parseInt(qtdInspecionada, 10)) {
        cancelarEnvio('Erro ao montar o checklist das unidades. Reabra o modal e tente novamente.');
        return;
    }

    const existeUnidadeIncompleta = Array.from(cardsUnidades).some((card) => {
        const respondidos = card.querySelectorAll('.causa-status-ok:checked, .causa-status-nok:checked').length;
        return respondidos < totalCausas;
    });
    if (existeUnidadeIncompleta) {
        cancelarEnvio('Complete o checklist de todas as unidades inspecionadas antes de enviar.');
        return;
    }

    const outrosSemCausa = validarOutrosChecklistPintura(containerChecklist);
    if (outrosSemCausa.length > 0) {
        cancelarEnvio('Escolha a causa em "Outros"', 'Selecione ao menos uma causa em:<br>' + outrosSemCausa.join('<br>'));
        return;
    }

    const semFoto = validarImagensChecklistPintura(containerChecklist);
    if (semFoto.length > 0) {
        cancelarEnvio('Foto obrigatória na não conformidade', 'Anexe ao menos uma foto em:<br>' + semFoto.join('<br>'));
        return;
    }

    // Cada causa fixa marcada como "Ñ OK" vira um bloco (soma as unidades e
    // junta as fotos). "Outros" vira um bloco com as causas escolhidas,
    // somando as unidades que escolheram a mesma combinação.
    const causasAgregadas = new Map();
    containerChecklist.querySelectorAll(".causa-status-nok:checked").forEach((radio) => {
        const item = radio.closest(".checklist-causa-item");
        const causasIds = item.dataset.outros
            ? Array.from(item.querySelectorAll(".outros-causa-check:checked")).map((c) => c.value).sort()
            : [radio.getAttribute("data-causa-id")];
        const chave = causasIds.join(",");
        if (!causasAgregadas.has(chave)) {
            causasAgregadas.set(chave, { causasIds, quantidade: 0, imagens: [], fotosRascunho: [] });
        }
        const entrada = causasAgregadas.get(chave);
        entrada.quantidade += 1;
        entrada.imagens.push(...Array.from(item.querySelector(".causa-imagens").files));
        // fotos já salvas no "Salvar parcial" (o servidor reaproveita o arquivo)
        entrada.fotosRascunho.push(...fotosSalvasDoItemPintura(item).map((foto) => foto.id));
    });

    let totalBlocos = 0;
    for (const entrada of causasAgregadas.values()) {
        totalBlocos += 1;
        entrada.causasIds.forEach((causaId) => formData.append(`causas_${totalBlocos}`, causaId));
        entrada.fotosRascunho.forEach((id) => formData.append(`fotos_rascunho_${totalBlocos}`, id));
        formData.append(`quantidade_${totalBlocos}`, entrada.quantidade);
        for (let i = 0; i < entrada.imagens.length; i++) {
            formData.append(`imagens_${totalBlocos}`, await comprimirImagemPintura(entrada.imagens[i], i));
        }
    }

    formData.append("quantidade-total-causas", totalBlocos);
    // Conformes / não conformes são calculados pelo checklist (campos
    // desabilitados não entram sozinhos no FormData)
    formData.append("conformidade-inspecao-pintura", document.getElementById("conformidade-inspecao-pintura").value);
    formData.append("nao-conformidade-inspecao-pintura", document.getElementById("nao-conformidade-inspecao-pintura").value);

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
        // o servidor apagou o rascunho junto com o envio
        RASCUNHO_PINTURA.fotos = [];
        RASCUNHO_PINTURA.removidas = new Set();
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
        verificarPendenciasInspecao();
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