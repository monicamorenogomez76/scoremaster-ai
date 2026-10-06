import React, { useEffect, useRef, useState } from 'react';
import { createConcert, deleteConcert, patternDates, updateConcert, weekdayOptions } from './concerts.js';
import { listWorks } from './library.js';
import { todayIso } from './rehearsals.js';

const longDate = iso => { const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' }); };

function initialDraft(concert) {
  const schedule = concert?.schedule;
  return {
    title: concert?.title || '', date: concert?.date || '', time: concert?.time || '', place: concert?.place || '', notes: concert?.notes || '',
    work_ids: (concert?.works || []).map(work => work.id),
    weekdays: schedule?.weekdays || [], rehearsal_time: schedule?.time || '20:00',
    duration: String(schedule?.duration_minutes || 90), start_date: schedule?.start_date || todayIso(),
  };
}

// A concert: date, programme in concert order and the weekly pattern of its rehearsals.
export function ConcertEditor({ concert, onSaved, onCancel }) {
  const [draft, setDraft] = useState(() => initialDraft(concert));
  const [works, setWorks] = useState([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const heading = useRef(null);
  useEffect(() => { listWorks().then(setWorks).catch(failure => setError(failure.message)); }, []);
  useEffect(() => { heading.current?.focus(); }, []);

  const set = (field, value) => setDraft(current => ({ ...current, [field]: value }));
  // The programme keeps the order in which works are added; it can be reordered afterwards.
  const toggleWork = id => set('work_ids', draft.work_ids.includes(id) ? draft.work_ids.filter(work => work !== id) : [...draft.work_ids, id]);
  const move = (index, step) => {
    const order = draft.work_ids.slice(), target = index + step;
    if (target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    set('work_ids', order);
  };
  const toggleDay = day => set('weekdays', draft.weekdays.includes(day) ? draft.weekdays.filter(item => item !== day) : [...draft.weekdays, day].sort());
  const schedule = draft.weekdays.length ? { weekdays: draft.weekdays, time: draft.rehearsal_time, duration_minutes: Number(draft.duration),
    start_date: draft.start_date } : null;
  const dates = patternDates(schedule, draft.date, todayIso());
  const titleOf = id => works.find(work => work.id === id)?.title || (concert?.works || []).find(work => work.id === id)?.title || 'Obra';

  const save = async event => {
    event.preventDefault();
    setSaving(true); setError('');
    const body = { title: draft.title.trim(), date: draft.date, time: draft.time || null, place: draft.place.trim() || null,
      notes: draft.notes.trim(), work_ids: draft.work_ids, schedule };
    try { onSaved(concert?.id ? await updateConcert(concert.id, body) : await createConcert(body)); }
    catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };
  const remove = async () => { try { await deleteConcert(concert.id); onSaved(null); } catch (failure) { setError(failure.message); } };

  return <form id="concert-editor" className="rehearsal-editor surface" onSubmit={save} aria-labelledby="concert-editor-title">
    <h2 id="concert-editor-title" ref={heading} tabIndex={-1}>{concert?.id ? 'Editar concierto' : 'Nuevo concierto'}</h2>
    <div className="editor-grid">
      <label>Título<input type="text" required maxLength={200} value={draft.title} onChange={event => set('title', event.target.value)} /></label>
      <label>Fecha del concierto<input type="date" required value={draft.date} onChange={event => set('date', event.target.value)} /></label>
      <label>Hora del concierto<input type="time" value={draft.time} onChange={event => set('time', event.target.value)} /></label>
      <label>Lugar<input type="text" maxLength={200} value={draft.place} onChange={event => set('place', event.target.value)} /></label>
    </div>
    <label className="editor-wide">Notas<textarea rows={2} maxLength={2000} value={draft.notes} onChange={event => set('notes', event.target.value)} /></label>

    <fieldset className="editor-works">
      <legend>Programa (en orden de concierto)</legend>
      {works.length === 0 && <p className="result-supporting">Añade obras en Repertorio para incluirlas en el programa.</p>}
      {works.map(work => <label key={work.id} className="check-field">
        <input type="checkbox" checked={draft.work_ids.includes(work.id)} onChange={() => toggleWork(work.id)} />
        {work.title}<span className="table-supporting">{work.file_name}</span>
      </label>)}
      {draft.work_ids.length > 0 && <ol className="programme-order">{draft.work_ids.map((id, index) => <li key={id}>
        <span>{index + 1}. {titleOf(id)}</span>
        <button type="button" className="secondary-action" disabled={index === 0} onClick={() => move(index, -1)}>Subir</button>
        <button type="button" className="secondary-action" disabled={index === draft.work_ids.length - 1} onClick={() => move(index, 1)}>Bajar</button>
      </li>)}</ol>}
    </fieldset>

    <fieldset className="editor-works">
      <legend>Ensayos (patrón semanal)</legend>
      <div className="weekday-picker" role="group" aria-label="Días de ensayo">
        {weekdayOptions.map(([day, short, name]) => <label key={day} className="weekday-option">
          <input type="checkbox" aria-label={name} checked={draft.weekdays.includes(day)} onChange={() => toggleDay(day)} />{short}
        </label>)}
      </div>
      <div className="editor-grid">
        <label>Fecha de inicio<input type="date" value={draft.start_date} onChange={event => set('start_date', event.target.value)} /></label>
        <label>Hora de ensayo<input type="time" value={draft.rehearsal_time} onChange={event => set('rehearsal_time', event.target.value)} /></label>
        <label>Duración de cada ensayo (minutos)<input type="number" min="10" max="600" value={draft.duration} onChange={event => set('duration', event.target.value)} /></label>
      </div>
      {schedule && (dates.length === 0 ? <p className="result-supporting">El patrón no da ningún ensayo antes del concierto.</p>
        : <><p className="result-supporting">{dates.length === 1 ? '1 ensayo' : dates.length + ' ensayos'} antes del concierto:</p>
            <ul className="pattern-preview">{dates.map(date => <li key={date}>{longDate(date)}</li>)}</ul></>)}
    </fieldset>

    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="editor-actions">
      <button type="submit" className="primary-action" disabled={saving}>{saving ? 'Guardando…' : 'Guardar concierto'}</button>
      <button type="button" className="secondary-action" onClick={onCancel}>Cancelar</button>
      {concert?.id && (confirming
        ? <><button type="button" className="danger-action" onClick={remove}>Eliminar definitivamente</button>
            <button type="button" className="secondary-action" onClick={() => setConfirming(false)}>No eliminar</button></>
        : <button type="button" className="danger-action" onClick={() => setConfirming(true)}>Eliminar concierto</button>)}
    </div>
  </form>;
}
