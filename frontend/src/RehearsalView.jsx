import React, { useEffect, useState } from 'react';
import { View } from './View.jsx';
import { ActivityStatus } from './ActivityStatus.jsx';
import { explainRehearsal, sourceText } from './explanations.js';
import { blockScoreLabel, calendarLabel, omittedBlockText, rehearsalBlockDetail, rehearsalBlockTitle } from './labels.js';
import { rehearsalSchedule } from './schedule.js';
import { AgendaCalendar } from './AgendaCalendar.jsx';
import { RehearsalEditor } from './RehearsalEditor.jsx';
import { RehearsalReview } from './RehearsalReview.jsx';
import { canReview, listRehearsals, rehearsalDateText, splitRehearsals } from './rehearsals.js';
import { t } from './i18n.js';

const VISIBLE_OMITTED = 5;

// Timeline of the rehearsal: each block is as wide as its minutes; pressing it opens the score
// at its measures with only the instruments it involves (the whole band for the tutti).
function RehearsalCalendar({ blocks, onOpenPassage }) {
  const [start, setStart] = useState('19:00');
  const schedule = rehearsalSchedule(blocks, start);
  const open = (block, range) => onOpenPassage(block.parts, range, blockScoreLabel(block));
  return <div className="rehearsal-calendar">
    <label className="duration-field" htmlFor="rehearsal-start">{t('Hora de inicio')}
      <input id="rehearsal-start" type="time" value={start} onChange={event => setStart(event.target.value)} />
    </label>
    <div className="calendar-track" role="list" aria-label={t('Horario del ensayo')}>
      {schedule.map((block, index) => {
        const ranges = block.type === 'tutti' ? block.measure_ranges || [] : [block.measure_range];
        return <div key={index} role="listitem" className={'calendar-slot calendar-slot--' + (block.type === 'sectional' ? block.group : block.type)}
          style={{ flexGrow: block.share, flexBasis: 0 }}>
          <button type="button" className="calendar-block" disabled={!ranges.length}
            aria-label={block.start + '–' + block.end + ' · ' + rehearsalBlockTitle(block) + ' · ' + block.minutes + ' min'}
            onClick={() => open(block, ranges[0])}>
            <span className="calendar-time">{block.start}</span>
            <span className="calendar-name">{calendarLabel(block)}</span>
          </button>
          {ranges.length > 1 && <div className="calendar-ranges">{ranges.map(range =>
            <button key={range} type="button" className="calendar-range" aria-label={t('Abrir compases {range} con toda la banda', { range })}
              onClick={() => open(block, range)}>{range}</button>)}</div>}
        </div>;
      })}
    </div>
  </div>;
}

// «¿Por qué este plan?» (step 20): written only from the rehearsal, its works' analysis, its concert and
// the last review, by AI or by the demo, always saying which; each cited block opens its passage.
function RehearsalWhy({ rehearsal, onOpenBlock }) {
  const [state, setState] = useState({ open: false, loading: false, result: null, error: '' });
  const toggle = async () => {
    if (state.open) { setState(current => ({ ...current, open: false })); return; }
    if (state.result) { setState(current => ({ ...current, open: true })); return; }
    setState({ open: true, loading: true, result: null, error: '' });
    try { setState({ open: true, loading: false, result: await explainRehearsal(rehearsal.id), error: '' }); }
    catch (failure) { setState({ open: true, loading: false, result: null, error: failure.message }); }
  };
  const { result } = state;
  const label = block => [block.title, block.work_title, block.measures && t('compases {range}', { range: block.measures })].filter(Boolean).join(' · ');
  return <div className="rehearsal-why">
    <button type="button" className="link-action" aria-expanded={state.open} onClick={toggle}>
      {state.open ? t('Ocultar la explicación') : t('¿Por qué este plan?')}</button>
    {state.open && <>
      <ActivityStatus label={state.loading ? t('Preparando la explicación del ensayo') : ''} />
      {state.error && <p className="result-supporting" role="alert">{state.error}</p>}
      {result && <div className="explanation-body" aria-live="polite">
        <p className={'explanation-source' + (result.mode === 'llm' ? ' is-ai' : ' is-demo')}>{sourceText(result)}</p>
        <p className="explanation-summary">{result.explanation.summary}</p>
        <ul className="explanation-factors">{result.explanation.reasons.map((reason, index) => <li key={index}>
          <p>{reason.text}</p>
          <div className="passage-actions">{reason.blocks.map(code => {
            const block = result.blocks[code];
            return block && <button key={code} type="button" className="passage-open" disabled={!block.work_id}
              onClick={() => onOpenBlock({ work_id: block.work_id, parts: block.parts, measures: block.measures, label: block.title })}>
              {label(block)}</button>;
          })}</div>
        </li>)}</ul>
        <p className="explanation-tip"><strong>{t('Para dirigirlo:')}</strong> {result.explanation.advice}</p>
      </div>}
    </>}
  </div>;
}

