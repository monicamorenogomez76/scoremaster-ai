import React from 'react';
import { byDifficulty, displayFamilyName, displayInstrumentName, findingLabel, gradeOf, gradeScaleOf, gradeText } from './labels.js';

function MetricCard({ label, value, detail }) {
  return <div className="metric-card"><div className="label">{label}</div><div className="value">{value}</div><div className="subvalue">{detail}</div></div>;
}

// Dashboard at the top of the analysis view: the work's grade, its families and the priority passage.
export function OverviewPanel({ data, onStart, onOpenDifficulty }) {
  const difficulty = data?.difficulty || {};
  const families = byDifficulty(Object.entries(difficulty.by_family || {}), 'score');
  const passages = difficulty.critical_passages || [];
  const scale = gradeScaleOf(difficulty);
  const priority = passages[0];
  return <>
    <div id="overview-empty" className="overview-empty surface" hidden={Boolean(data)}>
      <div><h2>Aún no hay análisis</h2><p>Sube un archivo MusicXML o abre una de tus obras en Inicio para ver su dificultad y sus pasajes críticos.</p></div>
      <button className="primary-action" type="button" onClick={onStart}>Ir a Inicio</button>
    </div>
    <div id="overview-result" hidden={!data}>{data && <>
      <div id="overview-metrics">
        <div className="dashboard-grid">
          <MetricCard label="Grado de la obra" value={gradeText(difficulty, scale)} detail="Estimación provisional · percentil 80 por familia" />
          <MetricCard label="Pasajes críticos" value={String(passages.length)} detail="Agrupados por instrumento" />
          <MetricCard label="Familias" value={String(families.length)} detail="Secciones de la partitura" />
        </div>
        {families.length > 0 && <section className="family-chart" aria-label="Grado de dificultad por familia">
          <h2>Dónde concentrar el ensayo</h2>
          <p>Grado de dificultad por familia · escala de 1 a {scale.grades}</p>
          {families.map(([family, details]) => <div key={family} className="chart-row">
            <span>{displayFamilyName(family, details)}</span>
            <div className="chart-track" aria-hidden="true"><div className="chart-fill" style={{ width: gradeOf(details, scale) / scale.grades * 100 + '%' }} /></div>
            <span className="chart-value">Grado {gradeOf(details, scale)}</span>
          </div>)}
        </section>}
      </div>
    </>}</div>
    {priority && <div id="overview-priority" className="overview-empty surface">
      <div>
        <p className="eyebrow">Pasaje prioritario</p>
        <h2 id="overview-priority-title">{displayInstrumentName(priority.instrument, (difficulty.by_instrument || {})[priority.instrument]) + ' · compases ' + priority.measure_range}</h2>
        <p id="overview-priority-detail">{(priority.findings || []).map(findingLabel).join(' · ') || 'Pasaje marcado para revisión.'}</p>
      </div>
      <button id="open-priority" className="primary-action" type="button" onClick={onOpenDifficulty}>Ver pasajes</button>
    </div>}
  </>;
}
