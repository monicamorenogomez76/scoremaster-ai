import React, { useEffect, useRef, useState } from 'react';
import { listWorks } from './library.js';
import { agendaTime, createRehearsal, deleteRehearsal, duplicateBlock, moveBlock, proposalBlocks, proposeRehearsal, todayIso, updateRehearsal } from './rehearsals.js';

let nextKey = 0;
const keyed = block => ({ ...block, key: ++nextKey });
const emptyBlock = () => keyed({ title: '', minutes: '', objective: '', work_id: '', measures: '', sections: '' });

function initialDraft(rehearsal) {
  return {
    date: rehearsal?.date || todayIso(), time: rehearsal?.time || '', duration_minutes: String(rehearsal?.duration_minutes || 90),
    place: rehearsal?.place || '', objectives: rehearsal?.objectives || '',
    work_ids: (rehearsal?.works || []).map(work => work.id),
    blocks: (rehearsal?.blocks || []).map(block => keyed({ ...block, minutes: String(block.minutes), work_id: block.work_id || '',
      sections: (block.sections || []).join(', ') })),
  };
}

// What the API receives: numbers, sections as a list, and only works chosen for the rehearsal.
function payload(draft) {
  return {
    date: draft.date, time: draft.time || null, duration_minutes: Number(draft.duration_minutes), place: draft.place.trim() || null,
    objectives: draft.objectives.trim(), work_ids: draft.work_ids,
    blocks: draft.blocks.map(block => ({
      title: block.title.trim(), minutes: Number(block.minutes), objective: block.objective.trim(),
      work_id: draft.work_ids.includes(block.work_id) ? block.work_id : null, measures: block.measures.trim(),
      sections: block.sections.split(',').map(section => section.trim()).filter(Boolean),
    })),
  };
}

