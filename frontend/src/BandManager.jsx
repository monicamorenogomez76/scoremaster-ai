import React, { useEffect, useState } from 'react';
import { activateBand, bandBody, bandDraft, createBand, deleteBand, levelChoices, listBands, loadCatalog, sectionLevelRows,
  templateGroups, updateBand } from './bands.js';
import { weekdays } from './concerts.js';
import { t } from './i18n.js';

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
    <h2 id="band-editor-title">{band?.id ? t('Editar banda') : t('Nueva banda')}</h2>
    <div className="editor-grid">
      <label>{t('Nombre de la banda')}<input type="text" required maxLength={200} value={draft.name} onChange={event => set('name', event.target.value)} /></label>
      <label>{t('Localidad')}<input type="text" maxLength={200} value={draft.locality} onChange={event => set('locality', event.target.value)} /></label>
      <label>{t('Lugar de ensayo')}<input type="text" maxLength={200} value={draft.place} onChange={event => set('place', event.target.value)} /></label>
    </div>
    <fieldset className="editor-works">
      <legend>{t('Días de ensayo')}</legend>
      <div className="weekday-picker" role="group" aria-label={t('Días de ensayo')}>
        {weekdays().map(([day, short, name]) => <label key={day} className="weekday-option">
          <input type="checkbox" aria-label={name} checked={draft.rehearsal_weekdays.includes(day)} onChange={() => toggleDay(day)} />{short}
        </label>)}
      </div>
      <div className="editor-grid">
        <label>{t('Hora de ensayo')}<input type="time" value={draft.rehearsal_time} onChange={event => set('rehearsal_time', event.target.value)} /></label>
        <label>{t('Duración del ensayo (minutos)')}<input type="number" min="10" max="600" value={draft.rehearsal_minutes}
          onChange={event => set('rehearsal_minutes', event.target.value)} /></label>
      </div>
    </fieldset>
    <fieldset className="editor-works">
      <legend>{t('Plantilla instrumental')}</legend>
      <p className="result-supporting">{t('Músicos de cada instrumento de la banda, aunque ninguna obra los pida todavía; la percusión cuenta los percusionistas en total.')}</p>
      {templateGroups(catalog).map(([family, rows]) => <div key={family} className="template-family">
        <h3>{family}</h3>
        <div className="template-rows">{rows.map(row => <label key={row.key} className="template-row">
          <span>{row.label}</span>
          <input type="number" min="0" max="1000" aria-label={t('Plantilla: {instrument}', { instrument: row.label })} value={draft.profile[row.key] ?? ''}
            placeholder="0" onChange={event => setIn('profile', row.key, event.target.value)} />
        </label>)}</div>
      </div>)}
    </fieldset>
    <fieldset className="editor-works">
      <legend>{t('Nivel por sección')}</legend>
      <p className="result-supporting">{t('Nivel orientativo de cada sección con la rúbrica de grados, para personalizar los planes de ensayo.')}</p>
      <div className="template-rows">{sectionLevelRows().map(([key, label]) => <label key={key} className="template-row">
        <span>{label}</span>
        <select aria-label={t('Nivel de {section}', { section: label })} value={draft.section_levels[key] || ''} onChange={event => setIn('section_levels', key, event.target.value)}>
          {levelChoices().map(([value, text]) => <option key={value} value={value}>{text}</option>)}
        </select>
      </label>)}</div>
    </fieldset>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="editor-actions">
      <button type="submit" className="primary-action" disabled={saving}>{saving ? t('Guardando…') : t('Guardar banda')}</button>
      <button type="button" className="secondary-action" onClick={onCancel}>{t('Cancelar')}</button>
      {band?.id && (confirming
        ? <><button type="button" className="danger-action" onClick={remove}>{t('Eliminar definitivamente')}</button>
            <button type="button" className="secondary-action" onClick={() => setConfirming(false)}>{t('No eliminar')}</button></>
        : <button type="button" className="danger-action" onClick={() => setConfirming(true)}>{t('Eliminar banda')}</button>)}
    </div>
  </form>;
}

// «ensaya lunes y jueves a las 20:00».
function rehearsalDays(band) {
  const names = band.rehearsal_weekdays.map(day => weekdays()[day][2]);
  const days = names.length === 1 ? names[0] : t('{list} y {last}', { list: names.slice(0, -1).join(', '), last: names[names.length - 1] });
  return band.rehearsal_time ? t('ensaya {days} a las {time}', { days, time: band.rehearsal_time }) : t('ensaya {days}', { days });
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
      <h2 id="band-manager-title">{t('Tus bandas')}</h2>
      <div className="band-manager-actions">
        {bands && bands.length > 0 && <label className="band-select-field">{t('Banda activa')}
          <select id="band-select" value={active?.id || ''} onChange={event => activate(event.target.value)}>
            {bands.map(band => <option key={band.id} value={band.id}>{band.name + (band.active ? ' · ' + t('activa') : '')}</option>)}
          </select>
        </label>}
        {active && <button type="button" className="secondary-action" onClick={() => setEditing(active)}>{t('Editar banda')}</button>}
        <button id="new-band" type="button" className="primary-action" onClick={() => setEditing({})}>{t('Nueva banda')}</button>
      </div>
    </div>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {bands && bands.length === 0 && !editing && <p className="result-supporting">{t('Crea tu banda con su plantilla completa: será la que usen los análisis y los planes.')}</p>}
    {active && !editing && <p className="result-supporting">{[active.locality, active.place,
      active.rehearsal_weekdays.length ? rehearsalDays(active) : null,
      t('{count} músicos', { count: Object.values(active.profile).reduce((total, count) => total + count, 0) })].filter(Boolean).join(' · ')}</p>}
    {editing && <BandEditor key={editing.id || 'new'} band={editing} catalog={catalog}
      onSaved={() => { setEditing(null); refresh(); }} onCancel={() => setEditing(null)} />}
  </section>;
}
