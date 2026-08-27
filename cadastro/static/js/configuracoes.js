document.addEventListener('DOMContentLoaded', () => {
    const modalListaEl = document.getElementById('modalDestinatariosNotificacao');
    const modalFormEl = document.getElementById('modalFormDestinatarioNotificacao');
    const modalLista = new bootstrap.Modal(modalListaEl);
    const modalForm = new bootstrap.Modal(modalFormEl);

    const tituloModalLista = document.getElementById('modalDestinatariosNotificacaoLabel');
    const tabela = document.getElementById('tabelaDestinatariosNotificacao');
    const form = document.getElementById('formDestinatarioNotificacao');
    const inputId = document.getElementById('destinatarioNotificacaoId');
    const inputTipo = document.getElementById('destinatarioNotificacaoTipo');
    const inputNome = document.getElementById('destinatarioNotificacaoNome');
    const inputTelefone = document.getElementById('destinatarioNotificacaoTelefone');
    const inputAtivo = document.getElementById('destinatarioNotificacaoAtivo');
    const tituloModalForm = document.getElementById('modalFormDestinatarioNotificacaoLabel');
    const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;

    let tipoAtual = null;
    let rotuloAtual = '';

    function escapeHtml(texto) {
        const div = document.createElement('div');
        div.textContent = texto ?? '';
        return div.innerHTML;
    }

    async function carregarDestinatarios() {
        tabela.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Carregando...</td></tr>';

        try {
            const response = await fetch(`/cadastro/api/destinatarios-notificacao/?tipo=${encodeURIComponent(tipoAtual)}`);
            const data = await response.json();

            if (!data.destinatarios || data.destinatarios.length === 0) {
                tabela.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Nenhum destinatário cadastrado.</td></tr>';
                return;
            }

            tabela.innerHTML = data.destinatarios.map(destinatario => `
                <tr>
                    <td class="fw-semibold">${escapeHtml(destinatario.nome)}</td>
                    <td>${escapeHtml(destinatario.telefone)}</td>
                    <td>
                        ${destinatario.ativo
                            ? '<span class="badge text-bg-success">Ativo</span>'
                            : '<span class="badge text-bg-secondary">Inativo</span>'}
                    </td>
                    <td class="text-end">
                        <div class="d-inline-flex gap-2">
                            <button type="button" class="btn btn-outline-primary btn-sm btn-editar-destinatario"
                                data-id="${destinatario.id}"
                                data-nome="${escapeHtml(destinatario.nome)}"
                                data-telefone="${escapeHtml(destinatario.telefone)}"
                                data-ativo="${destinatario.ativo}">
                                Editar
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm btn-excluir-destinatario" data-id="${destinatario.id}">
                                Excluir
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        } catch (error) {
            tabela.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-4">Erro ao carregar destinatários.</td></tr>';
        }
    }

    function abrirModalLista(tipo, rotulo) {
        tipoAtual = tipo;
        rotuloAtual = rotulo;
        tituloModalLista.textContent = `Destinatários - ${rotulo}`;
        modalLista.show();
    }

    function abrirModalForm({ id = '', nome = '', telefone = '', ativo = true } = {}) {
        inputId.value = id;
        inputTipo.value = tipoAtual;
        inputNome.value = nome;
        inputTelefone.value = telefone;
        inputAtivo.checked = ativo === true || ativo === 'true';
        tituloModalForm.textContent = id ? 'Editar destinatário' : `Adicionar destinatário - ${rotuloAtual}`;

        modalLista.hide();
        modalForm.show();
    }

    document.querySelectorAll('.btn-abrir-destinatarios').forEach(botao => {
        botao.addEventListener('click', () => {
            abrirModalLista(botao.dataset.tipo, botao.dataset.rotulo);
        });
    });

    modalListaEl.addEventListener('show.bs.modal', () => {
        if (tipoAtual) {
            carregarDestinatarios();
        }
    });

    document.getElementById('btnAbrirAddDestinatario').addEventListener('click', () => {
        abrirModalForm();
    });

    tabela.addEventListener('click', (event) => {
        const btnEditar = event.target.closest('.btn-editar-destinatario');
        if (btnEditar) {
            abrirModalForm({
                id: btnEditar.dataset.id,
                nome: btnEditar.dataset.nome,
                telefone: btnEditar.dataset.telefone,
                ativo: btnEditar.dataset.ativo,
            });
            return;
        }

        const btnExcluir = event.target.closest('.btn-excluir-destinatario');
        if (btnExcluir) {
            excluirDestinatario(btnExcluir.dataset.id);
        }
    });

    async function excluirDestinatario(id) {
        const confirmacao = await Swal.fire({
            title: 'Excluir destinatário?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Excluir',
            cancelButtonText: 'Cancelar',
        });

        if (!confirmacao.isConfirmed) return;

        try {
            const response = await fetch(`/cadastro/delete/destinatario-notificacao/${id}/`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': csrfToken },
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Erro ao excluir.');
            }

            carregarDestinatarios();
        } catch (error) {
            Swal.fire({ icon: 'error', title: 'Erro', text: error.message });
        }
    }

    modalFormEl.addEventListener('hidden.bs.modal', () => {
        if (!modalListaEl.classList.contains('show')) {
            modalLista.show();
        }
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        const id = inputId.value;
        const payload = {
            nome: inputNome.value.trim(),
            telefone: inputTelefone.value.trim(),
            ativo: inputAtivo.checked,
            tipo_notificacao: inputTipo.value,
        };

        const url = id
            ? `/cadastro/edit/destinatario-notificacao/${id}/`
            : '/cadastro/add/destinatario-notificacao/';
        const method = id ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Erro ao salvar.');
            }

            modalForm.hide();
        } catch (error) {
            Swal.fire({ icon: 'error', title: 'Erro', text: error.message });
        }
    });
});
