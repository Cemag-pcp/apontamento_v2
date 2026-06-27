document.addEventListener('DOMContentLoaded', function() {
    const tabela = document.getElementById('tabela-conjuntos');
    const rows = Array.from(tabela.querySelectorAll('tbody tr'));
    const rowsPerPage = 10;
    const pagination = document.getElementById('pagination');
    let currentPage = 1;
    let filteredRows = rows;
    
    // Elementos do filtro
    const filtroCodigo = document.getElementById('filtro-codigo');
    const filtroDescricao = document.getElementById('filtro-descricao');
    const btnFiltrar = document.getElementById('btn-filtrar');
    const btnLimpar = document.getElementById('btn-limpar-filtros');
    
    // Função para aplicar filtros
    function aplicarFiltros() {
        const codigoFiltro = filtroCodigo.value.toLowerCase();
        const descricaoFiltro = filtroDescricao.value.toLowerCase();
        
        filteredRows = rows.filter(row => {
            const codigo = row.cells[0].textContent.toLowerCase();
            const descricao = row.cells[1].textContent.toLowerCase();
            
            return codigo.includes(codigoFiltro) && 
                   descricao.includes(descricaoFiltro);
        });
        
        currentPage = 1;
        showPage(currentPage);
    }
    
    // Event listeners para filtros
    btnFiltrar.addEventListener('click', aplicarFiltros);
    
    // Limpar filtros
    btnLimpar.addEventListener('click', function() {
        filtroCodigo.value = '';
        filtroDescricao.value = '';
        filteredRows = rows;
        currentPage = 1;
        showPage(currentPage);
    });
    
    // Função para mostrar a página
    function showPage(page) {
        currentPage = page;
        const start = (page - 1) * rowsPerPage;
        const end = start + rowsPerPage;
        
        // Esconder todas as linhas primeiro
        rows.forEach(row => row.style.display = 'none');
        
        // Mostrar apenas as linhas filtradas na página atual
        filteredRows.slice(start, end).forEach(row => {
            row.style.display = '';
        });
        
        updatePagination();
    }
    
    function updatePagination() {
        pagination.innerHTML = '';
        const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
        
        function createPageItem(text, page = null, active = false, disabled = false) {
            const li = document.createElement('li');
            li.className = 'page-item' + (active ? ' active' : '') + (disabled ? ' disabled' : '');
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = text;
            if (page && !disabled) {
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    showPage(page);
                });
            }
            li.appendChild(a);
            pagination.appendChild(li);
        }
        
        if (currentPage > 1) {
            createPageItem('Anterior', currentPage - 1);
        } else {
            createPageItem('Anterior', null, false, true);
        }
        
        let pageLinksToShow = 1; // quantas páginas vizinhas exibir
        
        if (currentPage > 1 + pageLinksToShow) {
            createPageItem(1, 1);
            if (currentPage > 2 + pageLinksToShow) {
                createPageItem('...');
            }
        }
        
        for (let i = currentPage - pageLinksToShow; i <= currentPage + pageLinksToShow; i++) {
            if (i > 0 && i <= totalPages) {
                createPageItem(i, i, currentPage === i);
            }
        }
        
        if (currentPage < totalPages - pageLinksToShow) {
            if (currentPage < totalPages - pageLinksToShow - 1) {
                createPageItem('...');
            }
            createPageItem(totalPages, totalPages);
        }
        
        if (currentPage < totalPages) {
            createPageItem('Próximo', currentPage + 1);
        } else {
            createPageItem('Próximo', null, false, true);
        }
    }
    
    showPage(1);
});