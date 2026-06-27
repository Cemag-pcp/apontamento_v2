$("#produto-estanqueidade-tanque").on("change", function () {

    let codigoTanque = $(this).val();

    console.log(codigoTanque) //035939 - FTC4300R

    // Campo para 4300 e 6500
    let listaCodigosTanque = [
        "4300",
        "6500"
    ];

    let tanqueEncontrado = listaCodigosTanque.some(codigo => codigoTanque.includes(codigo));

    if (tanqueEncontrado) {
        $("#col-parteInferior, #col-corpoLongarina").show();
        $("#col-corpoTanque, #col-corpoChassi").hide();

        $("#pressao-inicial-parte-inferior").attr("required", true);
        $("#duracao-parte-inferior").attr("required", true);
        $("#pressao-final-parte-inferior").attr("required", true);
        $("#vazamento-parte-inferior").attr("required", true);

        $("#pressao-inicial-longarina").attr("required", true);
        $("#duracao-longarina").attr("required", true);
        $("#pressao-final-longarina").attr("required", true);
        $("#vazamento-longarina").attr("required", true);

        $("#pressao-inicial-corpo-tanque").removeAttr("required");
        $("#duracao-corpo-tanque").removeAttr("required");
        $("#pressao-final-corpo-tanque").removeAttr("required");
        $("#vazamento-corpo-tanque").removeAttr("required");

        $("#pressao-inicial-corpo-chassi").removeAttr("required");
        $("#duracao-corpo-chassi").removeAttr("required");
        $("#pressao-final-corpo-chassi").removeAttr("required");
        $("#vazamento-corpo-chassi").removeAttr("required");

    } else {
        $("#col-parteInferior, #col-corpoLongarina").hide();
        $("#col-corpoTanque, #col-corpoChassi").show();

        $("#pressao-inicial-parte-inferior").removeAttr("required");
        $("#duracao-parte-inferior").removeAttr("required");
        $("#pressao-final-parte-inferior").removeAttr("required");
        $("#vazamento-parte-inferior").removeAttr("required");

        $("#pressao-inicial-longarina").removeAttr("required");
        $("#duracao-longarina").removeAttr("required");
        $("#pressao-final-longarina").removeAttr("required");
        $("#vazamento-longarina").removeAttr("required");

        $("#pressao-inicial-corpo-tanque").attr("required", true);
        $("#duracao-corpo-tanque").attr("required", true);
        $("#pressao-final-corpo-tanque").attr("required", true);
        $("#vazamento-corpo-tanque").attr("required", true);

        $("#pressao-inicial-corpo-chassi").attr("required", true);
        $("#duracao-corpo-chassi").attr("required", true);
        $("#pressao-final-corpo-chassi").attr("required", true);
        $("#vazamento-corpo-chassi").attr("required", true);
    }
})


function disabledAllTypesReinspecao() {
    $('#col-parteInferior-reinspecao').hide();
    $('#col-corpoLongarina-reinspecao').hide();
    $('#col-corpoTanque-reinspecao').hide();
    $('#col-corpoChassi-reinspecao').hide();

    $("#flag-corpo-do-tanque-parte-inferior-reinspecao").val(false)
    $("#flag-corpo-do-tanque-longarinas-reinspecao").val(false)
    $("#flag-corpo-do-tanque-reinspecao").val(false)
    $("#flag-corpo-do-tanque-chassi-reinspecao").val(false)

    $("#col-parteInferior-reinspecao input, #col-parteInferior-reinspecao select").prop("required", false);
    $("#col-parteInferior-reinspecao input, #col-parteInferior-reinspecao select").prop("disabled", false);
    $("#button-corpo-do-tanque-parte-inferior-reinspecao").css("background-color", "#fff");
    $("#button-corpo-do-tanque-parte-inferior-reinspecao h6")
        .addClass("text-dark")
        .removeClass("text-success");

    // Alterar ícones (remover fa-plus e adicionar fa-check)
    $("#button-corpo-do-tanque-parte-inferior-reinspecao i")
        .addClass("fa-plus")
        .removeClass("fa-check")
        .removeClass("text-success")

    $("#col-corpoLongarina-reinspecao input, #col-corpoLongarina-reinspecao select").prop("required", false);
    $("#col-corpoLongarina-reinspecao input, #col-corpoLongarina-reinspecao select").prop("disabled", false);
    $("#button-corpo-do-tanque-longarinas-reinspecao").css("background-color", "#fff");
    $("#button-corpo-do-tanque-longarinas-reinspecao h6")
        .addClass("text-dark")
        .removeClass("text-success");

    // Alterar ícones (remover fa-plus e adicionar fa-check)
    $("#button-corpo-do-tanque-longarinas-reinspecao i")
        .addClass("fa-plus")
        .removeClass("fa-check")
        .removeClass("text-success")

    $("#col-corpoTanque-reinspecao input, #col-corpoTanque-reinspecao select").prop("required", false);
    $("#col-corpoTanque-reinspecao input, #col-corpoTanque-reinspecao select").prop("disabled", false);
    $("#button-corpo-do-tanque-reinspecao").css("background-color", "#fff");
    $("#button-corpo-do-tanque-reinspecao h6")
        .addClass("text-dark")
        .removeClass("text-success");

    // Alterar ícones (remover fa-plus e adicionar fa-check)
    $("#button-corpo-do-tanque-reinspecao i")
        .addClass("fa-plus")
        .removeClass("fa-check")
        .removeClass("text-success")

    $("#col-corpoChassi-reinspecao input, #col-corpoChassi-reinspecao select").prop("required", false);
    $("#col-corpoChassi-reinspecao input, #col-corpoChassi-reinspecao select").prop("disabled", false);
    $("#button-corpo-do-tanque-chassi-reinspecao").css("background-color", "#fff");
    $("#button-corpo-do-tanque-chassi-reinspecao h6")
        .addClass("text-dark")
        .removeClass("text-success");

    $("#button-corpo-do-tanque-chassi-reinspecao i")
        .addClass("fa-plus")
        .removeClass("fa-check")
        .removeClass("text-success")
}