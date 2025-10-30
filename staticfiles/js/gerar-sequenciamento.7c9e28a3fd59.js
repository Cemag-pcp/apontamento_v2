import { renderCallendar } from './full-calendar.js';

function carregarBaseCarretas() {
    const dataInicio = document.getElementById('data-inicio').value;
    const dataFim = document.getElementById('data-fim').value;

    return fetch(`api/buscar-carretas-base/?data_inicio=${dataInicio}&data_fim=${dataFim}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        popularTabelaResumo(data.cargas.cargas); // Chama a função para popular a tabela
    })
    .catch(error => {
        console.error('Erro ao carregar os dados:', error);
    });
}

function popularTabelaResumo(cargas) {
    const tabelaResumo = document.getElementById('tabelaResumo');

    if (cargas.length === 0) {
        tabelaResumo.innerHTML = "<tr><td colspan='4'>Nenhum dado disponível</td></tr>";
        return;
    }

    tabelaResumo.innerHTML = ""; // Limpa a tabela antes de popular os novos dados

    cargas.forEach(item => {
        const linha = document.createElement('tr');
        linha.innerHTML = `
            <td>${item.data_carga}</td>
            <td>${item.codigo_recurso}</td>
            <td>${item.quantidade}</td>
            <td>${item.presente_no_carreta}</td>
        `;
        tabelaResumo.appendChild(linha);
    });
}

function gerarArquivos(){
    const dataInicio = document.getElementById("data-inicio").value;
    const dataFim = document.getElementById("data-fim").value;
    const setor = document.getElementById("setorSelect").value;

    if (!dataInicio || !dataFim || !setor) {
        alert("Preencha todos os campos!");
        return;
    }

    const url = `api/gerar-arquivos/?data_inicio=${dataInicio}&data_fim=${dataFim}&setor=${setor}`;

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error("Erro ao gerar sequenciamento.");
            }
            return response.blob();
        })
        .then(blob => {
            const urlBlob = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = urlBlob;
            a.download = "sequenciamento.zip";
            document.body.appendChild(a);
            a.click();
            a.remove();
        })
        .catch(error => console.error("Erro:", error));
}

function gerarPlanejamento() {
    const btngerarPlanejamento = document.getElementById("gerarPlanejamento");
    const dataInicio = document.getElementById("data-inicio").value;
    const dataFim = document.getElementById("data-fim").value;
    const setor = document.getElementById("setorSelect").value;

    btngerarPlanejamento.disabled = true;
    btngerarPlanejamento.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando...';

    const url = `api/gerar-dados-ordem/?data_inicio=${dataInicio}&data_fim=${dataFim}&setor=${setor}`;

    fetch(url, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
    })
    .then(response => {
        return response.json().then(data => {
            if (!response.ok) {
                throw data; // Lança o erro para ser tratado no catch
            }
            return data;
        });
    })
    .then(data => {
        alert("Planejamento gerado com sucesso!");
        renderCallendar();
    })
    .catch(error => {
        console.error("Erro ao criar ordens:", error);
        if (error && error.error) {
            alert("Erro ao gerar planejamento: " + error.error);
        } else {
            alert("Erro inesperado ao processar a solicitação.");
        }
    })
    .finally(() => {
        btngerarPlanejamento.innerHTML = '<i class="fas fa-save"></i> Gerar Planejamento';
        btngerarPlanejamento.disabled = false;
    });
}

async function gerarEtiquetaQrCode() {
    const btnGerarEtiquetas = document.getElementById("gerarEtiquetas");
    const dataInicio = document.getElementById("data-inicio").value;
    const setor = document.getElementById("setorSelect").value;

    console.log(setor);

    if (setor === 'montagem') {
        btnGerarEtiquetas.disabled = true;
        btnGerarEtiquetas.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando...';

        const url = `api/imprimir-etiquetas/?data_carga=${dataInicio}`;

        fetch(url, {
            method: "GET",
            headers: { "Content-Type": "application/json" },
        })
        .then(response => {
            return response.json().then(data => {
                if (!response.ok) {
                    throw data; // Lança o erro para ser tratado no catch
                }
                return data;
            });
        })
        .then(data => {
            alert("Etiquetas geradas com sucesso!");
        })
        .catch(error => {
            console.error("Erro ao gerar etiquetas:", error);
            if (error && error.error) {
                alert("Erro ao gerar etiquetas: " + error.error);
            } else {
                alert("Erro inesperado ao processar a solicitação.");
            }
        })
        .finally(() => {
            btnGerarEtiquetas.innerHTML = '<i class="fas fa-qrcode"></i> Gerar Etiquetas';
        });

    } else if (setor === 'pintura') {
        // abrir um modal mostrando as cargas e as carretas logo abaixo de cada carga
        // carga 1
        //  carreta 1 - 2 un.
        //  carreta 2 - 3 un.
        // carga 2
        //  carreta 1 - 2 un.
        //  carreta 2 - 3 un.
        // ao lado de cada carga terá um checkbox para marcar
        // será enviado para o backend apenas a carga escolhida e a dataInicio.

        const dataFim = dataInicio;
        btnGerarEtiquetas.disabled = true;

        // cria (ou reaproveita) um modal simples
        const ensureModal = () => {
            let modal = document.getElementById("modalPintura");
            if (!modal) {
            modal = document.createElement("div");
            modal.id = "modalPintura";
            Object.assign(modal.style, {
                position: "fixed",
                inset: "0",
                background: "rgba(0,0,0,.45)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: "9999",
            });

            const box = document.createElement("div");
            box.id = "modalPinturaBox";
            Object.assign(box.style, {
                background: "#fff",
                width: "min(720px, 92vw)",
                maxHeight: "80vh",
                borderRadius: "12px",
                boxShadow: "0 10px 30px rgba(0,0,0,.2)",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
            });
            box.innerHTML = `
                <div style="padding:16px 20px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
                <h3 style="margin:0;font:600 18px/1.2 system-ui">Selecionar carga para Pintura</h3>
                <button id="fecharModalPintura" style="border:0;background:#f5f5f5;padding:8px 12px;border-radius:8px;cursor:pointer">Fechar</button>
                </div>
                <div id="modalPinturaBody" style="padding:12px 20px;overflow:auto"></div>
                <div style="padding:14px 20px;border-top:1px solid #eee;display:flex;gap:10px;justify-content:flex-end">
                <button id="confirmarCargaPintura" style="background:#10b981;color:#fff;border:0;padding:10px 16px;border-radius:10px;font-weight:600;cursor:pointer">Confirmar</button>
                </div>
            `;
            modal.appendChild(box);
            document.body.appendChild(modal);

            document.getElementById("fecharModalPintura").onclick = () => {
                modal.remove();
            };
            }
            return modal;
        };

        try {
            // busca carretas/cargas
            const resp = await fetch(`api/buscar-carretas-base/?data_inicio=${encodeURIComponent(dataInicio)}&data_fim=${encodeURIComponent(dataFim)}`);
            if (!resp.ok) throw new Error(`Falha ao buscar cargas (${resp.status})`);
            const payload = await resp.json();
            const lista = Array.isArray(payload?.cargas?.cargas) ? payload.cargas.cargas : [];

            // filtra apenas as presentes e agrupa por nome da carga
            const grupos = lista
            .filter(item => item?.presente_no_carreta === '✅')
            .reduce((acc, item) => {
                const key = item.carga || "Sem carga";
                (acc[key] ||= []).push(item);
                return acc;
            }, {});

            const modal = ensureModal();
            const body = document.getElementById("modalPinturaBody");
            body.innerHTML = "";

            if (Object.keys(grupos).length === 0) {
            body.innerHTML = `<p style="margin:8px 0 16px">Nenhuma carga presente no período informado.</p>`;
            } else {
            // monta a lista: carga (checkbox) e, abaixo, carretas com quantidades
            const wrap = document.createElement("div");
            wrap.style.display = "grid";
            wrap.style.gap = "14px";

            Object.entries(grupos).forEach(([cargaNome, itens]) => {
                const card = document.createElement("div");
                Object.assign(card.style, {
                border: "1px solid #eee",
                borderRadius: "10px",
                padding: "12px",
                });

                // header da carga com checkbox (apenas uma pode ser marcada)
                const header = document.createElement("label");
                header.style.display = "flex";
                header.style.alignItems = "center";
                header.style.gap = "10px";
                header.style.marginBottom = "8px";

                const chk = document.createElement("input");
                chk.type = "checkbox";
                chk.name = "cargaEscolhida";
                chk.value = cargaNome;
                chk.addEventListener("change", (e) => {
                // garante seleção única
                if (e.target.checked) {
                    document.querySelectorAll('input[name="cargaEscolhida"]').forEach(el => {
                    if (el !== e.target) el.checked = false;
                    });
                }
                });

                const titulo = document.createElement("strong");
                titulo.textContent = cargaNome;

                header.appendChild(chk);
                header.appendChild(titulo);
                card.appendChild(header);

                // lista de carretas (codigo_recurso) e quantidades
                const ul = document.createElement("ul");
                ul.style.margin = "0 0 0 28px";
                ul.style.padding = "0";
                ul.style.listStyle = "disc";

                itens.forEach(it => {
                const li = document.createElement("li");
                li.style.margin = "4px 0";
                li.textContent = `${it.codigo_recurso} — ${it.quantidade} un.`;
                ul.appendChild(li);
                });

                card.appendChild(ul);
                wrap.appendChild(card);
            });

            body.appendChild(wrap);
            }

            // ação do confirmar
            document.getElementById("confirmarCargaPintura").onclick = async () => {
            const selecionada = /** @type {HTMLInputElement|null} */(document.querySelector('input[name="cargaEscolhida"]:checked'));
            if (!selecionada) {
                alert("Selecione uma carga para confirmar.");
                return;
            }

            const payload = {
                data_inicio: dataInicio,
                carga: selecionada.value
            };

            try {
                const r = await fetch("api/imprimir-etiquetas-pintura/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (!r.ok) {
                    const txt = await r.text().catch(() => "");
                    throw new Error(`Falha ao confirmar carga (${r.status}) ${txt}`);
                }

                alert("Carga confirmada com sucesso!");
                document.getElementById("modalPintura")?.remove();
            } catch (err) {
                console.error(err);
                alert("Não foi possível confirmar. Tente novamente.");
            }
            };

        } catch (err) {
            console.error(err);
            alert("Erro ao carregar cargas para pintura. Verifique as datas e tente novamente.");
        } finally {
            btnGerarEtiquetas.disabled = false;
        }

    } else {
        console.log("Escolha montagem ou pintura")
    }

}

document.addEventListener('DOMContentLoaded', () => {
    const btPesquisar = document.getElementById('pesquisarDados');
    const btngerarSequenciamento = document.getElementById('gerarSequenciamento');
    const btngerarPlanejamento = document.getElementById('gerarPlanejamento');
    const btnGerarEtiquetas = document.getElementById('gerarEtiquetas');

    btPesquisar.addEventListener('click', () => {
        btPesquisar.disabled = true; // Desabilita o botão antes de carregar os dados
        btPesquisar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pesquisando...';
    
        carregarBaseCarretas().finally(() => {
            btPesquisar.disabled = false; // Reabilita o botão após a execução
            btngerarSequenciamento.disabled = false;
            btngerarPlanejamento.disabled = false;
            btnGerarEtiquetas.disabled = false;
            btPesquisar.innerHTML = '<i class="fas fa-search"></i> Pesquisar';

        });
    });

    btngerarSequenciamento.addEventListener('click', () => {
        btngerarSequenciamento.disabled = true; // Desabilita o botão antes de carregar os dados
        
        gerarArquivos().finally(() => {
            btngerarSequenciamento.disabled = false; // Reabilita o botão após a execução
        });
    });

    btngerarPlanejamento.addEventListener("click", gerarPlanejamento);
    btnGerarEtiquetas.addEventListener("click", gerarEtiquetaQrCode);

});