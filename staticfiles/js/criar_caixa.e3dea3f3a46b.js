document.addEventListener('DOMContentLoaded', function() {
    const dataCarga = document.getElementById('dataCarga');
    const selectCarga = document.getElementById('selectCarga');
    const selectCliente = document.getElementById('selectCliente');
    const carretasContainer = document.getElementById('carretasContainer');
    const btnSalvarPacote = document.getElementById('btnSalvarPacote');
    const etapa2 = document.getElementById('etapa2');
    const etapa3 = document.getElementById('etapa3');
    const etapa4 = document.getElementById('etapa4');

    // Quando a data é selecionada
    dataCarga.addEventListener('change', function() {
        const data = this.value;
        if (data) {
            // Chama API para buscar clientes
            buscarCargas(data);
            etapa2.style.display = 'block';
        } else {
            etapa2.style.display = 'none';
            etapa3.style.display = 'none';
            etapa4.style.display = 'none';
            selectCliente.disabled = true;
            btnSalvarPacote.disabled = true;
        }
    });

    // Quando a carga é selecionada
    selectCarga.addEventListener('change', function() {
        const cliente = this.value;
        const data = dataCarga.value;
        const carga = selectCarga.value;

        if (data && carga) {
            // Chama API para buscar carretas
            buscarClientes(data, carga);
            etapa3.style.display = 'block';
        } else {
            etapa3.style.display = 'none';
            btnSalvarPacote.disabled = true;
        }
    });

    selectCliente.addEventListener('change', function() {
        const cliente = this.value;
        const data = dataCarga.value;
        
        if (data && cliente) {
            // Chama API para buscar carretas
            buscarCarretas(data, cliente);
            etapa4.style.display = 'block';
        } else {
            etapa4.style.display = 'none';
            btnSalvarPacote.disabled = true;
        }
    });

    // Salvar pacote
    btnSalvarPacote.addEventListener('click', async function () {
        const data = dataCarga.value;
        const carga = selectCarga.value;
        const clienteId = selectCliente.value;
        const observacoes = document.getElementById('observacoes').value;

        const checkboxesSelecionados = document.querySelectorAll('.carreta-checkbox:checked');

        // Constrói os itens do pacote a partir dos checkboxes
        const itens = Array.from(checkboxesSelecionados).map(cb => ({
            codigo_peca: cb.value, // assumindo que o nome da carreta é o código
            quantidade: parseInt(cb.dataset.qtde) || 1,
            cor: cb.dataset.cor || 'laranja',
            descricao: `Recurso: ${cb.value}`
        }));

        const pacote = {
            data_carga: data,
            carga_nome: carga,
            cliente_codigo: clienteId,
            observacoes: observacoes,
            itens: itens
        };

        console.log('Enviando pacote para backend:', pacote);

        try {
            const response = await fetch('api/criar-caixa/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(pacote)
            });

            if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro ao criar pacote');
            }

            const resultado = await response.json();
            console.log('Pacote criado:', resultado);
            alert(`✅ Pacote ${resultado.numero} criado com sucesso!`);
        } catch (err) {
            console.error('Erro ao criar pacote:', err);
            alert(`❌ Erro: ${err.message}`);
        }

        alert('Pacote criado com sucesso!');
        
        // Reset do formulário
        document.getElementById('formCriarPacote').reset();
        etapa2.style.display = 'none';
        etapa3.style.display = 'none';
        etapa4.style.display = 'none';
        selectCliente.disabled = true;
        btnSalvarPacote.disabled = true;
        
        // Fecha o modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('criarCaixaModal'));
        modal.hide();
        
        // Recarrega a tabela
        // carregarTabelaExpedicoes();
    });


});

// Função para obter CSRF token
export function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Função para buscar cargas via API
async function buscarCargas(data) {
    console.log('Buscando cargas para data:', data);

    // resetar select
    selectCarga.innerHTML = '<option value="">Carregando...</option>';

    try {
        const response = await fetch(`api/cargas_disponiveis/?data_carga=${encodeURIComponent(data)}`);
        if (!response.ok) {
            throw new Error(`Erro na API: ${response.status}`);
        }

        // Como sua view retorna uma lista de códigos, ex.: ["CLI001","CLI002"]
        const cargas = await response.json();

        // Popula o select de cargas
        selectCliente.innerHTML = '<option value="">Selecione um cliente</option>';
        cargas.forEach((carga, idx) => {
            const option = document.createElement('option');
            option.value = carga;  // valor = código vindo do backend
            option.textContent = carga; // exibe o código (ou nome se preferir)
            selectCarga.appendChild(option);
        });

        selectCarga.disabled = false;
    } catch (err) {
        console.error('Erro ao buscar cargas:', err);
        alert('Erro ao carregar cargas. Tente novamente.');
    }
}

