export async function confirmarInicioOrdem(currentOrdemId) {
    try {
        Swal.fire({
            title: 'Verificando quantidade pendente...',
            text: 'Aguarde enquanto verificamos se a ordem pode ser iniciada.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            },
        });

        const response = await fetch(`/montagem/api/verificar-qt-restante/?ordem_id=${currentOrdemId}`);
        if (!response.ok) {
            const err = await response.json();
            throw err;
        }
        const data = await response.json();
        Swal.close();

        if (data.ordens.length === 0) {
            throw new Error("Ordem não encontrada.");
        }

        const ordem = data.ordens[0];
        if (ordem.restante === 0.0) {
            throw new Error("Essa ordem já foi totalmente produzida. Não é possível iniciá-la novamente.");
        }

        // Se chegou até aqui, pode iniciar a ordem
        return await iniciarOrdem(currentOrdemId);
    } catch (error) {
        console.error('Erro ao verificar quantidade pendente:', error);

        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Não foi possível verificar a quantidade pendente. Tente novamente.',
        });

        return false;
    }
}

async function iniciarOrdem(ordemId) {
    try {
        Swal.fire({
            title: 'Iniciando...',
            text: 'Por favor, aguarde enquanto a ordem está sendo iniciada.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            },
        });

        const response = await fetch("/montagem/api/ordens/atualizar-status/", {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: "iniciada",
                ordem_id: ordemId
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw err;
        }
        await response.json();
        Swal.close();

        // Fecha o modal de confirmação
        const modalElement = document.getElementById('confirmModal');
        const confirmModal = bootstrap.Modal.getInstance(modalElement);
        confirmModal.hide();

        Swal.fire({
            icon: 'success',
            title: 'Sucesso!',
            text: 'A ordem foi iniciada com sucesso.'
        });

        return true;
    } catch (error) {
        console.error('Erro ao iniciar a ordem:', error);

        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: error.message || 'Ocorreu um erro ao tentar iniciar a ordem. Tente novamente.',
        });
        return false;
    }
}