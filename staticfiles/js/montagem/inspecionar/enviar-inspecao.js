document.getElementById("form-inspecao").addEventListener("submit", function (event) {
    event.preventDefault();

    const modal = document.getElementById('modal-inspecionar-montagem');
    const modalInstance = bootstrap.Modal.getInstance(modal); // Obter a instância existente
    let buttonInspecionarMontagem = document.getElementById("submit-inspecionar-montagem");
    buttonInspecionarMontagem.disabled = true;
    buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "flex";

    function cancelarEnvio(mensagem) {
        Swal.fire({ icon: 'error', title: mensagem });
        buttonInspecionarMontagem.disabled = false;
        buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "none";
    }

    // Criar um objeto FormData para enviar os arquivos
    const formData = new FormData(this); // Usar o formulário diretamente

    const qtdProduzida = document.getElementById("qtd-produzida-montagem").value;
    const qtdInspecionada = document.getElementById("qtd-inspecao-montagem").value;

    if (qtdInspecionada === "" || parseInt(qtdInspecionada, 10) < 1) {
        cancelarEnvio('Informe a quantidade inspecionada (mínimo 1).');
        return;
    }

    if (parseFloat(qtdInspecionada) > parseFloat(qtdProduzida)) {
        cancelarEnvio('Quantidade Inspecionada não pode ser maior que a quantidade Produzida');
        return;
    }

    const cardsUnidades = document.querySelectorAll("#unidades-checklist-montagem .unidade-checklist-card");
    const totalCausas = totalItensChecklistMontagem();

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

    const semFalha = validarFalhasChecklistMontagem(document.getElementById("unidades-checklist-montagem"));
    if (semFalha.length > 0) {
        Swal.fire({
            icon: 'error',
            title: 'Escolha a falha',
            html: 'Selecione ao menos uma falha em:<br>' + semFalha.join('<br>'),
        });
        buttonInspecionarMontagem.disabled = false;
        buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "none";
        return;
    }

    const semFoto = validarImagensNaoConformidadeMontagem(document.getElementById("unidades-checklist-montagem"));
    if (semFoto.length > 0) {
        Swal.fire({
            icon: 'error',
            title: 'Foto obrigatória na não conformidade',
            html: 'Anexe ao menos uma foto em:<br>' + semFoto.join('<br>'),
        });
        buttonInspecionarMontagem.disabled = false;
        buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "none";
        return;
    }

    // Cada grupo "Ñ OK" vira um bloco com as falhas escolhidas, somando as
    // unidades com a mesma combinação (agregarNaoConformidadesMontagem).
    const blocos = agregarNaoConformidadesMontagem(document.getElementById("unidades-checklist-montagem"));
    let totalBlocos = 0;
    blocos.forEach((bloco) => {
        totalBlocos += 1;
        bloco.causasIds.forEach((causaId) => formData.append(`causas_${totalBlocos}`, causaId));
        formData.append(`quantidade_${totalBlocos}`, bloco.quantidade);
        bloco.imagens.forEach((file) => formData.append(`imagens_${totalBlocos}`, file));
        bloco.fotosRascunho.forEach((id) => formData.append(`fotos_rascunho_${totalBlocos}`, id));
    });

    formData.append("quantidade-total-causas", totalBlocos);
    // Campos desabilitados (conformidade/nao-conformidade sao calculados a
    // partir do checklist) nao entram automaticamente no FormData.
    formData.append("conformidade-inspecao-montagem", document.getElementById("conformidade-inspecao-montagem").value);
    formData.append("nao-conformidade-inspecao-montagem", document.getElementById("nao-conformidade-inspecao-montagem").value);

    // Enviar os dados para o backend
    fetch("/inspecao/api/envio-inspecao-montagem/", {
        method: "POST",
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData, // Usar FormData em vez de JSON
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
        // o servidor apagou o rascunho junto com o envio
        RASCUNHO_MONTAGEM.fotos = [];
        RASCUNHO_MONTAGEM.removidas = new Set();
        if (modalInstance) {
            modalInstance.hide();
        }
        const Toast = Swal.mixin({
            toast: true,
            position: "bottom-end",
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true,
            didOpen: (toast) => {
              toast.onmouseenter = Swal.stopTimer;
              toast.onmouseleave = Swal.resumeTimer;
            }
          });
          Toast.fire({
            icon: "success",
            title: "Inspeção realizada com sucesso"
          });
        buscarItensInspecao(1);
        buscarItensReinspecao(1);
        buscarItensInspecionados(1);
    })
    .catch(error => {
        console.error(error);
        Swal.fire({
            icon: 'error',
            title: 'Erro no envio da inspeção',
            text: error, // Exibe a mensagem do backend corretamente
        });
    })
    .finally(() => {
        buttonInspecionarMontagem.disabled = false;
        buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "none";
    });
});
