import React, { useState } from 'react';
import { blockWorkText, proposalBlocks, proposeRehearsal } from './rehearsals.js';

// Right column of the summary, as in the author's mock-up. Until the AI provider arrives (F2b) the
// proposal is the deterministic calculation, and the panel says so: it never passes for AI.
export function SummaryAssistant({ works, defaultMinutes, onReview }) {
  const [minutes, setMinutes] = useState(String(defaultMinutes || 90));
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generate = async () => {
    setBusy(true); setError('');
    try {
      const proposal = await proposeRehearsal(works.map(work => work.id), Number(minutes) || 0);
      setDraft({ minutes: Number(minutes), blocks: proposalBlocks(proposal), skipped: proposal.omitted_works.map(item => item.title) });
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const review = () => onReview({ key: 'draft-' + Date.now(), duration_minutes: draft.minutes,
    works: works.map(work => ({ id: work.id, title: work.title })), blocks: draft.blocks });

  return <section id="summary-assistant" className="summary-card summary-assistant surface" aria-labelledby="summary-assistant-title">
    <div className="summary-card-heading">
      <h2 id="summary-assistant-title">Asistente de ensayo</h2>
      <span className="status-tag">Propuesta calculada · sin IA</span>
    </div>
    <h3 className="assistant-question">¿Preparamos la sesión?</h3>
    <p className="result-supporting">Crea un plan con las obras en preparación: calentamiento, pasajes por líneas comunes y secciones, y tutti.</p>
    {works.length === 0
      ? <p className="result-supporting">Marca obras como «En preparación» en Repertorio para proponer un plan.</p>
      : <>
          <p className="assistant-works">{works.map(work => work.title).join(' · ')}</p>
          <div className="assistant-controls">
            <label>Duración (minutos)<input type="number" min="10" max="600" value={minutes} onChange={event => setMinutes(event.target.value)} /></label>
            <button type="button" className="primary-action" disabled={busy} onClick={generate}>{busy ? 'Calculando…' : 'Generar propuesta'}</button>
          </div>
        </>}
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {draft && <div className="assistant-draft">
      <div className="summary-card-heading"><h3>Plan de ensayo</h3><span className="status-tag">Borrador</span></div>
      <ol className="draft-list">{draft.blocks.map((block, index) => <li key={index} className="draft-block">
        <span className="agenda-number" aria-hidden="true">{index + 1}</span>
        <div><strong>{block.title} ({block.minutes} min)</strong><span className="table-supporting">{blockWorkText(block)}</span></div>
      </li>)}</ol>
      {draft.skipped.length > 0 && <p className="result-supporting">No caben en este tiempo: {draft.skipped.join(', ')}.</p>}
      <button type="button" className="secondary-action assistant-review" onClick={review}>Revisar y editar</button>
      <p className="table-supporting">El borrador no sustituye a ningún ensayo guardado hasta que lo guardes.</p>
    </div>}
    <p className="table-supporting assistant-next">La conversación con IA («Pregunta sobre tu ensayo») llegará en la siguiente fase.</p>
  </section>;
}
