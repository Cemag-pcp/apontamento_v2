const form = document.querySelector('#modal-inspecao-tanque form');
const modalSoldaTanque = document.getElementById('modal-inspecionar-solda-tanque');
const submitButton = document.getElementById('inspecionar-tanque');
const spinnerTanqueEstanqueidade = document.getElementById("spinner-tanque-estanqueidade");
const statusButtonTanqueEstanqueidade = document.getElementById("status-button-tanque-estanqueidade");

// Adicionar evento de envio
form.addEventListener('submit', async (event) => {
    event.preventDefault(); // Previne o comportamento padrão de envio do formulário

    // Exibir o spinner e mudar o texto do botão
    submitButton.disabled = true;
    spinnerTanqueEstanqueidade.classList.remove('d-none');
    statusButtonTanqueEstanqueidade.innerText = 'Enviando...';

    // Criar um objeto FormData
    const formData = new FormData();

    const parseVazamento = (value) => {
        if (value === "Sim") return true;
        if (value === "Não") return false;
        return value;
    }

    // Adicionar os dados do formulário ao FormData
    formData.append('tipo_inspecao', 'Tanques');
    formData.append('data_inspecao', document.getElementById('data-inspecao-estanqueidade-tanque').value);
    formData.append('data_carga', document.getElementById('data-carga-estanqueidade-tanque').value);
    formData.append('inspetor', document.getElementById('inspetores_estanqueidade_tanque').value);
    formData.append('produto', document.getElementById('produto-estanqueidade-tanque').value);

    // Adicionar os dados dos testes
    formData.append('testes[parte_inferior][pressao_inicial]', document.getElementById('pressao-inicial-parte-inferior').value);
    formData.append('testes[parte_inferior][duracao]', document.getElementById('duracao-parte-inferior').value);
    formData.append('testes[parte_inferior][pressao_final]', document.getElementById('pressao-final-parte-inferior').value);
    formData.append('testes[parte_inferior][vazamento]', parseVazamento(document.getElementById('vazamento-parte-inferior').value));

    formData.append('testes[corpo_longarina][pressao_inicial]', document.getElementById('pressao-inicial-longarina').value);
    formData.append('testes[corpo_longarina][duracao]', document.getElementById('duracao-longarina').value);
    formData.append('testes[corpo_longarina][pressao_final]', document.getElementById('pressao-final-longarina').value);
    formData.append('testes[corpo_longarina][vazamento]', parseVazamento(document.getElementById('vazamento-longarina').value));

    formData.append('testes[corpo_tanque][pressao_inicial]', document.getElementById('pressao-inicial-corpo-tanque').value);
    formData.append('testes[corpo_tanque][duracao]', document.getElementById('duracao-corpo-tanque').value);
    formData.append('testes[corpo_tanque][pressao_final]', document.getElementById('pressao-final-corpo-tanque').value);
    formData.append('testes[corpo_tanque][vazamento]', parseVazamento(document.getElementById('vazamento-corpo-tanque').value));

    formData.append('testes[corpo_chassi][pressao_inicial]', document.getElementById('pressao-inicial-corpo-chassi').value);
    formData.append('testes[corpo_chassi][duracao]', document.getElementById('duracao-corpo-chassi').value);
    formData.append('testes[corpo_chassi][pressao_final]', document.getElementById('pressao-final-corpo-chassi').value);
    formData.append('testes[corpo_chassi][vazamento]', parseVazamento(document.getElementById('vazamento-corpo-chassi').value));

    // Enviar dados via fetch
    try {
        const response = await fetch('/inspecao/api/envio-inspecao-tanque/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: formData,
        });

        const result = await response.json();
        console.log(result);

        // Processar a resposta aqui
        if (response.ok) {
            const modalEstanqueidade = bootstrap.Modal.getInstance(document.getElementById("modal-inspecao-tanque"));
            modalEstanqueidade.hide();

            Swal.fire({
                icon: 'success',
                title: 'Sucesso!',
                text: 'Inspeção de estanqueidade registrada. Preencha agora a inspeção de solda.',
                timer: 3000,
                showConfirmButton: false
            });
            
            document.getElementById('id-inspecao-solda-tanque').value = result.id_inspecao; // ID da inspeção recém-criada
            document.getElementById('peca-inspecao-solda-tanque').value = document.getElementById('produto-estanqueidade-tanque').value; // Nome da peça ou conjunto
            document.getElementById('qtd-produzida-solda-tanque').value = 1; // Quantidade da OP

            const modalSolda = new bootstrap.Modal(document.getElementById('modal-inspecionar-solda-tanque'));
            modalSolda.show();

            buscarItensInspecionadosEstanqueidadeTanque(1);
            buscarItensReinspecaoEstanqueidadeTanque(1);
        } else {
            // Se houver erro, mostre uma mensagem de erro
            const Toast = Swal.mixin({
                toast: true,
                position: "bottom-end",
                showConfirmButton: false,
                timer: 2000,
                timerProgressBar: true,
                didOpen: (toast) => {
                    toast.onmouseenter = Swal.stopTimer;
                    toast.onmouseleave = Swal.resumeTimer;
                }
            });
            Toast.fire({
                icon: "error",
                title: "Erro ao enviar os dados para o servidor!"
            });
        }
    } catch (error) {
        console.error('Erro ao enviar dados:', error);
        const Toast = Swal.mixin({
            toast: true,
            position: "bottom-end",
            showConfirmButton: false,
            timer: 2000,
            timerProgressBar: true,
            didOpen: (toast) => {
                toast.onmouseenter = Swal.stopTimer;
                toast.onmouseleave = Swal.resumeTimer;
            }
        });
        Toast.fire({
            icon: "error",
            title: "Erro ao enviar os dados para o servidor!"
        });
        setTimeout(() => {
            location.reload();
        }, 2000);
    } finally {
        submitButton.disabled = false;
        spinnerTanqueEstanqueidade.classList.add('d-none');
        statusButtonTanqueEstanqueidade.innerText = 'Inspecionar';
        const modal = bootstrap.Modal.getInstance(document.getElementById("modal-inspecao-tanque"));
        modal.hide();
    }
});



