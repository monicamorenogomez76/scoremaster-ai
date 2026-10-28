// PDF scores (decided 2026-10-27): the server keeps the PDFs and starts the reader in GitHub Actions; the
// browser follows the reading until the work is analysed. Plain functions, so the Node tests can import them.
import { apiFetch, apiJson } from './api.js';

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
  if (!list.length) return 'Elige al menos un PDF.';
  if (list.length > MAX_FILES) return `Sube como mucho ${MAX_FILES} PDF.`;
  const notPdf = list.find(file => !/\.pdf$/i.test(file.name));
  if (notPdf) return 'Solo se aceptan archivos PDF: ' + notPdf.name + '.';
  const large = list.find(file => file.size > MAX_FILE_BYTES);
  if (large) return 'Cada PDF puede tener hasta 20 MB: ' + large.name + '.';
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
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se pudo enviar el PDF.');
  return data.id;
}

export const pdfImportStatus = id => apiJson('/pdf-imports/' + encodeURIComponent(id), {},
  'No se pudo consultar la lectura del PDF.');

export function pdfStatusText(status) {
  switch (status?.status) {
    case 'queued': return 'Poniendo en marcha el lector de PDF. Tarda uno o dos minutos…';
    case 'reading': return status.pages_total
      ? `Leyendo la página ${status.pages_done} de ${status.pages_total}…` : 'Preparando la lectura…';
    case 'analysing': return 'Analizando la obra leída…';
    case 'done': return 'Obra leída y analizada.';
    case 'failed': return status.error || 'No se pudo leer el PDF.';
    default: return '';
  }
}
