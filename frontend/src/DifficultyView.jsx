import React, { useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import { explainWork, sourceText } from './explanations.js';
import { byDifficulty, dimensionLabelsEs, displayFamilyName, displayInstrumentName, findingLabel, gradeOf, gradeScaleOf, gradeText } from './labels.js';

function Bar({ percent }) {
  return <div className="family-bar"><span style={{ width: Math.max(0, Math.min(100, percent)) + '%' }} /></div>;
}

function TreeNode({ title, grade, onSelect, children }) {
  return <button type="button" className="tree-node" onClick={onSelect}>
    <span className="tree-node-head"><span>{title}</span><strong className="tree-grade">{grade}</strong></span>
    {children}
  </button>;
}

const passageCount = count => count + (count === 1 ? ' pasaje crítico' : ' pasajes críticos');

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
      ? <p className="result-empty">No se encontraron instrumentos en la partitura.</p>
      : <div className="tree-node-list">{ordered.map(([name, entry]) =>
          <TreeNode key={name} title={displayFamilyName(name, entry)} grade={gradeText(entry, scale)} onSelect={() => { setFamily(name); setInstrument(null); }}>
            <Bar percent={Math.max(12, gradeOf(entry, scale) / scale.grades * 100)} />
            <span className="tree-node-support">
              <span>{(entry.instruments || []).length} instrumentos</span>
              <span>{passages.filter(passage => passage.family === name).length} pasajes</span>
            </span>
          </TreeNode>)}</div>;
  } else if (!instrument) {
    const ordered = byDifficulty((familyDetails.instruments || []).map(name => [name, instruments[name] || {}]), 'difficulty_score');
    content = ordered.length === 0
      ? <p className="result-empty">No hay instrumentos clasificados en esta familia.</p>
      : <div className="tree-node-list">{ordered.map(([name, entry]) =>
          <TreeNode key={name} title={displayInstrumentName(name, entry)} grade={gradeText(entry, scale)} onSelect={() => setInstrument(name)}>
            <span className="tree-node-support">{passageCount(passages.filter(passage => passage.instrument === name).length)}</span>
          </TreeNode>)}</div>;
  } else {
    const selected = passages.filter(passage => passage.instrument === instrument);
    content = <>
      <h3 className="result-metric">{displayInstrumentName(instrument, details)}</h3>
      <p className="tree-grade tree-instrument-details">{gradeText(details, scale)} · índice {details.difficulty_score ?? 0} / {scale.indexMax}</p>
      <div className="tree-dimensions">{Object.entries(details.dimensions || {}).map(([dimension, value]) =>
        <div key={dimension} className="tree-dimension">
          <span>{dimensionLabelsEs[dimension] || dimension}</span>
          <Bar percent={Number(value) / scale.indexMax * 100} />
          <strong>{Number(value).toFixed(1)}</strong>
        </div>)}</div>
      <h3 className="tree-passage-heading">Pasajes a revisar</h3>
      {selected.length === 0
        ? <p className="result-empty">No se han detectado pasajes críticos para este instrumento.</p>
        : <ul className="result-list">{selected.map(passage => <li key={passage.measure_range}>
            <strong className="tree-passage-title">Compases {passage.measure_range}</strong>
            <div className="passage-actions">
              {(passage.findings || []).map(code => <span key={code} className="pill">{findingLabel(code)}</span>)}
              <button type="button" className="passage-open" onClick={() => onOpenPassage(instrument, passage.measure_range)}>Ver pasaje</button>
            </div>
          </li>)}</ul>}
    </>;
  }

  return <div>
    <nav className="tree-nav" aria-label="Ruta de dificultad">
      <button type="button" aria-current={family ? 'false' : 'page'} onClick={() => { setFamily(null); setInstrument(null); }}>Todas las familias</button>
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
      <h2 id="work-explanation-title">¿Por qué esta dificultad?</h2>
      <button type="button" className="secondary-action" disabled={state.loading || !workId} onClick={ask}>
        {result ? 'Volver a explicar' : 'Explicar la dificultad'}</button>
    </div>
    <ActivityStatus label={state.loading ? 'Preparando la explicación a partir del análisis' : ''} />
    {state.error && <p className="result-supporting" role="alert">{state.error}</p>}
    {result && <div className="explanation-body" aria-live="polite">
      <p id="explanation-source" className={'explanation-source' + (result.mode === 'llm' ? ' is-ai' : ' is-demo')}>{sourceText(result)}</p>
      <p className="explanation-summary">{result.explanation.summary}</p>
      <ul className="explanation-factors">{result.explanation.factors.map((factor, index) => <li key={index}>
        <p>{factor.text}</p>
        {factor.passages.length > 0 && <div className="passage-actions">{factor.passages.map(code => {
          const passage = result.passages[code];
          return passage && <button key={code} type="button" className="passage-open"
            onClick={() => onOpenPassage(passage.instrument, passage.measures)}>{passage.label} · compases {passage.measures}</button>;
        })}</div>}
      </li>)}</ul>
      <p className="explanation-tip"><strong>Para estudiarla:</strong> {result.explanation.study_tip}</p>
    </div>}
  </section>;
}

// Explorer from family to instrument, below the dashboard of the analysis view.
export function DifficultyPanel({ data, onOpenPassage }) {
  return <div id="difficulty-content" className="view-content">
    <section className="result-section result-section--wide">
      <h2>Dificultad por familias e instrumentos</h2>
      <p className="result-supporting">Explora de la familia al instrumento y abre la partitura en el pasaje señalado.</p>
      <DifficultyTree difficulty={data.difficulty || {}} onOpenPassage={onOpenPassage} />
    </section>
  </div>;
}
