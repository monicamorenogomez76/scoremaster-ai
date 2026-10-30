import React from 'react';
import { byDifficulty, displayFamilyName, displayInstrumentName, familyCountsForWork, findingLabel, gradeOf, gradeScaleOf, gradeText,
  gradeReasons, workGradeDetail } from './labels.js';
import { t } from './i18n.js';

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
      <div><h2>{t('Aún no hay análisis')}</h2><p>{t('Sube un archivo MusicXML o abre una de tus obras en Inicio para ver su dificultad y sus pasajes críticos.')}</p></div>
      <button className="primary-action" type="button" onClick={onStart}>{t('Ir a Inicio')}</button>
    </div>
    <div id="overview-result" hidden={!data}>{data && <>
      <div id="overview-metrics">
        <div className="dashboard-grid">
          <MetricCard label={t('Grado de la obra')} value={gradeText(difficulty, scale)} detail={workGradeDetail(difficulty)} />
          <MetricCard label={t('Pasajes críticos')} value={String(passages.length)} detail={t('Agrupados por instrumento')} />
          <MetricCard label={t('Familias')} value={String(families.length)} detail={t('Secciones de la partitura')} />
        </div>
        {gradeReasons(difficulty).length > 0 && <section id="grade-reasons" className="grade-reasons" aria-labelledby="grade-reasons-title">
          <h2 id="grade-reasons-title">{t('Por qué tiene este grado')}</h2>
          <ul>{gradeReasons(difficulty).map(reason => <li key={reason}>{reason}</li>)}</ul>
        </section>}
        {families.length > 0 && <section className="family-chart" aria-label={t('Grado de dificultad por familia')}>
          <h2>{t('Dónde concentrar el ensayo')}</h2>
          <p>{t('Grado de dificultad por familia · escala de 1 a {grades}', { grades: scale.grades })}</p>
          {families.map(([family, details]) => <div key={family} className="chart-row">
            <span>{displayFamilyName(family, details)}
              {!familyCountsForWork(details) && <span className="chart-note">{t('No cuenta para el grado de la obra')}</span>}</span>
            <div className="chart-track" aria-hidden="true"><div className="chart-fill" style={{ width: gradeOf(details, scale) / scale.grades * 100 + '%' }} /></div>
            <span className="chart-value">{t('Grado {grade}', { grade: gradeOf(details, scale) })}</span>
          </div>)}
        </section>}
      </div>
    </>}</div>
    {priority && <div id="overview-priority" className="overview-empty surface">
      <div>
        <p className="eyebrow">{t('Pasaje prioritario')}</p>
        <h2 id="overview-priority-title">{displayInstrumentName(priority.instrument, (difficulty.by_instrument || {})[priority.instrument]) + ' · ' + t('compases {range}', { range: priority.measure_range })}</h2>
        <p id="overview-priority-detail">{(priority.findings || []).map(findingLabel).join(' · ') || t('Pasaje marcado para revisión.')}</p>
      </div>
      <button id="open-priority" className="primary-action" type="button" onClick={onOpenDifficulty}>{t('Ver pasajes')}</button>
    </div>}
  </>;
}
