// Adicionar evento de envio
document.getElementById('reinspecaoFormTanque').addEventListener('submit', async (event) => {
    event.preventDefault(); // Previne o comportamento padrão de envio do formulário
    const submitButtonReinsp = document.getElementById('reinspecionar-tanque');
    const spinnerTanqueEstanqueidadeReinsp = document.getElementById("spinner-tanque-estanqueidade-reinspecao");
    const statusButtonTanqueEstanqueidadeReinsp = document.getElementById("status-button-tanque-estanqueidade-reinspecao");

    // Exibir o spinner e mudar o texto do botão
    submitButtonReinsp.disabled = true;
    spinnerTanqueEstanqueidadeReinsp.classList.remove('d-none');
    statusButtonTanqueEstanqueidadeReinsp.innerText = 'Enviando...';

    // Criar um objeto FormData
    const formData = new FormData();

    const parseVazamento = (value) => {
        if (value === "Sim") return true;
        if (value === "Não") return false;
        return value;
    }

    // Adicionar os dados do formulário ao FormData
    formData.append('id', document.getElementById('id_estanqueidade_tanque_reinspecao').value);
    formData.append('id_dados_execucao', document.getElementById('id_dados_execucao_estanqueidade_tanque_reinspecao').value);
    formData.append('tipo_inspecao', 'Tanques');
    formData.append('data_reinspecao', document.getElementById('data_estanqueidade_tanque_reinspecao').value);
    formData.append('data_carga', document.getElementById('data-carga-estanqueidade-tanque-reinspecao').value);
    formData.append('inspetor', document.getElementById('inspetores_estanqueidade_tanque_reinspecao').value);
    formData.append('produto', document.getElementById('produto-estanqueidade-tanque-reinspecao').value);

    // Adicionar os dados dos testes
    formData.append('testes[parte_inferior][pressao_inicial]', document.getElementById('pressao-inicial-corpo-do-tanque-parte-inferior-reinspecao').value);
    formData.append('testes[parte_inferior][duracao]', document.getElementById('duracao-corpo-do-tanque-parte-inferior-reinspecao').value);
    formData.append('testes[parte_inferior][pressao_final]', document.getElementById('pressao-final-corpo-do-tanque-parte-inferior-reinspecao').value);
    formData.append('testes[parte_inferior][vazamento]', parseVazamento(document.getElementById('vazamento-corpo-do-tanque-parte-inferior-reinspecao').value));

    formData.append('testes[corpo_longarina][pressao_inicial]', document.getElementById('pressao-inicial-corpo-do-tanque-+-longarinas-reinspecao').value);
    formData.append('testes[corpo_longarina][duracao]', document.getElementById('duracao-corpo-do-tanque-+-longarinas-reinspecao').value);
    formData.append('testes[corpo_longarina][pressao_final]', document.getElementById('pressao-final-corpo-do-tanque-+-longarinas-reinspecao').value);
    formData.append('testes[corpo_longarina][vazamento]', parseVazamento(document.getElementById('vazamento-corpo-do-tanque-+-longarinas-reinspecao').value));

    formData.append('testes[corpo_tanque][pressao_inicial]', document.getElementById('pressao-inicial-corpo-do-tanque-reinspecao').value);
    formData.append('testes[corpo_tanque][duracao]', document.getElementById('duracao-corpo-do-tanque-reinspecao').value);
    formData.append('testes[corpo_tanque][pressao_final]', document.getElementById('pressao-final-corpo-do-tanque-reinspecao').value);
    formData.append('testes[corpo_tanque][vazamento]', parseVazamento(document.getElementById('vazamento-corpo-do-tanque-reinspecao').value));

    formData.append('testes[corpo_chassi][pressao_inicial]', document.getElementById('pressao-inicial-corpo-do-tanque-+-chassi-reinspecao').value);
    formData.append('testes[corpo_chassi][duracao]', document.getElementById('duracao-corpo-do-tanque-+-chassi-reinspecao').value);
    formData.append('testes[corpo_chassi][pressao_final]', document.getElementById('pressao-final-corpo-do-tanque-+-chassi-reinspecao').value);
    formData.append('testes[corpo_chassi][vazamento]', parseVazamento(document.getElementById('vazamento-corpo-do-tanque-+-chassi-reinspecao').value));

    // Enviar dados via fetch
    try {
        const response = await fetch('/inspecao/api/envio-reinspecao-tanque/', {
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
            // Se a resposta for OK, mostre uma mensagem de sucesso
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
                icon: "success",
                title: "Inspeção registrada com sucesso!"
            });
            setTimeout(() => {
                location.reload();
            }, 2000);
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
            setTimeout(() => {
                location.reload();
            }, 2000);
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
    }
});
