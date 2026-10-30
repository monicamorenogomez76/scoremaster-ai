import React from 'react';
import { t } from './i18n.js';

const minutesText = ({ done, total }) => total ? t('{done} de {total} minutos', { done, total }) : t('sin minutos planificados');
const passagesText = ({ resolved, improve, pending, total }) => !total ? t('sin pasajes revisados')
  : [t('{resolved} de {total} resueltos', { resolved, total }),
    improve && t(improve === 1 ? '{count} mejorable' : '{count} mejorables', { count: improve }),
    pending && t(pending === 1 ? '{count} pendiente' : '{count} pendientes', { count: pending })].filter(Boolean).join(', ');

// A bar with its percentage written next to it, so the bar is never the only cue; what it counts is read out.
function CoverageCell({ percent, detail, tone }) {
  return <span className="coverage-cell" title={detail}>
    <span className="coverage-track" aria-hidden="true">
      <span className={'coverage-fill coverage-fill--' + tone} style={{ width: (percent || 0) + '%' }} />
    </span>
    <span className="coverage-value">{percent == null ? '—' : percent + ' %'}</span>
    <span className="visually-hidden">: {detail}</span>
  </span>;
}

// Rehearsals held of the series, in the heading of the card.
export const coverageHeadline = ({ rehearsals }) => rehearsals.total
  ? t('{done} de {total} ensayos hechos ({percent} %)', rehearsals) : null;

// «Cobertura hasta el concierto» (requested 2026-10-26): per work of the programme, the minutes rehearsed and
// the passages resolved in the director's reviews. Compact, so the summary still fits on one screen.
export function ConcertCoverage({ coverage }) {
  const { rehearsals, works } = coverage;
  if (!rehearsals.total) return <p className="result-supporting">{t('Planifica en Conciertos los ensayos de este concierto para seguir su preparación.')}</p>;
  return <table className="summary-table coverage-table">
    <thead><tr><th scope="col">{t('Obra')}</th><th scope="col">{t('Tiempo ensayado')}</th><th scope="col">{t('Pasajes resueltos')}</th></tr></thead>
    <tbody>{works.map(work => <tr key={work.id}>
      <th scope="row">{work.title}</th>
      <td><CoverageCell percent={work.minutes.percent} tone="time" detail={minutesText(work.minutes)} /></td>
      <td><CoverageCell percent={work.passages.percent} tone="resolved" detail={passagesText(work.passages)} /></td>
    </tr>)}</tbody>
  </table>;
}
