document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('iniciar-reinspecao-tanque')) {
            document.getElementById("reinspecaoFormTanque").reset();
            
            const id = event.target.getAttribute("data-id");
            const data = event.target.getAttribute("data-data");
            const dataCarga = event.target.getAttribute("data-data-carga");
            const peca = event.target.getAttribute("data-peca");

            document.getElementById("id_estanqueidade_tanque_reinspecao").value = id;
            document.getElementById("data_estanqueidade_tanque_reinspecao").value = data;
            document.getElementById("data-carga-estanqueidade-tanque-reinspecao").value = dataCarga;
            document.getElementById("produto-estanqueidade-tanque-reinspecao").value = peca;
            document.getElementById("data_estanqueidade_tanque_reinspecao").value = data;


            const testes = [1, 2].map(num => ({
                pressaoInicial: event.target.getAttribute(`data-pressao-inicial-${num}`),
                pressaoFinal: event.target.getAttribute(`data-pressao-final-${num}`),
                tipoTeste: event.target.getAttribute(`data-tipo-teste-${num}`),
                tempoExecucao: event.target.getAttribute(`data-tempo-execucao-${num}`),
                naoConformidade: event.target.getAttribute(`data-nao-conformidade-${num}`)
            }));

            disabledAllTypesReinspecao();
            testes.forEach(item => {
                atualizarReinspecao(item.tipoTeste, item)
            });

            new bootstrap.Modal(document.getElementById("modal-reinspecao-tanque")).show();
        }
    });
});

function atualizarReinspecao(tipoTeste, item) {
    const elementos = {
        "Corpo do tanque parte inferior": "col-parteInferior-reinspecao",
        "Corpo do tanque + longarinas": "col-corpoLongarina-reinspecao",
        "Corpo do tanque": "col-corpoTanque-reinspecao",
        "Corpo do tanque + chassi": "col-corpoChassi-reinspecao"
    };

    if (elementos[tipoTeste]) {
        const div = document.getElementById(elementos[tipoTeste]);
        div.style.display = "block";
        div.querySelectorAll("input, select").forEach(el => el.value = "");
        if (item.naoConformidade === 'false') {
            console.log(`flag-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`)
            document.getElementById(`flag-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`).value = false;
            document.getElementById(`pressao-inicial-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`).value = item.pressaoInicial;
            document.getElementById(`pressao-final-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`).value = item.pressaoFinal;
            document.getElementById(`duracao-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`).value = item.tempoExecucao;
            document.getElementById(`vazamento-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`).value = "Não";
            
            div.querySelectorAll("input, select").forEach(el => el.disabled = true);
            const button = document.getElementById(`button-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`);
            button.style.backgroundColor = "#d5ffd5";
            button.querySelector("h6").classList.replace("text-dark", "text-success");
            const icon = button.querySelector("svg");
            icon.classList.replace("fa-plus", "fa-check");
            icon.classList.add("text-success");
        } else {
            div.querySelectorAll("input, select").forEach(el => el.disabled = false);
            const button = document.getElementById(`button-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`);
            button.style.backgroundColor = "#fff";
            button.querySelector("h6").classList.replace("text-success", "text-dark");
            const icon = button.querySelector("svg");
            icon.classList.replace("fa-check", "fa-plus");
            icon.classList.add("text-dark");

            div.querySelectorAll("input, select").forEach(el => el.required = true);
            document.getElementById(`duracao-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`).value = "00:00:00";
            document.getElementById(`flag-${tipoTeste.replace(/\s+/g, '-').toLowerCase()}-reinspecao`).value = true;
        }
    }
}
