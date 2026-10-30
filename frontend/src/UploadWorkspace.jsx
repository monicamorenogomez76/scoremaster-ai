import React, { useRef } from 'react';
import { instrumentChoices } from './instrument-session.js';
import { displayInstrumentName } from './labels.js';
import { t } from './i18n.js';

export function UploadWorkspace({ upload }) {
  const input = useRef(null);
  const { state, parts, assignments } = upload;
  return <>
    <form id="upload-form" onSubmit={event => { event.preventDefault(); upload.submit(); }} aria-busy={state.busy}>
      <label className="file-field" htmlFor="file">{t('Archivo de partitura')}
        <input id="file" ref={input} type="file" accept=".musicxml,.mxl,.xml" required
          onChange={event => upload.selectFile(event.target.files[0] || null)} />
      </label>
      <button type="submit" disabled={state.busy}>{state.busy ? t('Cargando…') : t('Subir y analizar')}</button>
      <button id="new-score" type="button" className="score-tool" onClick={() => {
        input.current.value = ''; upload.reset(); input.current.focus();
      }}>{t('Nueva partitura')}</button>
      <div id="instrument-assignment" className="instrument-assignment" hidden={!parts.length}>
        {parts.length > 0 && <p>{t('El archivo no identifica estos instrumentos. Asígnalos para analizar y escuchar sus sonidos correctos.')}</p>}
        {parts.map(part => <label key={part.id}>{t('Parte {number}', { number: part.number })}{' '}
          <select data-part-id={part.id} value={assignments[part.id] || ''} disabled={state.busy}
            onChange={event => upload.setAssignments(previous => ({ ...previous, [part.id]: event.target.value }))}>
            <option value="">{t('Sin identificar')}</option>
            {instrumentChoices.map(([name]) => <option key={name} value={name}>{displayInstrumentName(name)}</option>)}
          </select>
        </label>)}
      </div>
    </form>
    {/* While busy, the step and its time are shown in the top bar, visible from every view. */}
    <div id="result" className="analysis-status" hidden={!state.message || state.busy} aria-live="polite"
      role={state.error ? 'alert' : 'status'}>{state.busy ? '' : state.message}</div>
  </>;
}
