import assert from 'node:assert/strict';
import test from 'node:test';
import { answerSource, askWork, MAX_QUESTION, suggestions } from '../../../frontend/src/workQuestions.js';

// Asking the work (M6, 2026-11-20): the suggested questions are answered by rules and the free ones by the AI when there
// is one; who answered, and from which data, is always said.
test('a question goes to the server as its words or as a suggestion', async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options.method, JSON.parse(options.body), options.headers.get('Content-Type')]);
    return new Response(JSON.stringify({ mode: 'demo' }), { status: 200 });
  };
  await askWork('w 1', { question: '¿Me falta alguien?' });
  await askWork('w 1', { suggestion: 'band' });
  assert.deepEqual(calls, [
    ['/works/w%201/questions', 'POST', { question: '¿Me falta alguien?' }, 'application/json'],
    ['/works/w%201/questions', 'POST', { suggestion: 'band' }, 'application/json']]);
  assert.equal(MAX_QUESTION, 300);
});

test('the suggestions are the ones the server answers by rules', () => {
  assert.deepEqual(suggestions().map(([id]) => id), ['grade', 'passages', 'band', 'form', 'schedule']);
  assert.ok(suggestions().every(([, label]) => label.endsWith('?')));
});

test('who answered is always said, with the data the AI chose to read', () => {
  assert.equal(answerSource({ mode: 'llm', provider: 'gemini', model: 'gemini-3.5-flash-lite', tools: ['band', 'schedule'] }),
    'Respondida con IA (gemini · gemini-3.5-flash-lite) a partir de estos datos de ScoreMaster: banda y ensayos y conciertos. Puede contener imprecisiones: contrástala con la partitura.');
  assert.equal(answerSource({ mode: 'llm', provider: 'gemini', model: 'm', tools: [] }),
    'Respondida con IA (gemini · m) sin leer datos de la obra.');
  assert.equal(answerSource({ mode: 'demo', fallback_reason: null, tools: ['difficulty'] }),
    'Respondida con reglas a partir de estos datos de ScoreMaster, sin IA: dificultad.');
  assert.equal(answerSource({ mode: 'demo', fallback_reason: null, tools: [] }), 'Respondida con reglas, sin IA.');
  assert.match(answerSource({ mode: 'demo', fallback_reason: 'rate_limit', tools: ['band'] }),
    /^La IA ha alcanzado su límite de uso: se responde con reglas, sin IA/);
});
