import React, { useEffect, useId, useRef, useState } from 'react';
import { checkPdfFiles, pdfAvailable, pdfImportStatus, PDF_POLL_MS, pdfStatusText, startPdfImport } from './pdfImport.js';

// «Desde un PDF» (author's decision, 2026-10-27): one score or the parts of a work (one PDF per instrument), read by
// the reader in GitHub Actions. Shown only when the server has a reader. The reading takes minutes: the director
// sees its progress and the work opens when it is analysed.
export function PdfUpload({ visible, minutes, onOpenWork }) {
  const [available, setAvailable] = useState(false);
  const [kind, setKind] = useState('score');
  const [files, setFiles] = useState([]);
  const [title, setTitle] = useState('');
  const [reading, setReading] = useState(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const input = useRef(null);
  const ids = useId();

  useEffect(() => {
    if (!visible) return undefined;
    let current = true;
    pdfAvailable().then(found => { if (current) setAvailable(found); });
    return () => { current = false; };
  }, [visible]);

  // Follows the reading every few seconds until it ends; the work opens when it is analysed.
  useEffect(() => {
    if (!reading) return undefined;
    let current = true, timer;
    const poll = async () => {
      try {
        const found = await pdfImportStatus(reading);
        if (!current) return;
        setStatus(found);
        if (found.status === 'done') { setReading(null); onOpenWork(found.work_id); return; }
        if (found.status === 'failed') { setReading(null); return; }
      } catch (failure) {
        if (current) setError(failure.message);
      }
      if (current) timer = setTimeout(poll, PDF_POLL_MS);
    };
    poll();
    return () => { current = false; clearTimeout(timer); };
  }, [reading, onOpenWork]);

  if (!available) return null;
  const busy = Boolean(reading);
  const submit = async event => {
    event.preventDefault();
    const problem = checkPdfFiles(files);
    setError(problem); setStatus(null);
    if (problem) return;
    try {
      setStatus({ status: 'queued' });
      setReading(await startPdfImport(files, kind, title.trim(), minutes));
    } catch (failure) {
      setStatus(null); setError(failure.message);
    }
  };
  const message = error || pdfStatusText(status);
  const failed = Boolean(error) || status?.status === 'failed';
  return <form id="pdf-upload" className="pdf-upload" onSubmit={submit} aria-busy={busy} aria-labelledby={ids + 'title'}>
    <h3 id={ids + 'title'}>Desde un PDF</h3>
    <p className="result-supporting">Se lee con reconocimiento óptico de partituras. Funciona mejor con PDF exportados de
      un editor de partituras. Revisa la obra leída: su grado es provisional y no entra en las valoraciones de los músicos.</p>
    <fieldset className="pdf-kind" disabled={busy}>
      <legend>Qué vas a subir</legend>
      <label><input type="radio" name="pdf-kind" value="score" checked={kind === 'score'} onChange={() => setKind('score')} />
        Partitura general (uno o varios PDF, en orden)</label>
      <label><input type="radio" name="pdf-kind" value="parts" checked={kind === 'parts'} onChange={() => setKind('parts')} />
        Particellas (un PDF por instrumento, con su nombre en el archivo)</label>
    </fieldset>
    <label className="file-field" htmlFor={ids + 'files'}>Archivos PDF
      <input id={ids + 'files'} ref={input} type="file" accept="application/pdf,.pdf" multiple disabled={busy}
        onChange={event => { setFiles(Array.from(event.target.files || [])); setError(''); setStatus(null); }} />
    </label>
    <label className="pdf-title" htmlFor={ids + 'name'}>Título de la obra (opcional)
      <input id={ids + 'name'} type="text" maxLength={200} value={title} disabled={busy} onChange={event => setTitle(event.target.value)} />
    </label>
    <button className="primary-action" type="submit" disabled={busy}>{busy ? 'Leyendo…' : 'Leer PDF'}</button>
    <p className="analysis-status" role={failed ? 'alert' : 'status'} aria-live="polite" hidden={!message}>{message}</p>
  </form>;
}
