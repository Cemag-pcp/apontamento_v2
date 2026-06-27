import { carregarTabela, getOperadorById } from './datatable-list-operador.js';

let botaoClicado = null;

const modalEditOperador = new bootstrap.Modal(document.getElementById('editOperador'));
const modalDesativarOperador = new bootstrap.Modal(document.getElementById('desativarOperador'));
const modalAdicionarOperador = new bootstrap.Modal(document.getElementById('adicionarOperadorModal'));

function buttonChangeStatus(btns) {
    btns.forEach(button => {
        const spinner = button.querySelector('.spinner-border');
        button.disabled = !button.disabled;
        if (spinner) spinner.style.display = button.disabled ? 'inline-block' : 'none';
    });
}

function showToast(tipo, titulo, mensagem) {
    Swal.fire({
        icon: tipo,
        title: titulo,
        text: mensagem,
        position: 'bottom-end',
        timer: 3000,
        timerProgressBar: true,
        toast: true,
        showConfirmButton: false,
    });
}

async function desativarOperador(idOperador, csrfToken) {
    const response = await fetch(`/cadastro/edit/operador/${idOperador}/`, {
        method: 'PATCH',
        headers: { 'X-CSRFToken': csrfToken },
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Erro ao desativar operador.');
    }
}

function preencherModalEdicao(idOperador) {
    const operador = getOperadorById(idOperador);
    if (!operador) return;

    document.getElementById('matriculaOperador').value = operador.matricula;
    document.getElementById('nomeOperador').value = operador.nome;
    document.getElementById('setorOperador').value = operador.setor_id;
}

function abrirModalDesativacao(idOperador) {
    const operador = getOperadorById(idOperador);
    if (!operador) return;

    document.getElementById('operadorDesativar').textContent = operador.nome;
    document.getElementById('operadorIdDesativar').value = operador.id;
    modalDesativarOperador.show();
}

async function carregarSetores() {
    const response = await fetch('/cadastro/api/setores/');
    const data = await response.json();

    const setorOperador = document.getElementById('setorOperador');
    const setorNovoOperador = document.getElementById('setorNovoOperador');

    [setorOperador, setorNovoOperador].forEach(select => {
        select.innerHTML = '<option value="">-----</option>';
        data.setores.forEach(setor => {
            const option = document.createElement('option');
            option.value = setor.id;
            option.textContent = setor.nome;
            select.appendChild(option);
        });
    });
}

function bindPageEvents() {
    const addOperadorBtn = document.getElementById('addOperador');
    const tableOperadores = document.getElementById('tableOperadores');

    addOperadorBtn.addEventListener('click', () => {
        addOperadorBtn.disabled = true;
        modalAdicionarOperador.show();
    });

    tableOperadores.addEventListener('click', event => {
        const btnEdit = event.target.closest('.btnEditOperador');
        const btnDesativar = event.target.closest('.btnDesativarOperador');

        if (btnEdit) {
            botaoClicado = btnEdit;
            btnEdit.disabled = true;
            const idOperador = btnEdit.id.split('-')[1];
            preencherModalEdicao(idOperador);
            modalEditOperador.show();
        }

        if (btnDesativar) {
            botaoClicado = btnDesativar;
            btnDesativar.disabled = true;
            const idOperador = btnDesativar.id.split('-')[1];
            abrirModalDesativacao(idOperador);
        }
    });

    $('#editOperador').on('hidden.bs.modal', () => {
        if (botaoClicado) botaoClicado.disabled = false;
        document.getElementById('formEditOperador').reset();
    });

    $('#desativarOperador').on('hidden.bs.modal', () => {
        if (botaoClicado) botaoClicado.disabled = false;
        document.getElementById('formDesativarOperador').reset();
    });

    $('#adicionarOperadorModal').on('hidden.bs.modal', () => {
        addOperadorBtn.disabled = false;
        document.getElementById('formAdicionarOperador').reset();
    });
}

function bindForms() {
    document.getElementById('formEditOperador').addEventListener('submit', async event => {
        event.preventDefault();

        const idOperador = botaoClicado.id.split('-')[1];
        const form = event.target;
        const dados = new FormData(form);
        const btnsForm = form.querySelectorAll('.btn');
        const obj = Object.fromEntries(dados.entries());

        buttonChangeStatus(btnsForm);

        try {
            const response = await fetch(`/cadastro/edit/operador/${idOperador}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': obj.csrfmiddlewaretoken,
                },
                body: JSON.stringify(obj),
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Erro desconhecido.');
            }

            modalEditOperador.hide();
            await carregarTabela();
            showToast('success', 'Editado', 'Operador atualizado com sucesso.');
        } catch (error) {
            showToast('error', 'Erro ao editar', error.message);
        } finally {
            buttonChangeStatus(btnsForm);
        }
    });

    document.getElementById('formDesativarOperador').addEventListener('submit', async event => {
        event.preventDefault();

        const idOperador = botaoClicado.id.split('-')[1];
        const form = event.target;
        const dados = new FormData(form);
        const btnsForm = form.querySelectorAll('.btn');
        const obj = Object.fromEntries(dados.entries());

        buttonChangeStatus(btnsForm);

        try {
            await desativarOperador(idOperador, obj.csrfmiddlewaretoken);
            modalDesativarOperador.hide();
            await carregarTabela();
            showToast('success', 'Desativado', 'Operador desativado com sucesso.');
        } catch (error) {
            showToast('error', 'Erro ao desativar', error.message);
        } finally {
            buttonChangeStatus(btnsForm);
        }
    });

    document.getElementById('formAdicionarOperador').addEventListener('submit', async event => {
        event.preventDefault();

        const form = event.target;
        const dados = new FormData(form);
        const btnsForm = form.querySelectorAll('.btn');
        const obj = Object.fromEntries(dados.entries());

        buttonChangeStatus(btnsForm);

        try {
            const response = await fetch('/cadastro/add/operador/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': obj.csrfmiddlewaretoken,
                },
                body: JSON.stringify(obj),
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Erro desconhecido.');
            }

            modalAdicionarOperador.hide();
            await carregarTabela();
            showToast('success', 'Adicionado', 'Operador adicionado com sucesso.');
        } catch (error) {
            showToast('error', 'Erro ao adicionar', error.message);
        } finally {
            buttonChangeStatus(btnsForm);
        }
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    await carregarTabela();
    await carregarSetores();
    bindPageEvents();
    bindForms();
});
