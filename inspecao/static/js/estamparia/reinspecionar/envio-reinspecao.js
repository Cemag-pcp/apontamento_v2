document.getElementById('saveReinspection').addEventListener('click', function () {
    const form = document.getElementById('reinspectionForm');
    const formData = new FormData();

    // Dados básicos
    formData.append('idInspecao', document.getElementById('id-reinspecao').value);
    formData.append('dataReinspecao', document.getElementById('dataReinspecao').value);
    formData.append('conjuntoNameReinspecao', document.getElementById('conjuntoNameReinspecao').value);
    formData.append('maquinaReinspecao', document.getElementById('maquinaReinspecao').value);
    formData.append('pecasProduzidasReinspecao', document.getElementById('pecasProduzidasReinspecao').value);
    formData.append('inspetorReinspecao', document.getElementById('inspetorReinspecao').value);

    // Medições Técnicas
    formData.append('qtdConformidadeReinspecao', document.getElementById('qtdConformidadeReinspecao').value);
    formData.append('qtdNaoConformidadeReinspecao', document.getElementById('qtdNaoConformidadeReinspecao').value);

    // Detalhes das não conformidades (clonados)
    const nonConformities = document.querySelectorAll('.containerNonConformityItemsReinspecao');
    nonConformities.forEach((container, index) => {
        // Quantidade afetada
        const quantidadeAfetada = container.querySelector('.quantidadeAfetada')?.value || 0;
        formData.append(`quantidade_reinspecao_${index + 1}`, quantidadeAfetada);

        // Causas selecionadas (checkboxes)
        const causasSelecionadas = container.querySelectorAll('input[type="checkbox"]:checked');
        causasSelecionadas.forEach((checkbox, cIndex) => {
            formData.append(`causas_reinspecao_${index + 1}`, checkbox.value);
        });

        // Imagens
        const imagens = container.querySelector('.foto-nao-conformidade')?.files;
        if (imagens) {
            for (let i = 0; i < imagens.length; i++) {
                formData.append(`imagens_reinspecao_${index + 1}`, imagens[i]);
            }
        }
    });

    formData.append('quantidade_total_causas', nonConformities.length)

    // Enviar com Fetch
    fetch('/inspecao/api/envio-reinspecao-estamparia/', {
        method: 'POST',
        headers: {
            'X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData
    })
    .then(response => {
        if (response.ok) {
            alert("Formulário enviado com sucesso!");
            // Pode limpar ou fechar modal aqui
            buscarItensInspecao(1);
            buscarItensReinspecao(1);
            buscarItensInspecionados(1);
        } else {
            alert("Erro ao enviar formulário.");
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert("Erro ao enviar.");
    });
});