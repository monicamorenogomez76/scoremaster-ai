// The director's own PDF beside the score (2026-11-05): read in the browser and never sent to the server, so no
// commercial score is kept. Told by its content and always shown as a PDF: a page renamed .pdf must not run here.
import { t } from '../i18n.js';

const PDF_MAGIC = '%PDF';

export async function localPdf(file, urls = URL) {
  const start = new TextDecoder().decode(await file.slice(0, PDF_MAGIC.length).arrayBuffer());
  if (start !== PDF_MAGIC) throw new Error(t('{name} no es un PDF.', { name: file.name }));
  return urls.createObjectURL(new Blob([file], { type: 'application/pdf' }));
}
