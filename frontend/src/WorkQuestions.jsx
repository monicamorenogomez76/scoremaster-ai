import React, { useRef, useState } from 'react';
import { ActivityStatus } from './ActivityStatus.jsx';
import { answerSource, askWork, MAX_QUESTION, suggestions } from './workQuestions.js';
import { t } from './i18n.js';

// Asking the work (M6, 2026-11-20): suggested questions answered by rules, or a question in the director's words that the
// AI answers from the data of ScoreMaster it chose to read. The answers stay in this page only: nothing is kept.
export function WorkQuestions({ workId, onOpenPassage }) {
  const [question, setQuestion] = useState('');
  const [asked, setAsked] = useState([]);
  const [busy, setBusy] = useState(false);
  const counter = useRef(0);
  const ask = async body => {
    const id = ++counter.current;
    const text = body.question || suggestions().find(([name]) => name === body.suggestion)?.[1];
    setAsked(previous => [...previous, { id, text }]);
    setBusy(true);
    let outcome;
    try { outcome = { result: await askWork(workId, body) }; }
    catch (failure) { outcome = { error: failure.message }; }
    setAsked(previous => previous.map(item => item.id === id ? { ...item, ...outcome } : item));
    setBusy(false);
  };
  const submit = event => {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion('');
    ask({ question: text });
  };
  return <section className="surface work-questions" aria-labelledby="work-questions-title">
    <h2 id="work-questions-title">{t('Preguntar a la obra')}</h2>
    <p className="result-supporting">{t('La IA solo lee los datos de ScoreMaster sobre esta obra (dificultad, banda, análisis, ensayos y conciertos) y no cambia nada. Las preguntas sugeridas se responden con reglas, sin gastar cupo.')}</p>
    <div className="work-question-suggestions" role="group" aria-label={t('Preguntas sugeridas')}>
      {suggestions().map(([name, label]) => <button key={name} type="button" className="secondary-action" disabled={busy}
        onClick={() => ask({ suggestion: name })}>{label}</button>)}
    </div>
    <form className="work-question-form" onSubmit={submit}>
      <label htmlFor="work-question">{t('Tu pregunta')}</label>
      <textarea id="work-question" rows={2} maxLength={MAX_QUESTION} value={question} aria-describedby="work-question-help"
        onChange={event => setQuestion(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) submit(event); }} />
      <p id="work-question-help" className="result-supporting">{t('Por ejemplo: «¿Qué tiene que preparar la trompeta?» o «¿Llegamos al concierto?». Hasta {count} caracteres.', { count: MAX_QUESTION })}</p>
      <button type="submit" className="primary-action" disabled={busy || !question.trim()}>{t('Preguntar')}</button>
    </form>
    <ActivityStatus label={busy ? t('Buscando la respuesta en los datos de la obra') : ''} />
    {asked.length > 0 && <ol className="work-question-log" aria-live="polite">
      {asked.map(item => <li key={item.id} className="work-question-item">
        <p className="work-question-asked">{item.text}</p>
        {item.error && <p className="result-supporting" role="alert">{item.error}</p>}
        {item.result && <WorkAnswer result={item.result} onOpenPassage={onOpenPassage} />}
      </li>)}
    </ol>}
  </section>;
}

function WorkAnswer({ result, onOpenPassage }) {
  return <div className="work-question-answer">
    <p className={'explanation-source' + (result.mode === 'llm' ? ' is-ai' : ' is-demo')}>{answerSource(result)}</p>
    <p>{result.answer.answer}</p>
    {result.cites.length > 0 && <div className="passage-actions" aria-label={t('En qué se apoya')}>
      {result.cites.map(cite => cite.kind === 'passage'
        ? <button key={cite.id} type="button" className="passage-open"
          onClick={() => onOpenPassage(cite.instrument, cite.measures)}>{cite.text}</button>
        : <span key={cite.id} className="work-question-cite">{cite.text}</span>)}
    </div>}
  </div>;
}
