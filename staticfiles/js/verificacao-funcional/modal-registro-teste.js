document.addEventListener("DOMContentLoaded", () => {
    const formRegistroTesteVerificacaoFuncional = document.getElementById("form-registro-teste-verificacao-funcional");
    const modalTesteVerificacaoFuncional = new bootstrap.Modal(document.getElementById("modal-verificacao-funcional"));
    document.addEventListener("click", function(event){
        if (event.target.classList.contains('iniciar-verificacao-pendentes')){
            document.getElementById('peca').textContent = event.target.getAttribute('data-peca');
            document.getElementById('ordemId').textContent = 'Ordem #'+event.target.getAttribute('data-ordem');
            document.getElementById('dataCriacao').textContent = event.target.getAttribute('data-data');
            document.getElementById('tipoPintura').textContent = event.target.getAttribute('data-tipo');
            document.getElementById('cor').textContent = event.target.getAttribute('data-cor');
            document.getElementById('btn-registrar-teste').setAttribute('data-id', event.target.getAttribute('data-id'));

            if (document.getElementById('tipoPintura').textContent === 'PU'){
                document.getElementById('testePolimerizacao').style.display = 'none';
                document.getElementById('status-polimerizacao-aprovado').disabled = true;
                document.getElementById('status-polimerizacao-reprovado').disabled = true;
            }else{
                document.getElementById('testePolimerizacao').style.display = 'block';
                document.getElementById('status-polimerizacao-aprovado').disabled = false;
                document.getElementById('status-polimerizacao-reprovado').disabled = false;
            }

            formRegistroTesteVerificacaoFuncional.reset()
            modalTesteVerificacaoFuncional.show();
        }
    })

    // capturar valores ao clicar no botão "Registrar Teste"
    formRegistroTesteVerificacaoFuncional.addEventListener("submit", (event) => {
        event.preventDefault();

        const btnRegistrarTeste = document.getElementById('btn-registrar-teste');
        const spinnerTeste = document.getElementById('spinner-teste');
        const statusTeste = document.getElementById('status-btn-teste');

        btnRegistrarTeste.disabled = true;
        spinnerTeste.classList.remove('d-none');
        statusTeste.textContent = 'Registrando...';

        const formData = new FormData();
        
        // const dados = {};

        const idRegistro = document.getElementById('btn-registrar-teste').getAttribute('data-id');

        // dados['idRegistro'] = idRegistro;
        formData.append('idRegistro', idRegistro);

        // Radios marcados
        document.querySelectorAll("input[type='radio']:checked").forEach(radio => {
            // dados[radio.name] = radio.value;
            formData.append(radio.name, radio.value);
        });

        // Inputs de texto, number, hidden, etc.
        document.querySelectorAll("input[type='text'], input[type='number'], input[type='hidden']").forEach(input => {
            if (input.value.trim() !== "") {
                // dados[input.name || input.id] = input.value;
                formData.append(input.name || input.id, input.value);
            }
        });

        // Textareas
        document.querySelectorAll("textarea").forEach(textarea => {
            if (textarea.value.trim() !== "") {
                // dados[textarea.name || textarea.id] = textarea.value;
                formData.append(textarea.name || textarea.id, textarea.value);
            }
        });

        // Selects
        document.querySelectorAll("select").forEach(select => {
            if (select.value) {
                // dados[select.name || select.id] = select.value;
                formData.append(select.name || select.id, select.value);
            }
        });

        // Imagem
        const imagemInput = document.getElementById("upload-imagem-teste");
        if (imagemInput && imagemInput.files.length > 0) {
            formData.append("imagem", imagemInput.files[0]);
        }

        console.log("Dados coletados:", formData);

        formData.forEach((value, key) => {
            if (value === 'aprovado'){
                formData.set(key, true);
            }else if (value === 'reprovado'){
                formData.set(key, false);
            }
        });

        // for (const key in formData){
        //     console.log(key);
        //     if (formData[key] === 'aprovado'){
        //         formData[key] = true;
        //     }else if (formData[key] === 'reprovado'){
        //         formData[key] = false;
        //     }
        // }

        // Exemplo: enviar via fetch
        
        fetch("/inspecao/api/realizar-verificacao-funcional/", {
            method: "POST",
            headers: { 
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
             },
            
            body: formData,
        })
        .then(res => res.json())
        .then(data => { 
            console.log("Resposta do servidor:", data)
            // Aqui você pode adicionar lógica para fechar o modal, mostrar uma mensagem de sucesso, etc.
            if (data.status === 'ok' && data.causa_reprovacao){
                Swal.fire({
                    title: 'Teste registrado',
                    text: 'Peça reprovada!',
                    icon: 'success', // você pode usar 'success', 'warning', 'info', 'error'
                    confirmButtonText: 'OK'
                });
            }else if (data.status === 'ok'){
                Swal.fire({
                    title: 'Teste registrado',
                    text: 'Peça aprovada com sucesso!',
                    icon: 'success',
                    confirmButtonText: 'OK'
                });
            }else if (data.error){
                Swal.fire({
                    title: 'Erro',
                    text: data.error,
                    icon: 'error',
                    confirmButtonText: 'OK'
                });
            }
            
            
        })
        .catch(err => console.error("Erro:", err))
        .finally(() => {
            // Qualquer ação final, se necessário
            statusTeste.textContent = 'Registrar Teste';
            btnRegistrarTeste.disabled = false;
            spinnerTeste.classList.add('d-none');

            modalTesteVerificacaoFuncional.hide();
            buscarItensPendentes(1);
            buscarItensFinalizados(1);
        });
        
    });
})