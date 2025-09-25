export function confirmarInicioOrdem(currentOrdemId){
    Swal.fire({
        title: 'Verificando quantidade pendente...',
        text: 'Aguarde enquanto verificamos se a ordem pode ser iniciada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        },
    });

    // Primeiro, verificar se a ordem tem quantidade pendente
    fetch(`/montagem/api/verificar-qt-restante/?ordem_id=${currentOrdemId}`)
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        Swal.close(); // Fecha o loading

        if (data.ordens.length === 0) {
            throw new Error("Ordem não encontrada.");
        }

        const ordem = data.ordens[0]; // Pegamos a primeira ordem retornada
        if (ordem.restante === 0.0) {
            throw new Error("Essa ordem já foi totalmente produzida. Não é possível iniciá-la novamente.");
        }

        // Se chegou até aqui, pode iniciar a ordem
        return iniciarOrdem(currentOrdemId);
    })
    .catch(error => {
        console.error('Erro ao verificar quantidade pendente:', error);

        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Não foi possível verificar a quantidade pendente. Tente novamente.',
        });

        return false;
    });
}

function iniciarOrdem(ordemId) {

    Swal.fire({
        title: 'Iniciando...',
        text: 'Por favor, aguarde enquanto a ordem está sendo iniciada.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        },
    });

    fetch("/montagem/api/ordens/atualizar-status/", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            status: "iniciada",
            ordem_id: ordemId
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        Swal.close(); // Fecha o loading

        // Fecha o modal de confirmação
        const modalElement = document.getElementById('confirmModal');
        const confirmModal = bootstrap.Modal.getInstance(modalElement);
        confirmModal.hide();

        // Mostra mensagem de sucesso
        Swal.fire({
            icon: 'success',
            title: 'Sucesso!',
            text: 'A ordem foi iniciada com sucesso.'
        })
        return true;
    })
    .catch(error => {
        console.error('Erro ao iniciar a ordem:', error);

        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Ocorreu um erro ao tentar iniciar a ordem. Tente novamente.',
        });
        return false;
    });
}
