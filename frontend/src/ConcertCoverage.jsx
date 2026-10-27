import React from 'react';

const minutesText = ({ done, total }) => total ? done + ' de ' + total + ' minutos' : 'sin minutos planificados';
const passagesText = ({ resolved, improve, pending, total }) => !total ? 'sin pasajes revisados'
  : [resolved + ' de ' + total + ' resueltos', improve && improve + ' mejorable' + (improve === 1 ? '' : 's'),
    pending && pending + ' pendiente' + (pending === 1 ? '' : 's')].filter(Boolean).join(', ');

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
  ? rehearsals.done + ' de ' + rehearsals.total + ' ensayos hechos (' + rehearsals.percent + ' %)' : null;

// «Cobertura hasta el concierto» (requested 2026-10-26): per work of the programme, the minutes rehearsed and
// the passages resolved in the director's reviews. Compact, so the summary still fits on one screen.
export function ConcertCoverage({ coverage }) {
  const { rehearsals, works } = coverage;
  if (!rehearsals.total) return <p className="result-supporting">Planifica en Conciertos los ensayos de este concierto para seguir su preparación.</p>;
  return <table className="summary-table coverage-table">
    <thead><tr><th scope="col">Obra</th><th scope="col">Tiempo ensayado</th><th scope="col">Pasajes resueltos</th></tr></thead>
    <tbody>{works.map(work => <tr key={work.id}>
      <th scope="row">{work.title}</th>
      <td><CoverageCell percent={work.minutes.percent} tone="time" detail={minutesText(work.minutes)} /></td>
      <td><CoverageCell percent={work.passages.percent} tone="resolved" detail={passagesText(work.passages)} /></td>
    </tr>)}</tbody>
  </table>;
}
