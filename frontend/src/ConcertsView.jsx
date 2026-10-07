import React, { useEffect, useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import { proposalActivity } from './progress.js';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { ConcertEditor } from './ConcertEditor.jsx';
import { concertProgress, daysUntil, listConcerts, monthGrid, phaseLabel, planItemsToSave, proposeConcertPlan,
  saveConcertPlan } from './concerts.js';
import { RehearsalReview } from './RehearsalReview.jsx';
import { canReview, listRehearsals, proposalBlocks, rehearsalDateText, todayIso } from './rehearsals.js';
import { View } from './View.jsx';

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const DAY_NAMES = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];

function daysLeftText(concert, today) {
  const days = daysUntil(concert.date, today);
  if (days === 0) return 'Hoy';
  if (days < 0) return 'Celebrado';
  return days === 1 ? 'Falta 1 día' : 'Faltan ' + days + ' días';
}

// Month at a glance: concerts and the rehearsals that prepare them.
function MonthCalendar({ concerts, rehearsals }) {
  const now = new Date();
  const [shown, setShown] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const titles = Object.fromEntries(concerts.map(concert => [concert.id, concert.title]));
  const events = [...concerts.map(concert => ({ date: concert.date, kind: 'concert', label: concert.title })),
    ...rehearsals.filter(item => item.concert_id).map(item => ({ date: item.date, kind: 'rehearsal',
      label: phaseLabel(item.phase) + ' · ' + (titles[item.concert_id] || '') }))];
  const step = delta => setShown(({ year, month }) => {
    const index = year * 12 + month - 1 + delta;
    return { year: Math.floor(index / 12), month: index % 12 + 1 };
  });
  return <section className="month-calendar surface" aria-labelledby="month-title">
    <div className="summary-card-heading">
      <button type="button" className="secondary-action" aria-label="Mes anterior" onClick={() => step(-1)}>‹</button>
      <h2 id="month-title">{MONTHS[shown.month - 1][0].toUpperCase() + MONTHS[shown.month - 1].slice(1)} de {shown.year}</h2>
      <button type="button" className="secondary-action" aria-label="Mes siguiente" onClick={() => step(1)}>›</button>
    </div>
    <div className="month-grid" role="grid">
      {DAY_NAMES.map(name => <div key={name} className="month-day-name" role="columnheader">{name}</div>)}
      {monthGrid(shown.year, shown.month, events).flat().map((day, index) => day
        ? <div key={day.date} role="gridcell" className={'month-day' + (day.events.some(event => event.kind === 'concert') ? ' has-concert' : '')}>
            <span className="month-day-number">{day.day}</span>
            {day.events.map((event, at) => <span key={at} className={'month-event event-' + event.kind} title={event.label}>
              {event.kind === 'concert' ? event.label : phaseLabel(rehearsals.find(item => item.date === day.date && item.concert_id)?.phase)}
            </span>)}
          </div>
        : <div key={'empty-' + index} className="month-day is-empty" role="gridcell" />)}
    </div>
  </section>;
}

