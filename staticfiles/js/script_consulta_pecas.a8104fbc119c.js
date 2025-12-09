// URLs das APIs (substitua pelas URLs reais)
const API_URLS = {
    carretas: '/core/api/consulta-carreta/',
    conjuntos: '/core/api/consulta-conjunto/',
    pecas: '/core/api/consulta-peca/'
};

// Elementos DOM - Carreta
const carretaInput = document.getElementById('carretaInput');
const carretaDropdown = document.getElementById('carretaDropdown');
const carretaLoading = document.getElementById('carretaLoading');
// const carretaSelected = document.getElementById('carretaSelected');
// const carretaSelectedCode = document.getElementById('carretaSelectedCode');
// const carretaSelectedDesc = document.getElementById('carretaSelectedDesc');
const carretaRemove = document.getElementById('carretaRemove');
const carretaId = document.getElementById('carretaId');

// Elementos DOM - Conjunto
const conjuntoInput = document.getElementById('conjuntoInput');
const conjuntoDropdown = document.getElementById('conjuntoDropdown');
const conjuntoLoading = document.getElementById('conjuntoLoading');
// const conjuntoSelected = document.getElementById('conjuntoSelected');
// const conjuntoSelectedCode = document.getElementById('conjuntoSelectedCode');
// const conjuntoSelectedDesc = document.getElementById('conjuntoSelectedDesc');
const conjuntoRemove = document.getElementById('conjuntoRemove');
const conjuntoId = document.getElementById('conjuntoId');

// Outros elementos DOM
const consultarBtn = document.getElementById('consultarBtn');
const limparBtn = document.getElementById('limparBtn');
// const imprimirBtn = document.getElementById('imprimirBtn');
const tabelaLoading = document.getElementById('tabelaLoading');
const emptyState = document.getElementById('emptyState');
const resultadosTable = document.getElementById('resultadosTable');
const resultadosBody = document.getElementById('resultadosBody');
// const totalRegistros = document.getElementById('totalRegistros');

// Variáveis para controle de timeout
let carretaTimeout = null;
let conjuntoTimeout = null;
const DELAY_MS = 300; // Delay para evitar muitas requisições enquanto digita

// Função para mostrar/esconder loading
function toggleLoading(element, show) {
    if (show) {
        element.classList.add('show');
    } else {
        element.classList.remove('show');
    }
}

