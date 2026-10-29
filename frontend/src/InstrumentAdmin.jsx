import React, { useEffect, useState } from 'react';
import { addInstrumentName, createInstrument, deleteInstrumentName, filterInstruments, instrumentGroups, instrumentKeys,
  instrumentSections, loadAdminInstruments, loadLearnedNames, newInstrumentBody } from './instrumentCatalog.js';

const sectionName = section => (instrumentSections.find(([value]) => value === section) || [section, section])[1];
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
    }, `«${name}» se reconoce ahora como ${instrument.label_es}.`);
  };
  const promote = item => run(() => addInstrumentName(item.canonical_id, item.name),
    `«${item.name}» se reconoce ahora como ${item.label_es} en todas las cuentas.`);
  const removeName = (instrument, name) => run(() => deleteInstrumentName(name.id),
    `«${name.name}» ya no se reconoce como ${instrument.label_es}.`);
  const create = event => {
    event.preventDefault();
    const body = newInstrumentBody(form);
    run(async () => { await createInstrument(body); setForm(EMPTY_FORM); }, `${body.label_es} está en el catálogo.`);
  };
  const field = name => ({ value: form[name], onChange: event => setForm(current => ({ ...current, [name]: event.target.value })) });

  const shown = catalog ? filterInstruments(catalog.instruments, query) : [];
  return <section className="surface settings-card instrument-admin" aria-labelledby="settings-instruments-title">
    <h2 id="settings-instruments-title">Instrumentos</h2>
    <p className="result-supporting">Los nombres con los que cada instrumento aparece en guiones y particellas, en cualquier idioma.
      Los números de parte y la tonalidad escrita («Trompeta en Sib 2») se reconocen solos. Las obras se analizan de nuevo
      con el catálogo nuevo la próxima vez que arranque el servidor.</p>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {!catalog && !error && <p className="result-supporting" role="status">Cargando el catálogo…</p>}
    {catalog && <>
      <label className="search-field" htmlFor="instrument-search">Buscar instrumento o nombre
        <input id="instrument-search" type="search" value={query} onChange={event => setQuery(event.target.value)} />
      </label>
      <p className="result-supporting" role="status">{status || `${shown.length} de ${catalog.instruments.length} instrumentos.`}</p>
      {shown.length === 0 ? <p className="result-supporting">Ningún instrumento tiene ese nombre.</p> :
        <ul className="instrument-admin-list">
          {shown.map(instrument => <li key={instrument.canonical_id}>
            <details>
              <summary>{instrument.label_es} <span className="result-supporting">· {instrument.label_en} · {sectionName(instrument.section)}
                {' '}· {instrument.names.length} nombres</span></summary>
              <ul className="instrument-names" aria-label={`Nombres de ${instrument.label_es}`}>
                {instrument.names.map(name => <li key={name.id} className="instrument-name">
                  <span>{name.name}</span>
                  <button type="button" className="link-action" disabled={busy}
                    aria-label={`Quitar el nombre ${name.name} de ${instrument.label_es}`}
                    onClick={() => removeName(instrument, name)}>Quitar</button>
                </li>)}
              </ul>
              <form className="instrument-name-form" onSubmit={event => addName(event, instrument)}>
                <label htmlFor={`instrument-name-${instrument.canonical_id}`}>Nuevo nombre para {instrument.label_es}</label>
                <input id={`instrument-name-${instrument.canonical_id}`} type="text" maxLength={120}
                  value={drafts[instrument.canonical_id] || ''}
                  onChange={event => setDrafts(current => ({ ...current, [instrument.canonical_id]: event.target.value }))} />
                <button type="submit" className="secondary-action" disabled={busy || !(drafts[instrument.canonical_id] || '').trim()}>
                  Añadir nombre</button>
              </form>
            </details>
          </li>)}
        </ul>}
      {learned.length > 0 && <section className="instrument-learned" aria-labelledby="instrument-learned-title">
        <h3 id="instrument-learned-title">Nombres confirmados por las cuentas</h3>
        <p className="result-supporting">Las cuentas los confirmaron al revisar sus obras; en las demás salen propuestos.
          Al añadirlos al catálogo se reconocen en todas sin preguntar.</p>
        <ul className="instrument-names">
          {learned.map(item => <li key={item.name + item.canonical_id} className="instrument-name">
            <span>{item.name} → {item.label_es} <span className="result-supporting">· {item.accounts === 1 ? '1 cuenta' : item.accounts + ' cuentas'}</span></span>
            <button type="button" className="link-action" disabled={busy}
              aria-label={`Añadir ${item.name} al catálogo como ${item.label_es}`} onClick={() => promote(item)}>Añadir al catálogo</button>
          </li>)}
        </ul>
      </section>}
      <details className="instrument-new">
        <summary>Nuevo instrumento</summary>
        <form className="instrument-new-form" onSubmit={create}>
          <label htmlFor="instrument-label-es">Nombre en español<input id="instrument-label-es" type="text" required maxLength={80} {...field('label_es')} /></label>
          <label htmlFor="instrument-label-en">Nombre en inglés<input id="instrument-label-en" type="text" required maxLength={80} {...field('label_en')} /></label>
          <label htmlFor="instrument-family">Familia (por ejemplo, dulzaina)<input id="instrument-family" type="text" required maxLength={40} {...field('family')} /></label>
          <label htmlFor="instrument-section">Sección<select id="instrument-section" {...field('section')}>
            {instrumentSections.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label htmlFor="instrument-key">Tonalidad<select id="instrument-key" {...field('transposition')}>
            {instrumentKeys.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label htmlFor="instrument-sound">Suena como<select id="instrument-sound" {...field('sound')}>
            <option value="">Sin sonido de altura (percusión)</option>
            {catalog.sounds.map(sound => <option key={sound} value={sound}>{sound.replaceAll('_', ' ')}</option>)}</select></label>
          <label htmlFor="instrument-group">Grupo de ensayo<select id="instrument-group" {...field('rehearsal_group')}>
            {instrumentGroups.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label htmlFor="instrument-names">Nombres en las partituras, uno por línea
            <textarea id="instrument-names" required rows={3} {...field('names')} /></label>
          <button type="submit" className="primary-action" disabled={busy}>Crear instrumento</button>
        </form>
      </details>
    </>}
  </section>;
}
