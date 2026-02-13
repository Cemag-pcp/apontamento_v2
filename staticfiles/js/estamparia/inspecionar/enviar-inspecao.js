function contarConformidadeLinhas() {
    const linhasVisiveis = Array.from(document.querySelectorAll('tr[id^="linhaMedicao"]'))
        .filter((linha) => linha.style.display !== "none");

    let conformes = 0;
    let naoConformeRadios = 0;

    for (const linha of linhasVisiveis) {
        const i = parseInt(linha.id.replace("linhaMedicao", ""), 10);
        if (document.getElementById(`conforming${i}`)?.checked) {
            conformes += 1;
        } else if (document.getElementById(`nonConforming${i}`)?.checked) {
            naoConformeRadios += 1;
        }
    }

    return { conformes, naoConformeRadios };
}

function montarResumoInspecao() {
    const qtdMortaInicioOperacao = parseInt(document.getElementById('qtdMortaInicioOperacao').value, 10) || 0;
    const qtdMorta = parseInt(document.getElementById('numPecaDefeituosa').value, 10) || 0;

    let naoConformeQuantidade = 0;
    document.querySelectorAll('.non-conformity-item').forEach((item) => {
        const id = item.id.replace('nonConformityItem', '');
        const quantidade = parseInt(document.getElementById(`quantidadeAfetada${id}`)?.value, 10) || 0;
        naoConformeQuantidade += quantidade;
    });

    const { conformes, naoConformeRadios } = contarConformidadeLinhas();

    const naoConforme = naoConformeQuantidade > 0 ? naoConformeQuantidade : naoConformeRadios;

    const totalInspecionadas = conformes + naoConforme + qtdMortaInicioOperacao + qtdMorta;

    return {
        totalInspecionadas,
        naoConforme,
        qtdMortaInicioOperacao,
        qtdMorta,
        conformes
    };
}

function abrirResumoInspecao() {
    if (!validarFormulario()) {
        return;
    }

    const resumo = montarResumoInspecao();
    const container = document.getElementById('inspectionConfirmSummary');
    if (container) {
        container.innerHTML = `
            <p><strong>Voce confirma que ao total foram inspecionadas ${resumo.totalInspecionadas} unidades</strong></p>
            <ul class="mb-0">
                <li>${resumo.naoConforme} nao conforme</li>
                <li>${resumo.qtdMortaInicioOperacao} morreram no inicio da operacao</li>
                <li>${resumo.qtdMorta} pecas mortas (processo anterior)</li>
                <li>${resumo.conformes} estao conformes</li>
            </ul>
        `;
    }

    const modalEl = document.getElementById('inspectionConfirmModal');
    if (modalEl) {
        new bootstrap.Modal(modalEl).show();
    }
}

function confirmarEEnviarInspecao() {
    const modalEl = document.getElementById('inspectionConfirmModal');
    const modal = modalEl ? bootstrap.Modal.getInstance(modalEl) : null;
    if (modal) {
        modal.hide();
    }
    enviarDadosInspecao();
}

