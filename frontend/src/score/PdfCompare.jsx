import React, { useEffect, useId, useState } from 'react';
import { localPdf } from './pdf-compare.js';
import { t } from '../i18n.js';

// A PDF from the computer beside the score, to check the reading by eye. Nothing is uploaded.
export function PdfCompare({ workId, children }) {
  const input = useId();
  const [pdf, setPdf] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => () => { if (pdf) URL.revokeObjectURL(pdf.url); }, [pdf]);
  // Another work: the score viewer stays mounted, so the PDF of the last one goes by hand.
  useEffect(() => { setPdf(null); setError(''); }, [workId]);

  const choose = async event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      setPdf({ url: await localPdf(file), name: file.name });
      setError('');
    } catch (failure) { setError(failure.message); }
  };

  return <div className={pdf ? 'score-compare score-compare-open' : 'score-compare'}>
    <div className="score-compare-tools">
      <label className="secondary-action" htmlFor={input}>{pdf ? t('Cambiar el PDF') : t('Comparar con un PDF de tu ordenador')}</label>
      <input id={input} className="score-compare-input" type="file" accept=".pdf,application/pdf" onChange={choose} />
      {pdf && <button className="secondary-action" type="button" onClick={() => setPdf(null)}>{t('Cerrar el PDF')}</button>}
      <span className="result-supporting">{t('El PDF se abre solo en tu navegador: no se sube ni se guarda.')}</span>
      {error && <p className="score-compare-error" role="alert">{error}</p>}
    </div>
    <div className="score-compare-score">{children}</div>
    {pdf && <aside className="score-compare-pdf" aria-label={t('PDF para comparar')}>
      <iframe src={pdf.url} title={t('PDF para comparar: {name}', { name: pdf.name })} />
      <a href={pdf.url} target="_blank" rel="noreferrer">{t('Abrir el PDF en otra pestaña')}</a>
    </aside>}
  </div>;
}
