import React, { useEffect, useState } from 'react';
import { gradeScaleOf, gradeText } from './labels.js';
import { listConcerts, nextConcert, nextConcertText } from './concerts.js';
import { listPriorities, listWorks } from './library.js';
import { blockWorkText, listRehearsals, listReviewPriorities, nextRehearsal, rehearsalDateText, summaryPriorityRows,
  todayIso } from './rehearsals.js';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { SectionWork } from './SectionWork.jsx';
import { concertCoverage, planCounts } from './dashboard.js';
import { ConcertCoverage, coverageHeadline } from './ConcertCoverage.jsx';
import { NextStep } from './NextStep.jsx';
import { View } from './View.jsx';
import { t } from './i18n.js';

// At a glance on a computer (requested 2026-10-05): a few rows, the rest one click away.
const VISIBLE_ROWS = 4;

function Card({ id, title, action, children }) {
  return <section id={id} className="summary-card surface" aria-labelledby={id + '-title'}>
    <header className="summary-card-heading"><h2 id={id + '-title'}>{title}</h2>{action}</header>
    {children}
  </section>;
}

// Home of the director, after its mock-up: the next rehearsal (with the next step of the
// concert) and the priorities on the left, the works in preparation on the right, as cells of one
// grid (2026-10-14) so the works column runs the whole height.
export function SummaryView({ active, user, hidden, onNavigate, onOpenWork, onOpenBlock, onPlanRehearsal, onEditRehearsal,
  onReviewRehearsal, busy }) {
  const [works, setWorks] = useState(null);
  const [priorities, setPriorities] = useState(null);
  const [rehearsals, setRehearsals] = useState(null);
  const [concerts, setConcerts] = useState([]);
  const [reviewPriorities, setReviewPriorities] = useState([]);
  const [error, setError] = useState('');
  const [detail, setDetail] = useState(false);
  const [revision, setRevision] = useState(0);
  const visible = !hidden && active === 'summary';
  useEffect(() => {
    if (!visible) return undefined;
    let current = true;
    Promise.all([listWorks(), listPriorities(), listRehearsals(), listConcerts(), listReviewPriorities()])
      .then(([found, passages, saved, programmed, reviewed]) => {
        if (current) { setWorks(found); setPriorities(passages); setRehearsals(saved); setConcerts(programmed); setReviewPriorities(reviewed); setError(''); }
      })
      .catch(failure => { if (current) setError(failure.message); });
    // Leaving the summary folds the agenda again: every visit starts at a glance.
    return () => { current = false; setDetail(false); };
  }, [visible, user?.email, revision]);
  const preparing = (works || []).filter(work => work.preparation_status === 'preparing');
  const link = (label, view) => <button type="button" className="link-action" onClick={() => onNavigate(view)}>{label}</button>;
  const next = rehearsals && nextRehearsal(rehearsals);
  const concert = nextConcert(concerts, todayIso());
  const priorityRows = priorities ? summaryPriorityRows(reviewPriorities, priorities) : null;
  const counts = planCounts(priorityRows || []);
  const coverage = rehearsals && concertCoverage(concert?.concert, rehearsals, todayIso());
  const gradeOf = workId => (works || []).find(work => work.id === workId)?.summary?.grade;
  const action = <button id="plan-rehearsal" className="primary-action" type="button" onClick={onPlanRehearsal}>{t('Planificar ensayo')}</button>;

  // The next concert takes the place of the description, so the summary still fits at a glance.
  const description = concert
    ? <span id="next-concert"><strong>{t('Próximo concierto:')}</strong> {nextConcertText(concert, todayIso())}{' '}
        <button type="button" className="link-action" onClick={() => onNavigate('concerts')}>{t('Ver conciertos')}</button>
        {(concert.concert.works || []).length > 0 && <span className="programme" aria-label={t('Programa del concierto')}>
          {concert.concert.works.map(work => <span key={work.id} className="programme-chip">{work.title}
            {gradeOf(work.id) != null && <> · <strong>{t('Grado {grade}', { grade: gradeOf(work.id) })}</strong></>}</span>)}
        </span>}</span>
    : t('Lo que necesitas para dirigir la próxima sesión.');
  return <View name="summary" active={active} eyebrow={t('Resumen')} title={t('Tu próximo ensayo, preparado')}
    description={description} action={action}>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="summary-layout">
      <Card id="summary-rehearsal" title={next?.date === todayIso() ? t('Ensayo de hoy') : t('Próximo ensayo')}
        action={next ? <span className="card-actions">
            {next.blocks.length > 0 && <button type="button" className="link-action detail-toggle" aria-expanded={detail}
              onClick={() => setDetail(open => !open)}>{detail ? t('Ocultar detalle') : t('Ver detalle')}</button>}
            <button id="edit-rehearsal" type="button" className="link-action" onClick={() => onEditRehearsal(next)}>{t('Editar')}</button>
          </span> : link(t('Ir a Ensayos'), 'rehearsal')}>
        <NextStep concerts={concerts} rehearsals={rehearsals || []} onReviewRehearsal={onReviewRehearsal}
          onOpenBlock={onOpenBlock} onChanged={() => setRevision(value => value + 1)} />
        {rehearsals && !next && <div className="empty-workspace"><h3>{t('No hay ensayos programados')}</h3>
          <p>{t('Planifica el próximo ensayo con sus obras y su agenda para tenerlo aquí.')}</p></div>}
        {next && <>
          <p className="result-supporting">{[rehearsalDateText(next), t('{minutes} minutos', { minutes: next.duration_minutes }), next.place].filter(Boolean).join(' · ')}</p>
          <AgendaCalendar blocks={next.blocks} start={next.time} onOpenBlock={onOpenBlock} />
          {next.blocks.length === 0 && <p className="result-supporting">{t('Este ensayo aún no tiene agenda.')}</p>}
          {detail && next.blocks.length > 0 && <ol className="agenda-list">{next.blocks.map((block, index) => <li key={index} className="agenda-item">
                <span className="agenda-number" aria-hidden="true">{index + 1}</span>
                <span className="agenda-minutes">{block.minutes} min</span>
                <div>
                  {block.work_id
                    ? <button type="button" className="link-action agenda-title" onClick={() => onOpenBlock({ ...block, label: block.title + ' · ' + block.work_title })}>{block.title}</button>
                    : <strong className="agenda-title">{block.title}</strong>}
                  {block.work_id
                    ? <button type="button" className="link-action agenda-work" onClick={() => onOpenWork(block.work_id)}>{blockWorkText(block)}</button>
                    : <span className="agenda-work">{blockWorkText(block)}</span>}
                  {block.objective && <span className="table-supporting">{block.objective}</span>}
                </div>
              </li>)}</ol>}
        </>}
      </Card>


      <Card id="summary-priorities" title={t('Prioridades por sección')}>
        {priorityRows && priorityRows.length === 0 && <div className="empty-workspace"><h3>{t('Sin prioridades por ahora')}</h3>
          <p>{t('Aquí aparecen lo pendiente de tu última revisión de ensayo y los pasajes críticos de las obras en preparación.')}</p></div>}
        {priorityRows && priorityRows.length > 0 && <table className="summary-table">
          <thead><tr><th scope="col">{t('Sección')}</th><th scope="col">{t('Obra')}</th><th scope="col">{t('Pasaje')}</th><th scope="col">{t('Motivo')}</th><th scope="col">{t('Origen')}</th></tr></thead>
          <tbody>{priorityRows.slice(0, VISIBLE_ROWS).map((row, index) => <tr key={index}>
            <th scope="row">{row.family && <span className={'family-dot family-dot--' + row.family} aria-hidden="true" />}{row.section}</th>
            <td><button type="button" className="link-action" disabled={busy} onClick={() => onOpenWork(row.work_id)}>{row.title}</button>
              <span className="table-supporting">{row.detail}</span></td>
            <td>{row.range ? <button type="button" className="link-action" disabled={busy}
              onClick={() => onOpenBlock({ work_id: row.work_id, parts: row.parts, measures: row.range, label: row.section + ' · ' + row.title })}>{row.measures}</button>
              : row.measures}</td>
            <td>{row.reason}</td>
            <td><span className="status-tag" title={row.originTitle}>{row.origin}</span></td>
          </tr>)}</tbody>
        </table>}
        {priorityRows && priorityRows.length > VISIBLE_ROWS && <p className="table-supporting">{t('Y {count} más.', { count: priorityRows.length - VISIBLE_ROWS })}</p>}
      </Card>
      <Card id="summary-plan" title={t('Dónde trabajar')}><SectionWork counts={counts} /></Card>
      {/* Without a next concert there is nothing to cover, and the summary keeps fitting on one screen. */}
      {coverage && <Card id="summary-coverage" title={t('Cobertura hasta el concierto')} action={coverageHeadline(coverage) && <span className="coverage-headline">{coverageHeadline(coverage)}</span>}>
        <ConcertCoverage coverage={coverage} />
      </Card>}
      <Card id="summary-works" title={t('Obras en preparación')} action={link(t('Ver repertorio'), 'repertoire')}>
        {works && preparing.length === 0 && <div className="empty-workspace"><h3>{t('Ninguna obra en preparación')}</h3>
          <p>{t('Marca en Repertorio las obras que estáis preparando para seguirlas desde aquí.')}</p></div>}
        {preparing.length > 0 && <table className="summary-table">
          <thead><tr><th scope="col">{t('Obra')}</th><th scope="col">{t('Compositor')}</th><th scope="col">{t('Dificultad')}</th></tr></thead>
          <tbody>{preparing.slice(0, VISIBLE_ROWS).map(work => <tr key={work.id}>
            <td><button type="button" className="link-action" disabled={busy} onClick={() => onOpenWork(work.id)}>{work.title}</button>
              <span className="table-supporting">{work.file_name}</span></td>
            <td>{work.composer || '—'}</td>
            <td>{work.summary?.grade == null ? t('Sin analizar')
              : gradeText(work.summary, gradeScaleOf({ scale: { grades: work.summary.grade_max } }))}</td>
          </tr>)}</tbody>
        </table>}
        {preparing.length > VISIBLE_ROWS && <p className="table-supporting">{t('Y {count} más en Repertorio.', { count: preparing.length - VISIBLE_ROWS })}</p>}
      </Card>
    </div>
  </View>;
}
