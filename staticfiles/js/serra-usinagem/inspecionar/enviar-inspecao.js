function enviarDadosInspecao() {
    if (!validarFormulario()) {
        return;
    }

    const buttonSalvarInspecao = document.getElementById('saveInspection');
    buttonSalvarInspecao.disabled = true;
    buttonSalvarInspecao.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>';

    const formData = new FormData();

    formData.append('inspecao_id', document.getElementById('id-inspecao').value);
    formData.append('dataInspecao', document.getElementById('dataInspecao').value);
    formData.append('pecasProduzidas', document.getElementById('pecasProduzidas').value);
    formData.append('inspetor', document.getElementById('inspetor').value);
    formData.append('inspecao_total', document.getElementById('inspecao_total').value);

    const inspecoesAtivas = [];
    document.querySelectorAll('.inspection-checkbox:checked').forEach(checkbox => {
        const tipo = checkbox.id.replace('checkbox-inspecao-', '');
        inspecoesAtivas.push(tipo);
    });
    formData.append('inspecoes_ativas', JSON.stringify(inspecoesAtivas));

    const causasPecaMorta = [];
    document.querySelectorAll('.causas-morta-container .causa-checkbox:checked').forEach(checkbox => {
        causasPecaMorta.push(checkbox.value);
    });
    formData.append('causasPecaMorta', JSON.stringify(causasPecaMorta));

    const qtdProduzida = parseInt(document.getElementById('pecasProduzidas').value, 10) || 1;
    const qtdLinhasSelecionadas = parseInt(document.getElementById('measurementRowsCount')?.value, 10) || 1;
    const qtdLinhas = Math.max(1, Math.min(qtdProduzida, qtdLinhasSelecionadas));

    inspecoesAtivas.forEach(tipo => {
        const medidasTipo = [];
        const tipoCapitalizado = tipo.charAt(0).toUpperCase() + tipo.slice(1);

        const cabecalhos = [];
        document.querySelectorAll(`#sectionMedicao${tipoCapitalizado} .medida-input`).forEach((input, index) => {
            cabecalhos[index] = input.value.trim();
        });

        for (let linha = 1; linha <= qtdLinhas; linha++) {
            const medida = {};
            let algumCampoPreenchido = false;

            for (let coluna = 1; coluna <= 8; coluna++) {
                const nomeMedida = cabecalhos[coluna - 1];
                const valorInput = document.querySelector(`input[name="${tipo}_valor${linha}_${coluna}"]`);
                const valor = valorInput ? valorInput.value.trim() : '';

                if (nomeMedida && valor) {
                    medida[`medida${coluna}`] = { nome: nomeMedida, valor: valor };
                    algumCampoPreenchido = true;
                }
            }

            if (algumCampoPreenchido) {
                const conformeCheckbox = document.querySelector(`input[name="${tipo}_conformity${linha}"][value="conforming"]`);
                const conforme = conformeCheckbox ? conformeCheckbox.checked : false;
                medida.conforme = conforme;
                medidasTipo.push(medida);
            }
        }

        if (medidasTipo.length > 0) {
            formData.append(`medidas_${tipo}`, JSON.stringify(medidasTipo));
        }
    });

    const naoConformidades = [];
    document.querySelectorAll('.non-conformity-item').forEach(item => {
        const id = item.id.replace('nonConformityItem', '');
        const causas = [];

        document.querySelectorAll(`#causasContainer${id} .causa-checkbox:checked`).forEach(checkbox => {
            causas.push(checkbox.value);
        });

        const tipo = document.querySelector(`select[name="tipo_nao_conformidade${id}"]`)?.value || '';
        const quantidadeAfetada = document.getElementById(`quantidadeAfetada${id}`).value;
        const destino = document.getElementById(`destino${id}`).value;

        if (tipo || quantidadeAfetada || destino || causas.length > 0) {
            const naoConformidade = {
                id: id,
                tipo: tipo,
                quantidadeAfetada: quantidadeAfetada,
                destino: destino,
                causas: causas
            };

            const fotoInput = document.getElementById(`fotoNaoConformidade${id}`);
            if (fotoInput && fotoInput.files.length > 0) {
                for (let i = 0; i < fotoInput.files.length; i++) {
                    formData.append(`nc_files_${id}`, fotoInput.files[i]);
                }
            }

            naoConformidades.push(naoConformidade);
        }
    });

    if (naoConformidades.length > 0) {
        formData.append('naoConformidades', JSON.stringify(naoConformidades));
    }

    fetch('/inspecao/api/envio-inspecao-serra-usinagem/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: formData
    })
        .then(response => response.json().then(data => {
            if (!response.ok) throw new Error(data.error || `Erro HTTP! Status: ${response.status}`);
            return data;
        }))
        .then(() => {
            Toast.fire({
                icon: 'success',
                title: 'Inspecao gravada com sucesso!'
            });

            buscarItensInspecao(1);
            buscarItensReinspecao(1);
            buscarItensInspecionados(1);

            const modal = bootstrap.Modal.getInstance(document.getElementById('inspectionModal'));
            modal.hide();
        })
        .catch(error => {
            Toast.fire({
                icon: 'error',
                title: error.message
            });
            console.error('Erro:', error);
        })
        .finally(() => {
            buttonSalvarInspecao.disabled = false;
            buttonSalvarInspecao.innerHTML = 'Salvar';
        });
}

document.getElementById('saveInspection').addEventListener('click', enviarDadosInspecao);