// Função para buscar clientes via API
async function buscarClientes(data, carga) {
    console.log('Buscando clientes para data e carga:', data,carga);

    try {
        const response = await fetch(`api/clientes_disponiveis/?data_carga=${encodeURIComponent(data)}&carga=${encodeURIComponent(carga)}`);
        if (!response.ok) {
            throw new Error(`Erro na API: ${response.status}`);
        }

        // Como sua view retorna uma lista de códigos, ex.: ["CLI001","CLI002"]
        const clientes = await response.json();

        // Popula o select de clientes
        selectCliente.innerHTML = '<option value="">Selecione um cliente</option>';
        clientes.forEach((cliente, idx) => {
            const option = document.createElement('option');
            option.value = cliente;  // valor = código vindo do backend
            option.textContent = cliente; // exibe o código (ou nome se preferir)
            selectCliente.appendChild(option);
        });

        selectCliente.disabled = false;
    } catch (err) {
        console.error('Erro ao buscar clientes:', err);
        alert('Erro ao carregar clientes. Tente novamente.');
    }
}

// Função para buscar carretas via API
// Mapa de cores -> hex (mesmas cores que o backend gera: vermelho, azul, verde, laranja, amarelo, cinza)
const COLOR_HEX = {
    vermelho: '#ff0000',
    azul: '#0000ff',
    verde: '#00ff00',
    laranja: '#ffa500',
    amarelo: '#ffff00',
    cinza: '#808080'
};

// Função para buscar carretas via API
async function buscarCarretas(data, clienteId) {
    console.log('Buscando carretas para data:', data, 'e cliente:', clienteId);

    // estado de loading (opcional)
    carretasContainer.innerHTML = `
        <div class="text-muted">Carregando carretas...</div>
    `;

    try {
        const url = `api/carretas_disponiveis/?data_carga=${encodeURIComponent(data)}&cliente=${encodeURIComponent(clienteId)}`;
        const response = await fetch(url);
        if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`);
        }

        // back-end retorna array de registros:
        // [{ Recurso, Qtde, PED_NUMEROSERIE, cor }, ...]
        const registros = await response.json();

        // Agregar por Recurso (uma “carreta”)
        // totaliza Qtde e junta séries (se quiser usar depois)
        const porRecurso = new Map();
        registros.forEach(r => {
        const recurso = (r.Recurso || '').toString();
        const cor = (r.cor || 'laranja').toLowerCase();
        const qtde = Number(r.Qtde) || 0;
        const serie = r.PED_NUMEROSERIE || '';

        if (!porRecurso.has(recurso)) {
                porRecurso.set(recurso, {
                id: recurso,                         // usamos o próprio nome como id estável
                nome: recurso,                       // exibe o nome da carreta (Recurso)
                cor,
                corHex: COLOR_HEX[cor] || '#999999',
                totalQtde: 0,
                series: []
            });
        }
        const acc = porRecurso.get(recurso);
        acc.totalQtde += qtde;
        if (serie) acc.series.push(serie);
        });

        // Transforma em array para render
        const carretas = Array.from(porRecurso.values());

        // Monta HTML de checkboxes
        let html = '<div class="row">';
        carretas.forEach(carreta => {
        html += `
            <div class="col-md-6 mb-2">
            <div class="form-check d-flex align-items-center gap-2">
                <input
                class="form-check-input carreta-checkbox"
                type="checkbox"
                value="${carreta.id}"
                id="carreta-${CSS.escape(carreta.id)}"
                data-cor="${carreta.cor}"
                data-hex="${carreta.corHex}"
                data-qtde="${carreta.totalQtde}"
                >
                <label class="form-check-label" for="carreta-${CSS.escape(carreta.id)}">
                <span class="carreta-color" style="
                        display:inline-block;
                        width:12px;height:12px;border-radius:3px;
                        background-color:${carreta.corHex};
                        margin-right:6px;"></span>
                ${carreta.nome} — ${carreta.cor} (Qtde: ${carreta.totalQtde})
                </label>
            </div>
            </div>
        `;
        });
        html += '</div>';

        carretasContainer.innerHTML = html;

        // Adiciona event listeners aos checkboxes
        const checkboxes = document.querySelectorAll('.carreta-checkbox');
        checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', validarFormulario);
        });

    } catch (err) {
        console.error('Erro ao buscar carretas:', err);
        carretasContainer.innerHTML = `
        <div class="text-danger">Erro ao carregar carretas. Tente novamente.</div>
        `;
    }
}

// Valida se pelo menos uma carreta foi selecionada
function validarFormulario() {
    const checkboxes = document.querySelectorAll('.carreta-checkbox:checked');
    btnSalvarPacote.disabled = checkboxes.length === 0;
}
