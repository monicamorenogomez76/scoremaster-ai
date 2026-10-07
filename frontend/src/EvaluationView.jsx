import React, { useEffect, useRef, useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import {
  campaignSummary, createCampaign, exportCampaign, getCampaign, invitationProgress, listCampaigns, parseEmails,
  predictionText, removePassage, setCampaignStatus, setInvitations, shortfallText, statusLabel,
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
    <div className="campaign-body">
      <section className="campaign-passages-panel" aria-labelledby="campaign-passages-title">
        <h3 id="campaign-passages-title">Pasajes</h3>
        <p className="result-supporting">La predicción de ScoreLint solo la ves tú.{draft ? ' Quita los que no quieras valorar antes de abrir la campaña.' : ''}</p>
        <div className="table-scroll">
          <table className="campaign-passages">
            <thead><tr><th scope="col">#</th><th scope="col">Obra</th><th scope="col">Parte</th><th scope="col">Compases</th>
              <th scope="col">Predicción</th><th scope="col"><span className="visually-hidden">Acciones</span></th></tr></thead>
            <tbody>{campaign.passages.map((passage, index) => <tr key={passage.id}>
              <td>{index + 1}</td>
              <td>{passage.work_title}</td>
              <td>{passage.parts.map(displayInstrumentName).join(', ')}</td>
              <td>{passage.measure_range}</td>
              <td>{predictionText(passage.snapshot)}</td>
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

export function EvaluationView({ active, hidden, onOpenBlock }) {
  const [campaigns, setCampaigns] = useState({ owned: [], invited: [] });
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [shown, setShown] = useState(null);
  const [notice, setNotice] = useState('');
  const visible = !hidden && active === 'evaluation';
  const refresh = () => listCampaigns().then(found => { setCampaigns(found); setError(''); }).catch(failure => setError(failure.message));
  useEffect(() => { if (visible) refresh(); }, [visible]);
  const action = <button id="create-campaign" type="button" className="primary-action"
    onClick={() => { setShown(null); setNotice(''); setCreating(true); }}>Crear campaña</button>;
  return <View name="evaluation" active={active} eyebrow="Evaluación" title="Valoraciones"
    description="Músicos de confianza valoran pasajes de tus obras para comparar su criterio con el de ScoreLint." action={action}>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {creating && <CampaignEditor onCreated={(created, shortfall) => { setCreating(false); setNotice(shortfall); setShown(created.id); refresh(); }}
      onCancel={() => setCreating(false)} />}
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
              <button type="button" className="primary-action" onClick={() => { setCreating(false); setNotice(''); setShown(item.id); }}>Abrir</button>
            </div>
          </li>)}</ul>}
    </section>
  </View>;
}