// Função para fazer requisições à API
async function fetchAPI(url, params = {}) {
    try {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;
        
        const response = await fetch(fullUrl);
        
        if (!response.ok) {
            throw new Error(`Erro na API: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Erro na requisição:', error);
        return null;
    }
}

// Função para buscar carretas baseado no texto digitado
async function buscarCarretas(q) {
    toggleLoading(carretaLoading, true);
    
    // Aqui você pode ajustar os parâmetros conforme sua API
    const carretas = await fetchAPI(API_URLS.carretas, { q });
    
    toggleLoading(carretaLoading, false);

    console.log(carretas);
    
    if (carretas && carretas.carretas && carretas.carretas.length > 0) {
        carretaDropdown.innerHTML = '';

        carretas.carretas.forEach(carreta => {
            
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.innerHTML = `
                <span class="item-description">${carreta}</span>
            `;
            
            item.addEventListener('click', () => {
                selecionarCarreta(carreta);
            });
            
            carretaDropdown.appendChild(item);
        });
        
        carretaDropdown.classList.add('show');
    } else {
        carretaDropdown.innerHTML = '<div class="autocomplete-message">Nenhuma carreta encontrada</div>';
        carretaDropdown.classList.add('show');
    }
}

// Função para buscar conjuntos baseado na carreta e no texto digitado
async function buscarConjuntos(carreta, q) {
    toggleLoading(conjuntoLoading, true);
    
    // Aqui você pode ajustar os parâmetros conforme sua API
    const conjuntos = await fetchAPI(API_URLS.conjuntos, { carreta, q });
    
    toggleLoading(conjuntoLoading, false);
    
    if (conjuntos && conjuntos.conjuntos && conjuntos.conjuntos.length > 0) {
        conjuntoDropdown.innerHTML = '';
        
        conjuntos.conjuntos.forEach(conjunto => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.innerHTML = `
                <span class="item-code">${conjunto}</span>
            `;
            
            item.addEventListener('click', () => {
                selecionarConjunto(conjunto);
            });
            
            conjuntoDropdown.appendChild(item);
        });
        
        conjuntoDropdown.classList.add('show');
    } else {
        conjuntoDropdown.innerHTML = '<div class="autocomplete-message">Nenhum conjunto encontrado</div>';
        conjuntoDropdown.classList.add('show');
    }
}

// Função para selecionar uma carreta
function selecionarCarreta(carreta) {
    carretaId.value = carreta;
    carretaInput.value = carreta;
    carretaDropdown.classList.remove('show');
    
    // Habilitar campo de conjunto
    conjuntoInput.disabled = false;
    conjuntoInput.placeholder = 'Digite para buscar conjuntos...';
    
    // Limpar conjunto selecionado
    limparConjuntoSelecionado();

    // Buscar os conjuntos automaticamente
    buscarConjuntos(carreta, '');  // Passa string vazia para buscar todos

    // Verificar se pode habilitar o botão consultar
    verificarBotaoConsultar();
}

// Função para selecionar um conjunto
function selecionarConjunto(conjunto) {
    conjuntoId.value = conjunto;
    // conjuntoSelectedCode.textContent = conjunto.codigo;
    // conjuntoSelectedDesc.textContent = conjunto.descricao;
    // conjuntoSelected.classList.add('show');
    conjuntoInput.value = conjunto;
    conjuntoDropdown.classList.remove('show');
    
    // Verificar se pode habilitar o botão consultar
    verificarBotaoConsultar();
}

// Função para limpar carreta selecionada
function limparCarretaSelecionada() {
    carretaId.value = '';
    // carretaSelected.classList.remove('show');
    carretaInput.value = '';
    
    // Desabilitar e limpar campo de conjunto
    conjuntoInput.disabled = true;
    conjuntoInput.placeholder = 'Primeiro selecione uma carreta...';
    limparConjuntoSelecionado();
    
    // Desabilitar botão consultar
    consultarBtn.disabled = true;
}

// Função para limpar conjunto selecionado
function limparConjuntoSelecionado() {
    conjuntoId.value = '';
    // conjuntoSelected.classList.remove('show');
    conjuntoInput.value = '';
    
    // Desabilitar botão consultar
    consultarBtn.disabled = true;
}

// Função para verificar se pode habilitar o botão consultar
function verificarBotaoConsultar() {
    consultarBtn.disabled = !(carretaId.value && conjuntoId.value);
}

// Carregar dados da tabela
async function carregarDados() {
    const carretaIdValue = carretaId.value;
    const conjuntoIdValue = conjuntoId.value;
    
    if (!carretaIdValue || !conjuntoIdValue) {
        alert('Selecione tanto a carreta quanto o conjunto para consultar.');
        return;
    }
    
    // Mostrar loading e esconder outros elementos
    tabelaLoading.classList.add('show');
    emptyState.style.display = 'none';
    resultadosTable.style.display = 'none';
    
    const dados = await fetchAPI(API_URLS.pecas, { carreta: carretaIdValue, conjunto: conjuntoIdValue });
    
    tabelaLoading.classList.remove('show');
    
    if (dados && dados.pecas && dados.pecas.length > 0) {
        // Limpar tabela
        resultadosBody.innerHTML = '';

        // Adicionar dados à tabela
        dados.pecas.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <a href="https://drive.google.com/drive/u/0/search?q=${item.codigo_peca}" target="_blank" rel="noopener noreferrer">
                        <i class="fas fa-file-alt me-1"></i>
                    </a>
                </td>
                <td>${item.descricao_peca || '-'}</td>
                <td>${item.mp_peca || '-'}</td>
                <td class="text-end">${item.total_peca || 0}</td>
                <td>${item.conjunto_peca || '-'}</td>
                <td>${item.primeiro_processo || '-'}</td>
                <td>${item.segundo_processo || '-'}</td>
            `;
            resultadosBody.appendChild(row);
        });
        
        // Mostrar tabela e atualizar contador
        resultadosTable.style.display = 'table';
        // totalRegistros.textContent = `${dados.length} registro${dados.length !== 1 ? 's' : ''}`;
        // imprimirBtn.disabled = false;
    } else {
        // Mostrar estado vazio
        emptyState.style.display = 'block';
        // totalRegistros.textContent = '0 registros';
        // imprimirBtn.disabled = true;
    }
}

// Função de impressão
// function imprimir() {
//     const carretaTexto = `${carretaInput.textContent}`;
//     const conjuntoTexto = `${conjuntoInput.textContent}`;
    
