function enviarDadosInspecao() {
    if (!validarFormulario()) {
        return; // Não enviar se a validação falhar
    }

    const buttonSalvarInspecao = document.getElementById('saveInspection');
    buttonSalvarInspecao.disabled = true;
    buttonSalvarInspecao.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>';

    const formData = new FormData();

    // 1. Coletar informações básicas
    formData.append('id-inspecao', document.getElementById('id-inspecao').value);
    formData.append('dataInspecao', document.getElementById('dataInspecao').value);
    formData.append('pecasProduzidas', document.getElementById('pecasProduzidas').value);
    formData.append('inspetor', document.getElementById('inspetor').value);
    formData.append('numPecaDefeituosa', document.getElementById('numPecaDefeituosa').value);
    formData.append('inspecao_total', document.getElementById('inspecao_total').value);

    // 2. Coletar quais inspeções estão ativas
    const inspecoesAtivas = [];
    document.querySelectorAll('.inspection-checkbox:checked').forEach(checkbox => {
        const tipo = checkbox.id.replace('checkbox-inspecao-', '');
        inspecoesAtivas.push(tipo);
    });
    formData.append('inspecoes_ativas', JSON.stringify(inspecoesAtivas));

    // 3. Coletar causas de peças mortas
    const causasPecaMorta = [];
    document.querySelectorAll('.causas-morta-container .causa-checkbox:checked').forEach(checkbox => {
        causasPecaMorta.push(checkbox.value);
    });
    formData.append('causasPecaMorta', JSON.stringify(causasPecaMorta));

    // 4. Coletar medidas técnicas apenas dos tipos ativos
    inspecoesAtivas.forEach(tipo => {
        const medidasTipo = [];
        const tipoCapitalizado = tipo.charAt(0).toUpperCase() + tipo.slice(1);

        // Coletar cabeçalhos das medidas
        const cabecalhos = [];
        document.querySelectorAll(`#sectionMedicao${tipoCapitalizado} .medida-input`).forEach((input, index) => {
            cabecalhos[index] = input.value.trim();
        });

        // Coletar linhas de medição (3 linhas padrão)
        for (let linha = 1; linha <= 3; linha++) {
            const medida = {};
            let algumCampoPreenchido = false;

            // Coletar os 4 valores de medida
            for (let coluna = 1; coluna <= 4; coluna++) {
                const nomeMedida = cabecalhos[coluna-1] || `Medida ${coluna}`;
                const valorInput = document.querySelector(`input[name="${tipo}_valor${linha}_${coluna}"]`);
                const valor = valorInput ? valorInput.value.trim() : '';

                if (nomeMedida && valor) {
                    medida[`medida${coluna}`] = { nome: nomeMedida, valor: valor };
                    algumCampoPreenchido = true;
                }
            }

            // Se a linha tem dados, adicionar conformidade
            if (algumCampoPreenchido) {
                const conformeCheckbox = document.querySelector(`input[name="${tipo}_conformity${linha}"][value="conforming"]`);
                const conforme = conformeCheckbox ? conformeCheckbox.checked : false;
                medida['conforme'] = conforme;
                medidasTipo.push(medida);
            }
        }

        // Adicionar ao formData apenas se houver medidas
        if (medidasTipo.length > 0) {
            formData.append(`medidas_${tipo}`, JSON.stringify(medidasTipo));
        }
    });

    // 5. Coletar não conformidades (relacionadas aos tipos ativos)
    const naoConformidades = [];
    document.querySelectorAll('.non-conformity-item').forEach(item => {
        const id = item.id.replace('nonConformityItem', '');
        const causas = [];
        
        // Coletar causas selecionadas
        document.querySelectorAll(`#causasContainer${id} .causa-checkbox:checked`).forEach(checkbox => {
            causas.push(checkbox.value);
        });

        const naoConformidade = {
            tipo: document.querySelector(`select[name="tipo_nao_conformidade${id}"]`)?.value || '',
            quantidadeAfetada: document.getElementById(`quantidadeAfetada${id}`).value,
            destino: document.getElementById(`destino${id}`).value,
            causas: causas
        };

        // Coletar fotos
        const fotoInput = document.getElementById(`fotoNaoConformidade${id}`);
        if (fotoInput && fotoInput.files.length > 0) {
            for (let i = 0; i < fotoInput.files.length; i++) {
                formData.append(`fotos_nao_conformidade[${id}][${i}]`, fotoInput.files[i]);
            }
        }

        naoConformidades.push(naoConformidade);
    });
    formData.append('naoConformidades', JSON.stringify(naoConformidades));

    // 6. Enviar para o backend
    fetch('/inspecao/api/envio-inspecao-serra-usinagem/', {
        method: 'POST',
        headers: {
            "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: formData
    })
    .then(response => response.json().then(data => {
        if (!response.ok) throw new Error(data.error || `Erro HTTP! Status: ${response.status}`);
        return data;
    }))
    .then(data => {
        Toast.fire({
            icon: "success",
            title: "Inspeção gravada com sucesso!"
        });
        
        // Atualizar listagens
        buscarItensInspecao(1);
        buscarItensReinspecao(1);
        buscarItensInspecionados(1);
        
        // Fechar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('inspectionModal'));
        modal.hide();
    })
    .catch(error => {
        Toast.fire({
            icon: "error",
            title: error.message
        });
        console.error('Erro:', error);
    })
    .finally(() => {
        buttonSalvarInspecao.disabled = false;
        buttonSalvarInspecao.innerHTML = 'Salvar';
    });
}
// salvar inspeçao
document.getElementById('saveInspection').addEventListener('click', enviarDadosInspecao);