function RehearsalList({ id, title, items, empty, onEdit, onReview, onOpenBlock }) {
  return <section id={id} className="rehearsal-list" aria-labelledby={id + '-title'}>
    <h3 id={id + '-title'}>{title}</h3>
    {items.length === 0 ? <p className="result-supporting">{empty}</p>
      : <ul className="works-list">{items.map(item => <li key={item.id} className="works-item rehearsal-item">
          <div className="works-copy">
            <h4 className="works-title">{rehearsalDateText(item)}</h4>
            <p className="result-supporting">{[t('{minutes} minutos', { minutes: item.duration_minutes }), item.place, item.works.map(work => work.title).join(', ') || t('Sin obras')]
              .filter(Boolean).join(' · ')}</p>
            <p className="works-summary">{t(item.blocks.length === 1 ? '{count} bloque' : '{count} bloques', { count: item.blocks.length })}</p>
            <AgendaCalendar blocks={item.blocks} start={item.time} onOpenBlock={onOpenBlock} />
            {item.blocks.length > 0 && <RehearsalWhy rehearsal={item} onOpenBlock={onOpenBlock} />}
          </div>
          <div className="works-actions">
            {canReview(item) && <button type="button" className="primary-action" onClick={() => onReview(item)}>{item.reviewed_at ? t('Ver revisión') : t('Revisar')}</button>}
            <button type="button" className="secondary-action" onClick={() => onEdit(item)}>{t('Editar')}</button>
          </div>
        </li>)}</ul>}
  </section>;
}

// Saved rehearsals: create one, edit its agenda, or consult the ones already held.
function SavedRehearsals({ visible, editing, onEdit, onCloseEditor, onOpenBlock, reviewing, onReview, onCloseReview }) {
  const [rehearsals, setRehearsals] = useState([]);
  const [error, setError] = useState('');
  const refresh = () => listRehearsals().then(found => { setRehearsals(found); setError(''); }).catch(failure => setError(failure.message));
  useEffect(() => { if (visible) refresh(); }, [visible]);
  const { upcoming, past } = splitRehearsals(rehearsals);
  return <section id="saved-rehearsals" className="saved-rehearsals" aria-labelledby="saved-rehearsals-title">
    <div className="section-toolbar">
      <h2 id="saved-rehearsals-title">{t('Ensayos guardados')}</h2>
      <button id="create-rehearsal" type="button" className="primary-action" onClick={() => onEdit({})}>{t('Crear ensayo')}</button>
    </div>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {editing && <RehearsalEditor key={editing.id || editing.key || 'new'} rehearsal={editing}
      onSaved={() => { onCloseEditor(); refresh(); }} onCancel={onCloseEditor} />}
    {reviewing && <RehearsalReview key={reviewing.id} rehearsal={reviewing}
      onSaved={() => { onCloseReview(); refresh(); }} onCancel={onCloseReview} />}
    <RehearsalList id="rehearsals-upcoming" title={t('Próximos')} items={upcoming} empty={t('No hay ensayos programados.')} onEdit={onEdit} onReview={onReview} onOpenBlock={onOpenBlock} />
    <RehearsalList id="rehearsals-past" title={t('Realizados')} items={past} empty={t('Aún no hay ensayos realizados.')} onEdit={onEdit} onReview={onReview} onOpenBlock={onOpenBlock} />
  </section>;
}

