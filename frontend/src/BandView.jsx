import React from 'react';
import { View } from './View.jsx';
import { apiInstrumentName, bandIssueText, bandStatusLabels, displayInstrumentName, uniqueParts } from './labels.js';

export function BandView({ active, data, draft, onDraftChange, onUpdate, busy }) {
  const parts = uniqueParts(data?.parts);
  const bandFit = data?.band_fit || {};
  const issues = (bandFit.issues || []).map(bandIssueText);
  return <View name="band" active={active} eyebrow="BandFit" title="Mi banda"
    description="Ajusta el número de músicos para cada parte de la obra.">
    <div id="band-profile-editor" className="band-profile-editor surface" hidden={parts.length === 0}>
      <fieldset>
        <legend>Plantilla de esta obra</legend>
        <p className="result-supporting">Una plaza inicial por parte. Los cambios son temporales en esta demo.</p>
        <div id="band-profile-rows" className="band-profile-rows">{parts.map(part => {
          const key = apiInstrumentName(part);
          return <label key={part} className="band-profile-row">
            <span>{displayInstrumentName(part)}</span>
            <input type="number" min="0" step="1" value={draft[key] ?? '1'} aria-label={'Músicos para ' + displayInstrumentName(part)}
              onChange={event => onDraftChange(previous => ({ ...previous, [key]: event.target.value }))} />
          </label>;
        })}</div>
        <button id="update-analysis" className="band-profile-update" type="button" disabled={busy} onClick={onUpdate}>
          {busy ? 'Actualizando…' : 'Actualizar análisis'}
        </button>
      </fieldset>
    </div>
    {data
      ? <div id="band-content" className="view-content">
          <section className="result-section">
            <h2>Adaptación a la banda</h2>
            <p className="result-metric">{(bandFit.compatibility_percent ?? 0) + '%'}</p>
            <p className="result-supporting">{bandStatusLabels[bandFit.status] || 'Estado no disponible'}</p>
            <ul className="result-list">{issues.length === 0
              ? <li className="result-empty">La plantilla cubre los instrumentos requeridos.</li>
              : issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>
          </section>
        </div>
      : <div id="band-content" className="view-content empty-workspace"><h2>Aún no hay plantilla</h2><p>Analiza una obra para cargar sus partes y asignar músicos.</p></div>}
  </View>;
}
