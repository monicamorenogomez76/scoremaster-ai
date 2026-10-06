import React, { useState } from 'react';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { assistantStep, phaseLabel, planItemsToSave, proposeConcertPlan, saveConcertPlan } from './concerts.js';
import { proposalBlocks, rehearsalDateText, todayIso } from './rehearsals.js';

// The concert's series proposed (again), shown before it is saved.
function SeriesProposal({ concert, label, onSaved, onOpenBlock }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const run = async action => {
    setBusy(true); setError('');
    try { await action(); } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const propose = () => run(async () => setPreview(await proposeConcertPlan(concert.id, todayIso())));
  const save = () => run(async () => { await saveConcertPlan(concert.id, todayIso(), planItemsToSave(preview.rehearsals)); setPreview(null); onSaved(); });
  return <>
    {!preview && <button type="button" className="primary-action" disabled={busy} onClick={propose}>{busy ? 'Calculando…' : label}</button>}
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {preview && <div className="next-step-preview">
      <p className="table-supporting">Propuesta calculada con el análisis de cada obra y tus revisiones: revísala antes de guardar.</p>
      <ol className="draft-list">{preview.rehearsals.map(item => <li key={item.id || item.date} className="draft-rehearsal">
        <strong>{rehearsalDateText(item)} · {phaseLabel(item.phase)}</strong>
        <AgendaCalendar blocks={proposalBlocks(item)} start={item.time} onOpenBlock={onOpenBlock} />
      </li>)}</ol>
      <div className="editor-actions">
        <button type="button" className="primary-action" disabled={busy || !preview.rehearsals.length} onClick={save}>Guardar planificación</button>
        <button type="button" className="secondary-action" onClick={() => setPreview(null)}>Descartar</button>
      </div>
    </div>}
  </>;
}

// The one thing to do next for the coming concert, inside the rehearsal card (author's decision,
// 2026-10-06: no separate panel repeating the concert or the rehearsal). Nothing when all is done.
export function NextStep({ concerts, rehearsals, onReviewRehearsal, onOpenBlock, onChanged }) {
  const today = todayIso();
  const next = assistantStep(concerts, rehearsals, today);
  if (!['review', 'replan', 'plan'].includes(next.step)) return null;
  const when = next.rehearsal?.date === today ? 'El ensayo de hoy' : 'El ensayo del ' + (next.rehearsal ? rehearsalDateText(next.rehearsal, today) : '');
  return <div className="next-step" role="status">
    {next.step === 'review' && <>
      <p><strong>{when} está sin revisar.</strong> Lo que quede pendiente ganará tiempo en los siguientes ensayos.</p>
      <button type="button" className="primary-action" onClick={() => onReviewRehearsal(next.rehearsal)}>Revisar ensayo</button>
    </>}
    {next.step === 'replan' && <>
      <p><strong>Tu última revisión es posterior al plan</strong> de los próximos ensayos de {next.concert.title}.</p>
      <SeriesProposal key={next.concert.id + '-replan'} concert={next.concert} label="Replanificar los ensayos siguientes" onSaved={onChanged} onOpenBlock={onOpenBlock} />
    </>}
    {next.step === 'plan' && <>
      <p><strong>{next.concert.title}</strong> aún no tiene ensayos planificados.</p>
      <SeriesProposal key={next.concert.id + '-plan'} concert={next.concert} label="Proponer planificación" onSaved={onChanged} onOpenBlock={onOpenBlock} />
    </>}
  </div>;
}
