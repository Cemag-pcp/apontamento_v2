document.addEventListener('DOMContentLoaded', function() {

    const Toast = Swal.mixin({
        toast: true,
        position: "bottom-end",
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
          toast.onmouseenter = Swal.stopTimer;
          toast.onmouseleave = Swal.resumeTimer;
        }
      });
      
    let conjuntoParaRemover = null;

    // Quando clicar em "Remover" dentro da tabela
    const tabela = document.getElementById('tabela-conjuntos');
    tabela.addEventListener('click', function(event) {
        if (event.target && event.target.classList.contains('abrir-modal-remover')) {
            const button = event.target;
            conjuntoParaRemover = button.closest('tr');
            const modal = new bootstrap.Modal(document.getElementById('modal-conjuntos-inspecionar'));
            modal.show();
        }
    });

    // Quando clicar no botão "Remover" do modal
    document.getElementById('remove-conjunto').addEventListener('click', function() {
        if (!conjuntoParaRemover) return;

        const botaoRemover = this;
        const codigo = conjuntoParaRemover.querySelector('td:nth-child(1)').textContent.trim();

        botaoRemover.disabled = true;
        const originalHTML = botaoRemover.innerHTML;
        botaoRemover.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Removendo...
        `;

        fetch(`/inspecao/api/conjuntos-inspecionados/${codigo}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            }
        })
        .then(response => {
            if (response.ok) {
                conjuntoParaRemover.remove();
                const modal = bootstrap.Modal.getInstance(document.getElementById('modal-conjuntos-inspecionar'));
                modal.hide();
                Toast.fire({
                    icon: "success",
                    title: "Conjunto removido com sucesso"
                });
            } else {
                Toast.fire({
                    icon: "error",
                    title: "Erro ao remover o conjunto"
                });
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            Toast.fire({
                icon: "error",
                title: "Erro de conexão"
            });
        })
        .finally(() => {
            // Habilita de novo e volta o botão ao normal
            botaoRemover.disabled = false;
            botaoRemover.innerHTML = originalHTML;
        });
    });

    const btnAbrirModal = document.getElementById('btn-abrir-modal-adicionar');
    const modalAdicionar = new bootstrap.Modal(document.getElementById('modal-adicionar-conjuntos'));

    btnAbrirModal.addEventListener('click', function() {
        modalAdicionar.show();
    });

    document.getElementById('adicionar-conjunto').addEventListener('click', function() {

        const botaoAdicionar = this;
        const codigo = document.getElementById('codigo').value.trim();
        const descricao = document.getElementById('descricao').value.trim();

        botaoAdicionar.disabled = true;
        const originalHTML = botaoAdicionar.innerHTML;
        botaoAdicionar.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Adicionando...
        `;

        if (!codigo || !descricao) {
            Toast.fire({
                icon: "error",
                title: "Preencha todos os campos"
            });
            return;
        }

        fetch('/inspecao/api/conjuntos-inspecionados/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: JSON.stringify({
                codigo: codigo,
                descricao: descricao
            })
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Erro ao adicionar conjunto.');
        })
        .then(data => {
            // Adiciona nova linha na tabela sem reload
            const tabela = document.getElementById('tabela-conjuntos').querySelector('tbody');
            const novaLinha = document.createElement('tr');
            novaLinha.innerHTML = `
                <td>${data.codigo}</td>
                <td>${data.descricao}</td>
                <td>
                    <div class="dropdown">
                        <button class="btn btn-danger dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                            Remover
                        </button>
                        <ul class="dropdown-menu">
                            <li><button class="dropdown-item abrir-modal-remover" type="button">Remover</button></li>
                        </ul>
                    </div>
                </td>
            `;
            tabela.appendChild(novaLinha);

            // Fecha modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modal-adicionar-conjuntos'));
            modal.hide();

            // Limpa inputs
            document.getElementById('codigo').value = '';
            document.getElementById('descricao').value = '';

            Toast.fire({
                icon: "success",
                title: "Conjunto adicionado com sucesso!"
            });
        })
        .catch(error => {
            console.error('Erro:', error);
            Toast.fire({
                icon: "error",
                title: error
            });
        })
        .finally(() => {
            // Habilita de novo e volta o botão ao normal
            botaoAdicionar.disabled = false;
            botaoAdicionar.innerHTML = originalHTML;
        });
    });
});