// Creates or edits a saved rehearsal: its works and an agenda of blocks, each naming its work.
export function RehearsalEditor({ rehearsal, onSaved, onCancel }) {
  const [draft, setDraft] = useState(() => initialDraft(rehearsal));
  const [works, setWorks] = useState([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [proposalNote, setProposalNote] = useState('');
  const heading = useRef(null);
  useEffect(() => { listWorks().then(setWorks).catch(failure => setError(failure.message)); }, []);
  useEffect(() => { heading.current?.focus(); }, []);

  const set = (field, value) => setDraft(current => ({ ...current, [field]: value }));
  const setBlocks = change => setDraft(current => ({ ...current, blocks: change(current.blocks) }));
  const setBlock = (index, field, value) => setBlocks(blocks => blocks.map((block, at) => (at === index ? { ...block, [field]: value } : block)));
  const toggleWork = id => set('work_ids', draft.work_ids.includes(id) ? draft.work_ids.filter(work => work !== id) : [...draft.work_ids, id]);
  const chosen = works.filter(work => draft.work_ids.includes(work.id));
  const time = agendaTime(draft.blocks, Number(draft.duration_minutes) || 0);

  const save = async event => {
    event.preventDefault();
    setSaving(true); setError('');
    try {
      const saved = rehearsal?.id ? await updateRehearsal(rehearsal.id, payload(draft)) : await createRehearsal(payload(draft));
      onSaved(saved);
    } catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };
  // The app fills the agenda from the analysis of the chosen works; the director reviews it.
  const propose = async () => {
    setReplacing(false); setProposing(true); setError('');
    try {
      const proposal = await proposeRehearsal(draft.work_ids, Number(draft.duration_minutes) || 0);
      setBlocks(() => proposalBlocks(proposal).map(block => keyed({ ...block, minutes: String(block.minutes),
        work_id: block.work_id || '', sections: block.sections.join(', ') })));
      const skipped = proposal.omitted_works.map(item => item.title);
      setProposalNote('Agenda propuesta con el análisis de cada obra: calentamiento, pasajes por líneas comunes y '
        + 'subsecciones, y un tutti por obra. Revísala y ajústala antes de guardar.'
        + (skipped.length ? ' No caben en este tiempo: ' + skipped.join(', ') + '.' : ''));
    } catch (failure) { setError(failure.message); } finally { setProposing(false); }
  };
  const askPropose = () => (draft.blocks.length ? setReplacing(true) : propose());

  const remove = async () => {
    try { await deleteRehearsal(rehearsal.id); onSaved(null); } catch (failure) { setError(failure.message); }
  };

  return <form id="rehearsal-editor" className="rehearsal-editor surface" onSubmit={save} aria-labelledby="rehearsal-editor-title">
    <h2 id="rehearsal-editor-title" ref={heading} tabIndex={-1}>{rehearsal?.id ? 'Editar ensayo' : 'Nuevo ensayo'}</h2>
    <div className="editor-grid">
      <label>Fecha<input type="date" required value={draft.date} onChange={event => set('date', event.target.value)} /></label>
      <label>Hora<input type="time" value={draft.time} onChange={event => set('time', event.target.value)} /></label>
      <label>Duración (minutos)<input type="number" min="10" max="600" required value={draft.duration_minutes}
        onChange={event => set('duration_minutes', event.target.value)} /></label>
      <label>Lugar<input type="text" maxLength={200} value={draft.place} onChange={event => set('place', event.target.value)} /></label>
    </div>
    <label className="editor-wide">Objetivos<textarea maxLength={2000} rows={2} value={draft.objectives}
      onChange={event => set('objectives', event.target.value)} /></label>

    <fieldset className="editor-works">
      <legend>Obras del ensayo</legend>
      {works.length === 0 && <p className="result-supporting">Añade obras en Repertorio para incluirlas en el ensayo.</p>}
      {works.map(work => <label key={work.id} className="check-field">
        <input type="checkbox" checked={draft.work_ids.includes(work.id)} onChange={() => toggleWork(work.id)} />
        {work.title}<span className="table-supporting">{work.file_name}</span>
      </label>)}
    </fieldset>

    <div className="agenda-heading">
      <h3>Agenda</h3>
      <div className="agenda-propose">
        {replacing
          ? <><span>¿Sustituir los bloques actuales?</span>
              <button type="button" className="primary-action" onClick={propose}>Sustituir</button>
              <button type="button" className="secondary-action" onClick={() => setReplacing(false)}>Mantener</button></>
          : <button id="propose-agenda" type="button" className="primary-action" disabled={proposing || draft.work_ids.length === 0}
              onClick={askPropose}>{proposing ? 'Calculando…' : 'Proponer agenda'}</button>}
      </div>
      <p id="agenda-time" className={time.exceeded ? 'agenda-time is-over' : 'agenda-time'} aria-live="polite">
        Asignado: {time.assigned} de {Number(draft.duration_minutes) || 0} minutos · {time.exceeded ? 'sobran ' + time.exceeded + ' (exceso)' : 'quedan ' + time.remaining}
      </p>
    </div>
    {draft.work_ids.length === 0 && <p className="result-supporting">Elige las obras del ensayo para que la aplicación proponga la agenda.</p>}
    {proposalNote && <p className="proposal-note" role="status">{proposalNote}</p>}
    <ol className="agenda-editor">{draft.blocks.map((block, index) => <li key={block.key} className="agenda-block">
      <fieldset>
        <legend>Bloque {index + 1}</legend>
        <div className="editor-grid">
          <label>Título<input type="text" required maxLength={120} value={block.title} onChange={event => setBlock(index, 'title', event.target.value)} /></label>
          <label>Minutos<input type="number" min="1" max="600" required value={block.minutes} onChange={event => setBlock(index, 'minutes', event.target.value)} /></label>
          <label>Obra<select value={draft.work_ids.includes(block.work_id) ? block.work_id : ''} onChange={event => setBlock(index, 'work_id', event.target.value)}>
            <option value="">Toda la banda · sin obra concreta</option>
            {chosen.map(work => <option key={work.id} value={work.id}>{work.title}</option>)}
          </select></label>
          <label>Compases<input type="text" maxLength={40} placeholder="35-48" value={block.measures} onChange={event => setBlock(index, 'measures', event.target.value)} /></label>
          <label>Secciones<input type="text" placeholder="Maderas, Metales" value={block.sections} onChange={event => setBlock(index, 'sections', event.target.value)} /></label>
          <label>Objetivo<input type="text" maxLength={500} value={block.objective} onChange={event => setBlock(index, 'objective', event.target.value)} /></label>
        </div>
        <div className="block-actions">
          <button type="button" className="secondary-action" disabled={index === 0} onClick={() => setBlocks(blocks => moveBlock(blocks, index, -1))}>Subir</button>
          <button type="button" className="secondary-action" disabled={index === draft.blocks.length - 1} onClick={() => setBlocks(blocks => moveBlock(blocks, index, 1))}>Bajar</button>
          <button type="button" className="secondary-action" onClick={() => setBlocks(blocks => duplicateBlock(blocks, index).map((item, at) => (at === index + 1 ? keyed(item) : item)))}>Duplicar</button>
          <button type="button" className="secondary-action" onClick={() => setBlocks(blocks => blocks.filter((_, at) => at !== index))}>Eliminar</button>
        </div>
      </fieldset>
    </li>)}</ol>
    <button type="button" className="secondary-action" disabled={draft.blocks.length >= 50} onClick={() => setBlocks(blocks => [...blocks, emptyBlock()])}>Añadir bloque</button>

    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="editor-actions">
      <button type="submit" className="primary-action" disabled={saving}>{saving ? 'Guardando…' : 'Guardar ensayo'}</button>
      <button type="button" className="secondary-action" onClick={onCancel}>Cancelar</button>
      {rehearsal?.id && (confirming
        ? <><button type="button" className="danger-action" onClick={remove}>Eliminar definitivamente</button>
            <button type="button" className="secondary-action" onClick={() => setConfirming(false)}>No eliminar</button></>
        : <button type="button" className="danger-action" onClick={() => setConfirming(true)}>Eliminar ensayo</button>)}
    </div>
  </form>;
}