// The series that prepares a concert: proposed by the app, saved when the director has reviewed it,
// and replanned after the director's review of each rehearsal.
function ConcertPlanning({ concert, series, onChanged, onClose, onOpenBlock }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState(null);
  const progress = concertProgress(concert);
  const propose = async () => {
    setBusy(true); setError('');
    try { setPreview(await proposeConcertPlan(concert.id, todayIso())); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true); setError('');
    try { await saveConcertPlan(concert.id, todayIso(), planItemsToSave(preview.rehearsals)); setPreview(null); onChanged(); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const drop = index => setPreview(current => ({ ...current, rehearsals: current.rehearsals.filter((_, at) => at !== index) }));

  return <section id="concert-planning" className="surface concert-planning" aria-labelledby="concert-planning-title">
    <div className="summary-card-heading">
      <h2 id="concert-planning-title">Planificación · {concert.title}</h2>
      <button type="button" className="secondary-action" onClick={onClose}>Cerrar</button>
    </div>
    <p className="result-supporting">{progress.reviewed} de {progress.total} ensayos revisados · {concert.works.map(work => work.title).join(' · ') || 'Sin programa'}</p>
    {series.length > 0 && <ol className="series-list">{series.map(item => <li key={item.id} className="series-rehearsal">
      <div className="series-heading"><strong>{rehearsalDateText(item)}</strong><span className="status-tag">{phaseLabel(item.phase)}</span>
        {item.reviewed_at && <span className="status-tag">Revisado</span>}{item.fixed && <span className="status-tag">Fijo</span>}
        {canReview(item) && <button type="button" className="link-action" onClick={() => { setPreview(null); setReviewing(item); }}>Revisar</button>}</div>
      <AgendaCalendar blocks={item.blocks} start={item.time} onOpenBlock={onOpenBlock} />
    </li>)}</ol>}
    {reviewing && <RehearsalReview key={reviewing.id} rehearsal={reviewing}
      onSaved={() => { setReviewing(null); onChanged(); }} onCancel={() => setReviewing(null)} />}
    <div className="editor-actions">
      <button type="button" className="primary-action" disabled={busy} onClick={propose}>
        {busy && !preview ? 'Calculando…' : series.length ? 'Replanificar los ensayos siguientes' : 'Proponer planificación'}</button>
    </div>
    <ActivityStatus id="concert-plan-activity" label={busy && !preview ? proposalActivity('concert', (concert.works || []).length) : ''} />
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {preview && <div className="plan-preview">
      <p className="proposal-note" role="status">Propuesta calculada con el análisis de cada obra{series.length ? ' y tus revisiones' : ''}: revísala antes de guardar.
        {preview.kept?.length ? ' Se mantienen ' + preview.kept.length + ' ensayos ya revisados, pasados o fijos.' : ''}</p>
      {preview.rehearsals.length === 0 && <p className="result-supporting">No quedan ensayos que replanificar.</p>}
      <ol className="series-list">{preview.rehearsals.map((item, index) => <li key={item.id || item.date} className="planned-rehearsal">
        <div className="series-heading"><strong>{rehearsalDateText(item)}</strong><span className="status-tag">{phaseLabel(item.phase)}</span>
          {!item.id && <button type="button" className="link-action" onClick={() => drop(index)}>Quitar</button>}</div>
        <AgendaCalendar blocks={proposalBlocks(item)} start={item.time} onOpenBlock={onOpenBlock} />
        {item.omitted_works.length > 0 && <p className="table-supporting">No caben en este ensayo: {item.omitted_works.length} obra(s); irán las primeras en el siguiente.</p>}
      </li>)}</ol>
      <div className="editor-actions">
        <button type="button" className="primary-action" disabled={busy || preview.rehearsals.length === 0} onClick={save}>Guardar planificación</button>
        <button type="button" className="secondary-action" onClick={() => setPreview(null)}>Descartar</button>
      </div>
    </div>}
  </section>;
}

export function ConcertsView({ active, hidden, onOpenBlock }) {
  const [concerts, setConcerts] = useState([]);
  const [rehearsals, setRehearsals] = useState([]);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(null);
  const [planning, setPlanning] = useState(null);
  const visible = !hidden && active === 'concerts';
  const refresh = () => Promise.all([listConcerts(), listRehearsals()])
    .then(([found, saved]) => { setConcerts(found); setRehearsals(saved); setError(''); })
    .catch(failure => setError(failure.message));
  useEffect(() => { if (visible) refresh(); }, [visible]);
  const today = todayIso();
  const upcoming = concerts.filter(concert => concert.date >= today), past = concerts.filter(concert => concert.date < today).reverse();
  const planned = concerts.find(concert => concert.id === planning);
  const action = <button id="create-concert" type="button" className="primary-action" onClick={() => { setPlanning(null); setEditing({}); }}>Crear concierto</button>;

  const item = concert => {
    const progress = concertProgress(concert);
    return <li key={concert.id} className="works-item concert-item">
      <div className="works-copy">
        <h3 className="works-title">{concert.title}</h3>
        <p className="result-supporting">{[rehearsalDateText(concert), concert.place, daysLeftText(concert, today)].filter(Boolean).join(' · ')}</p>
        <p className="works-summary">{concert.works.map(work => work.title).join(' · ') || 'Sin programa'}</p>
        <p className="table-supporting">{progress.total ? progress.reviewed + ' de ' + progress.total + ' ensayos revisados' : 'Sin ensayos planificados'}</p>
      </div>
      <div className="works-actions">
        <button type="button" className="primary-action" onClick={() => { setEditing(null); setPlanning(concert.id); }}>Planificación</button>
        <button type="button" className="secondary-action" onClick={() => { setPlanning(null); setEditing(concert); }}>Editar</button>
      </div>
    </li>;
  };

  return <View name="concerts" active={active} eyebrow="Temporada" title="Conciertos"
    description="Cada concierto con su programa y la serie de ensayos que lo prepara." action={action}>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {editing && <ConcertEditor key={editing.id || 'new'} concert={editing}
      onSaved={() => { setEditing(null); refresh(); }} onCancel={() => setEditing(null)} />}
    {planned && <ConcertPlanning key={planned.id} concert={planned}
      series={rehearsals.filter(rehearsal => rehearsal.concert_id === planned.id)} onChanged={refresh} onClose={() => setPlanning(null)}
      onOpenBlock={onOpenBlock} />}
    <div className="concerts-layout">
      <div>
        <section className="rehearsal-list" aria-labelledby="concerts-upcoming-title">
          <h2 id="concerts-upcoming-title" className="panel-title">Próximos</h2>
          {upcoming.length === 0 ? <p className="result-supporting">No hay conciertos programados.</p>
            : <ul className="works-list">{upcoming.map(item)}</ul>}
        </section>
        {past.length > 0 && <section className="rehearsal-list" aria-labelledby="concerts-past-title">
          <h2 id="concerts-past-title" className="panel-title">Celebrados</h2>
          <ul className="works-list">{past.map(item)}</ul>
        </section>}
      </div>
      <MonthCalendar concerts={concerts} rehearsals={rehearsals} />
    </div>
  </View>;
}
