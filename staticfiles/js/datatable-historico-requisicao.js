$(document).ready(function () {
    const filtros = {
        dataSolicitacaoInicio: $("#data_solicitacao_inicio"),
        dataSolicitacaoFim: $("#data_solicitacao_fim"),
        dataEntregaInicio: $("#data_entrega_inicio"),
        dataEntregaFim: $("#data_entrega_fim"),
        chaveInnovaro: $("#chave_innovaro"),
        codigoItem: $("#codigo_item"),
    };

    const buildExportUrl = () => {
        const params = new URLSearchParams();

        if (filtros.dataSolicitacaoInicio.val()) {
            params.set("data_solicitacao_inicio", filtros.dataSolicitacaoInicio.val());
        }
        if (filtros.dataSolicitacaoFim.val()) {
            params.set("data_solicitacao_fim", filtros.dataSolicitacaoFim.val());
        }
        if (filtros.dataEntregaInicio.val()) {
            params.set("data_entrega_inicio", filtros.dataEntregaInicio.val());
        }
        if (filtros.dataEntregaFim.val()) {
            params.set("data_entrega_fim", filtros.dataEntregaFim.val());
        }
        if (filtros.chaveInnovaro.val()) {
            params.set("chave_innovaro", filtros.chaveInnovaro.val());
        }
        if (filtros.codigoItem.val()) {
            params.set("codigo_item", filtros.codigoItem.val());
        }

        return `/almox/historico/requisicao/exportar-csv/?${params.toString()}`;
    };

    const hasActiveFilters = () => {
        return [
            filtros.dataSolicitacaoInicio.val(),
            filtros.dataSolicitacaoFim.val(),
            filtros.dataEntregaInicio.val(),
            filtros.dataEntregaFim.val(),
            filtros.chaveInnovaro.val(),
            filtros.codigoItem.val(),
        ].some((valor) => (valor || "").trim() !== "");
    };

    const updateExportButtonState = () => {
        const botao = $("#exportar-csv-requisicao");
        const ativo = hasActiveFilters();
        botao.attr("href", ativo ? buildExportUrl() : "#");
        botao.toggleClass("disabled", !ativo);
        botao.attr("aria-disabled", ativo ? "false" : "true");
    };

    let table = $("#execucaoTable").DataTable({
        processing: true,
        serverSide: true,
        autoWidth: false,
        scrollX: true,
        ajax: {
            url: "/almox/api/historico/processa-historico-requisicao/",
            type: "POST",
            data: function (d) {
                d.data_solicitacao_inicio = filtros.dataSolicitacaoInicio.val();
                d.data_solicitacao_fim = filtros.dataSolicitacaoFim.val();
                d.data_entrega_inicio = filtros.dataEntregaInicio.val();
                d.data_entrega_fim = filtros.dataEntregaFim.val();
                d.chave_innovaro = filtros.chaveInnovaro.val();
                d.codigo_item = filtros.codigoItem.val();
            }
        },
        columns: [
            {
                data: "rpa",
                orderable: false,
                render: function (data) {
                    if (data === "OK") {
                        return '<span class="badge bg-success">Ok</span>';
                    }
                    if (data === null) {
                        return '<span class="badge bg-warning text-dark">Pendente</span>';
                    }
                    return '<span class="badge bg-warning text-dark">Erro</span>';
                }
            },
            { data: "chave_innovaro", orderable: false },
            { data: "data_solicitacao", orderable: false },
            { data: "classe_requisicao", orderable: false },
            { data: "item", orderable: false },
            { data: "quantidade", orderable: false },
            { data: "cc__nome", orderable: false },
            { data: "funcionario__nome", orderable: false },
            { data: "obs", orderable: false },
            { data: "entregue_por__nome", orderable: false },
            { data: "data_entrega", orderable: false },
            {
                data: "status",
                orderable: false,
                render: function (data) {
                    if (data === "Entregue") {
                        return '<span class="badge bg-success">Entregue</span>';
                    }
                    return '<span class="badge bg-warning text-dark">Pendente</span>';
                }
            },
        ],
        order: [[2, "desc"]],
        language: {
            search: "Procurar"
        }
    });

    [
        filtros.dataSolicitacaoInicio,
        filtros.dataSolicitacaoFim,
        filtros.dataEntregaInicio,
        filtros.dataEntregaFim,
    ].forEach((campo) => {
        campo.on("change", function () {
            table.ajax.reload();
            updateExportButtonState();
        });
    });

    filtros.chaveInnovaro.on("input", function () {
        table.ajax.reload();
        updateExportButtonState();
    });

    filtros.codigoItem.on("input", function () {
        table.ajax.reload();
        updateExportButtonState();
    });

    $("#limpar-filtros-requisicao").on("click", function () {
        filtros.dataSolicitacaoInicio.val("");
        filtros.dataSolicitacaoFim.val("");
        filtros.dataEntregaInicio.val("");
        filtros.dataEntregaFim.val("");
        filtros.chaveInnovaro.val("");
        filtros.codigoItem.val("");
        updateExportButtonState();
        table.ajax.reload();
    });

    $("#exportar-csv-requisicao").on("click", function (event) {
        if (!hasActiveFilters()) {
            event.preventDefault();
        }
    });

    updateExportButtonState();
    table.columns.adjust();
});
