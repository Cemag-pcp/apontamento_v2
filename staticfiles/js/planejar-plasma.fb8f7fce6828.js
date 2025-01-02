import { loadOrdens } from './ordem-criada.js';

document.getElementById('fileUpload').addEventListener('change', async (event) => {
    const fileInput = event.target;

    // Verifica se algum arquivo foi selecionado
    if (!fileInput.files.length) {
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: 'Nenhum arquivo selecionado.',
            confirmButtonText: 'OK'
        });
        return;
    }

    const form = document.getElementById('opPlasmaForm');

    // Verifica se o formulário é válido
    if (!form.checkValidity()) {
        form.reportValidity(); // Exibe as mensagens de erro padrão do navegador
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    formData.append('tipoMaquinaPlasma', 'plasma');

    // Obter o token CSRF do formulário
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    Swal.fire({
        title: 'Processando...',
        text: 'Aguarde enquanto processamos sua solicitação.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading(); // Exibe o spinner de carregamento
        }
    });

    try {
        const response = await fetch('/corte/processar-arquivo/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken, // Adicionar o token CSRF no cabeçalho
            },
            body: formData,
        });

        Swal.close();

        if (response.ok) {
            const data = await response.json();
            const table = document.getElementById('previewTable');
            const tbody = table.querySelector('tbody');
            tbody.innerHTML = '';

            // Preencher a tabela com os dados processados
            data.data.forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${row.peca || ''}</td>
                    <td>${row.qtd_planejada || ''}</td>
                    <td>${row.espessura || ''}</td>
                    <td>${row.aproveitamento || ''}</td>
                    <td>${row.tamanho_da_chapa || ''}</td>
                    <td>${row.qt_chapa || ''}</td>
                `;
                tbody.appendChild(tr);
            });

            // Mostrar a tabela e botão de confirmação
            table.style.display = 'block';
            document.getElementById('confirmButton').style.display = 'inline-block';
            document.getElementById('previewTable').style.display = 'block';

        } else {
            const errorData = await response.json();
            Swal.fire({
                icon: 'error',
                title: 'Erro',
                text: errorData.error || 'Erro ao processar o arquivo.',
                confirmButtonText: 'OK'
            });
        }
    } catch (error) {
        Swal.close();
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: 'Erro inesperado ao processar o arquivo.',
            confirmButtonText: 'OK'
        });
        console.error('Erro na requisição:', error);
    }
});

document.getElementById('confirmButton').addEventListener('click', async (event) => {

    event.preventDefault(); // Impede o envio padrão do formulário

    Swal.fire({
        title: 'Processando...',
        text: 'Aguarde enquanto processamos sua solicitação.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading(); // Exibe o spinner de carregamento
        }
    });

    const fileInput = document.getElementById('fileUpload');
    const descricaoInput = document.getElementById('descricaoOpPlasma');
    const tipoChapaInput = document.getElementById('tipoChapa');
    const retalhoCheckbox = document.getElementById('retalhoPlasma');
    const dataProgramacao = document.getElementById('dataProgramacao').value;

    const formData = new FormData();
    
    formData.append('file', fileInput.files[0]);
    formData.append('descricao', descricaoInput.value)
    formData.append('tipo_chapa', tipoChapaInput.value)
    formData.append('maquina', 'plasma')
    formData.append('retalho', retalhoCheckbox.checked)
    formData.append('dataProgramacao', dataProgramacao)

    // Obter o token CSRF do formulário
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    const response = await fetch('/corte/salvar-arquivo/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken, // Adicionar o token CSRF no cabeçalho
        },
        body: formData,
    });

    if (response.ok) {
        Swal.fire({
            icon: 'success',
            title: 'Salvo',
            text: 'Ordem gerada com sucesso.',
            confirmButtonText: 'OK'
        });

        document.getElementById('confirmButton').style.display = 'none';
        document.getElementById('previewTable').style.display = 'none';
        document.getElementById("opPlasmaForm").reset();

        const container = document.getElementById('ordens-container');
        container.innerHTML = ''; // Limpa as ordens existentes no container
        let page = 1; // Reinicia a página
        const limit = 10; // Quantidade de ordens por página
    
        // Recarrega os dados chamando a função de carregamento
        const fetchOrdens = loadOrdens(container, page, limit);
        fetchOrdens(); // Carrega novamente a primeira página

    } else {
        Swal.fire({
            icon: 'error',
            title: 'Erro',
            text: 'Erro ao salvar ordem de produção.',
            confirmButtonText: 'OK'
        });
        document.getElementById('confirmButton').style.display = 'none';
        document.getElementById('uploadButton').style.display = 'inline-block';

    }
});

document.getElementById('resetFilePlasma').addEventListener('click', () => {
    // Reseta o campo de upload de arquivo
    const fileInput = document.getElementById('fileUpload');
    fileInput.value = '';

    // Opcional: Esconde a tabela de visualização e botão de confirmação
    document.getElementById('previewTable').style.display = 'none';
    document.getElementById('confirmButton').style.display = 'none';

    Swal.fire({
        icon: 'success',
        title: 'Arquivo removido',
        text: 'O campo foi limpo com sucesso.',
        confirmButtonText: 'OK'
    });
});