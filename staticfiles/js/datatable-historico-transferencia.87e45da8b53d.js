$(document).ready(function () {
    function format(d) {
        return (
            "<dl>" +
            "<dt>RPA:</dt>" +
            "<dd>" + (d.rpa || "-") + "</dd>" +
            "</dl>"
        );
    }

    const filtros = {
        dataSolicitacaoInicio: $("#data_solicitacao_inicio"),
        dataSolicitacaoFim: $("#data_solicitacao_fim"),
        dataEntregaInicio: $("#data_entrega_inicio"),
        dataEntregaFim: $("#data_entrega_fim"),
        chaveInnovaro: $("#chave_innovaro"),
        codigoItem: $("#codigo_item"),
    };
    const exportarCsv = $("#exportar_csv");

    function atualizarLinkExportacao() {
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

        const queryString = params.toString();
        exportarCsv.attr(
            "href",
            "/almox/historico/transferencia/exportar-csv/" +
                (queryString ? `?${queryString}` : "")
        );
    }

    function hasActiveFilters() {
        return [
            filtros.dataSolicitacaoInicio.val(),
            filtros.dataSolicitacaoFim.val(),
            filtros.dataEntregaInicio.val(),
            filtros.dataEntregaFim.val(),
            filtros.chaveInnovaro.val(),
            filtros.codigoItem.val(),
        ].some((valor) => (valor || "").trim() !== "");
    }

    function atualizarEstadoBotaoExportacao() {
        const ativo = hasActiveFilters();
        exportarCsv.attr("href", ativo ? exportarCsv.attr("href") : "#");
        exportarCsv.toggleClass("disabled", !ativo);
        exportarCsv.attr("aria-disabled", ativo ? "false" : "true");
        if (ativo) {
            atualizarLinkExportacao();
        }
    }

    const table = $("#execucaoTable").DataTable({
        processing: true,
        serverSide: true,
        autoWidth: false,
        ajax: {
            url: "/almox/api/historico/processa-historico-transferencia/",
            type: "POST",
            data: function (d) {
                d.data_solicitacao_inicio = filtros.dataSolicitacaoInicio.val();
                d.data_solicitacao_fim = filtros.dataSolicitacaoFim.val();
                d.data_entrega_inicio = filtros.dataEntregaInicio.val();
                d.data_entrega_fim = filtros.dataEntregaFim.val();
                d.chave_innovaro = filtros.chaveInnovaro.val();
                d.codigo_item = filtros.codigoItem.val();
            },
        },
        columns: [
            {
                data: "rpa",
                orderable: false,
                defaultContent: "",
                render: function (data, type, row) {
                    const texto = data || "-";
                    return (
                        '<button type="button" class="btn btn-sm btn-link text-decoration-none p-0 me-2 toggle-details">+</button>' +
                        texto
                    );
                }
            },
            { data: "chave_innovaro", orderable: false, defaultContent: "" },
            { data: "data_solicitacao", orderable: false },
            { data: "item", orderable: false },
            { data: "quantidade", orderable: false },
            { data: "deposito_destino__nome", orderable: false },
            { data: "funcionario__nome", orderable: false },
            { data: "obs", orderable: false, defaultContent: "" },
            { data: "entregue_por__nome", orderable: false, defaultContent: "" },
            { data: "data_entrega", orderable: false, defaultContent: "" },
            {
                data: "status",
                orderable: false,
                render: function (data) {
                    if (data === "Entregue") {
                        return '<span class="badge bg-success">Entregue</span>';
                    }
                    return '<span class="badge bg-warning text-dark">Pendente</span>';
                },
            },
        ],
        order: [[2, "desc"]],
        language: {
            search: "Procurar",
            processing: "Carregando...",
            zeroRecords: "Nenhum registro encontrado",
            emptyTable: "Nenhum registro encontrado",
        },
        columnDefs: [
            { targets: 0, width: "140px" },
            { targets: 1, width: "170px" },
            { targets: 2, width: "140px" },
            { targets: 4, width: "90px" },
            { targets: 8, width: "130px" },
            { targets: 9, width: "140px" },
            { targets: 10, width: "110px" },
        ],
    });

    $("#execucaoTable tbody").on("click", ".toggle-details", function () {
        const tr = $(this).closest("tr");
        const row = table.row(tr);
        const botao = $(this);

        if (row.child.isShown()) {
            row.child.hide();
            tr.removeClass("shown");
            botao.text("+");
        } else {
            row.child(format(row.data())).show();
            tr.addClass("shown");
            botao.text("-");
        }
    });

    $("#execucaoTable tbody").on("click", "td", function (event) {
        if ($(event.target).hasClass("toggle-details")) {
            return;
        }

        const colunaIndex = table.cell(this).index()?.column;
        if (colunaIndex !== 0) {
            return;
        }

        let tr = $(this).closest("tr");
        let row = table.row(tr);
        let botao = tr.find(".toggle-details");

        if (row.child.isShown()) {
            row.child.hide();
            tr.removeClass("shown");
            botao.text("+");
        } else {
            row.child(format(row.data())).show();
            tr.addClass("shown");
            botao.text("-");
        }
    });

    $("#aplicar_filtros").on("click", function () {
        atualizarEstadoBotaoExportacao();
        table.ajax.reload(null, true);
    });

    $("#limpar_filtros").on("click", function () {
        Object.values(filtros).forEach(function (campo) {
            campo.val("");
        });
        atualizarEstadoBotaoExportacao();
        table.ajax.reload(null, true);
    });

    exportarCsv.on("click", function (event) {
        if (!hasActiveFilters()) {
            event.preventDefault();
        }
    });

    table.on("draw.dt", function () {
        table.columns.adjust();
    });

    $(window).on("resize", function () {
        table.columns.adjust();
    });

    atualizarEstadoBotaoExportacao();
    table.columns.adjust();
});
