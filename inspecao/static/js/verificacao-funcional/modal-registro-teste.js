document.addEventListener("DOMContentLoaded", () => {
    const formRegistroTesteVerificacaoFuncional = document.getElementById("form-registro-teste-verificacao-funcional");
    const modalTesteVerificacaoFuncional = new bootstrap.Modal(document.getElementById("modal-verificacao-funcional"));
    document.addEventListener("click", function(event){
        if (event.target.classList.contains('iniciar-verificacao-pendentes')){
            document.getElementById('peca').textContent = event.target.getAttribute('data-peca');
            document.getElementById('registroId').textContent = 'Registro #'+event.target.getAttribute('data-id');
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

        const dados = {};

        const idRegistro = document.getElementById('btn-registrar-teste').getAttribute('data-id');

        dados['idRegistro'] = idRegistro;

        // Radios marcados
        document.querySelectorAll("input[type='radio']:checked").forEach(radio => {
            dados[radio.name] = radio.value;
        });

        // Inputs de texto, number, hidden, etc.
        document.querySelectorAll("input[type='text'], input[type='number'], input[type='hidden']").forEach(input => {
            if (input.value.trim() !== "") {
                dados[input.name || input.id] = input.value;
            }
        });

        // Textareas
        document.querySelectorAll("textarea").forEach(textarea => {
            if (textarea.value.trim() !== "") {
                dados[textarea.name || textarea.id] = textarea.value;
            }
        });

        // Selects
        document.querySelectorAll("select").forEach(select => {
            if (select.value) {
                dados[select.name || select.id] = select.value;
            }
        });

        console.log("Dados coletados:", dados);

        for (const key in dados){
            if (dados[key] === 'aprovado'){
                dados[key] = true;
            }else if (dados[key] === 'reprovado'){
                dados[key] = false;
            }
        }

        // Exemplo: enviar via fetch
        
        fetch("/inspecao/api/realizar-verificacao-funcional/", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
             },
            
            body: JSON.stringify(dados)
        })
        .then(res => res.json())
        .then(data => { 
            console.log("Resposta do servidor:", data)
            // Aqui você pode adicionar lógica para fechar o modal, mostrar uma mensagem de sucesso, etc.
            if (data.status === 'ok' && data.causa_reprovacao){
                Swal.fire({
                    title: 'Teste registrado',
                    text: 'Peça reprovada! Causa da reprovação: ' + data.causa_reprovacao,
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
        });
        
    });
})