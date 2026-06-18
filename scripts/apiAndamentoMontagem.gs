function apiAndamentoMontagem() {
  const baseUrl = 'https://cmgprod.com.br/cargas/api/ordens_em_andamento_finalizada_montagem/';
  const limit = 500; // máximo aceito pela API, reduz o número de chamadas
  const pausaMs = 1000; // espera entre páginas para não sobrecarregar o servidor
  let skip = 0;
  let todosDados = [];

  while (true) {
    const url = `${baseUrl}?skip=${skip}&limit=${limit}`;

    const response = UrlFetchApp.fetch(url);
    const data = JSON.parse(response.getContentText());

    // Para quando a próxima página vier vazia
    if (!data || data.length === 0) {
      break;
    }

    todosDados = todosDados.concat(data);

    // Próxima página
    skip += limit;

    // Pausa entre páginas para evitar rajada de requisições pesadas
    if (data.length === limit) {
      Utilities.sleep(pausaMs);
    }
  }

  const nomeDaAba = 'Andamento montagem';
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(nomeDaAba);

  const startRow = 2;
  const startColumn = 1;

  const lastRow = sheet.getLastRow();
  const lastColumn = sheet.getLastColumn();

  // Apaga todo o conteúdo abaixo do cabeçalho
  if (lastRow >= startRow) {
    sheet
      .getRange(startRow, startColumn, lastRow - startRow + 1, lastColumn)
      .clearContent();
  }

  // Se não vier nada da API, para aqui
  if (todosDados.length === 0) {
    return;
  }

  // Monta matriz com os dados da API
  const valores = todosDados.map(row => Object.values(row));

  // Cola tudo de uma vez
  sheet
    .getRange(startRow, startColumn, valores.length, valores[0].length)
    .setValues(valores);
}
