import React, { useEffect, useState } from 'react';
import { apiFetch } from './api.js';
import { BandManager } from './BandManager.jsx';
import { View } from './View.jsx';
import { aiConfidence, createOwnInstrument, instrumentGroups, instrumentKeys, instrumentSections, loadInstrumentSuggestions, OTHER_INSTRUMENT,
  proposeInstruments, withAiProposals,
  ownInstrumentBody, ownInstrumentForm, withSuggestions } from './instrumentCatalog.js';
import { bandIssueText, bandStatusLabels, confirmationOptions, displayInstrumentName, instrumentLabel, unconfirmedStatusText } from './labels.js';
import { t } from './i18n.js';

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
    <legend>{t('Nuevo instrumento para «{part}»', { part })}</legend>
    <label htmlFor={id + '-name'}>{t('Nombre')}<input id={id + '-name'} type="text" maxLength={80} {...field('label_es')} /></label>
    <label htmlFor={id + '-section'}>{t('Familia')}<select id={id + '-section'} {...field('section')}>
      {instrumentSections.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
    <label htmlFor={id + '-key'}>{t('Tonalidad')}<select id={id + '-key'} {...field('transposition')}>
      {instrumentKeys.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
    <label htmlFor={id + '-sound'}>{t('Suena como')}<select id={id + '-sound'} {...field('sound')}>
      <option value="">{t('Sin sonido de altura (percusión)')}</option>
      {sounds.map(sound => <option key={sound} value={sound}>{sound.replaceAll('_', ' ')}</option>)}</select></label>
    <label htmlFor={id + '-group'}>{t('Grupo de ensayo')}<select id={id + '-group'} {...field('rehearsal_group')}>
      {instrumentGroups.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
    <button type="button" className="secondary-action" disabled={saving || !form.label_es.trim()} onClick={create}>
      {saving ? t('Creando…') : t('Crear instrumento')}</button>
    {status && <p className="result-supporting" role="alert">{status}</p>}
  </fieldset>;
}

const confidenceText = value => {
  const level = aiConfidence(value);
  return level === 'alta' ? t('confianza alta') : level === 'media' ? t('confianza media') : t('confianza baja');
};

function InstrumentConfirmation({ items, workId, onConfirm, busy }) {
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
  const [shown, setShown] = useState(items);
  useEffect(() => {
    let current = true;
    setShown(items);
    setChosen(Object.fromEntries(items.map(item => [item.part, item.proposal || ''])));
    // A name other accounts confirmed comes chosen, without changing what was already chosen.
    loadInstrumentSuggestions(items).then(suggestions => {
      if (!current) return;
      const proposed = withSuggestions(items, suggestions);
      setShown(proposed);
      setChosen(previous => Object.fromEntries(proposed.map(item => [item.part, previous[item.part] || item.proposal || ''])));
    });
    return () => { current = false; };
  }, [items]);
  // The AI proposes the parts nothing was chosen for (2026-10-31); it is asked on demand, so viewing spends no quota.
  const [asking, setAsking] = useState({ state: 'idle', message: '' });
  useEffect(() => { setAsking({ state: 'idle', message: '' }); }, [items]);
  const ask = async () => {
    setAsking({ state: 'loading', message: '' });
    try {
      const { proposals } = await proposeInstruments(workId);
      const count = Object.keys(proposals).length;
      setShown(current => withAiProposals(current, proposals));
      setChosen(previous => Object.fromEntries(Object.entries(previous).map(([part, identity]) =>
        [part, identity || proposals[part]?.instrument || ''])));
      setAsking({ state: 'done', message: count === 0 ? t('La IA no ha podido proponer ningún instrumento con seguridad.')
        : t(count === 1 ? 'La IA propone el instrumento de {count} parte. Revísalo antes de confirmar.'
          : 'La IA propone el instrumento de {count} partes. Revísalos antes de confirmar.', { count }) });
    } catch (failure) {
      setAsking({ state: 'error', message: failure.message });
    }
  };
  const selected = Object.fromEntries(Object.entries(chosen).filter(([, identity]) => identity && identity !== OTHER_INSTRUMENT));
  const created = (part, instrument) => {
    setCatalog(current => [...current, instrument]);
    setChosen(previous => ({ ...previous, [part]: instrument.canonical_id }));
  };
  return <section id="instrument-confirmation" className="surface band-confirmation">
    <h2>{t('Instrumentos por confirmar')}</h2>
    <p className="result-supporting">{t('Estas partes no cuentan en la plantilla hasta que confirmes qué instrumento las toca. Lo que confirmes se recordará en tus próximas obras.')}</p>
    <div className="band-profile-rows">{shown.map(item =>
      <div key={item.part} className="instrument-confirm-item">
        <label className="band-profile-row">
          <span>{item.part}<small className="result-supporting"> · {unconfirmedStatusText(item)}</small></span>
          <select value={chosen[item.part] || ''} aria-label={t('Instrumento de {part}', { part: item.part })}
            onChange={event => setChosen(previous => ({ ...previous, [item.part]: event.target.value }))}>
            <option value="">{t('Elige instrumento…')}</option>
            {confirmationOptions(item, catalog).map(entry =>
              <option key={entry.canonical_id} value={entry.canonical_id}>{instrumentLabel(entry)}</option>)}
            <option value={OTHER_INSTRUMENT}>{t('Otro instrumento…')}</option>
          </select>
        </label>
        {item.ai && <p className="result-supporting instrument-ai-reason">
          {t('IA, {confidence}: {reason}', { confidence: confidenceText(item.ai.confidence), reason: item.ai.reason })}</p>}
        {chosen[item.part] === OTHER_INSTRUMENT &&
          <OwnInstrumentForm part={item.part} sounds={sounds} onCreated={instrument => created(item.part, instrument)} />}
      </div>)}</div>
    <div className="editor-actions">
      <button id="confirm-instruments" className="band-profile-update" type="button"
        disabled={busy || Object.keys(selected).length === 0} onClick={() => onConfirm(selected)}>
        {busy ? t('Actualizando…') : t('Confirmar instrumentos')}
      </button>
      {workId && <button id="propose-instruments" className="secondary-action" type="button"
        disabled={asking.state === 'loading'} onClick={ask}>
        {asking.state === 'loading' ? t('Consultando a la IA…') : t('Proponer con IA')}
      </button>}
    </div>
    <p className="result-supporting" role={asking.state === 'error' ? 'alert' : 'status'}>{asking.message}</p>
  </section>;
}

export function BandView({ active, hidden, data, draft, onDraftChange, onUpdate, onConfirm, onBandActivated, busy }) {
  const bandFit = data?.band_fit || {};
  const requirements = bandFit.requirements || [];
  const unconfirmed = bandFit.unconfirmed || [];
  const issues = (bandFit.issues || []).map(bandIssueText);
  return <View name="band" active={active} eyebrow="BandFit" title={t('Mi banda')}
    description={t('Tus bandas con su plantilla fija y, debajo, cómo encaja la obra abierta en la banda activa.')}>
    <BandManager visible={!hidden && active === 'band'} onActivated={onBandActivated} />
    <h2 className="calculated-plan-title">{t('Adecuación de la obra abierta')}</h2>
    {unconfirmed.length > 0 && <InstrumentConfirmation items={unconfirmed} workId={data?.work_id} onConfirm={onConfirm} busy={busy} />}
    <div id="band-profile-editor" className="band-profile-editor surface" hidden={requirements.length === 0}>
      <fieldset>
        <legend>{t('Plantilla de esta obra')}</legend>
        <p className="result-supporting">{t('Empieza con los músicos que pide la obra: uno por voz y los percusionistas en total. Los cambios son temporales en esta demo.')}</p>
        <div id="band-profile-rows" className="band-profile-rows">{requirements.map(item =>
          <label key={item.key} className="band-profile-row">
            <span>{t(item.label_es)}<small className="result-supporting"> · {t('la obra pide {count}', { count: item.required })}</small></span>
            <input type="number" min="0" step="1" value={draft[item.key] ?? String(item.required)} aria-label={t('Músicos de {instrument}', { instrument: t(item.label_es) })}
              title={item.parts.map(part => displayInstrumentName(part)).join(', ')}
              onChange={event => onDraftChange(previous => ({ ...previous, [item.key]: event.target.value }))} />
          </label>)}</div>
        <button id="update-analysis" className="band-profile-update" type="button" disabled={busy} onClick={onUpdate}>
          {busy ? t('Actualizando…') : t('Actualizar análisis')}
        </button>
      </fieldset>
    </div>
    {data
      ? <div id="band-content" className="view-content">
          <section className="result-section">
            <h2>{t('Adaptación a la banda')}</h2>
            <p className="result-metric">{(bandFit.compatibility_percent ?? 0) + '%'}</p>
            <p className="result-supporting">{bandStatusLabels[bandFit.status] ? t(bandStatusLabels[bandFit.status]) : t('Estado no disponible')}</p>
            <ul className="result-list">{issues.length === 0
              ? <li className="result-empty">{t('La plantilla cubre los instrumentos requeridos.')}</li>
              : issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>
            {unconfirmed.length > 0 && <p className="result-supporting">{unconfirmed.length === 1
              ? t('Una parte está pendiente de confirmar y no cuenta todavía.')
              : t('{count} partes están pendientes de confirmar y no cuentan todavía.', { count: unconfirmed.length })}</p>}
          </section>
        </div>
      : <div id="band-content" className="view-content empty-workspace"><h2>{t('Aún no hay plantilla')}</h2><p>{t('Analiza una obra para cargar sus instrumentos y asignar músicos.')}</p></div>}
  </View>;
}
