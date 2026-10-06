import React, { useEffect, useState } from 'react';
import { View } from './View.jsx';
import { blockScoreLabel, calendarLabel, omittedBlockText, rehearsalBlockDetail, rehearsalBlockTitle } from './labels.js';
import { rehearsalSchedule } from './schedule.js';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { RehearsalEditor } from './RehearsalEditor.jsx';
import { RehearsalReview } from './RehearsalReview.jsx';
import { canReview, listRehearsals, rehearsalDateText, splitRehearsals } from './rehearsals.js';

const VISIBLE_OMITTED = 5;

// Timeline of the rehearsal: each block is as wide as its minutes; pressing it opens the score
// at its measures with only the instruments it involves (the whole band for the tutti).
function RehearsalCalendar({ blocks, onOpenPassage }) {
  const [start, setStart] = useState('19:00');
  const schedule = rehearsalSchedule(blocks, start);
  const open = (block, range) => onOpenPassage(block.parts, range, blockScoreLabel(block));
  return <div className="rehearsal-calendar">
    <label className="duration-field" htmlFor="rehearsal-start">Hora de inicio
      <input id="rehearsal-start" type="time" value={start} onChange={event => setStart(event.target.value)} />
    </label>
    <div className="calendar-track" role="list" aria-label="Horario del ensayo">
      {schedule.map((block, index) => {
        const ranges = block.type === 'tutti' ? block.measure_ranges || [] : [block.measure_range];
        return <div key={index} role="listitem" className={'calendar-slot calendar-slot--' + (block.type === 'sectional' ? block.group : block.type)}
          style={{ flexGrow: block.share, flexBasis: 0 }}>
          <button type="button" className="calendar-block" disabled={!ranges.length}
            aria-label={block.start + '–' + block.end + ' · ' + rehearsalBlockTitle(block) + ' · ' + block.minutes + ' min'}
            onClick={() => open(block, ranges[0])}>
            <span className="calendar-time">{block.start}</span>
            <span className="calendar-name">{calendarLabel(block)}</span>
          </button>
          {ranges.length > 1 && <div className="calendar-ranges">{ranges.map(range =>
            <button key={range} type="button" className="calendar-range" aria-label={'Abrir compases ' + range + ' con toda la banda'}
              onClick={() => open(block, range)}>{range}</button>)}</div>}
        </div>;
      })}
    </div>
  </div>;
}

function RehearsalList({ id, title, items, empty, onEdit, onReview, onOpenBlock }) {
  return <section id={id} className="rehearsal-list" aria-labelledby={id + '-title'}>
    <h3 id={id + '-title'}>{title}</h3>
    {items.length === 0 ? <p className="result-supporting">{empty}</p>
      : <ul className="works-list">{items.map(item => <li key={item.id} className="works-item rehearsal-item">
          <div className="works-copy">
            <h4 className="works-title">{rehearsalDateText(item)}</h4>
            <p className="result-supporting">{[item.duration_minutes + ' minutos', item.place, item.works.map(work => work.title).join(', ') || 'Sin obras']
              .filter(Boolean).join(' · ')}</p>
            <p className="works-summary">{item.blocks.length === 1 ? '1 bloque' : item.blocks.length + ' bloques'}</p>
            <AgendaCalendar blocks={item.blocks} start={item.time} onOpenBlock={onOpenBlock} />
          </div>
          <div className="works-actions">
            {canReview(item) && <button type="button" className="primary-action" onClick={() => onReview(item)}>{item.reviewed_at ? 'Ver revisión' : 'Revisar'}</button>}
            <button type="button" className="secondary-action" onClick={() => onEdit(item)}>Editar</button>
          </div>
        </li>)}</ul>}
  </section>;
}

