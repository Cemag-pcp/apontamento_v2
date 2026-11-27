// Finalizar retrabalho da pintura registrando o consumo.
//
// O modal usa o mesmo formulário do controle de pintura (/pintura/controle/),
// mas grava em ConsumoRetrabalhoPintura, ligado ao retrabalho e à peça. O
// retrabalho só é finalizado junto com o consumo (mesma requisição). No lote,
// o modal abre uma peça por vez; os dados gerais (fornecedor, cor, lote,
// pintor...) ficam preenchidos para a próxima e só as quantidades são limpas.

// Fatores de conversão L -> Kg (os mesmos da tela /pintura/controle/)
const CONVERSOES_CONSUMO_RETRABALHO = [
    { litrosId: "controleQuantidadeTinta", kgsId: "controleQuantidadeTintaKg", kgPorLitro: 1.1 },
    { litrosId: "controleCatalizador", kgsId: "controleCatalizadorKg", kgPorLitro: 0.988 },
    { litrosId: "controleDiluente", kgsId: "controleDiluenteKg", kgPorLitro: 1.086 },
];

let filaConsumoRetrabalho = [];
let totalConsumoRetrabalho = 0;
let finalizadosConsumoRetrabalho = 0;

function valorCampoConsumo(id) {
    return (document.getElementById(id).value || "").trim();
}

function formatarDecimalConsumo(valor) {
    if (!Number.isFinite(valor)) return "";
    return (Math.round(valor * 1000) / 1000).toFixed(3).replace(/\.?0+$/, "");
}

function converterCampoConsumo(origem, destino, fator, paraKg) {
    const valor = parseFloat(String(origem.value).replace(",", "."));
    if (!Number.isFinite(valor)) {
        destino.value = "";
        return;
    }
    destino.value = formatarDecimalConsumo(paraKg ? valor * fator : valor / fator);
}

function limparQuantidadesConsumo() {
    CONVERSOES_CONSUMO_RETRABALHO.forEach((c) => {
        document.getElementById(c.litrosId).value = "";
        document.getElementById(c.kgsId).value = "";
    });
}

function preencherItemConsumo(item) {
    const posicao = totalConsumoRetrabalho > 1
        ? ` (${totalConsumoRetrabalho - filaConsumoRetrabalho.length + 1} de ${totalConsumoRetrabalho})`
        : "";
    document.getElementById("consumo-retrabalho-peca").textContent = `${item.peca || ""}${posicao}`;

    if (!valorCampoConsumo("controleData")) {
        const hoje = new Date();
        hoje.setMinutes(hoje.getMinutes() - hoje.getTimezoneOffset());
        document.getElementById("controleData").value = hoje.toISOString().slice(0, 10);
    }

    // Cor da peça retrabalhada, se existir na lista
    const selectCor = document.getElementById("controleCor");
    const opcao = Array.from(selectCor.options).find(
        (o) => o.value && item.cor && o.value.toLowerCase() === String(item.cor).toLowerCase()
    );
    if (opcao) selectCor.value = opcao.value;

    limparQuantidadesConsumo();
}

// Abre o modal de consumo para uma ou mais peças (itens: [{id, peca, cor}])
function abrirConsumoRetrabalho(itens) {
    filaConsumoRetrabalho = (itens || []).filter((i) => i && i.id);
    if (!filaConsumoRetrabalho.length) return;
    totalConsumoRetrabalho = filaConsumoRetrabalho.length;
    finalizadosConsumoRetrabalho = 0;

    document.getElementById("controlePinturaForm").reset();
    preencherItemConsumo(filaConsumoRetrabalho[0]);
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modal-consumo-retrabalho-pintura")).show();
}

