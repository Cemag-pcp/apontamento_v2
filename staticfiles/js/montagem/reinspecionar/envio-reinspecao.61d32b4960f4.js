document.getElementById("form-reinspecao").addEventListener("submit", function (event) {
    event.preventDefault();

    let modal = document.getElementById('modal-reinspecionar-montagem');
    let modalInstance = bootstrap.Modal.getInstance(modal); // Obter a instância existente
    let buttonInspecionarMontagem = document.getElementById("submit-reinspecionar-montagem");
    buttonInspecionarMontagem.disabled = true;
    buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "flex";

    function cancelarEnvio(mensagem) {
        Swal.fire({ icon: 'error', title: mensagem });
        buttonInspecionarMontagem.disabled = false;
        buttonInspecionarMontagem.querySelector(".spinner-border").style.display = "none";
    }

    // Criar um objeto FormData para enviar os arquivos
    const formData = new FormData(this); // Usar o formulário diretamente

    const qtdReinspecao = document.getElementById("qtd-reinspecao-montagem").value;

    const cardsUnidades = document.querySelectorAll("#unidades-checklist-reinspecao-montagem .unidade-checklist-card");
    const totalCausas = CAUSAS_MONTAGEM.length;

    if (cardsUnidades.length !== parseInt(qtdReinspecao, 10)) {
        cancelarEnvio('Erro ao montar o checklist das unidades. Reabra o modal e tente novamente.');
        return;
    }

    const existeUnidadeIncompleta = Array.from(cardsUnidades).some((card) => {
        const respondidos = card.querySelectorAll('.causa-status-ok:checked, .causa-status-nok:checked').length;
        return respondidos < totalCausas;
    });

    if (existeUnidadeIncompleta) {
        cancelarEnvio('Complete o checklist de todas as unidades reinspecionadas antes de enviar.');
        return;
    }

    // Agrega as causas marcadas como "Ñ OK" em todas as unidades: cada
    // causa vira um "bloco" (mesmo formato que o backend ja espera via
    // request.POST.getlist(f"causas_reinspecao_{i}")), somando quantas
    // unidades falharam por aquela causa e juntando as imagens de todas elas.
    const causasAgregadas = new Map();
    document.querySelectorAll("#unidades-checklist-reinspecao-montagem .causa-status-nok:checked").forEach((radio) => {
        const causaId = radio.getAttribute("data-causa-id");
        const item = radio.closest(".checklist-causa-item");
        const imagensInput = item.querySelector(".causa-imagens");

        if (!causasAgregadas.has(causaId)) {
            causasAgregadas.set(causaId, { quantidade: 0, imagens: [] });
        }
        const entrada = causasAgregadas.get(causaId);
        entrada.quantidade += 1;
        entrada.imagens.push(...Array.from(imagensInput.files));
    });

    let totalBlocos = 0;
    causasAgregadas.forEach((entrada, causaId) => {
        totalBlocos += 1;
        formData.append(`causas_reinspecao_${totalBlocos}`, causaId);
        formData.append(`quantidade_reinspecao_${totalBlocos}`, entrada.quantidade);
        entrada.imagens.forEach((file) => {
            formData.append(`imagens_reinspecao_${totalBlocos}`, file);
        });
    });

    formData.append("quantidade-total-causas", totalBlocos);
    // Campos desabilitados (conformidade/nao-conformidade sao calculados a
    // partir do checklist) nao entram automaticamente no FormData.
    formData.append("conformidade-reinspecao-montagem", document.getElementById("conformidade-reinspecao-montagem").value);
    formData.append("nao-conformidade-reinspecao-montagem", document.getElementById("nao-conformidade-reinspecao-montagem").value);

    // Enviar os dados para o backend
    fetch("/inspecao/api/envio-reinspecao-montagem/", {
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