// Saved rehearsals: create one, edit its agenda, or consult the ones already held.
function SavedRehearsals({ visible, editing, onEdit, onCloseEditor, onOpenBlock }) {
  const [rehearsals, setRehearsals] = useState([]);
  const [error, setError] = useState('');
  const [reviewing, setReviewing] = useState(null);
  const refresh = () => listRehearsals().then(found => { setRehearsals(found); setError(''); }).catch(failure => setError(failure.message));
  useEffect(() => { if (visible) refresh(); }, [visible]);
  const { upcoming, past } = splitRehearsals(rehearsals);
  return <section id="saved-rehearsals" className="saved-rehearsals" aria-labelledby="saved-rehearsals-title">
    <div className="section-toolbar">
      <h2 id="saved-rehearsals-title">Ensayos guardados</h2>
      <button id="create-rehearsal" type="button" className="primary-action" onClick={() => onEdit({})}>Crear ensayo</button>
    </div>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {editing && <RehearsalEditor key={editing.id || editing.key || 'new'} rehearsal={editing}
      onSaved={() => { onCloseEditor(); refresh(); }} onCancel={onCloseEditor} />}
    {reviewing && <RehearsalReview key={reviewing.id} rehearsal={reviewing}
      onSaved={() => { setReviewing(null); refresh(); }} onCancel={() => setReviewing(null)} />}
    <RehearsalList id="rehearsals-upcoming" title="Próximos" items={upcoming} empty="No hay ensayos programados." onEdit={onEdit} onReview={setReviewing} onOpenBlock={onOpenBlock} />
    <RehearsalList id="rehearsals-past" title="Realizados" items={past} empty="Aún no hay ensayos realizados." onEdit={onEdit} onReview={setReviewing} onOpenBlock={onOpenBlock} />
  </section>;
}

export function RehearsalView({ active, hidden, onOpenBlock, data, minutes, onMinutesChange, onRecalculate, busy, onOpenPassage, editing, onEdit, onCloseEditor }) {
  const plan = data?.rehearsal_plan || {};
  const blocks = plan.segments || [];
  const omitted = plan.omitted || [];
  return <View name="rehearsal" active={active} eyebrow="Ensayos" title="Ensayos"
    description="Programa las sesiones con su agenda y consulta las que ya se han hecho.">
    <SavedRehearsals visible={!hidden && active === 'rehearsal'} editing={editing} onEdit={onEdit} onCloseEditor={onCloseEditor} onOpenBlock={onOpenBlock} />
    <h2 className="calculated-plan-title">Plan calculado de la obra abierta</h2>
    <p className="result-supporting">Ensayo de conjunto: primero quienes tocan lo mismo, después las subsecciones y un tutti final para juntar.</p>
    <div className="rehearsal-settings surface">
      <label className="duration-field" htmlFor="total-minutes">Duración prevista del ensayo
        <span className="duration-input"><input id="total-minutes" type="number" min="10" value={minutes}
          onChange={event => onMinutesChange(event.target.value)} /><span>minutos</span></span>
      </label>
      <button id="recalculate-rehearsal" type="button" disabled={busy} onClick={onRecalculate}>
        {busy ? 'Recalculando…' : 'Recalcular ensayo'}
      </button>
    </div>
    {data
      ? <div id="rehearsal-content" className="view-content">
          <section className="result-section result-section--wide">
            <h2>Bloques recomendados · {data.title || 'Partitura sin título'}</h2>
            <p className="result-supporting">Duración total: {plan.total_minutes ?? 0} minutos · Planificado: {plan.planned_minutes ?? 0} de {plan.total_minutes ?? 0} minutos</p>
            {blocks.length > 0 && <RehearsalCalendar blocks={blocks} onOpenPassage={onOpenPassage} />}
            <ol className="result-list">{blocks.length === 0
              ? <li className="result-empty">No hay bloques de ensayo disponibles.</li>
              : blocks.map((block, index) => <li key={index} className={'rehearsal-block rehearsal-block--' + block.type}>
                  <strong className="rehearsal-block-title">{rehearsalBlockTitle(block)}</strong> · {block.minutes} min
                  <div className="rehearsal-block-work">Obra: {data.title || 'Partitura sin título'}</div>
                  <div className="result-supporting">{rehearsalBlockDetail(block)}</div>
                </li>)}</ol>
            {omitted.length > 0 && <>
              <h3>No caben en este ensayo ({omitted.length})</h3>
              <ul className="result-list">{omitted.slice(0, VISIBLE_OMITTED).map((block, index) =>
                <li key={index} className="result-supporting">{omittedBlockText(block)}</li>)}</ul>
              {omitted.length > VISIBLE_OMITTED && <p className="result-supporting">Y {omitted.length - VISIBLE_OMITTED} más, de menor prioridad.</p>}
            </>}
          </section>
        </div>
      : <div id="rehearsal-content" className="view-content empty-workspace"><h2>Aún no hay plan</h2><p>Analiza una partitura para generar bloques de ensayo.</p></div>}
  </View>;
}
