import React, { useState } from 'react';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { assistantStep, daysUntil, phaseLabel, planItemsToSave, proposeConcertPlan, saveConcertPlan } from './concerts.js';
import { blockWorkText, proposalBlocks, proposeRehearsal, rehearsalDateText, todayIso } from './rehearsals.js';

// Single rehearsal without a concert: warm-up, passages and tutti of the works in preparation.
function FreeProposal({ works, defaultMinutes, onReview }) {
  const [minutes, setMinutes] = useState(String(defaultMinutes || 90));
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generate = async () => {
    setBusy(true); setError('');
    try {
      const proposal = await proposeRehearsal(works.map(work => work.id), Number(minutes) || 0);
      setDraft({ minutes: Number(minutes), blocks: proposalBlocks(proposal), skipped: proposal.omitted_works.map(item => item.title) });
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const review = () => onReview({ key: 'draft-' + Date.now(), duration_minutes: draft.minutes,
    works: works.map(work => ({ id: work.id, title: work.title })), blocks: draft.blocks });
  return <>
    <h3 className="assistant-question">¿Preparamos la sesión?</h3>
    <p className="result-supporting">Crea un plan con las obras en preparación: calentamiento, pasajes por líneas comunes y secciones, y tutti.</p>
    {works.length === 0
      ? <p className="result-supporting">Marca obras como «En preparación» en Repertorio, o crea un concierto, para proponer un plan.</p>
      : <>
          <p className="assistant-works">{works.map(work => work.title).join(' · ')}</p>
          <div className="assistant-controls">
            <label>Duración (minutos)<input type="number" min="10" max="600" value={minutes} onChange={event => setMinutes(event.target.value)} /></label>
            <button type="button" className="primary-action" disabled={busy} onClick={generate}>{busy ? 'Calculando…' : 'Generar propuesta'}</button>
          </div>
        </>}
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {draft && <div className="assistant-draft">
      <div className="summary-card-heading"><h3>Plan de ensayo</h3><span className="status-tag">Borrador</span></div>
      <ol className="draft-list">{draft.blocks.map((block, index) => <li key={index} className="draft-block">
        <span className="agenda-number" aria-hidden="true">{index + 1}</span>
        <div><strong>{block.title} ({block.minutes} min)</strong><span className="table-supporting">{blockWorkText(block)}</span></div>
      </li>)}</ol>
      {draft.skipped.length > 0 && <p className="result-supporting">No caben en este tiempo: {draft.skipped.join(', ')}.</p>}
      <button type="button" className="secondary-action assistant-review" onClick={review}>Revisar y editar</button>
      <p className="table-supporting">El borrador no sustituye a ningún ensayo guardado hasta que lo guardes.</p>
    </div>}
  </>;
}

// The concert's series proposed again (or for the first time), shown before it is saved.
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
    {preview && <div className="assistant-draft">
      <div className="summary-card-heading"><h3>Planificación propuesta</h3><span className="status-tag">Borrador</span></div>
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

// Right column of the summary. With a concert ahead it suggests the next step of its series; without
// one it proposes a single rehearsal. Until the AI provider arrives (F2b) everything is the
// deterministic calculation, and the panel says so: it never passes for AI.
export function SummaryAssistant({ works, defaultMinutes, onReview, concerts, rehearsals, onReviewRehearsal, onEditRehearsal,
  onOpenBlock, onChanged }) {
  const today = todayIso();
  const next = assistantStep(concerts, rehearsals, today);
  const concert = next.concert;
  const when = rehearsal => (rehearsal.date === today ? 'de hoy' : 'del ' + rehearsalDateText(rehearsal, today));

  return <section id="summary-assistant" className="summary-card summary-assistant surface" aria-labelledby="summary-assistant-title">
    <div className="summary-card-heading">
      <h2 id="summary-assistant-title">Asistente de ensayo</h2>
      <span className="status-tag">Propuesta calculada · sin IA</span>
    </div>
    {concert && <p className="assistant-works">{concert.title} · {daysUntil(concert.date, today) === 0 ? 'hoy' : 'faltan ' + daysUntil(concert.date, today) + ' días'}</p>}
    {next.step === 'free' && <FreeProposal works={works} defaultMinutes={defaultMinutes} onReview={onReview} />}
    {next.step === 'review' && <>
      <h3 className="assistant-question">¿Cómo fue el ensayo?</h3>
      <p className="result-supporting">Revisa el ensayo {when(next.rehearsal)}: lo que quede pendiente ganará tiempo en los siguientes ensayos y lo resuelto lo perderá.</p>
      <button type="button" className="primary-action" onClick={() => onReviewRehearsal(next.rehearsal)}>Revisar ensayo</button>
    </>}
    {next.step === 'replan' && <>
      <h3 className="assistant-question">Tu revisión cambia el plan</h3>
      <p className="result-supporting">La última revisión es posterior a la planificación de los próximos ensayos: conviene replanificarlos.</p>
      <SeriesProposal key={concert.id + '-replan'} concert={concert} label="Replanificar los ensayos siguientes" onSaved={onChanged} onOpenBlock={onOpenBlock} />
    </>}
    {next.step === 'plan' && <>
      <h3 className="assistant-question">¿Planificamos los ensayos?</h3>
      <p className="result-supporting">El concierto aún no tiene ensayos planificados hasta su fecha.</p>
      <SeriesProposal key={concert.id + '-plan'} concert={concert} label="Proponer planificación" onSaved={onChanged} onOpenBlock={onOpenBlock} />
    </>}
    {next.step === 'next' && <>
      <h3 className="assistant-question">Próximo ensayo del concierto</h3>
      <p className="result-supporting">{rehearsalDateText(next.rehearsal, today)} · {phaseLabel(next.rehearsal.phase)}</p>
      <AgendaCalendar blocks={next.rehearsal.blocks} start={next.rehearsal.time} onOpenBlock={onOpenBlock} />
      <button type="button" className="secondary-action" onClick={() => onEditRehearsal(next.rehearsal)}>Abrir en Ensayos</button>
    </>}
    <p className="table-supporting assistant-next">La conversación con IA («Pregunta sobre tu ensayo») llegará en la siguiente fase.</p>
  </section>;
}
