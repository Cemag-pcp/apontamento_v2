// Download em CSV das tabelas dos dashboards de inspecao.
//
// Uso no template: um botao com data-exportar-csv="<id da tabela>" e,
// opcionalmente, data-nome-csv="<nome base do arquivo>". Exporta o que esta
// renderizado na tabela (ja respeita o filtro de datas aplicado na tela).
// Separador ";" e BOM UTF-8 pra abrir certo no Excel em portugues.

function textoCelulaCsv(celula) {
    const texto = (celula.innerText || celula.textContent || '').replace(/\s+/g, ' ').trim();
    return `"${texto.replace(/"/g, '""')}"`;
}

function periodoFiltroCsv() {
    const inicio = document.getElementById('startDate')?.value;
    const fim = document.getElementById('endDate')?.value;
    if (inicio && fim) return `_${inicio}_a_${fim}`;
    if (inicio) return `_desde_${inicio}`;
    if (fim) return `_ate_${fim}`;
    return '';
}

function exportarTabelaCsv(tabelaId, nomeBase) {
    const tabela = document.getElementById(tabelaId);
    if (!tabela) return;

    const cabecalho = Array.from(tabela.querySelectorAll('thead th')).map(textoCelulaCsv);
    const linhas = Array.from(tabela.querySelectorAll('tbody tr'))
        // ignora a linha de aviso "Nenhum dado encontrado..." (uma celula so, com colspan)
        .filter((tr) => !(tr.cells.length === 1 && tr.cells[0].colSpan > 1))
        .map((tr) => Array.from(tr.cells).map(textoCelulaCsv).join(';'));

    if (linhas.length === 0) {
        alert('Não há dados nesta tabela para exportar no período selecionado.');
        return;
    }

    const csv = '﻿' + [cabecalho.join(';'), ...linhas].join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${nomeBase || tabelaId}${periodoFiltroCsv()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
}

document.addEventListener('click', (event) => {
    const botao = event.target.closest('[data-exportar-csv]');
    if (!botao) return;
    event.preventDefault();
    exportarTabelaCsv(botao.dataset.exportarCsv, botao.dataset.nomeCsv);
});
