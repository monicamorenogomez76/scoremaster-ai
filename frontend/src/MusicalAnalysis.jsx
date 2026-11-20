import React, { useEffect, useMemo, useRef, useState } from 'react';
import { SectionSheet, WorkMap } from './AnalysisMap.jsx';
import { articulationText, cadenceText, durationText, harmonyDetailsText, keyName, listText, loadAnalysisCommentary, loadMusicalAnalysis, markText, meterText, modulationText,
  orchestrationText, periodText, phrasesText, relationText, rhythmText, tempoText, textureKindText, textureText,
  themeShapeText, themeText, workMap } from './musicalAnalysis.js';
import { sourceText } from './explanations.js';
import { t } from './i18n.js';

// One answer per work: asked once, and an answer for another work is dropped.
function useWorkRequest(workId, enabled, load) {
  const [state, setState] = useState({ status: 'idle', result: null, error: '' });
  const asked = useRef(null);
  useEffect(() => { asked.current = null; setState({ status: 'idle', result: null, error: '' }); }, [workId]);
  useEffect(() => {
    if (!enabled || !workId || asked.current === workId) return;
    asked.current = workId;
    setState({ status: 'loading', result: null, error: '' });
    load(workId)
      .then(result => { if (asked.current === workId) setState({ status: 'done', result, error: '' }); })
      .catch(failure => { if (asked.current === workId) setState({ status: 'error', result: null, error: failure.message }); });
  }, [enabled, workId, load]);
  return state;
}

// A small table of the sections for one topic; on a phone each row is a card (data-label).
function SectionTable({ caption, columns, sections }) {
  return <div className="analysis-table-wrap" tabIndex={0} role="region" aria-label={caption}>
    <table className="analysis-table">
      <caption className="visually-hidden">{caption}</caption>
      <thead><tr><th scope="col">{t('Sección')}</th>{columns.map(([title]) => <th key={title} scope="col">{title}</th>)}</tr></thead>
      <tbody>{sections.map(section => <tr key={section.id}>
        <th scope="row">{section.label}<span className="result-supporting"> · {t('cc. {first}–{last}', { first: section.first, last: section.last })}</span></th>
        {columns.map(([title, value]) => <td key={title} data-label={title}>{value(section) || '—'}</td>)}
      </tr>)}</tbody>
    </table>
  </div>;
}

// A topic of the analysis: ScoreMaster's facts and, once asked, the commentary written about them.
function Topic({ id, title, commentary, opinion, children }) {
  return <section className="analysis-topic" aria-labelledby={id}>
    <h3 id={id}>{title}</h3>
    {children}
    {commentary && <div className={'analysis-commentary' + (opinion ? ' analysis-commentary--opinion' : '')}>
      <p className="analysis-commentary-label">{opinion ? t('Opinión del comentario') : t('Comentario')}</p>
      <p>{commentary.text}</p>
    </div>}
  </section>;
}

// The topics of the commentary of the whole work, in the order of a conservatory analysis; the interpretation goes apart.
const COMMENTARY_TOPICS = () => [['form', t('Forma')], ['themes', t('Temas')], ['harmony', t('Armonía')],
  ['texture', t('Textura y orquestación')], ['rhythm', t('Ritmo')], ['dynamics', t('Dinámicas, articulación y clímax')]];