export function RehearsalView({ active, hidden, onOpenBlock, reviewing, onReview, onCloseReview, data, minutes, onMinutesChange, onRecalculate, busy, onOpenPassage, editing, onEdit, onCloseEditor }) {
  const plan = data?.rehearsal_plan || {};
  const blocks = plan.segments || [];
  const omitted = plan.omitted || [];
  return <View name="rehearsal" active={active} eyebrow={t('Ensayos')} title={t('Ensayos')}
    description={t('Programa las sesiones con su agenda y consulta las que ya se han hecho.')}>
    <SavedRehearsals visible={!hidden && active === 'rehearsal'} editing={editing} onEdit={onEdit} onCloseEditor={onCloseEditor} onOpenBlock={onOpenBlock}
      reviewing={reviewing} onReview={onReview} onCloseReview={onCloseReview} />
    <h2 className="calculated-plan-title">{t('Plan calculado de la obra abierta')}</h2>
    <p className="result-supporting">{t('Ensayo de conjunto: primero quienes tocan lo mismo, después las subsecciones y un tutti final para juntar.')}</p>
    <div className="rehearsal-settings surface">
      <label className="duration-field" htmlFor="total-minutes">{t('Duración prevista del ensayo')}
        <span className="duration-input"><input id="total-minutes" type="number" min="10" value={minutes}
          onChange={event => onMinutesChange(event.target.value)} /><span>{t('minutos')}</span></span>
      </label>
      <button id="recalculate-rehearsal" type="button" disabled={busy} onClick={onRecalculate}>
        {busy ? t('Recalculando…') : t('Recalcular ensayo')}
      </button>
    </div>
    {data
      ? <div id="rehearsal-content" className="view-content">
          <section className="result-section result-section--wide">
            <h2>{t('Bloques recomendados · {title}', { title: data.title || t('Partitura sin título') })}</h2>
            <p className="result-supporting">{t('Duración total: {total} minutos · Planificado: {planned} de {total} minutos', { total: plan.total_minutes ?? 0, planned: plan.planned_minutes ?? 0 })}</p>
            {blocks.length > 0 && <RehearsalCalendar blocks={blocks} onOpenPassage={onOpenPassage} />}
            <ol className="result-list">{blocks.length === 0
              ? <li className="result-empty">{t('No hay bloques de ensayo disponibles.')}</li>
              : blocks.map((block, index) => <li key={index} className={'rehearsal-block rehearsal-block--' + block.type}>
                  <strong className="rehearsal-block-title">{rehearsalBlockTitle(block)}</strong> · {block.minutes} min
                  <div className="rehearsal-block-work">{t('Obra: {title}', { title: data.title || t('Partitura sin título') })}</div>
                  <div className="result-supporting">{rehearsalBlockDetail(block)}</div>
                </li>)}</ol>
            {omitted.length > 0 && <>
              <h3>{t('No caben en este ensayo ({count})', { count: omitted.length })}</h3>
              <ul className="result-list">{omitted.slice(0, VISIBLE_OMITTED).map((block, index) =>
                <li key={index} className="result-supporting">{omittedBlockText(block)}</li>)}</ul>
              {omitted.length > VISIBLE_OMITTED && <p className="result-supporting">{t('Y {count} más, de menor prioridad.', { count: omitted.length - VISIBLE_OMITTED })}</p>}
            </>}
          </section>
        </div>
      : <div id="rehearsal-content" className="view-content empty-workspace"><h2>{t('Aún no hay plan')}</h2><p>{t('Analiza una partitura para generar bloques de ensayo.')}</p></div>}
  </View>;
}