function payloadConsumoRetrabalho() {
    return {
        data: valorCampoConsumo("controleData"),
        fornecedor: valorCampoConsumo("controleFornecedor"),
        cor: valorCampoConsumo("controleCor"),
        lote: valorCampoConsumo("controleLote"),
        quantidade_tinta: valorCampoConsumo("controleQuantidadeTinta"),
        catalizador: valorCampoConsumo("controleCatalizador"),
        diluente: valorCampoConsumo("controleDiluente"),
        viscosidade: valorCampoConsumo("controleViscosidade"),
        pintor: valorCampoConsumo("controlePintor"),
        pistola: valorCampoConsumo("controlePistola"),
        qnt_demaos: valorCampoConsumo("controleDemaos"),
        pressao_ar_1: valorCampoConsumo("controlePressao1"),
        pressao_ar_2: valorCampoConsumo("controlePressao2"),
        pressao_ar_3: valorCampoConsumo("controlePressao3"),
    };
}

function atualizarListasRetrabalho() {
    if (typeof buscarItensRetrabalho === "function") buscarItensRetrabalho(1);
    if (typeof buscarItensEmProcesso === "function") buscarItensEmProcesso(1);
    if (typeof buscarItensInspecionadosRetrabalho === "function") buscarItensInspecionadosRetrabalho(1);
}

document.addEventListener("DOMContentLoaded", function () {
    const modalEl = document.getElementById("modal-consumo-retrabalho-pintura");
    const botaoSalvar = document.getElementById("btn-salvar-consumo-retrabalho");
    if (!modalEl || !botaoSalvar) return;

    CONVERSOES_CONSUMO_RETRABALHO.forEach((c) => {
        const litros = document.getElementById(c.litrosId);
        const kgs = document.getElementById(c.kgsId);
        litros.addEventListener("input", () => converterCampoConsumo(litros, kgs, c.kgPorLitro, true));
        kgs.addEventListener("input", () => converterCampoConsumo(kgs, litros, c.kgPorLitro, false));
    });

    botaoSalvar.addEventListener("click", function () {
        const item = filaConsumoRetrabalho[0];
        if (!item) return;

        const tinta = parseFloat(valorCampoConsumo("controleQuantidadeTinta").replace(",", "."));
        if (!Number.isFinite(tinta) || tinta <= 0) {
            Swal.fire({ icon: "warning", title: "Informe a quantidade de tinta consumida (L ou Kg)." });
            return;
        }

        botaoSalvar.disabled = true;
        botaoSalvar.querySelector(".spinner-border").style.display = "block";

        fetch("/pintura/api/finalizar-retrabalho-pintura-consumo/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
            },
            body: JSON.stringify({ id: item.id, consumo: payloadConsumoRetrabalho() }),
        })
            .then((response) => response.json().then((data) => {
                if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);
                return data;
            }))
            .then(() => {
                filaConsumoRetrabalho.shift();
                finalizadosConsumoRetrabalho += 1;

                if (filaConsumoRetrabalho.length) {
                    // Próxima peça do lote: mantém os dados gerais, limpa as quantidades
                    preencherItemConsumo(filaConsumoRetrabalho[0]);
                    document.getElementById("controleQuantidadeTinta").focus();
                    return;
                }

                bootstrap.Modal.getInstance(modalEl).hide();
                Swal.fire({
                    icon: "success",
                    title: finalizadosConsumoRetrabalho > 1
                        ? `${finalizadosConsumoRetrabalho} retrabalhos finalizados`
                        : "Retrabalho finalizado",
                    text: "Consumo registrado.",
                    timer: 2500,
                    showConfirmButton: false,
                });
            })
            .catch((error) => {
                Swal.fire({ icon: "error", title: "Erro ao finalizar", text: error.message });
            })
            .finally(() => {
                botaoSalvar.disabled = false;
                botaoSalvar.querySelector(".spinner-border").style.display = "none";
            });
    });

    // Fechou o modal (concluiu ou cancelou): o que faltou do lote continua em processo
    modalEl.addEventListener("hidden.bs.modal", function () {
        if (finalizadosConsumoRetrabalho > 0) atualizarListasRetrabalho();
        filaConsumoRetrabalho = [];
        finalizadosConsumoRetrabalho = 0;
        document.getElementById("controlePinturaForm").reset();
    });
});
