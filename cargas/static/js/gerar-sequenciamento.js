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

        const dataFim = dataInicio;

        const ensureModal = () => {
            let modal = document.getElementById("modalMontagem");
            if (!modal) {
                modal = document.createElement("div");
                modal.id = "modalMontagem";
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
                        <h3 style="margin:0;font:600 18px/1.2 system-ui">Selecionar carga para Montagem</h3>
                        <button id="fecharModalMontagem" style="border:0;background:#f5f5f5;padding:8px 12px;border-radius:8px;cursor:pointer">Fechar</button>
                    </div>
                    <div id="modalMontagemBody" style="padding:12px 20px;overflow:auto"></div>
                    <div style="padding:14px 20px;border-top:1px solid #eee;display:flex;gap:10px;justify-content:flex-end">
                        <button id="confirmarCargaMontagem" style="background:#2563eb;color:#fff;border:0;padding:10px 16px;border-radius:10px;font-weight:600;cursor:pointer">Confirmar</button>
                    </div>
                `;

                modal.appendChild(box);
                document.body.appendChild(modal);

                document.getElementById("fecharModalMontagem").onclick = () => modal.remove();
            }
            return modal;
        };

        try {
            const resp = await fetch(`api/buscar-carretas-base/?data_inicio=${encodeURIComponent(dataInicio)}&data_fim=${encodeURIComponent(dataFim)}`);
            if (!resp.ok) throw new Error("Erro ao buscar cargas");
            const payload = await resp.json();

            const lista = Array.isArray(payload?.cargas?.cargas) ? payload.cargas.cargas : [];
            const celulas = Array.isArray(payload?.cargas?.celulas) ? payload.cargas.celulas : [];

            const grupos = lista
                .filter(item => item?.presente_no_carreta === '✅')
                .reduce((acc, item) => {
                    const key = item.carga || "Sem carga";
                    (acc[key] ||= []).push(item);
                    return acc;
                }, {});

            const modal = ensureModal();
            const body = document.getElementById("modalMontagemBody");
            body.innerHTML = "";

            const wrap = document.createElement("div");
            wrap.style.display = "grid";
            wrap.style.gap = "14px";

            Object.entries(grupos).forEach(([cargaNome, itens]) => {
                const card = document.createElement("div");
                card.classList.add("card-carga-montagem");
                Object.assign(card.style, {
                    border: "1px solid #eee",
                    borderRadius: "10px",
                    padding: "12px",
                });

                const header = document.createElement("label");
                header.style.display = "flex";
                header.style.alignItems = "center";
                header.style.gap = "10px";
                header.style.marginBottom = "8px";

                const chk = document.createElement("input");
                chk.type = "checkbox";
                chk.name = "cargaMontagem";
                chk.value = cargaNome;
                chk.checked = true; // Marca todos os checkboxes
                chk.onchange = e => {
                    const card = e.target.closest(".card-carga-montagem");
                    // Quando desmarcar a carga, desmarcar todas as células dessa carga
                    if (!e.target.checked) {
                        card.querySelectorAll('input[name="celulaMontagem"]').forEach(cel => {
                            cel.checked = false;
                        });
                    } else {
                        // Quando marcar a carga, marcar todas as células dessa carga
                        card.querySelectorAll('input[name="celulaMontagem"]').forEach(cel => {
                            cel.checked = true;
                        });
                    }
                };

                header.appendChild(chk);
                header.appendChild(document.createTextNode(cargaNome));
                card.appendChild(header);

                const ul = document.createElement("ul");
                ul.style.margin = "0 0 0 28px";
                itens.forEach(it => {
                    const li = document.createElement("li");
                    li.textContent = `${it.codigo_recurso} — ${it.quantidade} un.`;
                    ul.appendChild(li);
                });
                card.appendChild(ul);

                if (celulas.length) {
                    const celWrap = document.createElement("div");
                    celWrap.style.margin = "8px 0 0 28px";

                    celulas.forEach(obj => {
                        const nome = obj?.celula ?? obj;
                        const lbl = document.createElement("label");
                        lbl.style.marginRight = "12px";

                        const ck = document.createElement("input");
                        ck.type = "checkbox";
                        ck.name = "celulaMontagem";
                        ck.value = nome;
                        ck.checked = true; // Marca todas as células por padrão
                        ck.onchange = e => {
                            // Se marcar uma célula e a carga não está marcada, marcar a carga
                            if (e.target.checked) {
                                const card = e.target.closest(".card-carga-montagem");
                                const chkCarga = card.querySelector('input[name="cargaMontagem"]');
                                if (chkCarga && !chkCarga.checked) {
                                    chkCarga.checked = true;
                                }
                            }
                        };

                        lbl.appendChild(ck);
                        lbl.appendChild(document.createTextNode(" " + nome));
                        celWrap.appendChild(lbl);
                    });

                    card.appendChild(celWrap);
                }

                wrap.appendChild(card);
            });

            body.appendChild(wrap);

            document.getElementById("confirmarCargaMontagem").onclick = async () => {
                const selecionadas = document.querySelectorAll('input[name="cargaMontagem"]:checked');
                if (selecionadas.length === 0) {
                    alert("Selecione ao menos uma carga.");
                    return;
                }

                const btnConfirmar = document.getElementById("confirmarCargaMontagem");
                btnConfirmar.disabled = true;
                btnConfirmar.innerHTML = 'Confirmando...';

                try {
                    // Coleta cada carga com suas respectivas células
                    const cargasComCelulas = Array.from(selecionadas).map(chk => {
                        const card = chk.closest(".card-carga-montagem");
                        const celulas = Array.from(
                            card.querySelectorAll('input[name="celulaMontagem"]:checked')
                        ).map(cel => cel.value);
                        
                        return {
                            nome: chk.value,
                            celulas: celulas
                        };
                    });

                    const payloadEnvio = {
                        data_inicio: dataInicio,
                        cargas: cargasComCelulas
                    };

                    const r = await fetch("api/imprimir-etiquetas-montagem/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payloadEnvio),
                    });

                    if (!r.ok) {
                        alert("Erro ao imprimir etiquetas de montagem.");
                        return;
                    }

                    const data = await r.json();
                    alert(`Total de impressões: ${data.payload}`);
                    // document.getElementById("modalMontagem").remove();
                } catch (error) {
                    console.error(error);
                    alert("Erro ao processar a solicitação.");
                } finally {
                    btnConfirmar.disabled = false;
                    btnConfirmar.innerHTML = 'Confirmar';
                }
            };

        } catch (e) {
            console.error(e);
            alert("Erro ao carregar cargas para montagem.");
        } finally {
            btnGerarEtiquetas.disabled = false;
        }

    } else if (setor === 'pintura') {
        // abrir um modal mostrando as cargas e as carretas logo abaixo de cada carga

        // carga 1
        //  carreta 1 - 2 un.
        //  carreta 2 - 3 un.
        //      celula 1
        //      celula 2
        //      celula 3

        // carga 2
        //  carreta 1 - 2 un.
        //  carreta 2 - 3 un.
        //      celula 1
        //      celula 2
        //      celula 3

        // ao lado de cada carga terá um checkbox para marcar
        // será enviado para o backend apenas a carga escolhida e a dataInicio.
        // terá também um grupo de itens com chckbox, podendo escolher mais de 1 contendo as celulas

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
            const celulas = Array.isArray(payload?.cargas?.celulas)
                ? payload.cargas.celulas
                : Array.isArray(payload?.celulas)
                ? payload.celulas
                : [];

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
                
                card.classList.add("card-carga-pintura");

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

                if (celulas.length) {
                    const celWrap = document.createElement("div");
                    celWrap.style.margin = "8px 0 0 28px";

                    const celTitulo = document.createElement("div");
                    celTitulo.textContent = "Células:";
                    celTitulo.style.fontSize = "12px";
                    celTitulo.style.marginBottom = "4px";
                    celWrap.appendChild(celTitulo);

                    const celList = document.createElement("div");
                    celList.style.display = "flex";
                    celList.style.flexWrap = "wrap";
                    celList.style.gap = "6px 12px";

                    celulas.forEach(obj => {
                        const celNome = obj?.celula ?? obj; // aceita {celula: 'X'} ou 'X'

                        const lbl = document.createElement("label");
                        lbl.style.display = "flex";
                        lbl.style.alignItems = "center";
                        lbl.style.gap = "4px";
                        lbl.style.fontSize = "12px";

                        const ck = document.createElement("input");
                        ck.type = "checkbox";
                        ck.name = "celulaPintura";
                        ck.value = celNome;

                        lbl.appendChild(ck);
                        lbl.appendChild(document.createTextNode(celNome));
                        celList.appendChild(lbl);
                    });

                    celWrap.appendChild(celList);
                    card.appendChild(celWrap);
                }

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

            // NOVO: pega apenas as células marcadas dentro do card da carga selecionada
            const cardSelecionado = selecionada.closest(".card-carga-pintura");
            const celulasSelecionadas = cardSelecionado
                ? Array.from(cardSelecionado.querySelectorAll('input[name="celulaPintura"]:checked')).map(el => el.value)
                : [];

            document.getElementById("confirmarCargaPintura").innerHTML = 'Imprimindo...';
            document.getElementById("confirmarCargaPintura").disabled = true;

            const payload = {
                data_inicio: dataInicio,
                carga: selecionada.value,
                // NOVO: adiciona as células escolhidas na mesma estrutura
                celulas: celulasSelecionadas,
            };

            try {
                const r = await fetch("api/imprimir-etiquetas-pintura/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                let bodyMsg = "";
                try {
                    const ct = r.headers.get("content-type") || "";
                    if (ct.includes("application/json")) {
                        const data = await r.json();
                        bodyMsg = typeof data === "string" ? data : JSON.stringify(data, null, 2);
                    } else {
                        bodyMsg = (await r.text()) || "(sem corpo)";
                    }
                    } catch {
                        bodyMsg = "(falha ao ler corpo da resposta)";
                    }

                    if (!r.ok) {
                    throw new Error(`Falha ao confirmar carga (${r.status})\n${bodyMsg}`);
                }

                alert(`Total de impressões: ${bodyMsg.payload}`);

                document.getElementById("confirmarCargaPintura").innerHTML = 'Confirmar';
                document.getElementById("confirmarCargaPintura").disabled = false;

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