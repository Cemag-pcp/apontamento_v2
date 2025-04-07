import { loadOrdens } from './ordem-criada.js';

document.getElementById('fileUploadLaser2').addEventListener('change', async (event) => {
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

    const form = document.getElementById('laser2Form');

    // Verifica se o formulário é válido
    if (!form.checkValidity()) {
        form.reportValidity(); // Exibe as mensagens de erro padrão do navegador
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    formData.append('tipoMaquina', 'laser_2');

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
        const response = await fetch('/corte/api/processar-arquivo/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken, // Adicionar o token CSRF no cabeçalho
            },
            body: formData,
        });

        Swal.close();

        if (response.ok) {
            const data = await response.json();
            const table = document.getElementById('previewTableLaser2');
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
                    <td>${row.qt_chapas || ''}</td>
                `;
                tbody.appendChild(tr);
            });

            // Mostrar a tabela e botão de confirmação
            table.style.display = 'block';
            document.getElementById('confirmButtonLaser2').style.display = 'inline-block';
            document.getElementById('previewTableLaser2').style.display = 'block';

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

document.getElementById('confirmButtonLaser1').addEventListener('click', async (event) => {

    event.preventDefault(); // Impede o envio padrão do formulário

    Swal.fire({
        title: 'Processando...',
        text: 'Aguarde enquanto processamos sua solicitação.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading(); // Exibe o spinner de carregamento
        }
    });

    const fileInput = document.getElementById('fileUploadLaser1');
    const descricaoInput = document.getElementById('descricaoLaser1');
    const tipoChapaInput = document.getElementById('tipoChapaLaser1');
    const retalhoCheckbox = document.getElementById('retalhoLaser1');
    const dataProgramacao = document.getElementById('dataProgramacaoLaser1').value;
    const espessura = document.getElementById('espessuraLaser1').value;
    const comprimento = document.getElementById('comprimentoLaser1').value;
    const largura = document.getElementById('larguraLaser1').value;

    const formData = new FormData();
    
    formData.append('file', fileInput.files[0]);
    formData.append('descricao', descricaoInput.value);
    formData.append('tipo_chapa', tipoChapaInput.value);
    formData.append('maquina', 'laser_1');
    formData.append('retalho', retalhoCheckbox.checked);
    formData.append('dataProgramacao', dataProgramacao);
    formData.append('espessura', espessura);
    formData.append('comprimento', comprimento);
    formData.append('largura', largura);

    // Obter o token CSRF do formulário
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    const response = await fetch('/corte/api/salvar-arquivo/', {
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

        document.getElementById('confirmButtonLaser1').style.display = 'none';
        document.getElementById("laser1Form").reset();

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
        document.getElementById('confirmButtonLaser2').style.display = 'none';

    }
});

document.getElementById('confirmButtonLaser2').addEventListener('click', async (event) => {

    event.preventDefault(); // Impede o envio padrão do formulário

    Swal.fire({
        title: 'Processando...',
        text: 'Aguarde enquanto processamos sua solicitação.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading(); // Exibe o spinner de carregamento
        }
    });

    const fileInput = document.getElementById('fileUploadLaser2');
    const descricaoInput = document.getElementById('descricaoLaser2');
    const tipoChapaInput = document.getElementById('tipoChapaLaser2');
    const retalhoCheckbox = document.getElementById('retalhoLaser2');
    const dataProgramacao = document.getElementById('dataProgramacaoLaser2').value;

    const formData = new FormData();
    
    formData.append('file', fileInput.files[0]);
    formData.append('descricao', descricaoInput.value)
    formData.append('tipo_chapa', tipoChapaInput.value)
    formData.append('maquina', 'laser_2')
    formData.append('retalho', retalhoCheckbox.checked)
    formData.append('dataProgramacao', dataProgramacao)

    // Obter o token CSRF do formulário
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    const response = await fetch('/corte/api/salvar-arquivo/', {
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

        document.getElementById('confirmButtonLaser2').style.display = 'none';
        document.getElementById('previewTableLaser2').style.display = 'none';
        document.getElementById("laser2Form").reset();

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
        document.getElementById('confirmButtonLaser2').style.display = 'none';

    }
});

document.getElementById('resetFileLaser2').addEventListener('click', () => {
    // Reseta o campo de upload de arquivo
    const fileInput = document.getElementById('fileUploadLaser2');
    fileInput.value = '';

    // Opcional: Esconde a tabela de visualização e botão de confirmação
    document.getElementById('previewTableLaser2').style.display = 'none';
    document.getElementById('confirmButtonLaser2').style.display = 'none';

    Swal.fire({
        icon: 'success',
        title: 'Arquivo removido',
        text: 'O campo foi limpo com sucesso.',
        confirmButtonText: 'OK'
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('ordens-container');
    const form = document.getElementById('filtro-form');
    const filtroOrdem = document.getElementById('filtro-ordem');
    const filtroMaquina = document.getElementById('filtro-maquina');
    const filtroStatus = document.getElementById('filtro-status');
    const filtroPeca = document.getElementById('filtro-peca');

    // Função para resetar dados e carregar com filtros
    const resetAndLoad = () => {
        container.innerHTML = ''; // Limpa os cards
        const page = 1; // Reinicia a página
        const hasMoreData = true; // Permite novos carregamentos
        const limit=10;

        // Passa os parâmetros de filtro para a chamada fetch
        loadOrdens(container, page, limit, {
            ordem: filtroOrdem.value,
            maquina: filtroMaquina.value,
            status: filtroStatus.value,
            peca: filtroPeca.value
        });

    };

    // Evento de envio do formulário para filtros
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        resetAndLoad(); // Reseta e recarrega os dados com filtros
    });

});