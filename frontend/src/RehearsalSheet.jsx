import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { rehearsalSheet } from './rehearsals.js';
import { t } from './i18n.js';

// Printable sheet of a saved rehearsal (requested 2026-10-30). It is rendered outside the app and shown only
// when printing, so the browser's dialog prints it or saves it as PDF; the document title names the file.
export function RehearsalSheet({ rehearsal, onDone }) {
  const sheet = rehearsalSheet(rehearsal);
  useEffect(() => {
    const title = document.title;
    document.title = sheet.fileName;
    document.body.classList.add('printing-sheet');
    window.addEventListener('afterprint', onDone);
    window.print();
    return () => {
      window.removeEventListener('afterprint', onDone);
      document.body.classList.remove('printing-sheet');
      document.title = title;
    };
  }, []);
  return createPortal(<article className="rehearsal-sheet" aria-labelledby="rehearsal-sheet-title">
    <header>
      <p className="rehearsal-sheet-brand">ScoreMaster</p>
      <h1 id="rehearsal-sheet-title">{sheet.title}</h1>
      <p>{sheet.facts.join(' · ')}</p>
      {sheet.objectives && <p><strong>{t('Objetivos:')}</strong> {sheet.objectives}</p>}
    </header>
    {sheet.rows.length === 0 ? <p>{t('Sin bloques en la agenda.')}</p>
      : <table>
          <caption>{t('Agenda del ensayo')}</caption>
          <thead><tr>
            <th scope="col" className="rehearsal-sheet-time">{t('Hora')}</th><th scope="col">{t('Bloque')}</th><th scope="col" className="rehearsal-sheet-minutes">{t('Min')}</th>
            <th scope="col">{t('Obra y compases')}</th><th scope="col">{t('Secciones')}</th><th scope="col">{t('Objetivo')}</th>
            {sheet.rows.some(row => row.review) && <th scope="col">{t('Revisión')}</th>}
          </tr></thead>
          <tbody>{sheet.rows.map((row, index) => <tr key={index}>
            <td className="rehearsal-sheet-time">{row.time || '—'}</td><th scope="row">{row.title}</th><td>{row.minutes}</td>
            <td>{row.work}</td><td>{row.sections}</td><td>{row.objective}</td>
            {sheet.rows.some(item => item.review) && <td>{row.review}</td>}
          </tr>)}</tbody>
        </table>}
    {sheet.unassigned > 0 && <p>{t('Sin asignar: {minutes} min', { minutes: sheet.unassigned })}</p>}
    {sheet.notes && <p><strong>{t('Notas del ensayo')}:</strong> {sheet.notes}</p>}
  </article>, document.body);
}
