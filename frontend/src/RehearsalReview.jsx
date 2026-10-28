import React, { useEffect, useRef, useState } from 'react';
import { blockWorkText, rehearsalDateText, reviewRehearsal, reviewStatusOptions } from './rehearsals.js';

// The director's review after a rehearsal (decided 2026-10-06): how each block went and a
// note; what is left pending gains priority when the next rehearsals are replanned.
export function RehearsalReview({ rehearsal, onSaved, onCancel }) {
  const [blocks, setBlocks] = useState(() => rehearsal.blocks.map(block => ({
    status: block.review?.status || 'resolved', note: block.review?.note || '' })));
  const [notes, setNotes] = useState(rehearsal.review_notes || '');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const heading = useRef(null);
  useEffect(() => { heading.current?.focus(); }, []);
  const set = (index, field, value) => setBlocks(current => current.map((block, at) => (at === index ? { ...block, [field]: value } : block)));

  const save = async event => {
    event.preventDefault();
    setSaving(true); setError('');
    try { onSaved(await reviewRehearsal(rehearsal.id, notes.trim(), blocks.map(block => ({ ...block, note: block.note.trim() })))); }
    catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };

  return <form id="rehearsal-review" className="rehearsal-editor surface" onSubmit={save} aria-labelledby="rehearsal-review-title">
    <h2 id="rehearsal-review-title" ref={heading} tabIndex={-1}>Revisión del ensayo · {rehearsalDateText(rehearsal)}</h2>
    <p className="result-supporting">Lo pendiente y lo mejorable ganan tiempo cuando replanifiques los ensayos siguientes; lo resuelto lo pierde.</p>
    <ol className="agenda-editor">{rehearsal.blocks.map((block, index) => <li key={index} className="review-block">
      <fieldset>
        <legend>{index + 1}. {block.title} · {block.minutes} min</legend>
        <p className="table-supporting">{blockWorkText(block)}</p>
        <div className="review-statuses" role="radiogroup" aria-label={'Cómo fue: ' + block.title}>
          {reviewStatusOptions.map(([status, label]) => <label key={status} className="weekday-option">
            <input type="radio" name={'review-' + index} value={status} checked={blocks[index].status === status}
              onChange={() => set(index, 'status', status)} />{label}
          </label>)}
        </div>
        <label>Nota<input type="text" maxLength={500} value={blocks[index].note} onChange={event => set(index, 'note', event.target.value)} /></label>
      </fieldset>
    </li>)}</ol>
    <label className="editor-wide">Notas del ensayo<textarea rows={2} maxLength={2000} value={notes} onChange={event => setNotes(event.target.value)} /></label>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="editor-actions">
      <button type="submit" className="primary-action" disabled={saving}>{saving ? 'Guardando…' : 'Guardar revisión'}</button>
      <button type="button" className="secondary-action" onClick={onCancel}>Cancelar</button>
    </div>
  </form>;
}
