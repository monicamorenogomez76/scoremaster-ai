import React, { useRef, useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import { answerSource, askRepertoire, askWork, MAX_QUESTION, repertoireSuggestions, suggestions } from './workQuestions.js';
import { t } from './i18n.js';

// Asking the work (M6, 2026-11-20): suggested questions answered by rules, or a question in the director's words that the
// AI answers from the data of ScoreMaster it chose to read. The answers stay in this page only: nothing is kept.
export function WorkQuestions({ workId, onOpenPassage }) {
  return <section className="surface work-questions" aria-labelledby="work-questions-title">
    <h2 id="work-questions-title">{t('Preguntar a la obra')}</h2>
    <QuestionPanel id="work-question" scope="work" ask={body => askWork(workId, body)} suggestions={suggestions()}
      intro={t('La IA solo lee los datos de ScoreMaster sobre esta obra (dificultad, banda, análisis, ensayos y conciertos) y no cambia nada. Las preguntas sugeridas se responden con reglas, sin gastar cupo.')}
      example={t('Por ejemplo: «¿Qué tiene que preparar la trompeta?» o «¿Llegamos al concierto?». Hasta {count} caracteres.', { count: MAX_QUESTION })}
      busyLabel={t('Buscando la respuesta en los datos de la obra')} onOpenPassage={onOpenPassage} />
  </section>;
}

// Asking the repertoire (M6, 2026-11-20): ScoreMaster chooses the works and the AI only reads the question and explains.
export function RepertoireQuestions({ onOpenWork }) {
  return <details className="surface work-questions repertoire-questions">
    <summary><h2>{t('Preguntar al repertorio')}</h2></summary>
    <QuestionPanel id="repertoire-question" scope="repertoire" ask={askRepertoire} suggestions={repertoireSuggestions()}
      intro={t('ScoreMaster elige las obras a partir de sus análisis; la IA solo interpreta la pregunta y explica el resultado, sin cambiar nada. Las preguntas sugeridas se responden con reglas, sin gastar cupo.')}
      example={t('Por ejemplo: «¿Qué obras de grado 2 duran menos de 5 minutos?» o «¿Qué le falta a Persis?». Hasta {count} caracteres.', { count: MAX_QUESTION })}
      busyLabel={t('Buscando la respuesta en tu repertorio')} onOpenWork={onOpenWork} />
  </details>;
}

function QuestionPanel({ id, scope, ask, suggestions: offered, intro, example, busyLabel, onOpenPassage, onOpenWork }) {
  const [question, setQuestion] = useState('');
  const [asked, setAsked] = useState([]);
  const [busy, setBusy] = useState(false);
  const counter = useRef(0);
  const send = async body => {
    const key = ++counter.current;
    const text = body.question || offered.find(([name]) => name === body.suggestion)?.[1];
    setAsked(previous => [...previous, { key, text }]);
    setBusy(true);
    let outcome;
    try { outcome = { result: await ask(body) }; }
    catch (failure) { outcome = { error: failure.message }; }
    setAsked(previous => previous.map(item => item.key === key ? { ...item, ...outcome } : item));
    setBusy(false);
  };
  const submit = event => {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion('');
    send({ question: text });
  };
  return <>
    <p className="result-supporting">{intro} {t('Si la IA está activada, tu pregunta y los datos del análisis se envían a Google Gemini; no escribas datos personales.')}</p>
    <div className="work-question-suggestions" role="group" aria-label={t('Preguntas sugeridas')}>
      {offered.map(([name, label]) => <button key={name} type="button" className="secondary-action" disabled={busy}
        onClick={() => send({ suggestion: name })}>{label}</button>)}
    </div>
    <form className="work-question-form" onSubmit={submit}>
      <label htmlFor={id}>{t('Tu pregunta')}</label>
      <textarea id={id} rows={2} maxLength={MAX_QUESTION} value={question} aria-describedby={id + '-help'}
        onChange={event => setQuestion(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) submit(event); }} />
      <p id={id + '-help'} className="result-supporting">{example}</p>
      <button type="submit" className="primary-action" disabled={busy || !question.trim()}>{t('Preguntar')}</button>
    </form>
    <ActivityStatus label={busy ? busyLabel : ''} />
    {asked.length > 0 && <ol className="work-question-log" aria-live="polite">
      {asked.map(item => <li key={item.key} className="work-question-item">
        <p className="work-question-asked">{item.text}</p>
        {item.error && <p className="result-supporting" role="alert">{item.error}</p>}
        {item.result && <Answer result={item.result} scope={scope} onOpenPassage={onOpenPassage} onOpenWork={onOpenWork} />}
      </li>)}
    </ol>}
  </>;
}

function Answer({ result, scope, onOpenPassage, onOpenWork }) {
  const open = cite => {
    if (cite.kind === 'passage' && onOpenPassage) return () => onOpenPassage(cite.instrument, cite.measures);
    if (cite.kind === 'work' && onOpenWork) return () => onOpenWork(cite.work_id);
    return null;
  };
  return <div className="work-question-answer">
    <p className={'explanation-source' + (result.mode === 'llm' ? ' is-ai' : ' is-demo')}>{answerSource(result, scope)}</p>
    <p>{result.answer.answer}</p>
    {result.cites.length > 0 && <div className="passage-actions" role="group" aria-label={t('En qué se apoya')}>
      {result.cites.map(cite => open(cite)
        ? <button key={cite.id} type="button" className="passage-open" onClick={open(cite)}>{cite.text}</button>
        : <span key={cite.id} className="work-question-cite">{cite.text}</span>)}
    </div>}
  </div>;
}
