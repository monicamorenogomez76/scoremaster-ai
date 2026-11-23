import React, { useEffect, useId, useRef, useState } from 'react';
import {
  ALTERS, STEPS, alterLabel, correctionLabel, doubtTarget, listCorrections, measureNotes, noteLabel, pitchLabel, saveCorrection,
  stepLabel, undoLastCorrection, workParts,
} from '../noteCorrections.js';
import { t } from '../i18n.js';

const DEFAULT_PITCH = ['C', 0, 5];
const samePitch = (one, other) => JSON.stringify(one ?? null) === JSON.stringify(other ?? null);

// The director corrects a note the PDF reader got wrong (2026-11-22): a part and a measure, one of its notes, and what
// it should be. A reader's doubt opens it on its part and measure (target). The work opens again with the correction.
export function NoteCorrections({ workId, target, onCorrected }) {
  const id = useId();
  const panel = useRef(null), notesHeading = useRef(null);
  const [open, setOpen] = useState(false);
  const [parts, setParts] = useState([]);
  const [corrections, setCorrections] = useState([]);
  const [partId, setPartId] = useState('');
  const [measure, setMeasure] = useState('');
  const [found, setFound] = useState(null);       // the measure shown: { measure, number, notes }
  const [chosen, setChosen] = useState(null);     // index of the note
  const [rest, setRest] = useState(false);
  const [pitch, setPitch] = useState(DEFAULT_PITCH);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ text: '', error: false });

  useEffect(() => {
    setParts([]); setCorrections([]); setFound(null); setChosen(null); setMessage({ text: '', error: false });
    if (!workId || !open) return;
    let current = true;
    Promise.all([workParts(workId), listCorrections(workId)]).then(([names, done]) => {
      if (!current) return;
      setParts(names); setCorrections(done);
      setPartId(previous => names.some(part => part.id === previous) ? previous : names[0]?.id || '');
    }).catch(failure => current && setMessage({ text: failure.message, error: true }));
    return () => { current = false; };
  }, [workId, open]);

  const show = async (part = partId, number = measure) => {
    if (!part || !String(number).trim()) return;
    setBusy(true); setMessage({ text: '', error: false }); setChosen(null);
    try {
      const answer = await measureNotes(workId, part, String(number).trim());
      setFound(answer);
      notesHeading.current?.focus();
    } catch (failure) { setFound(null); setMessage({ text: failure.message, error: true }); }
    finally { setBusy(false); }
  };

  // A doubt of the reader: its part and the first measure of its passage.
  useEffect(() => {
    if (!target) return;
    setOpen(true);
    panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [target]);
  useEffect(() => {
    if (!target || !parts.length) return;
    const place = doubtTarget(parts, target.part, target.passage);
    if (!place) { setMessage({ text: t('Esa parte no se encontró en la obra.'), error: true }); return; }
    setPartId(place.partId); setMeasure(place.measure);
    show(place.partId, place.measure);
  }, [target, parts]); // eslint-disable-line react-hooks/exhaustive-deps

  const choose = index => {
    setChosen(index);
    const note = found.notes[index];
    setRest(false);
    const before = found.notes.slice(0, index).reverse().find(item => item.pitch)?.pitch;
    setPitch(note.pitch || before || found.notes.find(item => item.pitch)?.pitch || DEFAULT_PITCH);
  };

  const note = chosen === null ? null : found?.notes[chosen];
  const wanted = rest ? null : pitch;
  const unchanged = !note || samePitch(note.pitch, wanted);

  const finish = async (work, done) => {
    setBusy(true); setMessage({ text: '', error: false });
    try {
      setCorrections(await work());
      await onCorrected?.();
      if (found) await show(partId, found.number);
      // After the measure is shown again, which clears the message.
      setMessage({ text: done, error: false });
    } catch (failure) { setMessage({ text: failure.message, error: true }); }
    finally { setBusy(false); }
  };
  const save = event => {
    event.preventDefault();
    if (unchanged) return;
    finish(() => saveCorrection(workId, partId, found.measure, note, wanted),
      t('Corrección guardada: {change}.', { change: pitchLabel(note.pitch) + ' → ' + pitchLabel(wanted) }));
  };
  const undo = () => finish(() => undoLastCorrection(workId), t('Última corrección deshecha.'));

  return <details ref={panel} className="note-corrections" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{t('Corregir notas')}{corrections.length ? ' · ' + (corrections.length === 1 ? t('1 corrección') : t('{count} correcciones', { count: corrections.length })) : ''}</summary>
    <p className="result-supporting">{t('Cambia la altura de una nota mal leída, o un silencio que es una nota y al revés. La obra se vuelve a analizar con la corrección; cada corrección queda anotada y la última se puede deshacer.')}</p>
    <form className="note-corrections-find" onSubmit={event => { event.preventDefault(); show(); }}>
      <label htmlFor={id + '-part'}>{t('Parte')}
        <select id={id + '-part'} value={partId} onChange={event => { setPartId(event.target.value); setFound(null); }}>
          {parts.map(part => <option key={part.id} value={part.id}>{part.name}</option>)}
        </select>
      </label>
      <label htmlFor={id + '-measure'}>{t('Compás')}
        <input id={id + '-measure'} inputMode="numeric" autoComplete="off" value={measure}
          onChange={event => setMeasure(event.target.value.replace(/[^\dA-Za-z]/g, '').slice(0, 10))} />
      </label>
      <button className="secondary-action" type="submit" disabled={busy || !partId || !measure.trim()}>{t('Ver las notas')}</button>
    </form>

    {found && <form className="note-corrections-edit" onSubmit={save}>
      <fieldset>
        <legend ref={notesHeading} tabIndex={-1}>{t('Compás {number}: elige la nota que corregir', { number: found.number })}</legend>
        {found.notes.length === 0 && <p className="result-empty">{t('Este compás no tiene notas que se puedan corregir.')}</p>}
        {found.notes.map((item, index) => <label key={index} className="note-corrections-choice" htmlFor={id + '-note-' + index}>
          <input id={id + '-note-' + index} type="radio" name={id + '-note'} checked={chosen === index} onChange={() => choose(index)} />
          {noteLabel(item, index)}
        </label>)}
      </fieldset>
      {note && <fieldset>
        <legend>{t('Debe ser')}</legend>
        <div className="note-corrections-kind">
          <label htmlFor={id + '-is-note'}><input id={id + '-is-note'} type="radio" name={id + '-kind'} checked={!rest} onChange={() => setRest(false)} />{t('Una nota')}</label>
          <label htmlFor={id + '-is-rest'}><input id={id + '-is-rest'} type="radio" name={id + '-kind'} checked={rest}
            disabled={note.chord} onChange={() => setRest(true)} />{t('Un silencio')}</label>
        </div>
        {!rest && <div className="note-corrections-pitch">
          <label htmlFor={id + '-step'}>{t('Nota')}
            <select id={id + '-step'} value={pitch[0]} onChange={event => setPitch([event.target.value, pitch[1], pitch[2]])}>
              {STEPS.map(step => <option key={step} value={step}>{stepLabel(step)}</option>)}
            </select>
          </label>
          <label htmlFor={id + '-alter'}>{t('Alteración')}
            <select id={id + '-alter'} value={pitch[1]} onChange={event => setPitch([pitch[0], Number(event.target.value), pitch[2]])}>
              {ALTERS.map(alter => <option key={alter} value={alter}>{alterLabel(alter)}</option>)}
            </select>
          </label>
          <label htmlFor={id + '-octave'}>{t('Octava')}
            <select id={id + '-octave'} value={pitch[2]} onChange={event => setPitch([pitch[0], pitch[1], Number(event.target.value)])}>
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map(octave => <option key={octave} value={octave}>{octave}</option>)}
            </select>
          </label>
        </div>}
        <p className="note-corrections-preview">{pitchLabel(note.pitch)} → <strong>{pitchLabel(wanted)}</strong></p>
        <button className="primary-action" type="submit" disabled={busy || unchanged}>{t('Guardar la corrección')}</button>
      </fieldset>}
    </form>}

    <p className={message.error ? 'score-compare-error' : 'result-supporting'} role={message.error ? 'alert' : 'status'}>{message.text}</p>

    {corrections.length > 0 && <section aria-labelledby={id + '-done'}>
      <h3 id={id + '-done'} className="note-corrections-title">{t('Correcciones de esta obra')}</h3>
      <ol className="note-corrections-list">{corrections.map(item => <li key={item.id}>{correctionLabel(item)}</li>)}</ol>
      <button className="secondary-action" type="button" disabled={busy} onClick={undo}>{t('Deshacer la última corrección')}</button>
    </section>}
  </details>;
}
