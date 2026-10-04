import React, { useState } from 'react';
import { View } from './View.jsx';
import { blockScoreLabel, calendarLabel, omittedBlockText, rehearsalBlockDetail, rehearsalBlockTitle } from './labels.js';
import { rehearsalSchedule } from './schedule.js';

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

export function RehearsalView({ active, data, minutes, onMinutesChange, onRecalculate, busy, onOpenPassage }) {
  const plan = data?.rehearsal_plan || {};
  const blocks = plan.segments || [];
  const omitted = plan.omitted || [];
  return <View name="rehearsal" active={active} eyebrow="RehearsalAI" title="Plan de ensayo"
    description="Ensayo de conjunto: primero quienes tocan lo mismo, después las subsecciones y un tutti final para juntar.">
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
            <h2>Bloques recomendados</h2>
            <p className="result-supporting">Duración total: {plan.total_minutes ?? 0} minutos · Planificado: {plan.planned_minutes ?? 0} de {plan.total_minutes ?? 0} minutos</p>
            {blocks.length > 0 && <RehearsalCalendar blocks={blocks} onOpenPassage={onOpenPassage} />}
            <ol className="result-list">{blocks.length === 0
              ? <li className="result-empty">No hay bloques de ensayo disponibles.</li>
              : blocks.map((block, index) => <li key={index} className={'rehearsal-block rehearsal-block--' + block.type}>
                  <strong className="rehearsal-block-title">{rehearsalBlockTitle(block)}</strong> · {block.minutes} min
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
