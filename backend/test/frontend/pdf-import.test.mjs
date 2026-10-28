import assert from 'node:assert/strict';
import test from 'node:test';
import { checkPdfFiles, pdfAvailable, pdfImportStatus, pdfStatusText, PDF_POLL_MS, remainingSeconds, startPdfImport } from '../../../frontend/src/pdfImport.js';
import { analysisStatusText } from '../../../frontend/src/library.js';

// PDF scores (decided 2026-10-27): the reader runs in GitHub Actions; the browser starts the reading and
// follows it until the work is analysed.
function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body });
    const [status, body] = routes[(options.method || 'GET') + ' ' + url] || [404, { detail: 'No se encontró la lectura del PDF.' }];
    return new Response(JSON.stringify(body), { status });
  };
  return calls;
}

const pdf = (name, size = 1000) => ({ name, size, type: 'application/pdf' });

test('the PDF option appears only when the server has a reader', async () => {
  fakeServer({ 'GET /pdf-imports/available': [200, { available: true }] });
  assert.equal(await pdfAvailable(), true);
  fakeServer({});
  assert.equal(await pdfAvailable(), false, 'an error hides the option');
});

test('the files are checked before anything is sent', () => {
  assert.equal(checkPdfFiles([]), 'Elige al menos un PDF.');
  assert.equal(checkPdfFiles([pdf('obra.musicxml')]), 'Solo se aceptan archivos PDF: obra.musicxml.');
  assert.equal(checkPdfFiles([pdf('obra.pdf', 21 * 1024 * 1024)]), 'Cada PDF puede tener hasta 20 MB: obra.pdf.');
  assert.equal(checkPdfFiles(Array.from({ length: 41 }, (_, index) => pdf(index + '.pdf'))), 'Sube como mucho 40 PDF.');
  assert.equal(checkPdfFiles([pdf('Flauta 1.PDF'), pdf('Trombón 1.pdf')]), '');
});

test('a reading starts with the files, its kind and the rehearsal minutes', async () => {
  const calls = fakeServer({ 'POST /pdf-imports': [202, { id: 'imp-1' }] });
  assert.equal(await startPdfImport([pdf('obra.pdf')], 'parts', 'Oregon Trail II', '90'), 'imp-1');
  const body = calls[0].body;
  assert.equal(body.get('kind'), 'parts');
  assert.equal(body.get('title'), 'Oregon Trail II');
  assert.equal(body.get('total_minutes'), '90');
  assert.equal(body.getAll('files').length, 1);
  fakeServer({ 'POST /pdf-imports': [502, { detail: 'No se pudo poner en marcha el lector de PDF. Inténtalo de nuevo.' }] });
  await assert.rejects(startPdfImport([pdf('obra.pdf')], 'score', '', '60'), /No se pudo poner en marcha/);
});

test('the director follows the reading in words', async () => {
  fakeServer({ 'GET /pdf-imports/imp-1': [200, { status: 'reading', pages_done: 7, pages_total: 20, error: null, work_id: null }] });
  assert.equal((await pdfImportStatus('imp-1')).pages_done, 7);
  assert.equal(pdfStatusText({ status: 'queued' }), 'En cola en GitHub: el lector arranca en un minuto o dos…');
  assert.equal(pdfStatusText({ status: 'preparing' }), 'Preparando el lector (copista)…');
  assert.equal(pdfStatusText({ status: 'reading', pages_done: 0, pages_total: 0 }), 'Preparando la lectura…');
  assert.equal(pdfStatusText({ status: 'reading', pages_done: 7, pages_total: 20 }), 'Leyendo la página 7 de 20…');
  assert.equal(pdfStatusText({ status: 'analysing' }), 'Analizando la obra leída…');
  assert.equal(pdfStatusText({ status: 'done' }), 'Obra leída y analizada.');
  assert.equal(pdfStatusText({ status: 'failed', error: 'No se pudo leer la página 2 de Flauta 1.pdf.' }),
    'No se pudo leer la página 2 de Flauta 1.pdf.');
  assert.ok(PDF_POLL_MS >= 3000, 'the browser does not hurry the server');
});

test('a work read from a PDF says so in the repertoire', () => {
  assert.equal(analysisStatusText({ summary: { grade: 3 }, source_format: 'pdf' }), 'Disponible · leída de PDF');
  assert.equal(analysisStatusText({ summary: { grade: 3 }, source_format: 'musicxml' }), 'Disponible');
});

test('while reading, the director sees how long is left', () => {
  // Samples of the polls: time in ms and pages read. From the first page on, 4 pages in 40 s: 15 left are 150 s.
  const samples = [{ at: 0, done: 0 }, { at: 10000, done: 1 }, { at: 50000, done: 5 }];
  assert.equal(remainingSeconds(samples, 20), 150);
  assert.equal(remainingSeconds([{ at: 0, done: 0 }], 20), null, 'no estimate before two pages');
  assert.equal(pdfStatusText({ status: 'reading', pages_done: 5, pages_total: 20 }, 150), 'Leyendo la página 5 de 20 · quedan unos 3 minutos…');
  assert.equal(pdfStatusText({ status: 'reading', pages_done: 19, pages_total: 20 }, 20), 'Leyendo la página 19 de 20 · falta menos de un minuto…');
  assert.equal(pdfStatusText({ status: 'reading', pages_done: 14, pages_total: 20 }, 60), 'Leyendo la página 14 de 20 · queda un minuto…');
});
