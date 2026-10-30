import React, { useEffect, useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import { proposalActivity } from './progress.js';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { ConcertEditor } from './ConcertEditor.jsx';
import { concertProgress, daysUntil, listConcerts, monthGrid, phaseLabel, planItemsToSave, proposeConcertPlan,
  saveConcertPlan, weekdays } from './concerts.js';
import { dateLocale, t } from './i18n.js';
import { RehearsalReview } from './RehearsalReview.jsx';
import { canReview, listRehearsals, proposalBlocks, rehearsalDateText, todayIso } from './rehearsals.js';
import { View } from './View.jsx';

// «Noviembre de 2026» / «November 2026».
const monthTitle = (year, month) => {
  const text = new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString(dateLocale(), { month: 'long', year: 'numeric', timeZone: 'UTC' });
  return text[0].toUpperCase() + text.slice(1);
};

function daysLeftText(concert, today) {
  const days = daysUntil(concert.date, today);
  if (days === 0) return t('Hoy');
  if (days < 0) return t('Celebrado');
  return t(days === 1 ? 'Falta {count} día' : 'Faltan {count} días', { count: days });
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
      <button type="button" className="secondary-action" aria-label={t('Mes anterior')} onClick={() => step(-1)}>‹</button>
      <h2 id="month-title">{monthTitle(shown.year, shown.month)}</h2>
      <button type="button" className="secondary-action" aria-label={t('Mes siguiente')} onClick={() => step(1)}>›</button>
    </div>
    {/* A table of weeks for screen readers (WCAG 1.3.1); the rows do not affect the layout of the grid. */}
    <div className="month-grid" role="table" aria-labelledby="month-title">
      <div className="month-row" role="row">
        {weekdays().map(([day, short, name]) => <div key={day} className="month-day-name" role="columnheader" title={name}>{short}</div>)}
      </div>
      {monthGrid(shown.year, shown.month, events).map((week, row) => <div key={row} className="month-row" role="row">
        {week.map((day, index) => day
          ? <div key={day.date} role="cell" className={'month-day' + (day.events.some(event => event.kind === 'concert') ? ' has-concert' : '')}>
              <span className="month-day-number">{day.day}</span>
              {day.events.map((event, at) => <span key={at} className={'month-event event-' + event.kind} title={event.label}>
                {event.kind === 'concert' ? event.label : phaseLabel(rehearsals.find(item => item.date === day.date && item.concert_id)?.phase)}
              </span>)}
            </div>
          : <div key={'empty-' + index} className="month-day is-empty" role="cell" />)}
      </div>)}
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
      <h2 id="concert-planning-title">{t('Planificación · {title}', { title: concert.title })}</h2>
      <button type="button" className="secondary-action" onClick={onClose}>{t('Cerrar')}</button>
    </div>
    <p className="result-supporting">{t('{reviewed} de {total} ensayos revisados', progress)} · {concert.works.map(work => work.title).join(' · ') || t('Sin programa')}</p>
    {series.length > 0 && <ol className="series-list">{series.map(item => <li key={item.id} className="series-rehearsal">
      <div className="series-heading"><strong>{rehearsalDateText(item)}</strong><span className="status-tag">{phaseLabel(item.phase)}</span>
        {item.reviewed_at && <span className="status-tag">{t('Revisado')}</span>}{item.fixed && <span className="status-tag">{t('Fijo')}</span>}
        {canReview(item) && <button type="button" className="link-action" onClick={() => { setPreview(null); setReviewing(item); }}>{t('Revisar')}</button>}</div>
      <AgendaCalendar blocks={item.blocks} start={item.time} onOpenBlock={onOpenBlock} />
    </li>)}</ol>}
    {reviewing && <RehearsalReview key={reviewing.id} rehearsal={reviewing}
      onSaved={() => { setReviewing(null); onChanged(); }} onCancel={() => setReviewing(null)} />}
    <div className="editor-actions">
      <button type="button" className="primary-action" disabled={busy} onClick={propose}>
        {busy && !preview ? t('Calculando…') : series.length ? t('Replanificar los ensayos siguientes') : t('Proponer planificación')}</button>
    </div>
    <ActivityStatus id="concert-plan-activity" label={busy && !preview ? proposalActivity('concert', (concert.works || []).length) : ''} />
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {preview && <div className="plan-preview">
      <p className="proposal-note" role="status">{series.length ? t('Propuesta calculada con el análisis de cada obra y tus revisiones: revísala antes de guardar.')
        : t('Propuesta calculada con el análisis de cada obra: revísala antes de guardar.')}
        {preview.kept?.length ? ' ' + t('Se mantienen {count} ensayos ya revisados, pasados o fijos.', { count: preview.kept.length }) : ''}</p>
      {preview.rehearsals.length === 0 && <p className="result-supporting">{t('No quedan ensayos que replanificar.')}</p>}
      <ol className="series-list">{preview.rehearsals.map((item, index) => <li key={item.id || item.date} className="planned-rehearsal">
        <div className="series-heading"><strong>{rehearsalDateText(item)}</strong><span className="status-tag">{phaseLabel(item.phase)}</span>
          {!item.id && <button type="button" className="link-action" onClick={() => drop(index)}>{t('Quitar')}</button>}</div>
        <AgendaCalendar blocks={proposalBlocks(item)} start={item.time} onOpenBlock={onOpenBlock} />
        {item.omitted_works.length > 0 && <p className="table-supporting">{t('No caben en este ensayo: {count} obra(s); irán las primeras en el siguiente.', { count: item.omitted_works.length })}</p>}
      </li>)}</ol>
      <div className="editor-actions">
        <button type="button" className="primary-action" disabled={busy || preview.rehearsals.length === 0} onClick={save}>{t('Guardar planificación')}</button>
        <button type="button" className="secondary-action" onClick={() => setPreview(null)}>{t('Descartar')}</button>
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
  const action = <button id="create-concert" type="button" className="primary-action" onClick={() => { setPlanning(null); setEditing({}); }}>{t('Crear concierto')}</button>;

  const item = concert => {
    const progress = concertProgress(concert);
    return <li key={concert.id} className="works-item concert-item">
      <div className="works-copy">
        <h3 className="works-title">{concert.title}</h3>
        <p className="result-supporting">{[rehearsalDateText(concert), concert.place, daysLeftText(concert, today)].filter(Boolean).join(' · ')}</p>
        <p className="works-summary">{concert.works.map(work => work.title).join(' · ') || t('Sin programa')}</p>
        <p className="table-supporting">{progress.total ? t('{reviewed} de {total} ensayos revisados', progress) : t('Sin ensayos planificados')}</p>
      </div>
      <div className="works-actions">
        <button type="button" className="primary-action" onClick={() => { setEditing(null); setPlanning(concert.id); }}>{t('Planificación')}</button>
        <button type="button" className="secondary-action" onClick={() => { setPlanning(null); setEditing(concert); }}>{t('Editar')}</button>
      </div>
    </li>;
  };

  return <View name="concerts" active={active} eyebrow={t('Temporada')} title={t('Conciertos')}
    description={t('Cada concierto con su programa y la serie de ensayos que lo prepara.')} action={action}>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {editing && <ConcertEditor key={editing.id || 'new'} concert={editing}
      onSaved={() => { setEditing(null); refresh(); }} onCancel={() => setEditing(null)} />}
    {planned && <ConcertPlanning key={planned.id} concert={planned}
      series={rehearsals.filter(rehearsal => rehearsal.concert_id === planned.id)} onChanged={refresh} onClose={() => setPlanning(null)}
      onOpenBlock={onOpenBlock} />}
    <div className="concerts-layout">
      <div>
        <section className="rehearsal-list" aria-labelledby="concerts-upcoming-title">
          <h2 id="concerts-upcoming-title" className="panel-title">{t('Próximos')}</h2>
          {upcoming.length === 0 ? <p className="result-supporting">{t('No hay conciertos programados.')}</p>
            : <ul className="works-list">{upcoming.map(item)}</ul>}
        </section>
        {past.length > 0 && <section className="rehearsal-list" aria-labelledby="concerts-past-title">
          <h2 id="concerts-past-title" className="panel-title">{t('Celebrados')}</h2>
          <ul className="works-list">{past.map(item)}</ul>
        </section>}
      </div>
      <MonthCalendar concerts={concerts} rehearsals={rehearsals} />
    </div>
  </View>;
}
