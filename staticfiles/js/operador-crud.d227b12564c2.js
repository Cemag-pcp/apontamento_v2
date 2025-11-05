
import {carregarTabela} from './datatable-list-operador.js';

let botaoClicado;

const modalEditOperador = new bootstrap.Modal(document.getElementById('editOperador'));
const modalDesativarOperador = new bootstrap.Modal(document.getElementById('desativarOperador'));
const modalAdicionarOperador = new bootstrap.Modal(document.getElementById('adicionarOperadorModal'));

document.addEventListener('DOMContentLoaded', async () => {
    await carregarTabela();
    await carregarSetores();
    eventosPagina();
    eventosFormularios();
})

function eventosPagina(){
    // const editBtns = document.querySelectorAll('[id^="btnEditOperador-"]');
    // const desativaBtns = document.querySelectorAll('[id^="btnDesativarOperador-"]');
    const addOperadorBtn = document.getElementById('addOperador');

    const tableOperadores = document.getElementById('tableOperadores');

    const matriculaOperadorModalInput = document.getElementById('matriculaOperador');
    const nomeOperadorModalInput = document.getElementById('nomeOperador');
    const nomeOperadorSpan = document.getElementById('operadorDesativar');
    const setorOperador = document.getElementById('setorOperador');

    // Adicionar Operador Btn
    addOperadorBtn.addEventListener('click',function(event){
        addOperadorBtn.disabled = true;
        modalAdicionarOperador.show();

    })

    tableOperadores.addEventListener('click', function(event) {
        const btnEdit = event.target.closest('.btnEditOperador');

        const btnDesativa = event.target.closest('.btnDesativarOperador');

        if (!btnEdit && !btnDesativa) return; // Se não for um botão de ação, sai da função


        if (btnEdit){
            btnEdit.disabled = true;

            botaoClicado = btnEdit;

            let idOperador = btnEdit.id.split('-')[1];
            //Preenchendo inputs
            matriculaOperadorModalInput.value = document.getElementById(`operadorMatricula-${idOperador}`).textContent;
            nomeOperadorModalInput.value = document.getElementById(`operadorNome-${idOperador}`).textContent;
            setorOperador.value = document.getElementById(`operadorSetor-${idOperador}`).getAttribute('data-id-setor');


            modalEditOperador.show();
            // console.log(event.target.id);
        }

        if (btnDesativa){
            btnDesativa.disabled = true;

            botaoClicado = btnDesativa;

            let idOperador = btnDesativa.id.split('-')[1];
            nomeOperadorSpan.textContent = document.getElementById(`operadorNome-${idOperador}`).textContent;
            modalDesativarOperador.show();
            // console.log(event.target.id);
        }
        


    })


    
    $('#editOperador').on('hidden.bs.modal',function(event){
        if (botaoClicado){
            botaoClicado.disabled = false;
        }
        
        //resetando o form
        document.getElementById('formEditOperador').reset();
    })

    $('#desativarOperador').on('hidden.bs.modal',function(event){
        if (botaoClicado){
            botaoClicado.disabled = false;
        }
        
        //resetando o form
        document.getElementById('formDesativarOperador').reset();
    })

    $('#adicionarOperadorModal').on('hidden.bs.modal',function(event){
        if (addOperadorBtn){
            addOperadorBtn.disabled = false;
        }
        
        //resetando o form
        document.getElementById('formAdicionarOperador').reset();
    })
    
}

function buttonChangeStatus(btns){
    // Função que desativa ou ativa botoes habilitando spinner caso tenha
    // Param: recebe uma lista de botoes

    btns.forEach(b => {
        const spinner = b.querySelector('.spinner-border');

        if (b.disabled){
            b.disabled = false;
            if (spinner) spinner.style.display = 'none';
        }else{
            b.disabled = true;
            if (spinner) spinner.style.display = 'inline-block';
        }
    })

}
function showToast(tipo, titulo, mensagem) {
    Swal.fire({
        icon: tipo, // 'success', 'error', 'warning', etc.
        title: titulo,
        position: 'bottom-end',
        timerProgressBar: true,
        text: mensagem,
        timer: 3000,
        toast: true,
        showConfirmButton: false,
    });
}

