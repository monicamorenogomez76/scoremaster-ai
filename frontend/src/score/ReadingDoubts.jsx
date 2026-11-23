import React, { useEffect, useId, useState } from 'react';
import { doubtsSummary, markDoubtsReviewed } from '../readingDoubts.js';
import { t } from '../i18n.js';

// The measures the PDF reader doubted (2026-11-22), by part: each passage opens beside the PDF to check it by eye, and a
// part is marked reviewed when it is right. Nothing for a work without doubts.
export function ReadingDoubts({ workId, doubts: initial, onOpenPassage, onCorrect }) {
  const heading = useId();
  const [doubts, setDoubts] = useState(initial || []);
  const [saving, setSaving] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { setDoubts(initial || []); setError(''); }, [workId, initial]);
  if (!doubts.length) return null;

  const mark = async (part, reviewed) => {
    // The box changes at once; a failed save puts it back.
    const before = doubts;
    setDoubts(doubts.map(doubt => doubt.part === part ? { ...doubt, reviewed } : doubt));
    setSaving(part);
    setError('');
    try { setDoubts(await markDoubtsReviewed(workId, part, reviewed)); }
    catch (failure) { setDoubts(before); setError(failure.message); }
    finally { setSaving(''); }
  };

  return <details className="reading-doubts" open={doubts.some(doubt => !doubt.reviewed)}>
    <summary id={heading}>{t('Dudas del lector de PDF')} · {doubtsSummary(doubts)}</summary>
    <p className="result-supporting">{t('Compases que el lector tomó de una particella porque la partitura general se leía de otra forma. Ábrelos junto al PDF y marca cada parte cuando esté bien.')}</p>
    {error && <p className="score-compare-error" role="alert">{error}</p>}
    <ul className="reading-doubts-list" aria-labelledby={heading}>
      {doubts.map((doubt, index) => {
        const box = heading + '-' + index;
        return <li key={doubt.part} className={doubt.reviewed ? 'reading-doubt reading-doubt-reviewed' : 'reading-doubt'}>
          <span className="reading-doubt-part">{doubt.part}</span>
          <span className="reading-doubt-passages">
            {doubt.passages.map(range => <button key={range} type="button" className="passage-open"
              aria-label={t('Ver {part}, compases {range}', { part: doubt.part, range })}
              onClick={() => onOpenPassage(doubt.part, range)}>{range}</button>)}
          </span>
          {onCorrect && <button type="button" className="secondary-action reading-doubt-correct"
            aria-label={t('Corregir {part}, compás {measure}', { part: doubt.part, measure: doubt.passages[0].split('-')[0] })}
            onClick={() => onCorrect(doubt.part, doubt.passages[0])}>{t('Corregir')}</button>}
          <label className="reading-doubt-check" htmlFor={box}>
            <input id={box} type="checkbox" checked={doubt.reviewed} disabled={saving === doubt.part}
              onChange={event => mark(doubt.part, event.target.checked)} />
            {t('Revisada')}
          </label>
        </li>;
      })}
    </ul>
  </details>;
}
