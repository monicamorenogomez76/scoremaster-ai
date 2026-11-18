import React, { useEffect, useRef, useState } from 'react';
import { cadenceText, keyName, loadMusicalAnalysis, markText, relationText, sectionShares, textureText } from './musicalAnalysis.js';
import { t } from './i18n.js';

// The analysis of the work as in a conservatory (2026-11-18): its form, keys, cadences and who plays what, calculated by
// ScoreMaster. Asked when the tab is first opened.
export function MusicalAnalysis({ workId, visible, fromPdf }) {
  const [state, setState] = useState({ status: 'idle', result: null, error: '' });
  // The work whose analysis was asked for: once per work, and an answer for another work is dropped.
  const asked = useRef(null);
  useEffect(() => { asked.current = null; setState({ status: 'idle', result: null, error: '' }); }, [workId]);
  useEffect(() => {
    if (!visible || !workId || asked.current === workId) return;
    asked.current = workId;
    setState({ status: 'loading', result: null, error: '' });
    loadMusicalAnalysis(workId)
      .then(result => { if (asked.current === workId) setState({ status: 'done', result, error: '' }); })
      .catch(failure => { if (asked.current === workId) setState({ status: 'error', result: null, error: failure.message }); });
  }, [visible, workId]);

  const { result } = state;
  return <section id="musical-analysis" className="musical-analysis" aria-labelledby="musical-analysis-title" aria-busy={state.status === 'loading'}>
    <h2 id="musical-analysis-title">{t('Análisis musical')}</h2>
    <p className="result-supporting">{t('Calculado por ScoreMaster a partir de la partitura: forma, tonalidades, cadencias y quién toca qué. La melodía es una aproximación.')}</p>
    {fromPdf && <p className="pdf-provisional" role="note">{t('Leída de PDF: el análisis es provisional, porque la lectura puede tener errores.')}</p>}
    {state.status === 'loading' && <p className="result-supporting">{t('Analizando la obra…')}</p>}
    {state.error && <p className="result-supporting" role="alert">{state.error}</p>}
    {result && !result.sections.length && <p className="result-supporting">{t('La obra no tiene notas que analizar.')}</p>}
    {result && result.sections.length > 0 && <>
      <dl className="analysis-summary">
        <div><dt>{t('Tonalidad principal')}</dt><dd>{keyName(result.main_key)}</dd></div>
        <div><dt>{t('Forma')}</dt><dd>{result.form}</dd></div>
        <div><dt>{t('Secciones')}</dt><dd>{result.sections.length}</dd></div>
        <div><dt>{t('Cadencias')}</dt><dd>{result.cadences.length}</dd></div>
      </dl>
      <ol className="analysis-timeline" aria-label={t('Secciones de la obra en orden')}>
        {result.sections.map((section, index) => <li key={section.id} className={'analysis-block analysis-block--' + section.relation}
          style={{ flexGrow: sectionShares(result.sections)[index] }}>
          <strong>{section.label}</strong>
          <span>{t('cc. {first}–{last}', { first: section.first, last: section.last })}</span>
          <span>{keyName(section.key)}</span>
        </li>)}
      </ol>
      {/* Scrolled sideways on a phone: reachable with the keyboard (WCAG 2.1.1). */}
      <div className="analysis-table-wrap" tabIndex={0} role="region" aria-label={t('Análisis por secciones')}>
        <table className="analysis-table">
          <caption className="visually-hidden">{t('Análisis por secciones')}</caption>
          <thead><tr>
            <th scope="col">{t('Sección')}</th><th scope="col">{t('Compases')}</th><th scope="col">{t('Tonalidad')}</th>
            <th scope="col">{t('Melodía')}</th><th scope="col">{t('Textura')}</th><th scope="col">{t('Marcas')}</th>
            <th scope="col">{t('Cadencias')}</th>
          </tr></thead>
          <tbody>{result.sections.map(section => {
            const cadences = result.cadences.filter(cadence => cadence.section === section.id);
            const marks = [...section.marks, ...section.marks_at_end].map(markText);
            return <tr key={section.id}>
              <th scope="row">{section.label}{section.like && <span className="result-supporting">
                {' '}{t('(vuelve el material de {section})', { section: result.sections.find(other => other.id === section.like)?.label || section.like })}</span>}</th>
              <td data-label={t('Compases')}>{t('{first}–{last}', { first: section.first, last: section.last })}</td>
              <td data-label={t('Tonalidad')}>{keyName(section.key)}<span className="result-supporting"> · {relationText(section.relation)}</span></td>
              <td data-label={t('Melodía')}>{section.melody || '—'}{section.doubled_by.length > 0 && <span className="result-supporting">
                {' '}{t('(doblada por {parts})', { parts: section.doubled_by.join(', ') })}</span>}</td>
              <td data-label={t('Textura')}>{textureText(section.texture)}<span className="result-supporting"> · {t('{count} partes', { count: section.playing.length })}</span></td>
              <td data-label={t('Marcas')}>{marks.join(', ') || '—'}</td>
              <td data-label={t('Cadencias')}>{cadences.map(cadence => t('{kind} (c. {measure})', { kind: cadenceText(cadence.kind), measure: cadence.measure })).join(', ') || '—'}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>
    </>}
  </section>;
}