// Funcao para enviar os dados ao backend
function enviarDadosInspecao() {
    if (!validarFormulario()) {
        return; // Nao enviar se a validacao falhar
    }

    const buttonSalvarInspecao = document.getElementById('saveInspection');
    buttonSalvarInspecao.disabled = true; // Desabilitar o botao para evitar multiplos cliques
    buttonSalvarInspecao.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>';

    const formData = new FormData();

    // Coletando as informacoes basicas
    formData.append('id-inspecao', document.getElementById('id-inspecao').value);
    formData.append('dataInspecao', document.getElementById('dataInspecao').value);
    formData.append('pecasProduzidas', document.getElementById('pecasProduzidas').value);
    formData.append('inspetor', document.getElementById('inspetor').value);
    formData.append('numPecaDefeituosa', document.getElementById('numPecaDefeituosa').value);
    formData.append('qtdMortaInicioOperacao', document.getElementById('qtdMortaInicioOperacao').value);
    formData.append('autoInspecaoNoturna', document.getElementById('autoInspecaoNoturna').checked);
    formData.append('inspecao_total', document.getElementById('inspecao_total').value);

    const { conformes, naoConformeRadios } = contarConformidadeLinhas();
    formData.append('qtdConformidadeLinhas', conformes);
    formData.append('qtdNaoConformidadeLinhas', naoConformeRadios);

    // Coletando causas de pecas mortas
    const causasPecaMorta = [];
    document.querySelectorAll('.causas-morta-container .causa-checkbox:checked').forEach((checkbox) => {
        causasPecaMorta.push(checkbox.value);
    });
    formData.append('causasPecaMorta', JSON.stringify(causasPecaMorta));

    // Coletando as medicoes tecnicas
    const medidas = [];

    const linhasVisiveis = Array.from(document.querySelectorAll('tr[id^="linhaMedicao"]'))
        .filter((linha) => linha.style.display !== "none");

    for (const linha of linhasVisiveis) {
        const i = parseInt(linha.id.replace("linhaMedicao", ""), 10);
        const medida = {};
        let algumCampoPreenchido = false;

        for (let j = 1; j <= 4; j++) {
            // Pega o nome da medida (cabecalho)
            const nomeMedida = document.getElementById(`medida${j}`).value.trim();

            // Pega o valor da medida na linha atual
            const valor = document.getElementById(`valor${i}_${j}`).value.trim();

            // Apenas coleta se o cabecalho estiver preenchido e o valor do campo tambem
            if (nomeMedida !== "" && valor !== "") {
                medida[`medida${j}`] = { nome: nomeMedida, valor: valor };
                algumCampoPreenchido = true; // Marca que existe pelo menos um campo valido
            }
        }

        // Coletar conformidade apenas se algum campo da linha foi preenchido
        if (algumCampoPreenchido) {
            medida['conforme'] = document.getElementById(`conforming${i}`).checked;
            medidas.push(medida);
        }
    }
    formData.append('medidas', JSON.stringify(medidas));

    // Coletando as nao conformidades
    const naoConformidades = [];
    document.querySelectorAll('.non-conformity-item').forEach((item) => {
        const id = item.id.replace('nonConformityItem', '');
        const causas = [];
        document.querySelectorAll(`#causasContainer${id} .causa-checkbox:checked`).forEach((checkbox) => {
            causas.push(checkbox.value);
        });

        const naoConformidade = {
            quantidadeAfetada: document.getElementById(`quantidadeAfetada${id}`).value,
            destino: document.getElementById(`destino${id}`).value,
            causas: causas
        };

        // Coletando foto da nao conformidade
        const foto = document.getElementById(`fotoNaoConformidade${id}`).files;
        if (foto) {
            for (let i = 0; i < foto.length; i++) {
                formData.append(`fotoNaoConformidade${id}`, foto[i]);
            }
        }

        naoConformidades.push(naoConformidade);
    });
    formData.append('naoConformidades', JSON.stringify(naoConformidades));

    // Enviar dados para o backend
    fetch('/inspecao/api/envio-inspecao-estamparia/', {
        method: 'POST',
        headers: {
            "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: formData
    })
    .then(response => {
        return response.json().then(data => {
            if (!response.ok) {
                throw new Error(data.error || `Erro na requisicao HTTP. Status: ${response.status}`);
            }
            return data;
        });
    })
    .then(data => {
        if (typeof limparRascunhoParcialInspecao === "function") {
            limparRascunhoParcialInspecao(document.getElementById('id-inspecao').value);
        }

        Toast.fire({
            icon: "success",
            title: `Inspecao gravada com sucesso.`
        });

        buscarItensInspecao(1);
        buscarItensReinspecao(1);
        buscarItensInspecionados(1);
        const modalInspectionModal = bootstrap.Modal.getInstance(document.getElementById('inspectionModal'));
        modalInspectionModal.hide();
    })
    .catch(error => {
        Toast.fire({
            icon: "error",
            title: error.message
        });
        console.error('Erro:', error);
        location.reload();
    }).finally(() => {
        buttonSalvarInspecao.disabled = false; // Reabilitar o botao
        buttonSalvarInspecao.innerHTML = 'Salvar';
    });
}

// salvar inspecao com confirmacao
document.getElementById('saveInspection').addEventListener('click', abrirResumoInspecao);
document.getElementById('confirmInspection').addEventListener('click', confirmarEEnviarInspecao);
