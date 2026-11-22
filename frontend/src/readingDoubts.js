// The doubts of the PDF reader (2026-11-22): the measures it took from a part because the score's staff read
// otherwise. The director checks each part against the PDF and marks it reviewed.
import { apiJson } from './api.js';
import { t } from './i18n.js';

export async function markDoubtsReviewed(workId, part, reviewed) {
  const answer = await apiJson('/works/' + encodeURIComponent(workId) + '/reading-doubts/review', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part, reviewed }),
  }, t('No se pudo guardar la revisión.'));
  return answer.reading_doubts;
}

export function doubtsSummary(doubts) {
  if (!doubts?.length) return '';
  const measures = doubts.reduce((sum, doubt) => sum + doubt.measures, 0);
  const left = doubts.filter(doubt => !doubt.reviewed).length;
  const counted = measures === 1 ? t('1 compás dudoso') : t('{count} compases dudosos', { count: measures });
  if (!left) return t('Todas las partes revisadas') + ' · ' + counted;
  return t('{left} de {total} partes por revisar', { left, total: doubts.length }) + ' · ' + counted;
}