function eventosFormularios(){

    // EDITAR
    document.getElementById('formEditOperador').addEventListener('submit', async function(event){
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
                body: JSON.stringify(obj)
            });

            const data = await response.json();

            if (response.ok) {
                if (modalEditOperador) modalEditOperador.hide();

                showToast('success', 'Editado!', 'Operador atualizado com sucesso.');

                await carregarTabela();
                eventosPagina();
            } else {
                showToast('error', 'Erro ao editar', data.error || 'Erro desconhecido.');
            }

        } catch (erro) {
            console.error('Erro:', erro);
            showToast('error', 'Erro de conexão', 'Verifique sua conexão com o servidor.');
        } finally {
            buttonChangeStatus(btnsForm);
        }
    })

    // DESATIVAR
    document.getElementById('formDesativarOperador').addEventListener('submit', async function(event){
        event.preventDefault();

        const idOperador = botaoClicado.id.split('-')[1];
        const form = event.target;
        const dados = new FormData(form);
        const btnsForm = form.querySelectorAll('.btn');
        const obj = Object.fromEntries(dados.entries());

        buttonChangeStatus(btnsForm);

        try {
            const response = await fetch(`/cadastro/edit/operador/${idOperador}/`, {
                method: 'PATCH',
                headers: {
                    'X-CSRFToken': obj.csrfmiddlewaretoken,
                }
            });

            const data = await response.json();

            if (response.ok) {
                if (modalDesativarOperador) modalDesativarOperador.hide();

                showToast('success', 'Desativado', 'Operador desativado com sucesso.');

                await carregarTabela();
                eventosPagina();
            } else {
                showToast('error', 'Erro ao desativar', data.error || 'Erro desconhecido.');
            }

        } catch (erro) {
            console.error('Erro:', erro);
            showToast('error', 'Erro de conexão', 'Não foi possível conectar ao servidor.');
        } finally {
            buttonChangeStatus(btnsForm);
        }
    })

    // ADICIONAR
    document.getElementById('formAdicionarOperador').addEventListener('submit', async function(event){
        event.preventDefault();

        const form = event.target;
        const dados = new FormData(form);
        const btnsForm = form.querySelectorAll('.btn');

        buttonChangeStatus(btnsForm);  // desativa os botões, por exemplo

        // Transforma FormData em objeto normal (para envio como JSON)
        const obj = Object.fromEntries(dados.entries());

        try {
            const response = await fetch('/cadastro/add/operador/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': obj.csrfmiddlewaretoken,
                },
                body: JSON.stringify(obj)
            });

            const data = await response.json();

            if (response.ok) {
                // Fecha o modal
                if (typeof modalAdicionarOperador !== 'undefined') {
                    modalAdicionarOperador.hide();
                }

                showToast('success','Operador adicionado com sucesso!')

                // Atualiza tabela ou ações pós-sucesso
                if (typeof carregarTabela === 'function') await carregarTabela();
                if (typeof eventosPagina === 'function') eventosPagina();

                

            } else {
                showToast('error','Erro ao adicionar operador', data.error || 'Erro desconhecido')
            }

        } catch (erro) {
            console.error('Erro na requisição:', erro);
            showToast('error','Erro de conexão','Não foi possível conectar ao servidor.')
        } finally {
            buttonChangeStatus(btnsForm);  // reativa botões
        }
    })
}

async function carregarSetores(){
    fetch('/cadastro/api/setores/')
    .then(response => response.json())
    .then(data => {
        const setorOperador = document.getElementById('setorOperador');
        const setorNovoOperador = document.getElementById('setorNovoOperador');
        setorOperador.innerHTML = ''; // Limpa opções existentes
        setorNovoOperador.innerHTML = '';
        
        // Criando uma opção vazia
        let emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '-----';
        setorOperador.appendChild(emptyOption);
        setorNovoOperador.appendChild(emptyOption.cloneNode(true));

        data.setores.forEach(setor => {
            const option = document.createElement('option');
            option.value = setor.id;
            option.textContent = setor.nome;
            setorOperador.appendChild(option);
            setorNovoOperador.appendChild(option.cloneNode(true));
        });
    })
}