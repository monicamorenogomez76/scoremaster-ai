import React from 'react';
import { View } from './View.jsx';
import { omittedBlockText, rehearsalBlockDetail, rehearsalBlockTitle } from './labels.js';

const VISIBLE_OMITTED = 5;

export function RehearsalView({ active, data, minutes, onMinutesChange, onRecalculate, busy }) {
  const plan = data?.rehearsal_plan || {};
  const blocks = plan.segments || [];
  const omitted = plan.omitted || [];
  return <View name="rehearsal" active={active} eyebrow="RehearsalAI" title="Plan de ensayo"
    description="Ensayo de conjunto: bloques seccionales por pasajes comunes y un tutti final para juntar.">
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
