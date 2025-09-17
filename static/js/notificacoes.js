document.addEventListener("DOMContentLoaded", function() {
    // --- Funções de UI ---
    function criarItemNotificacao(n) {
        let iconClass = "bi-info-circle text-primary";
        switch (n.tipo) {
            case "alerta": iconClass = "bi-exclamation-triangle text-warning"; break;
            case "aviso": iconClass = "bi-exclamation-circle text-info"; break;
            case "erro": iconClass = "bi-x-circle text-danger"; break;
        }
        const rota = n.rota || "#";
        const lidoClass = n.lido ? "" : "fw-bold";

        console.log(n.titulo);
        
        return `
            <a class="dropdown-item ${lidoClass}" href="${rota}" id="notificacao-${n.id}">
                <div class="d-flex align-items-start">
                    <div class="me-2"><i class="bi ${iconClass}"></i></div>
                    <div>
                        <strong>${n.titulo}</strong><br>
                        <small>${n.mensagem}</small>
                        <div class="text-muted small mt-1">${n.tempo}</div>
                    </div>
                </div>
            </a>
        `;
    }

    function atualizarBadge(quantidade) {
        const badge = document.getElementById("notificationBadge");
        if (badge) {
            if (quantidade > 0) {
                badge.innerText = quantidade;
                badge.style.display = "";
            } else {
                badge.style.display = "none";
            }
        }
    }

    // --- Lógica do Dropdown ---
    const bell = document.getElementById("notificationBell");
    const dropdown = document.getElementById("notificationDropdown");
    bell.addEventListener("click", function(event) {
        event.stopPropagation();
        dropdown.style.display = dropdown.style.display === "block" ? "none" : "block";
    });
    document.addEventListener("click", function() {
        if (dropdown.style.display === "block") {
            dropdown.style.display = "none";
        }
    });

    // --- Lógica do WebSocket com Reconexão ---
    let socket;
    let retryTimeout = 1000; // Começa com 1 segundo

    function connect() {
        const wsProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
        socket = new WebSocket(wsProtocol + window.location.host + "/ws/notificacoes/");

        socket.onopen = function(e) {
            console.log("WebSocket conectado com sucesso!");
            retryTimeout = 1000; // Reseta o timer de tentativa ao conectar
        };

        socket.onmessage = function(e) {
            const data = JSON.parse(e.data);
            const list = document.getElementById("notificationList");

            function criarItemNotificacao(n) {
                let iconClass = "bi-info-circle text-primary";
                switch (n.tipo) {
                    case "alerta": iconClass = "bi-exclamation-triangle text-warning"; break;
                    case "aviso": iconClass = "bi-exclamation-circle text-info"; break;
                    case "erro": iconClass = "bi-x-circle text-danger"; break;
                    case "sucesso": iconClass = "bi-check-circle text-success"; break;
                }
                const lidoClass = n.lido ? "" : "nao-lida"; // Ex: .nao-lida { background-color: #f8f9fa; }

                return `
                    <div class="dropdown-item-wrapper ${lidoClass}" id="notificacao-${n.id}">
                        <a class="dropdown-item" href="${n.rota || '#'}">
                            <div class="d-flex align-items-start">
                                <div class="me-2"><i class="bi ${iconClass}"></i></div>
                                <div>
                                    <strong>${n.titulo}</strong><br>
                                    ${n.mensagem}
                                    <div class="text-muted small">${n.tempo}</div>
                                </div>
                            </div>
                        </a>
                    </div>
                `;
            }


            if (data.type === "carga_inicial") {
                const payload = data.payload;
                atualizarBadge(payload.quantidade);
                list.innerHTML = "";
                payload.notificacoes.forEach(n => list.insertAdjacentHTML("beforeend", criarItemNotificacao(n)));
            } else if (data.type === "nova_notificacao") {
                console.log("Recebida nova notificação.");
                const payload = data.payload;
                
                atualizarBadge(payload.quantidade);
                
                const itemHtml = criarItemNotificacao(payload.notificacao);
                list.insertAdjacentHTML("afterbegin", itemHtml);

            } else if (data.type === "atualizacao_notificacao") {
                console.log("Recebida atualização de notificação.");
                const payload = data.payload;
                
                // 1. Atualiza o contador
                atualizarBadge(payload.quantidade);

                // 2. Encontra o elemento antigo na lista
                const notificacaoId = payload.notificacao.id;
                const oldElement = document.getElementById(`notificacao-${notificacaoId}`);

                if (oldElement) {
                    // 3. Gera o novo HTML com os dados atualizados
                    const novoItemHtml = criarItemNotificacao(payload.notificacao);
                    
                    // 4. Substitui completamente o elemento antigo pelo novo
                    oldElement.outerHTML = novoItemHtml;
                }
            }
        };

        socket.onclose = function(e) {
            console.error(`WebSocket fechado. Tentando reconectar em ${retryTimeout / 1000}s...`);
            // Espera antes de tentar reconectar
            setTimeout(connect, retryTimeout);
            // Aumenta o tempo de espera para a próxima tentativa (Exponential Backoff)
            retryTimeout = Math.min(retryTimeout * 2, 30000); // Dobra o tempo, com máximo de 30s
        };

        socket.onerror = function(err) {
            console.error("Erro no WebSocket:", err);
            // O evento 'onclose' será chamado logo após 'onerror', então a reconexão já será tratada lá.
            socket.close();
        };
    }

    // Inicia a primeira conexão
    connect();
});