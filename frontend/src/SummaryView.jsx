import React, { useEffect, useState } from 'react';
import { gradeScaleOf, gradeText } from './labels.js';
import { listConcerts, nextConcert } from './concerts.js';
import { listPriorities, listWorks } from './library.js';
import { blockWorkText, listRehearsals, listReviewPriorities, nextRehearsal, rehearsalDateText, summaryPriorityRows,
  todayIso } from './rehearsals.js';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { SectionWork } from './SectionWork.jsx';
import { planCounts } from './dashboard.js';
import { NextStep } from './NextStep.jsx';
import { View } from './View.jsx';

// At a glance on a computer (author's request, 2026-10-05): a few rows, the rest one click away.
const VISIBLE_ROWS = 4;

function Card({ id, title, action, children }) {
  return <section id={id} className="summary-card surface" aria-labelledby={id + '-title'}>
    <header className="summary-card-heading"><h2 id={id + '-title'}>{title}</h2>{action}</header>
    {children}
  </section>;
}

// Home of the director, after the author's mock-up: the next rehearsal (with the next step of the
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
  const gradeOf = workId => (works || []).find(work => work.id === workId)?.summary?.grade;
  const action = <button id="plan-rehearsal" className="primary-action" type="button" onClick={onPlanRehearsal}>Planificar ensayo</button>;

  // The next concert takes the place of the description, so the summary still fits at a glance.
  const description = concert
    ? <span id="next-concert"><strong>Próximo concierto:</strong> {[concert.concert.title, rehearsalDateText(concert.concert),
        concert.days === 0 ? 'hoy' : 'faltan ' + concert.days + (concert.days === 1 ? ' día' : ' días'),
        concert.remaining + (concert.remaining === 1 ? ' ensayo' : ' ensayos')].join(' · ')}{' '}
        <button type="button" className="link-action" onClick={() => onNavigate('concerts')}>Ver conciertos</button>
        {(concert.concert.works || []).length > 0 && <span className="programme" aria-label="Programa del concierto">
          {concert.concert.works.map(work => <span key={work.id} className="programme-chip">{work.title}
            {gradeOf(work.id) != null && <> · <strong>Grado {gradeOf(work.id)}</strong></>}</span>)}
        </span>}</span>
    : 'Lo que necesitas para dirigir la próxima sesión.';
  return <View name="summary" active={active} eyebrow="Resumen" title="Tu próximo ensayo, preparado"
    description={description} action={action}>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="summary-layout">
      <Card id="summary-rehearsal" title={next?.date === todayIso() ? 'Ensayo de hoy' : 'Próximo ensayo'}
        action={next ? <span className="card-actions">
            {next.blocks.length > 0 && <button type="button" className="link-action detail-toggle" aria-expanded={detail}
              onClick={() => setDetail(open => !open)}>{detail ? 'Ocultar detalle' : 'Ver detalle'}</button>}
            <button id="edit-rehearsal" type="button" className="link-action" onClick={() => onEditRehearsal(next)}>Editar</button>
          </span> : link('Ir a Ensayos', 'rehearsal')}>
        <NextStep concerts={concerts} rehearsals={rehearsals || []} onReviewRehearsal={onReviewRehearsal}
          onOpenBlock={onOpenBlock} onChanged={() => setRevision(value => value + 1)} />
        {rehearsals && !next && <div className="empty-workspace"><h3>No hay ensayos programados</h3>
          <p>Planifica el próximo ensayo con sus obras y su agenda para tenerlo aquí.</p></div>}
        {next && <>
          <p className="result-supporting">{[rehearsalDateText(next), next.duration_minutes + ' minutos', next.place].filter(Boolean).join(' · ')}</p>
          <AgendaCalendar blocks={next.blocks} start={next.time} onOpenBlock={onOpenBlock} />
          {next.blocks.length === 0 && <p className="result-supporting">Este ensayo aún no tiene agenda.</p>}
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


      <Card id="summary-priorities" title="Prioridades por sección">
        {priorityRows && priorityRows.length === 0 && <div className="empty-workspace"><h3>Sin prioridades por ahora</h3>
          <p>Aquí aparecen lo pendiente de tu última revisión de ensayo y los pasajes críticos de las obras en preparación.</p></div>}
        {priorityRows && priorityRows.length > 0 && <table className="summary-table">
          <thead><tr><th scope="col">Sección</th><th scope="col">Obra</th><th scope="col">Pasaje</th><th scope="col">Motivo</th><th scope="col">Origen</th></tr></thead>
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
        {priorityRows && priorityRows.length > VISIBLE_ROWS && <p className="table-supporting">Y {priorityRows.length - VISIBLE_ROWS} más.</p>}
      </Card>
      <Card id="summary-plan" title="Dónde trabajar"><SectionWork counts={counts} /></Card>
      <Card id="summary-works" title="Obras en preparación" action={link('Ver repertorio', 'repertoire')}>
        {works && preparing.length === 0 && <div className="empty-workspace"><h3>Ninguna obra en preparación</h3>
          <p>Marca en Repertorio las obras que estáis preparando para seguirlas desde aquí.</p></div>}
        {preparing.length > 0 && <table className="summary-table">
          <thead><tr><th scope="col">Obra</th><th scope="col">Compositor</th><th scope="col">Dificultad</th></tr></thead>
          <tbody>{preparing.slice(0, VISIBLE_ROWS).map(work => <tr key={work.id}>
            <td><button type="button" className="link-action" disabled={busy} onClick={() => onOpenWork(work.id)}>{work.title}</button>
              <span className="table-supporting">{work.file_name}</span></td>
            <td>{work.composer || '—'}</td>
            <td>{work.summary?.grade == null ? 'Sin analizar'
              : gradeText(work.summary, gradeScaleOf({ scale: { grades: work.summary.grade_max } }))}</td>
          </tr>)}</tbody>
        </table>}
        {preparing.length > VISIBLE_ROWS && <p className="table-supporting">Y {preparing.length - VISIBLE_ROWS} más en Repertorio.</p>}
      </Card>
    </div>
  </View>;
}
