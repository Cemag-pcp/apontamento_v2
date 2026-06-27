import { resetarCardsInicial, carregarOrdensIniciadas, carregarOrdensInterrompidas } from './ordem-criada-solda.js';

document.addEventListener('DOMContentLoaded', function() {
    const pecaInput = document.getElementById('pecaSelect');
    const pecasSugeridas = document.getElementById('pecasSugeridas');
    const btnSalvar = document.getElementById('btnSalvar');
    const btnLimparInput = document.getElementById('btnLimparInput');

    let selecaoValida = false;
    let buscaEmAndamento = false;
    let controller = null;  // controlará o cancelamento da requisição

    function debounce(func, delay) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    btnLimparInput.addEventListener('click', function () {
        pecaInput.value = '';
        document.getElementById('conjuntoId').value = '';
        selecaoValida = false;
        pecasSugeridas.innerHTML = '';
    });

    function mostrarLoading() {
        pecasSugeridas.innerHTML = '';
        const loadingItem = document.createElement('div');
        loadingItem.className = 'list-group-item d-flex align-items-center';
        loadingItem.style.cursor = 'not-allowed'; // <- aqui
        loadingItem.innerHTML = `
            <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            <span>Carregando resultados...</span>
        `;
        pecasSugeridas.appendChild(loadingItem);
    }

    pecaInput.addEventListener('input', debounce(function () {
        const termo = pecaInput.value.trim();
        selecaoValida = false;

        if (termo.length < 2) {
            pecasSugeridas.innerHTML = '';
            return;
        }

        mostrarLoading();
        buscaEmAndamento = true;

        buscarPecasNaAPI(termo).then(conjuntos => {
            
            if (buscaEmAndamento === false) return; // ignora se foi resetado

            pecasSugeridas.innerHTML = '';
            buscaEmAndamento = false;

            conjuntos.forEach(conjunto => {
                const item = document.createElement('a');
                item.href = '#';
                item.className = 'list-group-item list-group-item-action';
                item.textContent = `${conjunto.codigo} - ${conjunto.descricao}`;
                item.style.cursor = 'pointer'; // <- cursor normal quando carregou
            
                item.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
            
                    if (buscaEmAndamento) {
                        return;
                    }
            
                    pecaInput.value = `${conjunto.codigo} - ${conjunto.descricao}`;
                    document.getElementById('conjuntoId').value = conjunto.id;
                    selecaoValida = true;
                    pecasSugeridas.innerHTML = '';
                });
            
                pecasSugeridas.appendChild(item);
            });
        });
    }, 300));

    // Fecha a lista ao clicar fora
    document.addEventListener('click', function (e) {
        if (e.target !== pecaInput && !buscaEmAndamento) {
            pecasSugeridas.innerHTML = '';

            if (pecaInput.value.trim() !== '' && !selecaoValida) {
                verificarSelecaoValida(pecaInput.value.trim());
            }
        }
    });

    function verificarSelecaoValida(valorDigitado) {
        buscarPecasNaAPI(valorDigitado).then(conjuntos => {
            const valor = valorDigitado.toLowerCase();
            const conjuntoValido = conjuntos.some(conjunto =>
                `${conjunto.codigo} - ${conjunto.descricao}`.toLowerCase() === valor
            );

            if (!conjuntoValido) {
                pecaInput.value = '';
                document.getElementById('conjuntoId').value = '';
            } else {
                selecaoValida = true;
            }
        });
    }

    btnSalvar.addEventListener('click', function() {
        const form = document.getElementById('pecasForm');
        const quantidade = document.getElementById('quantidade');
        const dataCarga = document.getElementById('dataCarga');
        const setor = document.getElementById('setor');

        if (!pecaInput.value) {
            alert('Por favor, selecione uma peça.');
            return;
        }

        if (!dataCarga.value) {
            alert('Por favor, selecione uma data de carga.');
            return;
        }

        if (!quantidade.value || quantidade.value < 1) {
            alert('Por favor, informe uma quantidade válida (maior que 0).');
            return;
        }

        if (!setor.value) {
            alert('Por favor, selecione um setor.');
            return;
        }

        const dadosFormulario = {
            peca: pecaInput.value,
            conjuntoId: document.getElementById('conjuntoId').value,
            dataCarga: dataCarga.value,
            quantidade: quantidade.value,
            setor: setor.value,
            observacao: document.getElementById('observacao').value
        };

        btnSalvar.setAttribute('disabled', 'disabled');
        btnSalvar.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processando...';

        fetch('api/criar-ordem-fora-sequenciamento/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(dadosFormulario)
        })
        .then(response => response.json())
        .then(data => {

            // Recarrega os resultados com os novos filtros
            const filtroDataCarga = document.getElementById('filtro-data-carga');
            const filtroSetor = document.getElementById('filtro-setor');
    
            // Captura os valores atualizados dos filtros
            const filtros = {
                data_carga: filtroDataCarga.value,
                setor: filtroSetor.value
            };
    
            // Recarrega os resultados com os novos filtros
            resetarCardsInicial(filtros);
            carregarOrdensIniciadas(filtros);
            carregarOrdensInterrompidas(filtros);

            const modal = bootstrap.Modal.getInstance(document.getElementById('modalForaSequenciamento'));
            modal.hide();
            form.reset();
            selecaoValida = false;
            document.getElementById('conjuntoId').value = '';

            btnSalvar.removeAttribute('disabled');
            btnSalvar.innerHTML = '<i class="bi bi-check-circle me-1"></i>Salvar';

        })
        .catch(error => {
            console.error('Erro ao enviar dados:', error);
            alert('Erro ao criar a ordem.');

            btnSalvar.removeAttribute('disabled');
            btnSalvar.innerHTML = '<i class="bi bi-check-circle me-1"></i>Salvar';

        });

    });

    async function buscarPecasNaAPI(termo) {
        if (controller) {
            controller.abort();  // cancela a requisição anterior
        }
    
        controller = new AbortController();  // cria nova instância
        const signal = controller.signal;
    
        try {
            const response = await fetch('api/listar-conjuntos', { signal });
            const data = await response.json();
    
            if (!data.conjuntos) return [];
    
            return data.conjuntos.filter(conjunto =>
                conjunto.codigo.toLowerCase().includes(termo.toLowerCase()) ||
                conjunto.descricao.toLowerCase().includes(termo.toLowerCase())
            );
        } catch (error) {
            if (error.name === 'AbortError') {
                // Requisição cancelada, não fazer nada
                return [];
            } else {
                console.error('Erro ao buscar conjuntos:', error);
                return [];
            }
        }
    }

    async function carregarSetores() {
        try {
            const response = await fetch('api/buscar-maquinas');
            const data = await response.json();
    
            const selectSetor = document.getElementById('setor');
    
            if (data.maquinas && Array.isArray(data.maquinas)) {
                data.maquinas.forEach(maquina => {
                    const option = document.createElement('option');
                    option.value = maquina.id;
                    option.textContent = maquina.nome;
                    selectSetor.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Erro ao carregar setores:', error);
        }
    }

    carregarSetores();
});
