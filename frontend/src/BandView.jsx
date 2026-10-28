import React, { useEffect, useState } from 'react';
import { apiFetch } from './api.js';
import { BandManager } from './BandManager.jsx';
import { View } from './View.jsx';
import { createOwnInstrument, instrumentGroups, instrumentKeys, instrumentSections, OTHER_INSTRUMENT, ownInstrumentBody,
  ownInstrumentForm } from './instrumentCatalog.js';
import { bandIssueText, bandStatusLabels, confirmationOptions, displayInstrumentName, unconfirmedStatusText } from './labels.js';

// Parts without a confirmed instrument: the user picks it from the catalog (step 09) or, when it is not there,
// creates it for the account with its name, family and key (2026-10-28). What is confirmed is learnt for the next works.
function OwnInstrumentForm({ part, sounds, onCreated }) {
  const [form, setForm] = useState(() => ownInstrumentForm(part));
  const [status, setStatus] = useState('');
  const [saving, setSaving] = useState(false);
  const id = 'own-' + part.replace(/[^A-Za-z0-9]+/g, '-');
  const field = name => ({ value: form[name], onChange: event => setForm(current => ({ ...current, [name]: event.target.value })) });
  const create = async () => {
    setSaving(true); setStatus('');
    try { onCreated(await createOwnInstrument(ownInstrumentBody(part, form))); }
    catch (failure) { setStatus(failure.message); setSaving(false); }
  };
  return <fieldset className="own-instrument-form">
    <legend>Nuevo instrumento para «{part}»</legend>
    <label htmlFor={id + '-name'}>Nombre<input id={id + '-name'} type="text" maxLength={80} {...field('label_es')} /></label>
    <label htmlFor={id + '-section'}>Familia<select id={id + '-section'} {...field('section')}>
      {instrumentSections.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <label htmlFor={id + '-key'}>Tonalidad<select id={id + '-key'} {...field('transposition')}>
      {instrumentKeys.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <label htmlFor={id + '-sound'}>Suena como<select id={id + '-sound'} {...field('sound')}>
      <option value="">Sin sonido de altura (percusión)</option>
      {sounds.map(sound => <option key={sound} value={sound}>{sound.replaceAll('_', ' ')}</option>)}</select></label>
    <label htmlFor={id + '-group'}>Grupo de ensayo<select id={id + '-group'} {...field('rehearsal_group')}>
      {instrumentGroups.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <button type="button" className="secondary-action" disabled={saving || !form.label_es.trim()} onClick={create}>
      {saving ? 'Creando…' : 'Crear instrumento'}</button>
    {status && <p className="result-supporting" role="alert">{status}</p>}
  </fieldset>;
}

function InstrumentConfirmation({ items, onConfirm, busy }) {
  const [catalog, setCatalog] = useState([]);
  const [sounds, setSounds] = useState([]);
  const [chosen, setChosen] = useState({});
  useEffect(() => {
    let current = true;
    apiFetch('/instruments/catalog').then(response => response.json())
      .then(body => { if (current) { setCatalog(body.instruments || []); setSounds(body.sounds || []); } })
      .catch(() => { if (current) setCatalog([]); });
    return () => { current = false; };
  }, []);
  useEffect(() => {
    setChosen(Object.fromEntries(items.map(item => [item.part, item.proposal || ''])));
  }, [items]);
  const selected = Object.fromEntries(Object.entries(chosen).filter(([, identity]) => identity && identity !== OTHER_INSTRUMENT));
  const created = (part, instrument) => {
    setCatalog(current => [...current, instrument]);
    setChosen(previous => ({ ...previous, [part]: instrument.canonical_id }));
  };
  return <section id="instrument-confirmation" className="surface band-confirmation">
    <h2>Instrumentos por confirmar</h2>
    <p className="result-supporting">Estas partes no cuentan en la plantilla hasta que confirmes qué instrumento las toca.
      Lo que confirmes se recordará en tus próximas obras.</p>
    <div className="band-profile-rows">{items.map(item =>
      <div key={item.part} className="instrument-confirm-item">
        <label className="band-profile-row">
          <span>{item.part}<small className="result-supporting"> · {unconfirmedStatusText(item)}</small></span>
          <select value={chosen[item.part] || ''} aria-label={'Instrumento de ' + item.part}
            onChange={event => setChosen(previous => ({ ...previous, [item.part]: event.target.value }))}>
            <option value="">Elige instrumento…</option>
            {confirmationOptions(item, catalog).map(entry =>
              <option key={entry.canonical_id} value={entry.canonical_id}>{entry.label_es}</option>)}
            <option value={OTHER_INSTRUMENT}>Otro instrumento…</option>
          </select>
        </label>
        {chosen[item.part] === OTHER_INSTRUMENT &&
          <OwnInstrumentForm part={item.part} sounds={sounds} onCreated={instrument => created(item.part, instrument)} />}
      </div>)}</div>
    <button id="confirm-instruments" className="band-profile-update" type="button"
      disabled={busy || Object.keys(selected).length === 0} onClick={() => onConfirm(selected)}>
      {busy ? 'Actualizando…' : 'Confirmar instrumentos'}
    </button>
  </section>;
}

export function BandView({ active, hidden, data, draft, onDraftChange, onUpdate, onConfirm, onBandActivated, busy }) {
  const bandFit = data?.band_fit || {};
  const requirements = bandFit.requirements || [];
  const unconfirmed = bandFit.unconfirmed || [];
  const issues = (bandFit.issues || []).map(bandIssueText);
  return <View name="band" active={active} eyebrow="BandFit" title="Mi banda"
    description="Tus bandas con su plantilla fija y, debajo, cómo encaja la obra abierta en la banda activa.">
    <BandManager visible={!hidden && active === 'band'} onActivated={onBandActivated} />
    <h2 className="calculated-plan-title">Adecuación de la obra abierta</h2>
    {unconfirmed.length > 0 && <InstrumentConfirmation items={unconfirmed} onConfirm={onConfirm} busy={busy} />}
    <div id="band-profile-editor" className="band-profile-editor surface" hidden={requirements.length === 0}>
      <fieldset>
        <legend>Plantilla de esta obra</legend>
        <p className="result-supporting">Empieza con los músicos que pide la obra: uno por voz y los percusionistas en total. Los cambios son temporales en esta demo.</p>
        <div id="band-profile-rows" className="band-profile-rows">{requirements.map(item =>
          <label key={item.key} className="band-profile-row">
            <span>{item.label_es}<small className="result-supporting"> · la obra pide {item.required}</small></span>
            <input type="number" min="0" step="1" value={draft[item.key] ?? String(item.required)} aria-label={'Músicos de ' + item.label_es}
              title={item.parts.map(part => displayInstrumentName(part)).join(', ')}
              onChange={event => onDraftChange(previous => ({ ...previous, [item.key]: event.target.value }))} />
          </label>)}</div>
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
            {unconfirmed.length > 0 && <p className="result-supporting">{unconfirmed.length === 1
              ? 'Una parte está pendiente de confirmar y no cuenta todavía.'
              : unconfirmed.length + ' partes están pendientes de confirmar y no cuentan todavía.'}</p>}
          </section>
        </div>
      : <div id="band-content" className="view-content empty-workspace"><h2>Aún no hay plantilla</h2><p>Analiza una obra para cargar sus instrumentos y asignar músicos.</p></div>}
  </View>;
}
