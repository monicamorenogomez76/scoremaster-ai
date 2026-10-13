import React, { useEffect, useRef, useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import {
  campaignSummary, createCampaign, exportCampaign, getCampaign, invitationProgress, listCampaigns, parseEmails,
  predictionText, removePassage, setCampaignStatus, setInvitations, shortfallText, statusLabel,
  EXPERIENCE_OPTIONS, GRADE_RUBRIC, PRIORITY_LABELS, getLlmReview, llmReviewText, startLlmReview, nextToRate, ratedCount, ratingDraft, ratingToSend, saveProfile, saveRating,
} from './evaluations.js';
import { listWorks } from './library.js';
import { displayInstrumentName } from './labels.js';
import { View } from './View.jsx';

// A new campaign: the app proposes the passages of the chosen works from their analysis.
function CampaignEditor({ onCreated, onCancel }) {
  const [draft, setDraft] = useState({ title: '', instructions: '', work_ids: [], size: '50' });
  const [works, setWorks] = useState([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const heading = useRef(null);
  useEffect(() => { listWorks().then(found => setWorks(found.filter(work => work.summary?.grade != null)))
    .catch(failure => setError(failure.message)); }, []);
  useEffect(() => { heading.current?.focus(); }, []);
  const set = (field, value) => setDraft(current => ({ ...current, [field]: value }));
  const toggle = id => set('work_ids', draft.work_ids.includes(id) ? draft.work_ids.filter(item => item !== id) : [...draft.work_ids, id]);
  const save = async event => {
    event.preventDefault();
    setSaving(true); setError('');
    try {
      const size = Number(draft.size) || 50;
      const created = await createCampaign({ title: draft.title.trim(), instructions: draft.instructions.trim(),
        work_ids: draft.work_ids, size });
      onCreated(created, shortfallText(size, created.passages.length));
    } catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };
  return <form id="campaign-editor" className="rehearsal-editor surface" onSubmit={save} aria-labelledby="campaign-editor-title">
    <h2 id="campaign-editor-title" ref={heading} tabIndex={-1}>Nueva campaña de valoración</h2>
    <label>Título<input type="text" required maxLength={200} value={draft.title} onChange={event => set('title', event.target.value)} /></label>
    <label className="editor-wide">Instrucciones para los músicos<textarea rows={3} maxLength={2000} value={draft.instructions}
      placeholder="Por ejemplo: valora cada pasaje pensando en una banda amateur de nivel medio."
      onChange={event => set('instructions', event.target.value)} /></label>
    <fieldset className="editor-works">
      <legend>Obras de las que salen los pasajes</legend>
      {works.length === 0 && <p className="result-supporting">Analiza obras en Repertorio para proponer sus pasajes.</p>}
      {works.map(work => <label key={work.id} className="check-field">
        <input type="checkbox" checked={draft.work_ids.includes(work.id)} onChange={() => toggle(work.id)} />
        {work.title}<span className="table-supporting">{work.file_name}</span>
      </label>)}
    </fieldset>
    <label>Número de pasajes (entre 10 y 80)<input type="number" min="10" max="80" value={draft.size}
      onChange={event => set('size', event.target.value)} /></label>
    <p className="result-supporting">La aplicación propone alrededor de un 40 % de pasajes críticos y un 60 % no críticos, repartidos
      por obras y grados. Podrás quitar los que no quieras antes de abrir la campaña.</p>
    <ActivityStatus label={saving ? 'Proponiendo los pasajes con el análisis de ' + draft.work_ids.length
      + (draft.work_ids.length === 1 ? ' obra' : ' obras') : ''} />
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="editor-actions">
      <button type="submit" className="primary-action" disabled={saving || draft.work_ids.length === 0}>
        {saving ? 'Proponiendo…' : 'Proponer pasajes'}</button>
      <button type="button" className="secondary-action" onClick={onCancel}>Cancelar</button>
    </div>
  </form>;
}

function Invitations({ campaign, onChanged }) {
  const [text, setText] = useState(() => campaign.invitations.map(item => item.email).join('\n'));
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true); setError('');
    try {
      const updated = await setInvitations(campaign.id, parseEmails(text));
      setText(updated.invitations.map(item => item.email).join('\n'));
      onChanged(updated);
    }
    catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };
  return <section className="campaign-invitations" aria-labelledby="campaign-invitations-title">
    <h3 id="campaign-invitations-title">Músicos invitados</h3>
    <p className="result-supporting">Cada músico entra en {window.location.origin} con una cuenta creada con su email y abre
      Valoraciones. Nunca ve la predicción de ScoreLint.</p>
    <label>Emails (uno por línea)<textarea id="campaign-emails" rows={4} value={text} onChange={event => setText(event.target.value)} /></label>
    <div className="editor-actions">
      <button type="button" className="secondary-action" disabled={saving} onClick={save}>{saving ? 'Guardando…' : 'Guardar invitaciones'}</button>
    </div>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {campaign.invitations.length > 0 && <ul className="invitation-list">{campaign.invitations.map(item => <li key={item.email}>
      <span>{item.email}</span><span className="table-supporting">{invitationProgress(item, campaign.passages.length)}</span>
    </li>)}</ul>}
  </section>;
}

// Method B of the evaluation (step 22): the LLM rates every passage with the musicians' rubric from its
// measurements and notes, never seeing ScoreLint; only the director sees it. Followed while it runs.
function LlmReview({ campaignId, onReviewed }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const refresh = () => getLlmReview(campaignId).then(found => { setStatus(found); return found; }).catch(failure => setError(failure.message));
  useEffect(() => { refresh(); }, [campaignId]);
  useEffect(() => {
    if (status?.state !== 'running') return undefined;
    const timer = setInterval(() => refresh().then(found => { if (found && found.state !== 'running') onReviewed(); }), 5000);
    return () => clearInterval(timer);
  }, [status?.state]);
  const start = async () => {
    setError('');
    try { setStatus(await startLlmReview(campaignId)); } catch (failure) { setError(failure.message); }
  };
  if (!status) return null;
  const complete = status.available && status.total > 0 && status.done >= status.total;
  return <section id="llm-review" className="llm-review" aria-labelledby="llm-review-title">
    <div className="summary-card-heading">
      <h3 id="llm-review-title">Valoración independiente con IA</h3>
      <button type="button" className="secondary-action" disabled={!status.available || status.state === 'running' || complete}
        onClick={start}>{status.done && !complete ? 'Valorar los pendientes' : 'Valorar con IA'}</button>
    </div>
    <p className="result-supporting">La IA valora cada pasaje con la misma rúbrica que los músicos, a partir de sus medidas y
      sus notas, sin ver la predicción de ScoreLint. Es el método B de la evaluación: solo lo ves tú.</p>
    <ActivityStatus label={status.state === 'running' ? 'Valorando con IA: ' + status.done + ' de ' + status.total + ' pasajes' : ''} />
    {status.state !== 'running' && <p id="llm-review-status" className="table-supporting" role="status">{llmReviewText(status)}</p>}
    {error && <p className="result-supporting" role="alert">{error}</p>}
  </section>;
}

// The campaign of the director: its passages with ScoreLint's prediction, the musicians and its status.
function CampaignDetail({ id, notice, onClose, onChanged, onOpenBlock }) {
  const [campaign, setCampaign] = useState(null);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const heading = useRef(null);
  useEffect(() => { getCampaign(id).then(setCampaign).catch(failure => setError(failure.message)); }, [id]);
  useEffect(() => { if (campaign) heading.current?.focus(); }, [campaign?.id]);
  const changed = updated => { setCampaign(updated); onChanged(); };
  const run = async action => { setError(''); try { await action(); } catch (failure) { setError(failure.message); } };
  const remove = passage => run(async () => {
    await removePassage(campaign.id, passage.id);
    changed({ ...campaign, passages: campaign.passages.filter(item => item.id !== passage.id) });
  });
  const status = next => run(async () => { setConfirming(false); changed(await setCampaignStatus(campaign.id, next)); });
  if (!campaign) return error ? <p className="result-supporting" role="alert">{error}</p> : null;
  const draft = campaign.status === 'draft';
  return <section id="campaign-detail" className="surface campaign-detail" aria-labelledby="campaign-detail-title">
    <div className="summary-card-heading">
      <h2 id="campaign-detail-title" ref={heading} tabIndex={-1}>{campaign.title} <span className="status-tag">{statusLabel(campaign.status)}</span></h2>
      <button type="button" className="secondary-action" onClick={onClose}>Cerrar</button>
    </div>
    <p id="campaign-summary" className="result-supporting">{campaignSummary(campaign)}</p>
    {notice && <p id="campaign-notice" className="proposal-note" role="status">{notice}</p>}
    {campaign.instructions && <p className="campaign-instructions">{campaign.instructions}</p>}
    <div className="editor-actions">
      {draft && (confirming
        ? <><span>Al abrirla, los músicos invitados podrán valorar y ya no podrás quitar pasajes.</span>
            <button type="button" className="primary-action" onClick={() => status('open')}>Abrir ahora</button>
            <button type="button" className="secondary-action" onClick={() => setConfirming(false)}>Todavía no</button></>
        : <button type="button" className="primary-action" disabled={!campaign.passages.length} onClick={() => setConfirming(true)}>Abrir campaña</button>)}
      {campaign.status === 'open' && <button type="button" className="secondary-action" onClick={() => status('closed')}>Cerrar campaña</button>}
      <button type="button" className="secondary-action" onClick={() => run(() => exportCampaign(campaign))}>Exportar resultados</button>
    </div>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <LlmReview campaignId={campaign.id} onReviewed={() => getCampaign(campaign.id).then(setCampaign).catch(() => {})} />
    <div className="campaign-body">
      <section className="campaign-passages-panel" aria-labelledby="campaign-passages-title">
        <h3 id="campaign-passages-title">Pasajes</h3>
        <p className="result-supporting">La predicción de ScoreLint solo la ves tú.{draft ? ' Quita los que no quieras valorar antes de abrir la campaña.' : ''}</p>
        <div className="table-scroll">
          <table className="campaign-passages">
            <thead><tr><th scope="col">#</th><th scope="col">Obra</th><th scope="col">Parte</th><th scope="col">Compases</th>
              <th scope="col">ScoreLint</th><th scope="col">IA</th><th scope="col"><span className="visually-hidden">Acciones</span></th></tr></thead>
            <tbody>{campaign.passages.map((passage, index) => <tr key={passage.id}>
              <td>{index + 1}</td>
              <td>{passage.work_title}</td>
              <td>{passage.parts.map(displayInstrumentName).join(', ')}</td>
              <td>{passage.measure_range}</td>
              <td>{predictionText(passage.snapshot)}</td>
              <td title={passage.llm_review?.reason || ''}>{passage.llm_review ? predictionText(passage.llm_review) : '—'}</td>
              <td><span className="campaign-actions">
                <button type="button" className="link-action" onClick={() => onOpenBlock({ work_id: passage.work_id, parts: passage.parts,
                  measures: passage.measure_range, label: passage.label })}>Ver y escuchar</button>
                {draft && <button type="button" className="link-action" onClick={() => remove(passage)}>Quitar</button>}
              </span></td>
            </tr>)}</tbody>
          </table>
        </div>
      </section>
      <Invitations key={campaign.id} campaign={campaign} onChanged={changed} />
    </div>
  </section>;
}


// Who rates: asked once per campaign, before the first passage (only level and main instrument).
function ProfileForm({ campaign, onSaved }) {
  const [level, setLevel] = useState(campaign.profile.experience_level || '');
  const [instrument, setInstrument] = useState(campaign.profile.main_instrument || '');
  const [error, setError] = useState('');
  const save = async event => {
    event.preventDefault(); setError('');
    try { const saved = await saveProfile(campaign.id, level, instrument); onSaved(saved); }
    catch (failure) { setError(failure.message); }
  };
  return <form id="evaluator-profile" className="rehearsal-editor" onSubmit={save} aria-labelledby="evaluator-profile-title">
    <h3 id="evaluator-profile-title">Antes de empezar</h3>
    <p className="result-supporting">Solo se guardan tu nivel y tu instrumento; en los resultados apareces como «Evaluador n», sin nombre ni email.</p>
    <label>Tu experiencia<select required value={level} onChange={event => setLevel(event.target.value)}>
      <option value="">Elige una opción</option>
      {EXPERIENCE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
    <label>Tu instrumento principal<input type="text" required maxLength={100} value={instrument}
      onChange={event => setInstrument(event.target.value)} /></label>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <div className="editor-actions"><button type="submit" className="primary-action">Empezar a valorar</button></div>
  </form>;
}

function Choice({ name, value, current, onChange, children }) {
  return <label className={'rating-choice' + (current === value ? ' is-selected' : '')}>
    <input type="radio" name={name} value={value} checked={current === value} onChange={() => onChange(value)} />{children}
  </label>;
}

// The passages one at a time, never with ScoreLint's prediction; each rating is saved when moving on.
function RatingSession({ id, onClose, onChanged, onOpenPassage }) {
  const [campaign, setCampaign] = useState(null);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState(ratingDraft(null));
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const heading = useRef(null), passageTitle = useRef(null), moved = useRef(false);
  useEffect(() => {
    getCampaign(id).then(found => {
      setCampaign(found);
      const first = found.passages.findIndex(item => !item.rating);
      setIndex(first < 0 ? 0 : first);
    }).catch(failure => setError(failure.message));
  }, [id]);
  const passage = campaign?.passages[index];
  useEffect(() => { setDraft(ratingDraft(passage?.rating)); setError(''); }, [campaign?.id, index]);
  // Moving to another passage starts again at its title, not at the buttons just pressed.
  useEffect(() => {
    if (!moved.current) return;
    moved.current = false;
    passageTitle.current?.focus({ preventScroll: true });
    passageTitle.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [index]);
  const go = at => { moved.current = true; setIndex(at); };
  useEffect(() => { if (campaign) heading.current?.focus(); }, [campaign?.id]);
  if (!campaign) return error ? <p className="result-supporting" role="alert">{error}</p> : null;
  const open = campaign.status === 'open';
  const set = (field, value) => setDraft(current => ({ ...current, [field]: value }));
  const save = async event => {
    event.preventDefault();
    const rating = ratingToSend(draft);
    if (!rating) { setError('Indica la dificultad, si es crítico y la prioridad.'); return; }
    setSaving(true); setError('');
    try {
      await saveRating(campaign.id, passage.id, rating);
      const passages = campaign.passages.map((item, at) => (at === index ? { ...item, rating } : item));
      setCampaign({ ...campaign, passages });
      go(nextToRate(passages, index));
      onChanged();
    } catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };
  const done = ratedCount(campaign), total = campaign.passages.length;
  const profileMissing = !campaign.profile.experience_level;
  return <section id="rating-session" className="surface campaign-detail" aria-labelledby="rating-session-title">
    <div className="summary-card-heading">
      <h2 id="rating-session-title" ref={heading} tabIndex={-1}>{campaign.title} <span className="status-tag">{statusLabel(campaign.status)}</span></h2>
      <button type="button" className="secondary-action" onClick={onClose}>Cerrar</button>
    </div>
    {campaign.instructions && <p className="campaign-instructions">{campaign.instructions}</p>}
    <p id="rating-progress" className="result-supporting">{done} de {total} pasajes valorados{done === total && total ? ' · ¡gracias!' : ''}</p>
    <div className="rating-bar" aria-hidden="true"><span style={{ width: (total ? 100 * done / total : 0) + '%' }} /></div>
    {!open && <p className="proposal-note" role="status">La campaña está cerrada: puedes ver tus valoraciones, pero ya no cambiarlas.</p>}
    {open && profileMissing ? <ProfileForm campaign={campaign}
      onSaved={profile => setCampaign({ ...campaign, profile })} /> : passage && <>
      <nav className="rating-steps" aria-label="Pasajes">{campaign.passages.map((item, at) =>
        <button key={item.id} type="button" className={'rating-step' + (item.rating ? ' is-rated' : '') + (at === index ? ' is-current' : '')}
          aria-current={at === index ? 'step' : undefined} aria-label={'Pasaje ' + (at + 1) + (item.rating ? ', valorado' : ', sin valorar')}
          onClick={() => go(at)}>{at + 1}</button>)}</nav>
      <form id="rating-form" className="rating-form" onSubmit={save} aria-labelledby="rating-passage-title">
        <h3 id="rating-passage-title" ref={passageTitle} tabIndex={-1}>Pasaje {index + 1} de {total}</h3>
        <p className="rating-passage">{passage.work_title} · {passage.parts.map(displayInstrumentName).join(', ')} · compases {passage.measure_range}</p>
        <div className="editor-actions">
          <button type="button" className="primary-action" onClick={() => onOpenPassage(campaign.id, passage)}>Ver y escuchar el pasaje</button>
          <button type="button" className="secondary-action" onClick={() => onOpenPassage(campaign.id, passage, true)}>Ver su parte completa</button>
        </div>
        <fieldset disabled={!open}>
          <legend>Dificultad del pasaje: ¿qué nivel exige?</legend>
          <div className="rating-options rating-grades">{GRADE_RUBRIC.map(item =>
            <Choice key={item.grade} name="difficulty" value={String(item.grade)} current={draft.difficulty} onChange={value => set('difficulty', value)}>
              <strong>{item.grade} · {item.label}</strong><span>{item.standard} · {item.description}</span>
            </Choice>)}</div>
        </fieldset>
        <fieldset disabled={!open}>
          <legend>¿Es un pasaje crítico, especialmente problemático, que conviene trabajar aparte?</legend>
          <div className="rating-options">
            <Choice name="critical" value="yes" current={draft.critical} onChange={value => set('critical', value)}><strong>Sí</strong></Choice>
            <Choice name="critical" value="no" current={draft.critical} onChange={value => set('critical', value)}><strong>No</strong></Choice>
          </div>
        </fieldset>
        <fieldset disabled={!open}>
          <legend>Prioridad de ensayo</legend>
          <div className="rating-options">{[1, 2, 3, 4, 5].map(value =>
            <Choice key={value} name="priority" value={String(value)} current={draft.priority} onChange={choice => set('priority', choice)}>
              <strong>{value}</strong><span>{PRIORITY_LABELS[value]}</span>
            </Choice>)}</div>
        </fieldset>
        <label>Comentario (opcional)<textarea rows={2} maxLength={500} disabled={!open} value={draft.comment}
          onChange={event => set('comment', event.target.value)} /></label>
        {error && <p className="result-supporting" role="alert">{error}</p>}
        {open && <div className="editor-actions">
          <button type="submit" className="primary-action" disabled={saving}>{saving ? 'Guardando…' : 'Guardar y seguir'}</button>
          <span className="table-supporting">Cada valoración se guarda al pulsar; puedes seguir otro día.</span>
        </div>}
      </form>
    </>}
  </section>;
}

export function EvaluationView({ active, hidden, onOpenBlock, onOpenEvaluationPassage }) {
  const [campaigns, setCampaigns] = useState({ owned: [], invited: [] });
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [shown, setShown] = useState(null);
  const [notice, setNotice] = useState('');
  const [rating, setRating] = useState(null);
  const visible = !hidden && active === 'evaluation';
  const refresh = () => listCampaigns().then(found => { setCampaigns(found); setError(''); }).catch(failure => setError(failure.message));
  useEffect(() => { if (visible) refresh(); }, [visible]);
  const action = <button id="create-campaign" type="button" className="primary-action"
    onClick={() => { setShown(null); setRating(null); setNotice(''); setCreating(true); }}>Crear campaña</button>;
  return <View name="evaluation" active={active} eyebrow="Evaluación" title="Valoraciones"
    description="Músicos de confianza valoran pasajes de tus obras para comparar su criterio con el de ScoreLint." action={action}>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {creating && <CampaignEditor onCreated={(created, shortfall) => { setCreating(false); setNotice(shortfall); setShown(created.id); refresh(); }}
      onCancel={() => setCreating(false)} />}
    {rating && <RatingSession key={rating} id={rating} onClose={() => setRating(null)} onChanged={refresh}
      onOpenPassage={onOpenEvaluationPassage} />}
    {campaigns.invited.length > 0 && <section className="rehearsal-list" aria-labelledby="campaigns-invited-title">
      <h2 id="campaigns-invited-title" className="panel-title">Te han invitado a valorar</h2>
      <ul className="works-list">{campaigns.invited.map(item => <li key={item.id} className="works-item campaign-item">
        <div className="works-copy">
          <h3 className="works-title">{item.title} <span className="status-tag">{statusLabel(item.status)}</span></h3>
          <p className="result-supporting">{item.rated} de {item.passages} pasajes valorados</p>
        </div>
        <div className="works-actions">
          <button type="button" className="primary-action" onClick={() => { setCreating(false); setShown(null); setRating(item.id); }}>
            {item.status === 'open' ? (item.rated ? 'Seguir valorando' : 'Empezar') : 'Ver'}</button>
        </div>
      </li>)}</ul>
    </section>}
    {shown && <CampaignDetail key={shown} id={shown} notice={notice} onClose={() => setShown(null)} onChanged={refresh} onOpenBlock={onOpenBlock} />}
    <section className="rehearsal-list" aria-labelledby="campaigns-owned-title">
      <h2 id="campaigns-owned-title" className="panel-title">Mis campañas</h2>
      {campaigns.owned.length === 0 ? <p className="result-supporting">Aún no has creado ninguna campaña.</p>
        : <ul className="works-list">{campaigns.owned.map(item => <li key={item.id} className="works-item campaign-item">
            <div className="works-copy">
              <h3 className="works-title">{item.title} <span className="status-tag">{statusLabel(item.status)}</span></h3>
              <p className="result-supporting">{item.passages} pasajes · {item.invitations} músicos invitados · {item.rated} valoraciones</p>
            </div>
            <div className="works-actions">
              <button type="button" className="primary-action" onClick={() => { setCreating(false); setRating(null); setNotice(''); setShown(item.id); }}>Abrir</button>
            </div>
          </li>)}</ul>}
    </section>
  </View>;
}
