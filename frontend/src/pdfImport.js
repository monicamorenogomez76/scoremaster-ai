// PDF scores (decided 2026-10-27): the server keeps the PDFs and starts the reader in GitHub Actions; the
// browser follows the reading until the work is analysed. Plain functions, so the Node tests can import them.
import { apiFetch, apiJson } from './api.js';
import { t } from './i18n.js';

const MAX_FILES = 40;
const MAX_FILE_BYTES = 20 * 1024 * 1024;
export const PDF_POLL_MS = 4000;

export async function pdfAvailable() {
  try { return Boolean((await apiJson('/pdf-imports/available', {}, '')).available); }
  catch { return false; }
}

// An error in Spanish, or '' when the files can be sent.
export function checkPdfFiles(files) {
  const list = Array.from(files || []);
  if (!list.length) return t('Elige al menos un PDF.');
  if (list.length > MAX_FILES) return t('Sube como mucho {count} PDF.', { count: MAX_FILES });
  const notPdf = list.find(file => !/\.pdf$/i.test(file.name));
  if (notPdf) return t('Solo se aceptan archivos PDF: {name}.', { name: notPdf.name });
  const large = list.find(file => file.size > MAX_FILE_BYTES);
  if (large) return t('Cada PDF puede tener hasta 20 MB: {name}.', { name: large.name });
  return '';
}

// kind: "score" (one score, its PDFs in order) or "parts" (one PDF per instrument). The id of the reading.
export async function startPdfImport(files, kind, title, minutes) {
  const body = new FormData();
  Array.from(files).forEach(file => body.append('files', file));
  body.append('kind', kind);
  body.append('title', title || '');
  body.append('total_minutes', minutes || '60');
  const response = await apiFetch('/pdf-imports', { method: 'POST', body });
  let data = {};
  try { data = await response.json(); } catch { /* the message below */ }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : t('No se pudo enviar el PDF.'));
  return data.id;
}

export const pdfImportStatus = id => apiJson('/pdf-imports/' + encodeURIComponent(id), {},
  t('No se pudo consultar la lectura del PDF.'));

// Seconds left, from the polls' samples ({at: ms, done: pages}) since the first page read (the first one also loads
// copista); null until there are two of them.
export function remainingSeconds(samples, total) {
  const read = (samples || []).filter(sample => sample.done >= 1);
  if (read.length < 2) return null;
  const first = read[0], last = read[read.length - 1];
  const rate = (last.done - first.done) / ((last.at - first.at) / 1000);
  return rate > 0 ? Math.round((total - last.done) / rate) : null;
}

const leftText = seconds => (seconds == null ? '' : ' · ' + (seconds < 60 ? t('falta menos de un minuto')
  : seconds <= 90 ? t('queda un minuto') : t('quedan unos {minutes} minutos', { minutes: Math.ceil(seconds / 60) })));

// Each step of the reading in words (2026-10-28: the wait had no news), with the time left while reading.
export function pdfStatusText(status, remaining = null) {
  switch (status?.status) {
    case 'queued': return t('En cola en GitHub: el lector arranca en un minuto o dos…');
    case 'preparing': return t('Preparando el lector (copista)…');
    case 'reading': return status.pages_total
      ? t('Leyendo la página {done} de {total}{left}…', { done: status.pages_done, total: status.pages_total, left: leftText(remaining) })
      : t('Preparando la lectura…');
    case 'analysing': return t('Analizando la obra leída…');
    case 'done': return t('Obra leída y analizada.');
    case 'failed': return status.error || t('No se pudo leer el PDF.');
    default: return '';
  }
}
