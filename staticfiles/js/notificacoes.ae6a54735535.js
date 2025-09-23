document.addEventListener('DOMContentLoaded', function () {
    let currentPage = 1;
    const notificationsContainer = document.getElementById('notifications-container');
    const unreadCountSpan = document.getElementById('unread-count');
    const loadMoreContainer = document.getElementById('load-more-container');
    const loadMoreBtn = document.getElementById('load-more-btn');
    // O 'initialLoader' original que vem do HTML será removido na primeira carga.
    // Vamos recriá-lo quando necessário.
    const spinnerHtml = `
        <div class="text-center" id="loading-spinner">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>`;

    // Função para criar o HTML de um card de notificação (sem alterações)
    function createNotificationCard(n) {
        let iconHtml = '';
        let borderColorClass = '';
        switch (n.tipo) {
            case 'sucesso': iconHtml = '<i class="bi bi-check-circle text-success fs-5"></i>'; borderColorClass = 'border-success'; break;
            case 'info': iconHtml = '<i class="bi bi-info-circle text-primary fs-5"></i>'; borderColorClass = 'border-primary'; break;
            case 'aviso': iconHtml = '<i class="bi bi-exclamation-triangle text-warning fs-5"></i>'; borderColorClass = 'border-warning'; break;
            case 'erro': iconHtml = '<i class="bi bi-x-circle text-danger fs-5"></i>'; borderColorClass = 'border-danger'; break;
            default: iconHtml = '<i class="bi bi-bell text-secondary fs-5"></i>';
        }
        const hasRoute = n.rota_acesso && n.rota_acesso !== '#';
        const lidoClass = n.lido ? '' : 'border-start border-4 ' + borderColorClass;
        const novoBadge = n.lido ? '' : '<span class="badge bg-secondary ms-2">Nova</span>';
        const clicavelClass = hasRoute ? 'card-clicavel' : '';
        const actionIcon = hasRoute ? '<div class="ms-3"><i class="bi bi-arrow-right-circle fs-4 text-muted"></i></div>' : '';
        const rotaHref = hasRoute ? n.rota_acesso : 'javascript:void(0);';
        const isLink = hasRoute;
        const cardContent = `<div class="card mb-3 ${lidoClass} ${clicavelClass}" id="notificacao-${n.id}"><div class="card-body d-flex align-items-center"><div class="flex-shrink-0 me-3">${iconHtml}</div><div class="flex-grow-1"><div class="d-flex align-items-center justify-content-between"><div><strong>${n.titulo}</strong> ${novoBadge}</div></div><div class="text-muted small my-1">${n.mensagem}</div><span class="text-muted small">${n.tempo_atras}</span></div>${actionIcon}</div></div>`;
        return isLink ? `<a href="${rotaHref}" style="text-decoration: none; color: inherit;">${cardContent}</a>` : cardContent;
    }

    function updateUnreadCount(count) {
        unreadCountSpan.textContent = `${count} ${count === 1 ? 'notificação não lida' : 'notificações não lidas'}`;
    }

    function markAsRead(ids) {
        if (ids.length === 0) return;
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        fetch('/core/api/notificacoes/marcar-como-lidas/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids })
        })
        .then(response => response.ok ? response.json() : Promise.reject("Falha ao marcar como lido"))
        .then(data => {
            console.log(data.message);
            ids.forEach(id => {
                const cardWrapper = document.getElementById(`notificacao-${id}`)?.closest('div.card');
                if (cardWrapper) {
                    cardWrapper.classList.remove('border-start', 'border-4', 'border-primary', 'border-success', 'border-warning', 'border-danger');
                    const badge = cardWrapper.querySelector('.badge');
                    if (badge) badge.remove();
                }
            });
        }).catch(error => console.error(error));
    }

    function fetchNotifications(page, onComplete) {
        // Se for a primeira página, limpa o conteúdo atual antes de buscar.
        // Isso é importante para a função de atualização.
        if (page === 1) {
            notificationsContainer.innerHTML = spinnerHtml;
            loadMoreContainer.style.display = 'none';
        }

        fetch(`/core/api/notificacoes/?page=${page}`)
            .then(response => response.json())
            .then(data => {
                // Se for a primeira página, remove o spinner antes de adicionar o novo conteúdo.
                if (page === 1) {
                    notificationsContainer.innerHTML = '';
                }
                
                if (data.notificacoes.length > 0) {
                    const unreadIds = data.notificacoes.filter(n => !n.lido).map(n => n.id);
                    data.notificacoes.forEach(n => {
                        notificationsContainer.insertAdjacentHTML('beforeend', createNotificationCard(n));
                    });
                    markAsRead(unreadIds);
                    const newUnreadCount = Math.max(0, data.unread_count - unreadIds.length);
                    updateUnreadCount(newUnreadCount);
                } else if (page === 1) {
                    notificationsContainer.innerHTML = '<div class="card mb-3"><div class="card-body text-center text-muted">Você não tem nenhuma notificação.</div></div>';
                    updateUnreadCount(0);
                }
                
                if (data.has_next) {
                    loadMoreContainer.style.display = 'block';
                } else {
                    loadMoreContainer.style.display = 'none';
                }
            })
            .catch(error => {
                console.error("Erro ao buscar notificações:", error);
                notificationsContainer.innerHTML = '<div class="alert alert-danger">Ocorreu um erro ao carregar as notificações.</div>';
            })
            .finally(() => {
                if (onComplete) onComplete();
            });
    }

    // --- Event Listeners ---
    loadMoreBtn.addEventListener('click', function () {
        const originalButtonText = this.innerHTML;
        this.disabled = true;
        this.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Carregando...`;
        currentPage++;
        fetchNotifications(currentPage, () => {
            this.disabled = false;
            this.innerHTML = originalButtonText;
        });
    });

    // ### NOVO CÓDIGO AQUI ###
    const updateNotification = document.getElementById('update-notification');
    if (updateNotification) {
        updateNotification.addEventListener('click', function () {
            // Desabilita o botão para evitar cliques múltiplos
            this.disabled = true;
            
            // Reseta a página para a primeira
            currentPage = 1;

            // Chama a função para buscar as notificações.
            // A função agora internamente limpa o container e mostra o spinner.
            // O callback reabilita o botão quando a operação terminar.
            fetchNotifications(currentPage, () => {
                this.disabled = false;
            });
        });
    }

    // --- Carga Inicial ---
    // A chamada inicial agora também usa a lógica de exibir o spinner.
    fetchNotifications(currentPage);
});
