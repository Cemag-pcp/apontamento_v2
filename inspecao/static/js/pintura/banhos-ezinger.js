document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("form-banho-ezinger");
    const modalElement = document.getElementById("modal-banho-ezinger");
    const registrosBody = document.getElementById("ezinger-registros-body");
    const spinner = document.getElementById("spinner-banho-ezinger");
    const textoBotao = document.getElementById("texto-botao-banho-ezinger");
    const dataRegistroInput = document.getElementById("registrado_em");
    const registroIdInput = document.getElementById("registro_id");
    const modalRegistrarAdicaoElement = document.getElementById("modal-registrar-adicao-ezinger");
    const registrarAdicaoRegistroIdInput = document.getElementById("registrar-adicao-registro-id");
    const registrarAdicaoDescricao = document.getElementById("registrar-adicao-descricao");
    const confirmarRegistrarAdicaoButton = document.getElementById("confirmar-registrar-adicao");
    const spinnerRegistrarAdicao = document.getElementById("spinner-registrar-adicao");
    const textoRegistrarAdicao = document.getElementById("texto-registrar-adicao");
    const chartCanvas = document.getElementById("ezinger-percentuais-chart");
    const acumuladoChartCanvas = document.getElementById("ezinger-acumulado-chart");
    const consumoMensalChartCanvas = document.getElementById("ezinger-consumo-mensal-chart");
    const paginacaoContainer = document.getElementById("ezinger-paginacao");
    let percentuaisChart = null;
    let acumuladoChart = null;
    let consumoMensalChart = null;
    let registros = [];
    let paginaAtual = 1;
    const REGISTROS_POR_PAGINA = 10;

    if (!form || !modalElement || !registrosBody) {
        return;
    }

    const TARGET_AK_L95 = 6;
    const CAPACITY_AK_L95 = 5950;
    const AK_FACTOR = 1.53;
    const ADDITIVE_FACTOR = 0.15;
    const TARGET_M_FE_212 = 1.2;
    const CAPACITY_M_FE_212 = 3950;
    const M_FE_212_FACTOR = 0.23;

    const inputIds = [
        "desengraxante_amostra_1",
        "desengraxante_amostra_2",
        "desengraxante_amostra_3",
        "fosfatizante_amostra_1",
        "fosfatizante_amostra_2",
        "fosfatizante_amostra_3",
    ];

    const getCsrfToken = () => {
        const token = document.cookie
            .split(";")
            .map((item) => item.trim())
            .find((item) => item.startsWith("csrftoken="));
        return token ? decodeURIComponent(token.split("=")[1]) : "";
    };

    const formatNumber = (value) => Number(value).toLocaleString("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });

    const formatPercent = (value) => `${formatNumber(value)}%`;
    const getCurrentDateTimeLocal = () => {
        const now = new Date();
        const offset = now.getTimezoneOffset();
        const local = new Date(now.getTime() - offset * 60000);
        return local.toISOString().slice(0, 16);
    };

    const setText = (id, value) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    };

    const parsePtBrDate = (value) => {
        const [datePart] = value.split(" ");
        const [day, month, year] = datePart.split("/");
        return `${year}-${month}-${day}`;
    };
    const parsePtBrMonth = (value) => {
        const [datePart] = value.split(" ");
        const [, month, year] = datePart.split("/");
        return `${year}-${month}`;
    };
    const parsePtBrDateTimeToLocalInput = (value) => {
        const [datePart, timePart] = value.split(" ");
        const [day, month, year] = datePart.split("/");
        return `${year}-${month}-${day}T${(timePart || "00:00").slice(0, 5)}`;
    };

    const readValues = (prefix) => [1, 2, 3]
        .map((index) => document.getElementById(`${prefix}_${index}`).value)
        .filter((value) => value !== "")
        .map((value) => Number(String(value).replace(",", ".")));

    const average = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
    const calculateAddition = (currentPercent, targetPercent, capacity) =>
        Number((Math.abs((currentPercent / 100) - (targetPercent / 100)) * capacity).toFixed(2));

    const calculate = () => {
        const desengraxante = readValues("desengraxante_amostra");
        const fosfatizante = readValues("fosfatizante_amostra");

        let mediaDesengraxante = null;
        let akL95Atual = null;
        if (desengraxante.length === 3) {
            mediaDesengraxante = Number(average(desengraxante).toFixed(2));
            akL95Atual = Number((mediaDesengraxante * AK_FACTOR).toFixed(2));
        }

        let mediaFosfatizante = null;
        let mFe212Atual = null;
        if (fosfatizante.length === 3) {
            mediaFosfatizante = Number(average(fosfatizante).toFixed(2));
            mFe212Atual = Number((mediaFosfatizante * M_FE_212_FACTOR).toFixed(2));
        }

        let akL95Adicionar = null;
        let aditivoAdicionar = null;
        if (akL95Atual !== null && akL95Atual < TARGET_AK_L95) {
            akL95Adicionar = calculateAddition(akL95Atual, TARGET_AK_L95, CAPACITY_AK_L95);
            aditivoAdicionar = Number((akL95Adicionar * ADDITIVE_FACTOR).toFixed(2));
        }

        let mFe212Adicionar = null;
        if (mFe212Atual !== null && mFe212Atual < TARGET_M_FE_212) {
            mFe212Adicionar = calculateAddition(mFe212Atual, TARGET_M_FE_212, CAPACITY_M_FE_212);
        }

        return {
            mediaDesengraxante,
            akL95Atual,
            mediaFosfatizante,
            mFe212Atual,
            akL95Adicionar,
            aditivoAdicionar,
            mFe212Adicionar,
        };
    };

    const updateSummary = () => {
        const result = calculate();

        setText(
            "desengraxante_media_display",
            result.mediaDesengraxante !== null ? formatNumber(result.mediaDesengraxante) : "Sem valores"
        );
        setText(
            "ak_l95_atual_display",
            result.akL95Atual !== null ? formatNumber(result.akL95Atual) : "Sem valor de média"
        );
        setText(
            "fosfatizante_media_display",
            result.mediaFosfatizante !== null ? formatNumber(result.mediaFosfatizante) : "Sem valores"
        );
        setText(
            "m_fe_212_atual_display",
            result.mFe212Atual !== null ? formatNumber(result.mFe212Atual) : "Sem valor de média"
        );

        setText(
            "analise_ak_l95_resumo",
            result.akL95Atual !== null ? formatPercent(result.akL95Atual) : "Sem valor de média"
        );
        setText(
            "analise_m_fe_212_resumo",
            result.mFe212Atual !== null ? formatPercent(result.mFe212Atual) : "Sem valor de média"
        );

        setText(
            "ak_l95_adicionar_display",
            result.akL95Adicionar !== null ? formatNumber(result.akL95Adicionar) : "Limite acima do especificado"
        );
        setText(
            "aditivo_adicionar_display",
            result.aditivoAdicionar !== null ? formatNumber(result.aditivoAdicionar) : "Limite acima do especificado"
        );
        setText(
            "m_fe_212_adicionar_display",
            result.mFe212Adicionar !== null ? formatNumber(result.mFe212Adicionar) : "Limite acima do especificado"
        );
    };

    const renderPagination = (totalRegistros) => {
        if (!paginacaoContainer) {
            return;
        }

        if (!totalRegistros) {
            paginacaoContainer.innerHTML = "";
            return;
        }

        const totalPaginas = Math.max(1, Math.ceil(totalRegistros / REGISTROS_POR_PAGINA));
        const inicio = (paginaAtual - 1) * REGISTROS_POR_PAGINA + 1;
        const fim = Math.min(paginaAtual * REGISTROS_POR_PAGINA, totalRegistros);

        paginacaoContainer.innerHTML = `
            <div class="ezinger-pagination-info">
                Exibindo ${inicio}-${fim} de ${totalRegistros} registros
            </div>
            <div class="btn-group">
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ezinger-pagina-anterior" ${paginaAtual === 1 ? "disabled" : ""}>
                    Anterior
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" disabled>
                    Página ${paginaAtual} de ${totalPaginas}
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ezinger-pagina-proxima" ${paginaAtual === totalPaginas ? "disabled" : ""}>
                    Próxima
                </button>
            </div>
        `;

        const botaoAnterior = document.getElementById("ezinger-pagina-anterior");
        const botaoProxima = document.getElementById("ezinger-pagina-proxima");

        if (botaoAnterior) {
            botaoAnterior.addEventListener("click", () => {
                if (paginaAtual > 1) {
                    paginaAtual -= 1;
                    renderRows(registros);
                }
            });
        }

        if (botaoProxima) {
            botaoProxima.addEventListener("click", () => {
                if (paginaAtual < totalPaginas) {
                    paginaAtual += 1;
                    renderRows(registros);
                }
            });
        }
    };

    const renderRows = (dados) => {
        if (!dados.length) {
            registrosBody.innerHTML = `
                <tr>
                    <td colspan="13" class="text-center text-muted py-4">Nenhum registro encontrado.</td>
                </tr>
            `;
            renderPagination(0);
            return;
        }

        const totalPaginas = Math.max(1, Math.ceil(dados.length / REGISTROS_POR_PAGINA));
        if (paginaAtual > totalPaginas) {
            paginaAtual = totalPaginas;
        }

        const inicio = (paginaAtual - 1) * REGISTROS_POR_PAGINA;
        const paginaDados = dados.slice(inicio, inicio + REGISTROS_POR_PAGINA);

        registrosBody.innerHTML = paginaDados.map((item) => `
            <tr>
                <td>${item.registrado_em}</td>
                <td>${item.registrado_por}</td>
                <td>${item.observacao ?? "-"}</td>
                <td>${item.desengraxante_media !== null ? formatNumber(item.desengraxante_media) : "-"}</td>
                <td>${item.desengraxante_acumulado !== null ? formatNumber(item.desengraxante_acumulado) : "-"}</td>
                <td>${item.ak_l95_atual !== null ? formatPercent(item.ak_l95_atual) : "-"}</td>
                <td>${item.fosfatizante_media !== null ? formatNumber(item.fosfatizante_media) : "-"}</td>
                <td>${item.fosfatizante_acumulado !== null ? formatNumber(item.fosfatizante_acumulado) : "-"}</td>
                <td>${item.m_fe_212_atual !== null ? formatPercent(item.m_fe_212_atual) : "-"}</td>
                <td>${item.ak_l95_adicionar !== null ? formatNumber(item.ak_l95_adicionar) : "Limite acima do especificado"}</td>
                <td>${item.aditivo_adicionar !== null ? formatNumber(item.aditivo_adicionar) : "Limite acima do especificado"}</td>
                <td>${item.m_fe_212_adicionar !== null ? formatNumber(item.m_fe_212_adicionar) : "Limite acima do especificado"}</td>
                <td>
                    <div class="d-flex align-items-center gap-2">
                    <button type="button" class="btn btn-outline-primary btn-sm ezinger-editar" data-id="${item.id}">
                        Editar
                    </button>
                    <button
                        type="button"
                        class="btn btn-sm ${item.adicao_registrada ? "btn-outline-success" : "btn-outline-secondary"} ezinger-registrar-adicao"
                        data-id="${item.id}"
                        title="${item.adicao_registrada ? `Adição registrada por ${item.adicao_registrada_por || "-"} em ${item.adicao_registrada_em || "-"}` : "Registrar adição"}"
                        ${item.adicao_registrada ? "disabled" : ""}
                    >
                        <i class="bi ${item.adicao_registrada ? "bi-check-circle-fill" : "bi-plus-circle"}"></i>
                    </button>
                    </div>
                </td>
            </tr>
        `).join("");

        registrosBody.querySelectorAll(".ezinger-editar").forEach((button) => {
            button.addEventListener("click", () => {
                const item = registros.find((registro) => String(registro.id) === button.dataset.id);
                if (!item) {
                    return;
                }

                if (registroIdInput) {
                    registroIdInput.value = item.id;
                }
                if (dataRegistroInput) {
                    dataRegistroInput.value = parsePtBrDateTimeToLocalInput(item.registrado_em);
                }

                document.getElementById("observacao").value = item.observacao && item.observacao !== "-" ? item.observacao : "";
                document.getElementById("desengraxante_amostra_1").value = item.desengraxante_amostras?.[0] ?? "";
                document.getElementById("desengraxante_amostra_2").value = item.desengraxante_amostras?.[1] ?? "";
                document.getElementById("desengraxante_amostra_3").value = item.desengraxante_amostras?.[2] ?? "";
                document.getElementById("fosfatizante_amostra_1").value = item.fosfatizante_amostras?.[0] ?? "";
                document.getElementById("fosfatizante_amostra_2").value = item.fosfatizante_amostras?.[1] ?? "";
                document.getElementById("fosfatizante_amostra_3").value = item.fosfatizante_amostras?.[2] ?? "";
                textoBotao.textContent = "Salvar edição";
                updateSummary();

                const modal = new bootstrap.Modal(modalElement);
                modal.show();
            });
        });

        registrosBody.querySelectorAll(".ezinger-registrar-adicao").forEach((button) => {
            button.addEventListener("click", () => {
                const item = registros.find((registro) => String(registro.id) === button.dataset.id);
                if (!item || item.adicao_registrada || !modalRegistrarAdicaoElement) {
                    return;
                }

                if (registrarAdicaoRegistroIdInput) {
                    registrarAdicaoRegistroIdInput.value = item.id;
                }

                if (registrarAdicaoDescricao) {
                    registrarAdicaoDescricao.textContent = `Confirma o registro da adição do banho de ${item.registrado_em}?`;
                }

                const modal = new bootstrap.Modal(modalRegistrarAdicaoElement);
                modal.show();
            });
        });

        renderPagination(dados.length);
    };

    const renderChart = (dados) => {
        if (!chartCanvas || typeof Chart === "undefined") {
            return;
        }

        const agrupadoPorDia = dados.reduce((acc, item) => {
            const dia = parsePtBrDate(item.registrado_em);
            if (!acc[dia]) {
                acc[dia] = {
                    akL95: [],
                    mFe212: [],
                };
            }

            if (item.ak_l95_atual !== null) {
                acc[dia].akL95.push(Number(item.ak_l95_atual));
            }
            if (item.m_fe_212_atual !== null) {
                acc[dia].mFe212.push(Number(item.m_fe_212_atual));
            }

            return acc;
        }, {});

        const labels = Object.keys(agrupadoPorDia).sort();
        const akL95Data = labels.map((label) => {
            const values = agrupadoPorDia[label].akL95;
            if (!values.length) {
                return null;
            }
            return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2));
        });
        const mFe212Data = labels.map((label) => {
            const values = agrupadoPorDia[label].mFe212;
            if (!values.length) {
                return null;
            }
            return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2));
        });

        if (percentuaisChart) {
            percentuaisChart.destroy();
        }

        percentuaisChart = new Chart(chartCanvas.getContext("2d"), {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "AK L95 (%)",
                        data: akL95Data,
                        borderColor: "#1d4ed8",
                        backgroundColor: "rgba(29, 78, 216, 0.18)",
                        tension: 0.25,
                        borderWidth: 2,
                        fill: false,
                    },
                    {
                        label: "M FE 212 (%)",
                        data: mFe212Data,
                        borderColor: "#15803d",
                        backgroundColor: "rgba(21, 128, 61, 0.18)",
                        tension: 0.25,
                        borderWidth: 2,
                        fill: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: "top",
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${formatNumber(context.parsed.y)}%`,
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: (value) => `${formatNumber(value)}%`,
                        },
                    },
                },
            },
        });
    };

    const renderAccumulatedChart = (dados) => {
        if (!acumuladoChartCanvas || typeof Chart === "undefined") {
            return;
        }

        const agrupadoPorDia = dados.reduce((acc, item) => {
            const dia = parsePtBrDate(item.registrado_em);
            if (!acc[dia]) {
                acc[dia] = {
                    akL95Adicionar: 0,
                    mFe212Adicionar: 0,
                };
            }

            acc[dia].akL95Adicionar += Number(item.ak_l95_adicionar || 0);
            acc[dia].mFe212Adicionar += Number(item.m_fe_212_adicionar || 0);

            return acc;
        }, {});

        const labels = Object.keys(agrupadoPorDia).sort();
        const akL95AdicionarData = labels.map((label) =>
            Number(agrupadoPorDia[label].akL95Adicionar.toFixed(2))
        );
        const mFe212AdicionarData = labels.map((label) =>
            Number(agrupadoPorDia[label].mFe212Adicionar.toFixed(2))
        );

        if (acumuladoChart) {
            acumuladoChart.destroy();
        }

        acumuladoChart = new Chart(acumuladoChartCanvas.getContext("2d"), {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "AK L95 adicionar",
                        data: akL95AdicionarData,
                        backgroundColor: "rgba(29, 78, 216, 0.75)",
                        borderColor: "#1d4ed8",
                        borderWidth: 1,
                    },
                    {
                        label: "M FE 212 adicionar",
                        data: mFe212AdicionarData,
                        backgroundColor: "rgba(21, 128, 61, 0.75)",
                        borderColor: "#15803d",
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: "top",
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${formatNumber(context.parsed.y)}`,
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => formatNumber(value),
                        },
                    },
                },
            },
        });
    };

    const renderMonthlyConsumptionChart = (dados) => {
        if (!consumoMensalChartCanvas || typeof Chart === "undefined") {
            return;
        }

        const agrupadoPorMes = dados.reduce((acc, item) => {
            const mes = parsePtBrMonth(item.registrado_em);
            if (!acc[mes]) {
                acc[mes] = {
                    hclConsumido: 0,
                    naohConsumido: 0,
                };
            }

            acc[mes].hclConsumido += Number(item.desengraxante_acumulado || 0);
            acc[mes].naohConsumido += Number(item.fosfatizante_acumulado || 0);

            return acc;
        }, {});

        const labels = Object.keys(agrupadoPorMes).sort();
        const hclData = labels.map((label) =>
            Number(agrupadoPorMes[label].hclConsumido.toFixed(2))
        );
        const naohData = labels.map((label) =>
            Number(agrupadoPorMes[label].naohConsumido.toFixed(2))
        );

        if (consumoMensalChart) {
            consumoMensalChart.destroy();
        }

        consumoMensalChart = new Chart(consumoMensalChartCanvas.getContext("2d"), {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "HCl consumido (mL)",
                        data: hclData,
                        backgroundColor: "rgba(217, 119, 6, 0.78)",
                        borderColor: "#b45309",
                        borderWidth: 1,
                    },
                    {
                        label: "NaOH consumido (mL)",
                        data: naohData,
                        backgroundColor: "rgba(8, 145, 178, 0.78)",
                        borderColor: "#0e7490",
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: "top",
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${formatNumber(context.parsed.y)} mL`,
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => `${formatNumber(value)} mL`,
                        },
                    },
                },
            },
        });
    };

    const loadRecords = async () => {
        registrosBody.innerHTML = `
            <tr>
                <td colspan="13" class="text-center text-muted py-4">Carregando registros...</td>
            </tr>
        `;

        try {
            const response = await fetch("/inspecao/api/banhos-ezinger/");
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || "Erro ao carregar registros.");
            }

            registros = result.dados || [];
            paginaAtual = 1;
            renderRows(registros);
            renderChart(registros);
            renderAccumulatedChart(registros);
            renderMonthlyConsumptionChart(registros);
        } catch (error) {
            registrosBody.innerHTML = `
                <tr>
                    <td colspan="13" class="text-center text-danger py-4">${error.message}</td>
                </tr>
            `;
            registros = [];
            renderPagination(0);
            renderChart([]);
            renderAccumulatedChart([]);
            renderMonthlyConsumptionChart([]);
        }
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const result = calculate();
        if (
            result.mediaDesengraxante === null ||
            result.mediaFosfatizante === null
        ) {
            window.alert("Preencha todas as amostras antes de confirmar.");
            return;
        }

        spinner.classList.remove("d-none");
        textoBotao.textContent = "Salvando...";

        try {
            const formData = new FormData(form);
            const response = await fetch("/inspecao/api/banhos-ezinger/salvar/", {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                },
                body: formData,
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Erro ao salvar registro.");
            }

            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
            }

            form.reset();
            updateSummary();
            await loadRecords();

            if (typeof Swal !== "undefined") {
                Swal.fire({
                    icon: "success",
                    title: registroIdInput && registroIdInput.value ? "Registro atualizado com sucesso" : "Registro salvo com sucesso",
                    timer: 1800,
                    showConfirmButton: false,
                });
            }
        } catch (error) {
            if (typeof Swal !== "undefined") {
                Swal.fire({
                    icon: "error",
                    title: "Erro ao salvar",
                    text: error.message,
                });
            } else {
                window.alert(error.message);
            }
        } finally {
            spinner.classList.add("d-none");
            textoBotao.textContent = "Confirmar";
        }
    });

    if (confirmarRegistrarAdicaoButton) {
        confirmarRegistrarAdicaoButton.addEventListener("click", async () => {
            const registroId = registrarAdicaoRegistroIdInput ? registrarAdicaoRegistroIdInput.value : "";
            if (!registroId) {
                return;
            }

            spinnerRegistrarAdicao?.classList.remove("d-none");
            if (textoRegistrarAdicao) {
                textoRegistrarAdicao.textContent = "Salvando...";
            }
            confirmarRegistrarAdicaoButton.disabled = true;

            try {
                const formData = new FormData();
                formData.append("registro_id", registroId);

                const response = await fetch("/inspecao/api/banhos-ezinger/registrar-adicao/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCsrfToken(),
                    },
                    body: formData,
                });

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Erro ao registrar adiÃ§Ã£o.");
                }

                const modal = bootstrap.Modal.getInstance(modalRegistrarAdicaoElement);
                if (modal) {
                    modal.hide();
                }

                if (registrarAdicaoRegistroIdInput) {
                    registrarAdicaoRegistroIdInput.value = "";
                }

                await loadRecords();

                if (typeof Swal !== "undefined") {
                    Swal.fire({
                        icon: "success",
                        title: "Adição registrada com sucesso",
                        timer: 1800,
                        showConfirmButton: false,
                    });
                }
            } catch (error) {
                if (typeof Swal !== "undefined") {
                    Swal.fire({
                        icon: "error",
                        title: "Erro ao registrar adiÃ§Ã£o",
                        text: error.message,
                    });
                } else {
                    window.alert(error.message);
                }
            } finally {
                spinnerRegistrarAdicao?.classList.add("d-none");
                if (textoRegistrarAdicao) {
                    textoRegistrarAdicao.textContent = "Confirmar";
                }
                confirmarRegistrarAdicaoButton.disabled = false;
            }
        });
    }

    modalElement.addEventListener("hidden.bs.modal", () => {
        form.reset();
        if (registroIdInput) {
            registroIdInput.value = "";
        }
        if (dataRegistroInput) {
            dataRegistroInput.value = getCurrentDateTimeLocal();
        }
        textoBotao.textContent = "Confirmar";
        updateSummary();
    });

    if (modalRegistrarAdicaoElement) {
        modalRegistrarAdicaoElement.addEventListener("hidden.bs.modal", () => {
            if (registrarAdicaoRegistroIdInput) {
                registrarAdicaoRegistroIdInput.value = "";
            }
            if (registrarAdicaoDescricao) {
                registrarAdicaoDescricao.textContent = "Esse registro será marcado como adição realizada.";
            }
            spinnerRegistrarAdicao?.classList.add("d-none");
            if (textoRegistrarAdicao) {
                textoRegistrarAdicao.textContent = "Confirmar";
            }
            if (confirmarRegistrarAdicaoButton) {
                confirmarRegistrarAdicaoButton.disabled = false;
            }
        });
    }

    inputIds.forEach((id) => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener("input", updateSummary);
        }
    });

    if (dataRegistroInput) {
        dataRegistroInput.value = getCurrentDateTimeLocal();
    }

    updateSummary();
    loadRecords();
});
