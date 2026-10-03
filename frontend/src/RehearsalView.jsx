import React from 'react';
import { View } from './View.jsx';
import { rehearsalSegmentText } from './labels.js';

const VISIBLE_SEGMENTS = 10;

export function RehearsalView({ active, data, minutes, onMinutesChange, onRecalculate, busy }) {
  const plan = data?.rehearsal_plan || {};
  const segments = (plan.segments || []).map(rehearsalSegmentText);
  return <View name="rehearsal" active={active} eyebrow="RehearsalAI" title="Plan de ensayo"
    description="Bloques priorizados a partir de los pasajes detectados.">
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
            <p className="result-supporting">Duración total: {plan.total_minutes ?? 0} minutos</p>
            <ul className="result-list">{segments.length === 0
              ? <li className="result-empty">No hay bloques de ensayo disponibles.</li>
              : segments.slice(0, VISIBLE_SEGMENTS).map((segment, index) => <li key={index}>{segment}</li>)}</ul>
            {segments.length > VISIBLE_SEGMENTS && <p className="result-supporting">{segments.length - VISIBLE_SEGMENTS} bloques adicionales no mostrados.</p>}
          </section>
        </div>
      : <div id="rehearsal-content" className="view-content empty-workspace"><h2>Aún no hay plan</h2><p>Analiza una partitura para generar bloques de ensayo.</p></div>}
  </View>;
}
