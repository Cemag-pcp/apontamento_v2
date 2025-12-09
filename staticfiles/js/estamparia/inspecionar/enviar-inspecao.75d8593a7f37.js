// Função para enviar os dados ao backend
function enviarDadosInspecao() {
    
    if (!validarFormulario()) {
        return; // Não enviar se a validação falhar
    }

    const buttonSalvarInspecao = document.getElementById('saveInspection');
    buttonSalvarInspecao.disabled = true; // Desabilitar o botão para evitar múltiplos cliques
    buttonSalvarInspecao.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>';

    const formData = new FormData();

    // Coletando as informações básicas
    formData.append('id-inspecao', document.getElementById('id-inspecao').value);
    formData.append('dataInspecao', document.getElementById('dataInspecao').value);
    formData.append('pecasProduzidas', document.getElementById('pecasProduzidas').value);
    formData.append('inspetor', document.getElementById('inspetor').value);
    formData.append('numPecaDefeituosa', document.getElementById('numPecaDefeituosa').value);
    formData.append('autoInspecaoNoturna', document.getElementById('autoInspecaoNoturna').checked);
    formData.append('inspecao_total', document.getElementById('inspecao_total').value);

    // Coletando causas de peças mortas
    const causasPecaMorta = [];
    document.querySelectorAll('.causas-morta-container .causa-checkbox:checked').forEach((checkbox) => {
        causasPecaMorta.push(checkbox.value);
    });
    formData.append('causasPecaMorta', JSON.stringify(causasPecaMorta));

    // Coletando as medições técnicas
    const medidas = [];

    for (let i = 1; i <= 3; i++) {
        const medida = {};
        let algumCampoPreenchido = false;

        for (let j = 1; j <= 4; j++) {
            // Pega o nome da medida (cabeçalho)
            const nomeMedida = document.getElementById(`medida${j}`).value.trim();

            // Pega o valor da medida na linha atual
            const valor = document.getElementById(`valor${i}_${j}`).value.trim();

            // Apenas coleta se o cabeçalho estiver preenchido e o valor do campo também
            if (nomeMedida !== "" && valor !== "") {
                medida[`medida${j}`] = { nome: nomeMedida, valor: valor };
                algumCampoPreenchido = true; // Marca que existe pelo menos um campo válido
            }
        }

        // Coletar conformidade apenas se algum campo da linha foi preenchido
        if (algumCampoPreenchido) {
            medida['conforme'] = document.getElementById(`conforming${i}`).checked;
            medidas.push(medida);
        }
    }
    formData.append('medidas', JSON.stringify(medidas));

    // Coletando as não conformidades
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
        
        // Coletando foto da não conformidade
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
                throw new Error(data.error || `Erro na requisição HTTP. Status: ${response.status}`);
            }
            return data;
        });
    })
    .then(data => {
        Toast.fire({
            icon: "success",
            title: `Inspeção gravada com sucesso.`
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
    }).finally(d => {
        buttonSalvarInspecao.disabled = false; // Reabilitar o botão
        buttonSalvarInspecao.innerHTML = 'Salvar';
    });
}

// salvar inspeçao
document.getElementById('saveInspection').addEventListener('click', enviarDadosInspecao);