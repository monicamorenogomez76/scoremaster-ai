import React, { useState } from 'react';
import { View } from './View.jsx';
import { byDifficulty, dimensionLabelsEs, displayFamilyName, displayInstrumentName, findingLabel, gradeOf } from './labels.js';

function Bar({ percent }) {
  return <div className="family-bar"><span style={{ width: Math.max(0, Math.min(100, percent)) + '%' }} /></div>;
}

function TreeNode({ title, grade, onSelect, children }) {
  return <button type="button" className="tree-node" onClick={onSelect}>
    <span className="tree-node-head"><span>{title}</span><strong className="tree-grade">Grado {grade}</strong></span>
    {children}
  </button>;
}

const passageCount = count => count + (count === 1 ? ' pasaje crítico' : ' pasajes críticos');

function DifficultyTree({ difficulty, onOpenPassage }) {
  const [family, setFamily] = useState(null);
  const [instrument, setInstrument] = useState(null);
  const families = difficulty.by_family || {}, instruments = difficulty.by_instrument || {};
  const passages = difficulty.critical_passages || [];
  const familyDetails = families[family] || {};
  const details = instruments[instrument] || {};

  let content;
  if (!family) {
    const ordered = byDifficulty(Object.entries(families), 'score');
    content = ordered.length === 0
      ? <p className="result-empty">No se encontraron instrumentos en la partitura.</p>
      : <div className="tree-node-list">{ordered.map(([name, entry]) =>
          <TreeNode key={name} title={displayFamilyName(name, entry)} grade={gradeOf(entry)} onSelect={() => { setFamily(name); setInstrument(null); }}>
            <Bar percent={Math.max(12, gradeOf(entry) * 20)} />
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
          <TreeNode key={name} title={displayInstrumentName(name, entry)} grade={gradeOf(entry)} onSelect={() => setInstrument(name)}>
            <span className="tree-node-support">{passageCount(passages.filter(passage => passage.instrument === name).length)}</span>
          </TreeNode>)}</div>;
  } else {
    const selected = passages.filter(passage => passage.instrument === instrument);
    content = <>
      <h3 className="result-metric">{displayInstrumentName(instrument, details)}</h3>
      <p className="tree-grade tree-instrument-details">Grado {gradeOf(details)} · índice {details.difficulty_score ?? 0} / 5</p>
      <div className="tree-dimensions">{Object.entries(details.dimensions || {}).map(([dimension, value]) =>
        <div key={dimension} className="tree-dimension">
          <span>{dimensionLabelsEs[dimension] || dimension}</span>
          <Bar percent={Number(value) * 20} />
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

export function DifficultyView({ active, data, onOpenPassage }) {
  return <View name="difficulty" active={active} eyebrow="ScoreLint" title="Dificultad y pasajes"
    description="Explora de la familia al instrumento y abre la partitura en el pasaje señalado.">
    {data
      ? <div id="difficulty-content" className="view-content">
          <section className="result-section result-section--wide">
            <h2>Dificultad por familias e instrumentos</h2>
            <DifficultyTree difficulty={data.difficulty || {}} onOpenPassage={onOpenPassage} />
          </section>
        </div>
      : <div id="difficulty-content" className="view-content empty-workspace"><h2>Aún no hay análisis</h2><p>Analiza una partitura para consultar la dificultad y abrir sus pasajes en notación.</p></div>}
  </View>;
}
