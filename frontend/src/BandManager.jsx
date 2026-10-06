import React, { useEffect, useState } from 'react';
import { activateBand, bandBody, bandDraft, createBand, deleteBand, levelOptions, listBands, loadCatalog, sectionLevelRows,
  templateGroups, updateBand } from './bands.js';
import { weekdayOptions } from './concerts.js';

// A fixed band: its data, rehearsal days, full instrumentation by family and a level per section.
function BandEditor({ band, catalog, onSaved, onCancel }) {
  const [draft, setDraft] = useState(() => bandDraft(band));
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const set = (field, value) => setDraft(current => ({ ...current, [field]: value }));
  const setIn = (field, key, value) => setDraft(current => ({ ...current, [field]: { ...current[field], [key]: value } }));
  const toggleDay = day => set('rehearsal_weekdays', draft.rehearsal_weekdays.includes(day)
    ? draft.rehearsal_weekdays.filter(item => item !== day) : [...draft.rehearsal_weekdays, day].sort());

  const save = async event => {
    event.preventDefault();
    setSaving(true); setError('');
    try { onSaved(band?.id ? await updateBand(band.id, bandBody(draft)) : await createBand(bandBody(draft))); }
    catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };
  const remove = async () => { try { await deleteBand(band.id); onSaved(null); } catch (failure) { setError(failure.message); } };

  return <form id="band-editor" className="rehearsal-editor surface" onSubmit={save} aria-labelledby="band-editor-title">
    <h2 id="band-editor-title">{band?.id ? 'Editar banda' : 'Nueva banda'}</h2>
    <div className="editor-grid">
      <label>Nombre de la banda<input type="text" required maxLength={200} value={draft.name} onChange={event => set('name', event.target.value)} /></label>
      <label>Localidad<input type="text" maxLength={200} value={draft.locality} onChange={event => set('locality', event.target.value)} /></label>
      <label>Lugar de ensayo<input type="text" maxLength={200} value={draft.place} onChange={event => set('place', event.target.value)} /></label>
    </div>
    <fieldset className="editor-works">
      <legend>Días de ensayo</legend>
      <div className="weekday-picker" role="group" aria-label="Días de ensayo">
        {weekdayOptions.map(([day, short, name]) => <label key={day} className="weekday-option">
          <input type="checkbox" aria-label={name} checked={draft.rehearsal_weekdays.includes(day)} onChange={() => toggleDay(day)} />{short}
        </label>)}
      </div>
      <div className="editor-grid">
        <label>Hora de ensayo<input type="time" value={draft.rehearsal_time} onChange={event => set('rehearsal_time', event.target.value)} /></label>
        <label>Duración del ensayo (minutos)<input type="number" min="10" max="600" value={draft.rehearsal_minutes}
          onChange={event => set('rehearsal_minutes', event.target.value)} /></label>
      </div>
    </fieldset>
    <fieldset className="editor-works">
      <legend>Plantilla instrumental</legend>
      <p className="result-supporting">Músicos de cada instrumento de la banda, aunque ninguna obra los pida todavía; la percusión cuenta los percusionistas en total.</p>
      {templateGroups(catalog).map(([family, rows]) => <div key={family} className="template-family">
        <h3>{family}</h3>
        <div className="template-rows">{rows.map(row => <label key={row.key} className="template-row">
          <span>{row.label}</span>
          <input type="number" min="0" max="1000" aria-label={'Plantilla: ' + row.label} value={draft.profile[row.key] ?? ''}
            placeholder="0" onChange={event => setIn('profile', row.key, event.target.value)} />
        </label>)}</div>
      </div>)}
    </fieldset>
    <fieldset className="editor-works">
      <legend>Nivel por sección</legend>
      <p className="result-supporting">Nivel orientativo de cada sección con la rúbrica de grados, para personalizar los planes de ensayo.</p>
      <div className="template-rows">{sectionLevelRows().map(([key, label]) => <label key={key} className="template-row">
        <span>{label}</span>
        <select aria-label={'Nivel de ' + label} value={draft.section_levels[key] || ''} onChange={event => setIn('section_levels', key, event.target.value)}>
          {levelOptions.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
        </select>
      </label>)}</div>
    </fieldset>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="editor-actions">
      <button type="submit" className="primary-action" disabled={saving}>{saving ? 'Guardando…' : 'Guardar banda'}</button>
      <button type="button" className="secondary-action" onClick={onCancel}>Cancelar</button>
      {band?.id && (confirming
        ? <><button type="button" className="danger-action" onClick={remove}>Eliminar definitivamente</button>
            <button type="button" className="secondary-action" onClick={() => setConfirming(false)}>No eliminar</button></>
        : <button type="button" className="danger-action" onClick={() => setConfirming(true)}>Eliminar banda</button>)}
    </div>
  </form>;
}

// The director's bands: the active one is the template of the analyses and BandFit.
export function BandManager({ visible, onActivated }) {
  const [bands, setBands] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState('');
  const refresh = () => listBands().then(found => { setBands(found); setError(''); return found; }).catch(failure => setError(failure.message));
  useEffect(() => {
    if (!visible) return;
    refresh();
    loadCatalog().then(setCatalog).catch(failure => setError(failure.message));
  }, [visible]);
  const active = (bands || []).find(band => band.active);
  const activate = async id => {
    try { const band = await activateBand(id); await refresh(); setEditing(null); onActivated(band); }
    catch (failure) { setError(failure.message); }
  };

  return <section id="band-manager" className="surface band-manager" aria-labelledby="band-manager-title">
    <div className="section-toolbar">
      <h2 id="band-manager-title">Tus bandas</h2>
      <div className="band-manager-actions">
        {bands && bands.length > 0 && <label className="band-select-field">Banda activa
          <select id="band-select" value={active?.id || ''} onChange={event => activate(event.target.value)}>
            {bands.map(band => <option key={band.id} value={band.id}>{band.name + (band.active ? ' · activa' : '')}</option>)}
          </select>
        </label>}
        {active && <button type="button" className="secondary-action" onClick={() => setEditing(active)}>Editar banda</button>}
        <button id="new-band" type="button" className="primary-action" onClick={() => setEditing({})}>Nueva banda</button>
      </div>
    </div>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {bands && bands.length === 0 && !editing && <p className="result-supporting">Crea tu banda con su plantilla completa: será la que usen los análisis y los planes.</p>}
    {active && !editing && <p className="result-supporting">{[active.locality, active.place,
      active.rehearsal_weekdays.length ? 'ensaya ' + active.rehearsal_weekdays.map(day => weekdayOptions[day][2]).join(' y ') +
        (active.rehearsal_time ? ' a las ' + active.rehearsal_time : '') : null,
      Object.values(active.profile).reduce((total, count) => total + count, 0) + ' músicos'].filter(Boolean).join(' · ')}</p>}
    {editing && <BandEditor key={editing.id || 'new'} band={editing} catalog={catalog}
      onSaved={() => { setEditing(null); refresh(); }} onCancel={() => setEditing(null)} />}
  </section>;
}
