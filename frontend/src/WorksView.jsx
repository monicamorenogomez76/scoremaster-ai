import React, { useCallback, useEffect, useState } from 'react';
import { View } from './View.jsx';
import { deleteWork, listWorks, workSummaryText } from './library.js';

const dateText = value => (value ? new Date(value).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' }) : '');

// The signed-in user's works: reopen one without uploading it again, or delete it with its analyses.
export function WorksView({ active, revision, onOpen, busy }) {
  const [works, setWorks] = useState(null);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(null);
  const refresh = useCallback(() => {
    listWorks().then(found => { setWorks(found); setError(''); }).catch(failure => setError(failure.message));
  }, []);
  useEffect(() => { if (active === 'works') refresh(); }, [active, revision, refresh]);

  const remove = async id => {
    setConfirming(null);
    try { await deleteWork(id); refresh(); } catch (failure) { setError(failure.message); }
  };

  return <View name="works" active={active} eyebrow="Biblioteca" title="Mis obras"
    description="Las obras que has analizado, con su último análisis. Solo tú puedes verlas.">
    <div id="works-content" className="view-content">
      {error && <p className="result-supporting" role="alert">{error}</p>}
      {works && works.length === 0 && <div className="empty-workspace"><h2>Aún no hay obras</h2><p>Analiza una partitura para guardarla aquí.</p></div>}
      {works && works.length > 0 && <ul className="works-list">{works.map(work =>
        <li key={work.id} className="works-item surface">
          <div className="works-copy">
            <h2 className="works-title">{work.title}</h2>
            <p className="result-supporting">{[work.composer, work.file_name, dateText(work.updated_at)].filter(Boolean).join(' · ')}</p>
            <p className="works-summary">{workSummaryText(work)}</p>
          </div>
          <div className="works-actions">
            <button className="work-open" type="button" disabled={busy} onClick={() => onOpen(work.id)}>Abrir</button>
            {confirming === work.id
              ? <><button className="work-delete-confirm" type="button" onClick={() => remove(work.id)}>Eliminar definitivamente</button>
                  <button type="button" onClick={() => setConfirming(null)}>Cancelar</button></>
              : <button className="work-delete" type="button" onClick={() => setConfirming(work.id)}>Eliminar</button>}
          </div>
        </li>)}</ul>}
    </div>
  </View>;
}
