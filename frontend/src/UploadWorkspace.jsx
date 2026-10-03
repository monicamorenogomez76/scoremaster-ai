import React, { useRef } from 'react';
import { instrumentChoices } from './instrument-session.js';
import { useScoreAnalysis } from './useScoreAnalysis.js';

export function UploadWorkspace({ workspace }) {
  const upload = useScoreAnalysis(workspace);
  const input = useRef(null);
  const { state, parts, assignments } = upload;
  return <>
    <form id="upload-form" onSubmit={event => { event.preventDefault(); upload.submit(); }} aria-busy={state.busy}>
      <label className="file-field" htmlFor="file">Archivo de partitura
        <input id="file" ref={input} type="file" accept=".musicxml,.mxl,.xml" required
          onChange={event => upload.selectFile(event.target.files[0] || null)} />
      </label>
      <button type="submit" disabled={state.busy}>{state.busy ? 'Cargando…' : 'Subir y analizar'}</button>
      <button id="new-score" type="button" className="score-tool" onClick={() => {
        input.current.value = ''; upload.reset(); input.current.focus();
      }}>Nueva partitura</button>
      <div id="instrument-assignment" className="instrument-assignment" hidden={!parts.length}>
        {parts.length > 0 && <p>El archivo no identifica estos instrumentos. Asígnalos para analizar y escuchar sus sonidos correctos.</p>}
        {parts.map(part => <label key={part.id}>Parte {part.number}{' '}
          <select data-part-id={part.id} value={assignments[part.id] || ''} disabled={state.busy}
            onChange={event => upload.setAssignments(previous => ({ ...previous, [part.id]: event.target.value }))}>
            <option value="">Sin identificar</option>
            {instrumentChoices.map(([name]) => <option key={name} value={name}>{workspace.displayInstrumentName(name)}</option>)}
          </select>
        </label>)}
      </div>
    </form>
    <div id="result" className="analysis-status" hidden={!state.message} aria-live="polite"
      role={state.error ? 'alert' : 'status'} aria-busy={state.busy}>{state.message}</div>
  </>;
}
