import React, { useEffect, useState } from 'react';
import { t } from './i18n.js';
import { instrumentLabel } from './labels.js';
import { addInstrumentName, createInstrument, deleteInstrumentName, filterInstruments, instrumentGroups, instrumentKeys,
  instrumentSections, loadAdminInstruments, loadLearnedNames, newInstrumentBody } from './instrumentCatalog.js';

const sectionName = section => t((instrumentSections.find(([value]) => value === section) || [section, section])[1]);
const EMPTY_FORM = { label_es: '', label_en: '', section: 'woodwinds', family: '', transposition: '', sound: '',
  rehearsal_group: 'flutes', names: '' };

// Configuración › Instrumentos (2026-10-28), only for the administration: the names each instrument is written with
// in the scores and parts, and new common instruments. The works are analysed again at the next start of the server.
export function InstrumentAdmin() {
  const [catalog, setCatalog] = useState(null);
  const [learned, setLearned] = useState([]);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [query, setQuery] = useState('');
  const [drafts, setDrafts] = useState({});
  const [form, setForm] = useState(EMPTY_FORM);
  const [busy, setBusy] = useState(false);

  const reload = async () => {
    try { setCatalog(await loadAdminInstruments()); setError(''); }
    catch (failure) { setError(failure.message); }
    try { setLearned((await loadLearnedNames()).names || []); } catch { setLearned([]); }
  };
  useEffect(() => { reload(); }, []);

  const run = async (action, done) => {
    setBusy(true); setStatus('');
    try { await action(); await reload(); setStatus(done); }
    catch (failure) { setStatus(failure.message); } finally { setBusy(false); }
  };
  const addName = (event, instrument) => {
    event.preventDefault();
    const name = (drafts[instrument.canonical_id] || '').trim();
    if (!name) return;
    run(async () => {
      await addInstrumentName(instrument.canonical_id, name);
      setDrafts(current => ({ ...current, [instrument.canonical_id]: '' }));
    }, t('«{name}» se reconoce ahora como {instrument}.', { name, instrument: instrumentLabel(instrument) }));
  };
  const promote = item => run(() => addInstrumentName(item.canonical_id, item.name),
    t('«{name}» se reconoce ahora como {instrument} en todas las cuentas.', { name: item.name, instrument: instrumentLabel(item) }));
  const removeName = (instrument, name) => run(() => deleteInstrumentName(name.id),
    t('«{name}» ya no se reconoce como {instrument}.', { name: name.name, instrument: instrumentLabel(instrument) }));
  const create = event => {
    event.preventDefault();
    const body = newInstrumentBody(form);
    run(async () => { await createInstrument(body); setForm(EMPTY_FORM); }, t('{instrument} está en el catálogo.', { instrument: instrumentLabel(body) }));
  };
  const field = name => ({ value: form[name], onChange: event => setForm(current => ({ ...current, [name]: event.target.value })) });

  const shown = catalog ? filterInstruments(catalog.instruments, query) : [];
  return <section className="surface settings-card instrument-admin" aria-labelledby="settings-instruments-title">
    <h2 id="settings-instruments-title">{t('Instrumentos')}</h2>
    <p className="result-supporting">{t('Los nombres con los que cada instrumento aparece en guiones y particellas, en cualquier idioma. Los números de parte y la tonalidad escrita («Trompeta en Sib 2») se reconocen solos. Las obras se analizan de nuevo con el catálogo nuevo la próxima vez que arranque el servidor.')}</p>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {!catalog && !error && <p className="result-supporting" role="status">{t('Cargando el catálogo…')}</p>}
    {catalog && <>
      <label className="search-field" htmlFor="instrument-search">{t('Buscar instrumento o nombre')}
        <input id="instrument-search" type="search" value={query} onChange={event => setQuery(event.target.value)} />
      </label>
      <p className="result-supporting" role="status">{status || t('{shown} de {total} instrumentos.', { shown: shown.length, total: catalog.instruments.length })}</p>
      {shown.length === 0 ? <p className="result-supporting">{t('Ningún instrumento tiene ese nombre.')}</p> :
        <ul className="instrument-admin-list">
          {shown.map(instrument => <li key={instrument.canonical_id}>
            <details>
              <summary>{instrument.label_es} <span className="result-supporting">· {instrument.label_en} · {sectionName(instrument.section)}
                {' '}· {t('{count} nombres', { count: instrument.names.length })}</span></summary>
              <ul className="instrument-names" aria-label={t('Nombres de {instrument}', { instrument: instrumentLabel(instrument) })}>
                {instrument.names.map(name => <li key={name.id} className="instrument-name">
                  <span>{name.name}</span>
                  <button type="button" className="link-action" disabled={busy}
                    aria-label={t('Quitar el nombre {name} de {instrument}', { name: name.name, instrument: instrumentLabel(instrument) })}
                    onClick={() => removeName(instrument, name)}>{t('Quitar')}</button>
                </li>)}
              </ul>
              <form className="instrument-name-form" onSubmit={event => addName(event, instrument)}>
                <label htmlFor={`instrument-name-${instrument.canonical_id}`}>{t('Nuevo nombre para {instrument}', { instrument: instrumentLabel(instrument) })}</label>
                <input id={`instrument-name-${instrument.canonical_id}`} type="text" maxLength={120}
                  value={drafts[instrument.canonical_id] || ''}
                  onChange={event => setDrafts(current => ({ ...current, [instrument.canonical_id]: event.target.value }))} />
                <button type="submit" className="secondary-action" disabled={busy || !(drafts[instrument.canonical_id] || '').trim()}>
                  {t('Añadir nombre')}</button>
              </form>
            </details>
          </li>)}
        </ul>}
      {learned.length > 0 && <section className="instrument-learned" aria-labelledby="instrument-learned-title">
        <h3 id="instrument-learned-title">{t('Nombres confirmados por las cuentas')}</h3>
        <p className="result-supporting">{t('Las cuentas los confirmaron al revisar sus obras; en las demás salen propuestos. Al añadirlos al catálogo se reconocen en todas sin preguntar.')}</p>
        <ul className="instrument-names">
          {learned.map(item => <li key={item.name + item.canonical_id} className="instrument-name">
            <span>{item.name} → {instrumentLabel(item)} <span className="result-supporting">· {t(item.accounts === 1 ? '{count} cuenta' : '{count} cuentas', { count: item.accounts })}</span></span>
            <button type="button" className="link-action" disabled={busy}
              aria-label={t('Añadir {name} al catálogo como {instrument}', { name: item.name, instrument: instrumentLabel(item) })} onClick={() => promote(item)}>{t('Añadir al catálogo')}</button>
          </li>)}
        </ul>
      </section>}
      <details className="instrument-new">
        <summary>{t('Nuevo instrumento')}</summary>
        <form className="instrument-new-form" onSubmit={create}>
          <label htmlFor="instrument-label-es">{t('Nombre en español')}<input id="instrument-label-es" type="text" required maxLength={80} {...field('label_es')} /></label>
          <label htmlFor="instrument-label-en">{t('Nombre en inglés')}<input id="instrument-label-en" type="text" required maxLength={80} {...field('label_en')} /></label>
          <label htmlFor="instrument-family">{t('Familia (por ejemplo, dulzaina)')}<input id="instrument-family" type="text" required maxLength={40} {...field('family')} /></label>
          <label htmlFor="instrument-section">{t('Sección')}<select id="instrument-section" {...field('section')}>
            {instrumentSections.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
          <label htmlFor="instrument-key">{t('Tonalidad')}<select id="instrument-key" {...field('transposition')}>
            {instrumentKeys.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
          <label htmlFor="instrument-sound">{t('Suena como')}<select id="instrument-sound" {...field('sound')}>
            <option value="">{t('Sin sonido de altura (percusión)')}</option>
            {catalog.sounds.map(sound => <option key={sound} value={sound}>{sound.replaceAll('_', ' ')}</option>)}</select></label>
          <label htmlFor="instrument-group">{t('Grupo de ensayo')}<select id="instrument-group" {...field('rehearsal_group')}>
            {instrumentGroups.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
          <label htmlFor="instrument-names">{t('Nombres en las partituras, uno por línea')}
            <textarea id="instrument-names" required rows={3} {...field('names')} /></label>
          <button type="submit" className="primary-action" disabled={busy}>{t('Crear instrumento')}</button>
        </form>
      </details>
    </>}
  </section>;
}