// The analysis of the work as in a conservatory (2026-11-18), topic by topic: the facts ScoreMaster calculates and,
// when the director asks for it, the commentary the AI (or the demo) writes about them (2026-11-19).
export function MusicalAnalysis({ workId, visible, fromPdf }) {
  const analysis = useWorkRequest(workId, visible, loadMusicalAnalysis);
  const [asking, setAsking] = useState(false);
  useEffect(() => setAsking(false), [workId]);
  const commentary = useWorkRequest(workId, asking, loadAnalysisCommentary);
  const { result } = analysis;
  const comment = commentary.result?.commentary;
  const labelOf = id => result.sections.find(section => section.id === id)?.label || id;
  // The map of the work and its chosen section (2026-11-20): the first one until the director picks another.
  const map = useMemo(() => (result?.sections.length ? workMap(result) : null), [result]);
  const [chosen, setChosen] = useState(null);
  useEffect(() => setChosen(null), [workId]);
  const section = map && (map.sections.find(item => item.id === chosen) || map.sections[0]);

  return <section id="musical-analysis" className="musical-analysis" aria-labelledby="musical-analysis-title" aria-busy={analysis.status === 'loading'}>
    <h2 id="musical-analysis-title">{t('Análisis musical')}</h2>
    <p className="result-supporting">{t('Calculado por ScoreMaster a partir de la partitura: forma, temas, tonalidades, cadencias, textura, ritmo, orquestación y quién toca qué. La melodía, las frases y los temas son una aproximación.')}</p>
    {fromPdf && <p className="pdf-provisional" role="note">{t('Leída de PDF: el análisis es provisional, porque la lectura puede tener errores.')}</p>}
    {analysis.status === 'loading' && <p className="result-supporting">{t('Analizando la obra…')}</p>}
    {analysis.error && <p className="result-supporting" role="alert">{analysis.error}</p>}
    {result && !result.sections.length && <p className="result-supporting">{t('La obra no tiene notas que analizar.')}</p>}
    {result && result.sections.length > 0 && <>
      <div className="analysis-commentary-bar" aria-live="polite">
        <button type="button" className="secondary-action" disabled={asking} onClick={() => setAsking(true)}>
          {commentary.status === 'loading' ? t('Redactando el comentario…') : t('Redactar el comentario')}</button>
        {commentary.error && <p className="result-supporting" role="alert">{commentary.error}</p>}
        {commentary.result && <p className={'explanation-source' + (commentary.result.mode === 'llm' ? ' is-ai' : ' is-demo')}>
          {sourceText(commentary.result)}</p>}
      </div>

      <Topic id="analysis-general" title={t('Datos generales')} commentary={comment && { text: comment.summary }}>
        <dl className="analysis-summary">
          <div><dt>{t('Tonalidad principal')}</dt><dd>{keyName(result.main_key)}</dd></div>
          <div><dt>{t('Forma')}</dt><dd>{result.form}</dd></div>
          <div><dt>{t('Duración')}</dt><dd>{durationText(result.general.seconds)}{result.general.assumed_tempo &&
            <span className="result-supporting"> · {t('sin tempo escrito')}</span>}</dd></div>
          <div><dt>{t('Compases')}</dt><dd>{result.general.measures}</dd></div>
          <div><dt>{t('Partes')}</dt><dd>{result.general.parts}</dd></div>
        </dl>
        <dl className="analysis-facts">
          {result.general.tempos.length > 0 && <div><dt>{t('Tempos')}</dt><dd>{listText(result.general.tempos.map(tempoText), 8)}</dd></div>}
          {result.general.meters.length > 0 && <div><dt>{t('Compás')}</dt><dd>{listText(result.general.meters.map(item =>
            t('{meter} (c. {measure})', item)), 8)}</dd></div>}
        </dl>
      </Topic>

      <WorkMap map={map} selected={section.id} onSelect={setChosen} />
      <SectionSheet analysis={result} section={section} onSelect={setChosen}
        comment={comment?.by_section.find(item => item.section === section.id)?.text} />

      {comment && <section className="analysis-topic" aria-labelledby="analysis-commentary-title">
        <h3 id="analysis-commentary-title">{t('Comentario de la obra')}</h3>
        {COMMENTARY_TOPICS().map(([name, title]) => <div key={name} className="analysis-commentary">
          <p className="analysis-commentary-label">{title}</p><p>{comment[name].text}</p></div>)}
      </section>}
      {comment && <Topic id="analysis-interpretation" title={t('Interpretación')} commentary={comment.interpretation} opinion />}

      <details className="analysis-tables">
        <summary>{t('Ver los datos en tabla (forma, temas, armonía, textura, ritmo y dinámicas)')}</summary>
      <Topic id="analysis-form" title={t('Forma')}>
        <SectionTable caption={t('Forma por secciones')} sections={result.sections} columns={[
          [t('Material'), section => section.like ? t('vuelve el material de {section}', { section: labelOf(section.like) }) : t('nuevo')],
          [t('Frases'), section => phrasesText(section) + (section.periods.length ? ' · ' + section.periods.map(periodText).join('; ') : '')],
          [t('Marcas'), section => [...section.marks, ...section.marks_at_end].map(markText).join(', ')],
        ]} />
      </Topic>

      <Topic id="analysis-themes" title={t('Temas')}>
        {result.themes.length > 0
          ? <ul className="analysis-themes">{result.themes.map(theme => <li key={theme.id}>
            <strong>{theme.id}</strong>{' '}{t('sección {section}, cc. {first}–{last}', { section: labelOf(theme.section), first: theme.first, last: theme.last })}
            {theme.part && <span className="result-supporting"> · {theme.part}</span>}
            {theme.contour && <span className="result-supporting"> · {themeShapeText(theme)}</span>}</li>)}</ul>
          : <p className="result-supporting">{t('No se distinguen temas claros.')}</p>}
        <SectionTable caption={t('Temas por secciones')} sections={result.sections} columns={[[t('Tema'), themeText]]} />
      </Topic>

      <Topic id="analysis-harmony" title={t('Armonía')}>
        <SectionTable caption={t('Armonía por secciones')} sections={result.sections} columns={[
          [t('Tonalidad'), section => [keyName(section.key) + ' · ' + relationText(section.relation),
            ...section.modulations.map(modulationText)].join('; ')],
          [t('Ritmo armónico y colores'), harmonyDetailsText],
          [t('Cadencias'), section => result.cadences.filter(cadence => cadence.section === section.id)
            .map(cadence => t('{kind} (c. {measure})', { kind: cadenceText(cadence.kind), measure: cadence.measure })).join(', ')],
        ]} />
      </Topic>

      <Topic id="analysis-texture" title={t('Textura y orquestación')}>
        <SectionTable caption={t('Textura y orquestación por secciones')} sections={result.sections} columns={[
          [t('Textura'), section => [textureKindText(section.texture_kind), textureText(section.texture)].filter(Boolean).join(', ')
            + ' · ' + t('{count} partes', { count: section.playing.length })],
          [t('Melodía'), section => section.melody && section.melody + (section.doubled_by.length
            ? ' ' + t('(doblada por {parts})', { parts: section.doubled_by.join(', ') }) : '')],
          [t('Orquestación'), orchestrationText],
        ]} />
      </Topic>

      <Topic id="analysis-rhythm" title={t('Ritmo')}>
        <SectionTable caption={t('Ritmo por secciones')} sections={result.sections} columns={[
          [t('Tempo'), section => [section.tempo ? '♩ = ' + section.tempo : '', section.meter].filter(Boolean).join(' · ')],
          [t('Ritmo y contrapunto'), rhythmText],
          [t('Métrica'), meterText],
        ]} />
      </Topic>

      <Topic id="analysis-dynamics" title={t('Dinámicas, articulación y clímax')}>
        {result.climax && <p>{t('Clímax: c. {measure}, sección {section}, {dynamic}, {count} partes', {
          measure: result.climax.measure, dynamic: result.climax.dynamic, count: result.climax.playing,
          section: labelOf(result.climax.section) })}</p>}
        <SectionTable caption={t('Dinámicas y articulación por secciones')} sections={result.sections} columns={[
          [t('Dinámicas'), section => section.dynamics.join(' ')], [t('Articulación'), articulationText]]} />
      </Topic>

      </details>
    </>}
  </section>;
}
