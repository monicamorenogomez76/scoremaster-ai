import React, { useCallback, useEffect, useState } from 'react';
import { analysisStatusText, deleteWork, listWorks, preparationLabels, updatePreparation, workSummaryText } from './library.js';
import { dateLocale, t } from './i18n.js';

const dateText = value => (value ? new Date(value).toLocaleDateString(dateLocale(), { day: 'numeric', month: 'short', year: 'numeric' }) : '');
// Accent- and case-insensitive search by title or composer.
const folded = text => (text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// The signed-in user's repertoire: search, set the preparation status, reopen or delete a work.
export function WorksList({ visible, revision, onOpen, busy }) {
  const [works, setWorks] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [confirming, setConfirming] = useState(null);
  const refresh = useCallback(() => {
    listWorks().then(found => { setWorks(found); setError(''); }).catch(failure => setError(failure.message));
  }, []);
  useEffect(() => { if (visible) refresh(); }, [visible, revision, refresh]);

  const remove = async id => {
    setConfirming(null);
    try { await deleteWork(id); refresh(); } catch (failure) { setError(failure.message); }
  };
  const prepare = async (id, status) => {
    try {
      const changed = await updatePreparation(id, status);
      setWorks(current => current.map(work => (work.id === id ? { ...work, preparation_status: changed.preparation_status } : work)));
    } catch (failure) { setError(failure.message); }
  };
  const shown = (works || []).filter(work => folded(work.title + ' ' + (work.composer || '')).includes(folded(query.trim())));

  return <section id="works-content" className="view-content works-section" aria-labelledby="works-heading">
    <div className="section-toolbar">
      <h2 id="works-heading">{t('Obras')}</h2>
      <label className="search-field">
        <span className="visually-hidden">{t('Buscar por título o compositor')}</span>
        <input id="works-search" type="search" placeholder={t('Buscar por título o compositor')} value={query}
          onChange={event => setQuery(event.target.value)} />
      </label>
    </div>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {works && works.length === 0 && <div className="empty-workspace"><h3>{t('Aún no hay obras')}</h3><p>{t('Añade una partitura MusicXML para analizarla y guardarla aquí. Solo tú puedes verlas.')}</p></div>}
    {works && works.length > 0 && shown.length === 0 && <p className="result-supporting">{t('Ninguna obra coincide con la búsqueda.')}</p>}
    {shown.length > 0 && <ul className="works-list">{shown.map(work =>
      <li key={work.id} className="works-item">
        <div className="works-copy">
          <h3 className="works-title">{work.title}</h3>
          <p className="result-supporting">{[work.composer, work.file_name, dateText(work.updated_at)].filter(Boolean).join(' · ')}</p>
          <p className="works-summary">{workSummaryText(work)}</p>
        </div>
        <label className="works-field">{t('Preparación')}
          <select className="work-preparation" value={work.preparation_status || 'review'} disabled={busy}
            onChange={event => prepare(work.id, event.target.value)}>
            {Object.entries(preparationLabels()).map(([status, label]) => <option key={status} value={status}>{label}</option>)}
          </select>
        </label>
        <p className="works-field">{t('Análisis')}<span className="status-tag">{analysisStatusText(work)}</span></p>
        <div className="works-actions">
          <button className="work-open primary-action" type="button" disabled={busy} onClick={() => onOpen(work.id)}>{t('Abrir')}</button>
          {confirming === work.id
            ? <><button className="work-delete-confirm danger-action" type="button" onClick={() => remove(work.id)}>{t('Eliminar definitivamente')}</button>
                <button type="button" className="secondary-action" onClick={() => setConfirming(null)}>{t('Cancelar')}</button></>
            : <button className="work-delete secondary-action" type="button" onClick={() => setConfirming(work.id)}>{t('Eliminar')}</button>}
        </div>
      </li>)}</ul>}
  </section>;
}
