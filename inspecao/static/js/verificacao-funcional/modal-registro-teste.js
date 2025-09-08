document.addEventListener("DOMContentLoaded", () => {
    const formRegistroTesteVerificacaoFuncional = document.getElementById("form-registro-teste-verificacao-funcional");
    document.addEventListener("click", function(event){
        if (event.target.classList.contains('iniciar-verificacao-pendentes')){
            document.getElementById('peca').textContent = event.target.getAttribute('data-peca');
            document.getElementById('registroId').textContent = 'Registro #'+event.target.getAttribute('data-id');
            document.getElementById('dataCarga').textContent = event.target.getAttribute('data-data');
            document.getElementById('tipoPintura').textContent = event.target.getAttribute('data-tipo');
            document.getElementById('cor').textContent = event.target.getAttribute('data-cor');

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
            const modal = new bootstrap.Modal(document.getElementById("modal-verificacao-funcional"));
            modal.show();
        }
    })

    // capturar valores ao clicar no botão "Registrar Teste"
    formRegistroTesteVerificacaoFuncional.addEventListener("submit", (event) => {
        event.preventDefault();
        const dados = {};
        console.log('teste');

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
        .then(data => console.log("Resposta do servidor:", data))
        .catch(err => console.error("Erro:", err));
        
    });
})