//     // Criar cabeçalho para impressão
//     const printHeader = document.createElement('div');
//     printHeader.innerHTML = `
//         <div style="text-align: center; margin-bottom: 20px;">
//             <h2>Relatório de Peças</h2>
//             <p><strong>Carreta:</strong> ${carretaTexto}</p>
//             <p><strong>Conjunto:</strong> ${conjuntoTexto}</p>
//             <p><strong>Data:</strong> ${new Date().toLocaleDateString('pt-BR')}</p>
//         </div>
//     `;
    
//     // Inserir cabeçalho temporariamente
//     document.body.insertBefore(printHeader, document.body.firstChild);
    
//     // Imprimir
//     window.print();
    
//     // Remover cabeçalho após impressão
//     setTimeout(() => {
//         document.body.removeChild(printHeader);
//     }, 1000);
// }

// Função para limpar formulário
function limparFormulario() {
    limparCarretaSelecionada();
    
    // Esconder tabela e mostrar estado vazio
    resultadosTable.style.display = 'none';
    emptyState.style.display = 'block';
    // totalRegistros.textContent = '0 registros';
    // imprimirBtn.disabled = true;
}

// Fechar dropdowns quando clicar fora
document.addEventListener('click', function(event) {
    if (!carretaInput.contains(event.target) && !carretaDropdown.contains(event.target)) {
        carretaDropdown.classList.remove('show');
    }
    
    if (!conjuntoInput.contains(event.target) && !conjuntoDropdown.contains(event.target)) {
        conjuntoDropdown.classList.remove('show');
    }
});

// Event Listeners
carretaInput.addEventListener('input', function() {
    const termo = this.value.trim();
    
    // Limpar timeout anterior
    if (carretaTimeout) {
        clearTimeout(carretaTimeout);
    }
    
    // Se o termo for vazio, esconder dropdown
    if (!termo) {
        carretaDropdown.classList.remove('show');
        return;
    }
    
    // Definir novo timeout para evitar muitas requisições
    carretaTimeout = setTimeout(() => {
        buscarCarretas(termo);
    }, DELAY_MS);
});

conjuntoInput.addEventListener('input', function() {
    const termo = this.value.trim();
    const carretaIdValue = carretaId.value;

    // Limpar timeout anterior
    if (conjuntoTimeout) {
        clearTimeout(conjuntoTimeout);
    }
    
    // Se o termo for vazio ou não tiver carreta selecionada, esconder dropdown
    if (!termo || !carretaIdValue) {
        conjuntoDropdown.classList.remove('show');
        return;
    }
    
    // Definir novo timeout para evitar muitas requisições
    conjuntoTimeout = setTimeout(() => {
        buscarConjuntos(carretaIdValue, termo);
    }, DELAY_MS);
});

conjuntoInput.addEventListener('focus', function () {
    const termo = this.value.trim();
    const carretaIdValue = carretaId.value;

    // Apenas se uma carreta já tiver sido selecionada
    if (carretaIdValue && !termo) {
        buscarConjuntos(carretaIdValue, '');
    }
});

// Event listeners para remover seleção
// carretaRemove.addEventListener('click', limparCarretaSelecionada);
// conjuntoRemove.addEventListener('click', limparConjuntoSelecionado);

// Event listeners para botões
consultarBtn.addEventListener('click', carregarDados);
limparBtn.addEventListener('click', limparFormulario);
// imprimirBtn.addEventListener('click', imprimir);

// Navegação pelo teclado nos dropdowns
function handleKeyNavigation(event, dropdown, items) {
    if (!dropdown.classList.contains('show')) return;
    
    const active = dropdown.querySelector('.autocomplete-item.active');
    const allItems = dropdown.querySelectorAll('.autocomplete-item');
    
    if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!active) {
            allItems[0]?.classList.add('active');
        } else {
            active.classList.remove('active');
            const next = active.nextElementSibling;
            if (next && next.classList.contains('autocomplete-item')) {
                next.classList.add('active');
            } else {
                allItems[0]?.classList.add('active');
            }
        }
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!active) {
            allItems[allItems.length - 1]?.classList.add('active');
        } else {
            active.classList.remove('active');
            const prev = active.previousElementSibling;
            if (prev && prev.classList.contains('autocomplete-item')) {
                prev.classList.add('active');
            } else {
                allItems[allItems.length - 1]?.classList.add('active');
            }
        }
    } else if (event.key === 'Enter') {
        event.preventDefault();
        if (active) {
            active.click();
        }
    } else if (event.key === 'Escape') {
        dropdown.classList.remove('show');
    }
}

carretaInput.addEventListener('keydown', (e) => handleKeyNavigation(e, carretaDropdown));
conjuntoInput.addEventListener('keydown', (e) => handleKeyNavigation(e, conjuntoDropdown));
