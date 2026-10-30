import React, { useEffect, useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import { explainWork, sourceText } from './explanations.js';
import { addExternalGrade, comparisonText, deleteExternalGrade, listExternalGrades, scales, valueOptions } from './externalGrades.js';
import { byDifficulty, dimensionLabelsEs, displayFamilyName, displayInstrumentName, findingLabel, gradeOf, gradeScaleOf, gradeText } from './labels.js';
import { t } from './i18n.js';

function Bar({ percent }) {
  return <div className="family-bar"><span style={{ width: Math.max(0, Math.min(100, percent)) + '%' }} /></div>;
}

function TreeNode({ title, grade, onSelect, children }) {
  return <button type="button" className="tree-node" onClick={onSelect}>
    <span className="tree-node-head"><span>{title}</span><strong className="tree-grade">{grade}</strong></span>
    {children}
  </button>;
}

const passageCount = count => t(count === 1 ? '{count} pasaje crítico' : '{count} pasajes críticos', { count });

function DifficultyTree({ difficulty, onOpenPassage }) {
  const [family, setFamily] = useState(null);
  const [instrument, setInstrument] = useState(null);
  const families = difficulty.by_family || {}, instruments = difficulty.by_instrument || {};
  const passages = difficulty.critical_passages || [];
  const scale = gradeScaleOf(difficulty);
  const familyDetails = families[family] || {};
  const details = instruments[instrument] || {};

  let content;
  if (!family) {
    const ordered = byDifficulty(Object.entries(families), 'score');
    content = ordered.length === 0
      ? <p className="result-empty">{t('No se encontraron instrumentos en la partitura.')}</p>
      : <div className="tree-node-list">{ordered.map(([name, entry]) =>
          <TreeNode key={name} title={displayFamilyName(name, entry)} grade={gradeText(entry, scale)} onSelect={() => { setFamily(name); setInstrument(null); }}>
            <Bar percent={Math.max(12, gradeOf(entry, scale) / scale.grades * 100)} />
            <span className="tree-node-support">
              <span>{t('{count} instrumentos', { count: (entry.instruments || []).length })}</span>
              <span>{t('{count} pasajes', { count: passages.filter(passage => passage.family === name).length })}</span>
            </span>
          </TreeNode>)}</div>;
  } else if (!instrument) {
    const ordered = byDifficulty((familyDetails.instruments || []).map(name => [name, instruments[name] || {}]), 'difficulty_score');
    content = ordered.length === 0
      ? <p className="result-empty">{t('No hay instrumentos clasificados en esta familia.')}</p>
      : <div className="tree-node-list">{ordered.map(([name, entry]) =>
          <TreeNode key={name} title={displayInstrumentName(name, entry)} grade={gradeText(entry, scale)} onSelect={() => setInstrument(name)}>
            <span className="tree-node-support">{passageCount(passages.filter(passage => passage.instrument === name).length)}</span>
          </TreeNode>)}</div>;
  } else {
    const selected = passages.filter(passage => passage.instrument === instrument);
    content = <>
      <h3 className="result-metric">{displayInstrumentName(instrument, details)}</h3>
      <p className="tree-grade tree-instrument-details">{gradeText(details, scale)} · {t('índice {score} / {max}', { score: details.difficulty_score ?? 0, max: scale.indexMax })}</p>
      <div className="tree-dimensions">{Object.entries(details.dimensions || {}).map(([dimension, value]) =>
        <div key={dimension} className="tree-dimension">
          <span>{dimensionLabelsEs[dimension] ? t(dimensionLabelsEs[dimension]) : dimension}</span>
          <Bar percent={Number(value) / scale.indexMax * 100} />
          <strong>{Number(value).toFixed(1)}</strong>
        </div>)}</div>
      <h3 className="tree-passage-heading">{t('Pasajes a revisar')}</h3>
      {selected.length === 0
        ? <p className="result-empty">{t('No se han detectado pasajes críticos para este instrumento.')}</p>
        : <ul className="result-list">{selected.map(passage => <li key={passage.measure_range}>
            <strong className="tree-passage-title">{t('Compases {range}', { range: passage.measure_range })}</strong>
            <div className="passage-actions">
              {(passage.findings || []).map(code => <span key={code} className="pill">{findingLabel(code)}</span>)}
              <button type="button" className="passage-open" onClick={() => onOpenPassage(instrument, passage.measure_range)}>{t('Ver pasaje')}</button>
            </div>
          </li>)}</ul>}
    </>;
  }

  return <div>
    <nav className="tree-nav" aria-label={t('Ruta de dificultad')}>
      <button type="button" aria-current={family ? 'false' : 'page'} onClick={() => { setFamily(null); setInstrument(null); }}>{t('Todas las familias')}</button>
      {family && <>›<button type="button" aria-current={instrument ? 'false' : 'page'} onClick={() => setInstrument(null)}>{displayFamilyName(family, familyDetails)}</button></>}
      {instrument && <span>› {displayInstrumentName(instrument, details)}</span>}
    </nav>
    <div>{content}</div>
  </div>;
}

// Why the work has its difficulty (step 20): written only from its analysis, by AI or by the demo,
// and always saying which; each cited passage opens in the score.
export function WorkExplanation({ workId, onOpenPassage }) {
  const [state, setState] = useState({ loading: false, result: null, error: '' });
  const ask = async () => {
    setState({ loading: true, result: null, error: '' });
    try { setState({ loading: false, result: await explainWork(workId), error: '' }); }
    catch (failure) { setState({ loading: false, result: null, error: failure.message }); }
  };
  const { result } = state;
  return <section id="work-explanation" className="surface work-explanation" aria-labelledby="work-explanation-title">
    <div className="summary-card-heading">
      <h2 id="work-explanation-title">{t('¿Por qué esta dificultad?')}</h2>
      <button type="button" className="secondary-action" disabled={state.loading || !workId} onClick={ask}>
        {result ? t('Volver a explicar') : t('Explicar la dificultad')}</button>
    </div>
    <ActivityStatus label={state.loading ? t('Preparando la explicación a partir del análisis') : ''} />
    {state.error && <p className="result-supporting" role="alert">{state.error}</p>}
    {result && <div className="explanation-body" aria-live="polite">
      <p id="explanation-source" className={'explanation-source' + (result.mode === 'llm' ? ' is-ai' : ' is-demo')}>{sourceText(result)}</p>
      <p className="explanation-summary">{result.explanation.summary}</p>
      <ul className="explanation-factors">{result.explanation.factors.map((factor, index) => <li key={index}>
        <p>{factor.text}</p>
        {factor.passages.length > 0 && <div className="passage-actions">{factor.passages.map(code => {
          const passage = result.passages[code];
          return passage && <button key={code} type="button" className="passage-open"
            onClick={() => onOpenPassage(passage.instrument, passage.measures)}>{passage.label} · {t('compases {range}', { range: passage.measures })}</button>;
        })}</div>}
      </li>)}</ul>
      <p className="explanation-tip"><strong>{t('Para estudiarla:')}</strong> {result.explanation.study_tip}</p>
    </div>}
  </section>;
}

// Grades publishers give the work (PR 5 of the closing plan): typed in from the publisher's page, never
// looked up nor asked to the AI, and compared with ScoreLint's grade.
const DEFAULT_VALUE = { grade: '3', pepper: 'ME' };

export function PublishedGrades({ workId, grade }) {
  const [grades, setGrades] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState({ scale: 'grade', value: DEFAULT_VALUE.grade, source: '', url: '', consulted_on: '' });
  useEffect(() => {
    let current = true;
    setGrades(null); setError('');
    listExternalGrades(workId).then(found => { if (current) setGrades(found); })
      .catch(failure => { if (current) { setGrades([]); setError(failure.message); } });
    return () => { current = false; };
  }, [workId]);
  const change = field => event => setDraft(previous => ({ ...previous, [field]: event.target.value }));
  const save = async event => {
    event.preventDefault();
    setSaving(true); setError('');
    try {
      const saved = await addExternalGrade(workId, draft);
      setGrades(previous => [...(previous || []), saved]);
      setDraft(previous => ({ ...previous, source: '', url: '', consulted_on: '' }));
    } catch (failure) { setError(failure.message); } finally { setSaving(false); }
  };
  const remove = async item => {
    setError('');
    try { await deleteExternalGrade(workId, item.id); setGrades(previous => previous.filter(other => other.id !== item.id)); }
    catch (failure) { setError(failure.message); }
  };
  return <section id="published-grades" className="surface published-grades" aria-labelledby="published-grades-title">
    <header className="summary-card-heading"><h2 id="published-grades-title">{t('Grado publicado')}</h2></header>
    <p className="result-supporting" aria-live="polite">{grades === null ? t('Cargando los grados publicados…') : comparisonText(grade, grades)}</p>
    {grades?.length > 0 && <ul className="published-grade-list">{grades.map(item => <li key={item.id}>
      <span><strong>{item.label}</strong>{' · '}
        {item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer">{item.source}</a> : item.source}
        {item.consulted_on && <span className="table-supporting">{t('Consultado el {date}', { date: item.consulted_on })}</span>}</span>
      <button type="button" className="link-action" aria-label={t('Borrar {label} de {source}', { label: item.label, source: item.source })} onClick={() => remove(item)}>{t('Borrar')}</button>
    </li>)}</ul>}
    <form className="published-grade-form" onSubmit={save}>
      <label htmlFor="published-scale">{t('Escala')}
        <select id="published-scale" value={draft.scale}
          onChange={event => setDraft(previous => ({ ...previous, scale: event.target.value, value: DEFAULT_VALUE[event.target.value] }))}>
          {scales.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
      <label htmlFor="published-value">{t('Grado')}
        <select id="published-value" value={draft.value} onChange={change('value')}>
          {valueOptions(draft.scale).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label htmlFor="published-source">{t('Editorial o catálogo')}
        <input id="published-source" type="text" required maxLength={200} value={draft.source} onChange={change('source')} /></label>
      <label htmlFor="published-url">{t('Enlace (opcional)')}
        <input id="published-url" type="url" maxLength={500} placeholder="https://" value={draft.url} onChange={change('url')} /></label>
      <label htmlFor="published-date">{t('Consultado el (opcional)')}
        <input id="published-date" type="date" value={draft.consulted_on} onChange={change('consulted_on')} /></label>
      <button type="submit" className="secondary-action" disabled={saving || !draft.source.trim()}>{saving ? t('Guardando…') : t('Añadir grado')}</button>
    </form>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    <p className="table-supporting">{t('Se escribe a mano desde la ficha de la editorial: la aplicación no lo busca ni se lo pide a la IA.')}</p>
  </section>;
}

// Explorer from family to instrument, below the dashboard of the analysis view.
export function DifficultyPanel({ data, onOpenPassage }) {
  return <div id="difficulty-content" className="view-content">
    <section className="result-section result-section--wide">
      <h2>{t('Dificultad por familias e instrumentos')}</h2>
      <p className="result-supporting">{t('Explora de la familia al instrumento y abre la partitura en el pasaje señalado.')}</p>
      <DifficultyTree difficulty={data.difficulty || {}} onOpenPassage={onOpenPassage} />
    </section>
  </div>;
}
