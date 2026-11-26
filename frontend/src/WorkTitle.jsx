import React, { useEffect, useRef, useState } from 'react';
import { renameWork } from './library.js';
import { t } from './i18n.js';

// The title and composer of the open work, which the director may change (2026-11-25): its recordings are searched by them.
export function WorkTitle({ data, onRenamed }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ title: '', composer: '' });
  const [state, setState] = useState({ busy: false, error: '' });
  const first = useRef(null), edit = useRef(null), back = useRef(false);
  useEffect(() => {
    if (editing) first.current?.select();
    else if (back.current) { back.current = false; edit.current?.focus(); }
  }, [editing]);
  const open = () => { setForm({ title: data.title || '', composer: data.composer || '' }); setState({ busy: false, error: '' }); setEditing(true); };
  const close = () => { back.current = true; setEditing(false); };
  const submit = async event => {
    event.preventDefault();
    setState({ busy: true, error: '' });
    try {
      const work = await renameWork(data.work_id, form.title, form.composer);
      onRenamed({ title: work.title, composer: work.composer });
      close();
    } catch (failure) { setState({ busy: false, error: failure.message }); }
  };
  const field = name => ({ value: form[name], maxLength: 300, disabled: state.busy, onChange: event => setForm({ ...form, [name]: event.target.value }) });
  return <>
    <h2 id="work-detail-title">{data?.title || t('Partitura sin título')}</h2>
    <p className="result-supporting">{data?.composer || t('Compositor no indicado en el MusicXML')}</p>
    {data?.work_id && !editing && <button id="work-rename" ref={edit} className="secondary-action" type="button" onClick={open}>{t('Cambiar título')}</button>}
    {editing && <form className="work-rename" onSubmit={submit} onKeyDown={event => { if (event.key === 'Escape') close(); }}>
      <label htmlFor="work-rename-title">{t('Título')}</label>
      <input id="work-rename-title" ref={first} type="text" required aria-describedby={state.error ? 'work-rename-error' : undefined} {...field('title')} />
      <label htmlFor="work-rename-composer">{t('Compositor (opcional)')}</label>
      <input id="work-rename-composer" type="text" {...field('composer')} />
      {state.error && <p id="work-rename-error" className="login-error" role="alert">{state.error}</p>}
      <div className="score-edit-actions">
        <button id="work-rename-save" className="primary-action" type="submit" disabled={state.busy || !form.title.trim()}>{state.busy ? t('Guardando…') : t('Guardar título')}</button>
        <button className="secondary-action" type="button" disabled={state.busy} onClick={close}>{t('Cancelar')}</button>
      </div>
    </form>}
  </>;
}
