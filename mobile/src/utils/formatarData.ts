// Converte datas ISO do backend ("2026-10-21" ou "2026-10-21T14:30:00...")
// pro formato brasileiro ("21/10/2026" / "21/10/2026 14:30"). Feito por
// string, sem new Date(), pra uma data pura nao mudar de dia por fuso.
// Valores fora do padrao ISO (ex: ja formatados) voltam como vieram.
export function formatarData(valor: string | null | undefined): string {
  if (!valor) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(valor);
  if (!m) return valor;
  const [, ano, mes, dia, hora, minuto] = m;
  const data = `${dia}/${mes}/${ano}`;
  return hora ? `${data} ${hora}:${minuto}` : data;
}
