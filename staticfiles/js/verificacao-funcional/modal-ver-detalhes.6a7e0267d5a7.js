function atribuirDadosModalVerDetalhes(){
    document.querySelectorAll(".historico-verificacao-funcional").forEach(btn => {
        btn.addEventListener("click", async function () {
            btn.disabled = true;
            const spinner = this.querySelector(".spinner-border");
            if (spinner) spinner.style.display = "inline-block";

            // pega data-attributes do botão
            const id = this.dataset.id;
            const peca = this.dataset.peca;
            const tipo = this.dataset.tipo;
            const cor = this.dataset.cor;
            const dataInicial = this.dataset.dataInicial;
            const dataAtualizacao = this.dataset.dataAtualizacao;

            // preenche dados da peça
            document.getElementById("modalPeca").textContent = peca;
            document.getElementById("modalTipo").textContent = tipo;
            document.getElementById("modalCor").textContent = cor;
            document.getElementById("modalDataInicial").textContent = dataInicial;
            document.getElementById("modalDataAtualizacao").textContent = dataAtualizacao;

            try {
                const resp = await fetch(`/inspecao/api/detalhes-verificacao-funcional/${id}/`);
                const data = await resp.json();

                // função para colocar badge colorida
                function formatBadge(valor){
                    if(valor.toLowerCase() === "aprovado") return `<span class="badge bg-success">${valor}</span>`;
                    if(valor.toLowerCase() === "reprovado") return `<span class="badge bg-danger">${valor}</span>`;
                    return `<span class="badge bg-secondary">${valor}</span>`;
                }
                
                console.log(data);
                document.getElementById("modalStatus").innerHTML = formatBadge(data.status_registro);
                document.getElementById("modalObservacao").textContent = data.observacao || "Nenhuma observação registrada.";
                document.getElementById("modalImagem").src = data.imagem_url || "#";
                document.getElementById("img-link").href = data.imagem_url || "#";
                if (!data.imagem_url){
                    document.getElementById("modalImagem").alt = "Nenhuma imagem registrada.";
                    document.getElementById("img-link").style.display = "none";
                }else{
                    document.getElementById("modalImagem").alt = "Imagem do Teste";
                    document.getElementById("img-link").style.display = "inline";
                }

                document.getElementById("modalAderencia").innerHTML = formatBadge(data.aderencia);
                document.getElementById("modalTonalidade").innerHTML = formatBadge(data.tonalidade);
                document.getElementById("modalPolimerizacao").innerHTML = formatBadge(data.polimerizacao);

                document.getElementById("modalEsp1").textContent = data.espessura_camada_1 ? data.espessura_camada_1 + ' µm' : "Não medido";
                document.getElementById("modalEsp2").textContent = data.espessura_camada_2 ? data.espessura_camada_2 + ' µm' : "Não medido";
                document.getElementById("modalEsp3").textContent = data.espessura_camada_3 ? data.espessura_camada_3 + ' µm' : "Não medido";
                document.getElementById("modalMedia").textContent = data.media_espessura ? data.media_espessura.toFixed(2) + ' µm' : "Não medido";
                document.getElementById("modalMetaEsp").textContent = data.meta_espessura;
                document.getElementById("modalResultadoEsp").textContent = data.resultado_espessura;

            } catch (error) {
                console.error(error);
                document.getElementById("modalExtra").innerHTML = `<p class="text-danger">Erro ao carregar detalhes.</p>`;
            } finally {
                if (spinner) spinner.style.display = "none";
                btn.disabled = false;
                new bootstrap.Modal(document.getElementById("detalhesModal")).show();
            }
        });
    });
}
