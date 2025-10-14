document.getElementById('saveReinspection').addEventListener('click', function () {
    const form = document.getElementById('reinspectionForm');
    const formData = new FormData();
    const reinspectionModal = document.getElementById('reinspectionModal');

    this.disabled = true; // Desabilitar o botão para evitar múltiplos cliques
    this.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>';

    const quantidadeConformidade = document.getElementById('qtdConformidadeReinspecao').value;
    const qtdNaoConformidadeReinspecao = document.getElementById('qtdNaoConformidadeReinspecao').value;
    const pecasProduzidas = document.getElementById('pecasProduzidasReinspecao').value;
    const inspetor = document.getElementById('inspetorReinspecao').value;
    const fichaReinspection = document.getElementById('fichaReinspection').files[0]; // Adicionado para verificar o arquivo

    if (!inspetor) {
        Toast.fire({
            icon: "error",
            title: "Por favor, informe o nome do inspetor."
        });
        this.disabled = false; // Reabilitar o botão
        this.innerHTML = 'Salvar';
        return
    }

    // Validação da ficha de inspeção (campo obrigatório)
    // if (!fichaReinspection) {
    //     Toast.fire({
    //         icon: "error",
    //         title: "Por favor, anexe a ficha de inspeção 100%."
    //     });
    //     this.disabled = false;
    //     this.innerHTML = 'Salvar';
    //     return;
    // }

    if(parseInt(quantidadeConformidade) > parseInt(pecasProduzidas)) {
        Toast.fire({
            icon: "error",
            title: "Quantidade de conformidde não pode ser maior que a quantidade de peças produzidas"
        });
        this.disabled = false; // Reabilitar o botão
        this.innerHTML = 'Salvar';
        return
    }

    if(parseInt(qtdNaoConformidadeReinspecao) !== 0) {

        const conformidadeMarcada = document.querySelectorAll('[name^="causasReinspecao[]"]:checked').length;
        
        if (conformidadeMarcada === 0) {
            Toast.fire({
                icon: "error",
                title: `Por favor, marque pelo menos uma opção de conformidade (Conforme ou Não Conforme).`
            });
            this.disabled = false; // Reabilitar o botão
            this.innerHTML = 'Salvar';
            return;
        }

        let somaQuantidadeAfetada = 0;
        const inputsQuantidadeAfetada = document.querySelectorAll('.quantidadeAfetada');
        inputsQuantidadeAfetada.forEach(input => {
            somaQuantidadeAfetada += Number(input.value) || 0;
        });

        if (parseInt(somaQuantidadeAfetada) !== parseInt(qtdNaoConformidadeReinspecao)) {
            Toast.fire({
                icon: "error",
                title: `A soma das quantidades afetadas (${somaQuantidadeAfetada}) deve ser igual à quantidade de não conformidades (${qtdNaoConformidadeReinspecao}).`
            });
            this.disabled = false; // Reabilitar o botão
            this.innerHTML = 'Salvar';
            return;
        }

        // Detalhes das não conformidades (clonados)
        const nonConformities = document.querySelectorAll('.containerNonConformityItemsReinspecao');

        for (let container of nonConformities) {
            const checkboxesMarcados = container.querySelectorAll('input[name="causasReinspecao[]"]:checked');
            if (checkboxesMarcados.length === 0) {
                Toast.fire({
                    icon: "error",
                    title: "Por favor, selecione pelo menos uma causa para cada não conformidade."
                });
                this.disabled = false; // Reabilitar o botão
                this.innerHTML = 'Salvar';
                return;
            }
        }

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
    }

    // Dados básicos
    formData.append('idInspecao', document.getElementById('id-reinspecao').value);
    formData.append('dataReinspecao', document.getElementById('dataReinspecao').value);
    formData.append('conjuntoNameReinspecao', document.getElementById('conjuntoNameReinspecao').value);
    formData.append('maquinaReinspecao', document.getElementById('maquinaReinspecao').value);
    formData.append('pecasProduzidasReinspecao', pecasProduzidas);
    formData.append('inspetorReinspecao', inspetor);

    // Medições Técnicas
    formData.append('qtdConformidadeReinspecao', quantidadeConformidade);
    formData.append('qtdNaoConformidadeReinspecao', document.getElementById('qtdNaoConformidadeReinspecao').value);

    const imagem = document.getElementById('fichaReinspection').files[0];
    if (imagem) {
        formData.append('ficha_reinspecao', imagem);
    }

    // Enviar com Fetch
    fetch('/inspecao/api/envio-reinspecao-serra-usinagem/', {
        method: 'POST',
        headers: {
            'X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData
    })
    .then(response => {
        if (response.ok) {
            Toast.fire({
                icon: "success",
                title: "Formulário enviado com sucesso!"
            });
            const bootstrapModal = bootstrap.Modal.getInstance(reinspectionModal);
            bootstrapModal.hide();

            buscarItensInspecao(1);
            buscarItensReinspecao(1);
            buscarItensInspecionados(1);
        } else {
            Toast.fire({
                icon: "error",
                title: "Erro ao enviar formulário."
            });
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        Toast.fire({
            icon: "error",
            title: "Erro ao enviar o formulário!"
        });
    }).finally(d => {
        this.disabled = false; // Reabilitar o botão
        this.innerHTML = 'Salvar';
    });
});