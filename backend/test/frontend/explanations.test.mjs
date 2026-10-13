import assert from 'node:assert/strict';
import test from 'node:test';
import { explainRehearsal, explainWork, sourceText } from '../../../frontend/src/explanations.js';

// The demo is never presented as AI (original brief), and a fallback says why the AI did not write it.
test('who wrote the explanation is always said', () => {
  assert.equal(sourceText({ mode: 'demo', fallback_reason: null }),
    'Modo demo · explicación redactada con reglas a partir del análisis de ScoreLint, sin IA.');
  assert.equal(sourceText({ mode: 'llm', provider: 'gemini', model: 'gemini-2.5-flash' }),
    'Redactada con IA (gemini · gemini-2.5-flash) solo a partir del análisis de ScoreLint. Puede contener imprecisiones: contrástala con la partitura.');
  assert.equal(sourceText({ mode: 'demo', fallback_reason: 'timeout' }),
    'La IA no respondió a tiempo: se muestra el modo demo, redactado con reglas, sin IA.');
  assert.match(sourceText({ mode: 'demo', fallback_reason: 'invalid' }), /^La IA dio una respuesta que no coincidía con el análisis/);
  assert.match(sourceText({ mode: 'demo', fallback_reason: 'rate_limit' }), /^La IA ha alcanzado su límite de uso/);
  assert.match(sourceText({ mode: 'demo', fallback_reason: 'error' }), /^La IA no está disponible/);
});

test('the explanation of a work is asked to the server', async () => {
  const calls = [];
  globalThis.fetch = async url => { calls.push(url); return new Response(JSON.stringify({ mode: 'demo' }), { status: 200 }); };
  assert.equal((await explainWork('w 1')).mode, 'demo');
  assert.deepEqual(calls, ['/works/w%201/explanation']);
});

test('the explanation of a rehearsal is asked to the server', async () => {
  const calls = [];
  globalThis.fetch = async url => { calls.push(url); return new Response(JSON.stringify({ mode: 'demo' }), { status: 200 }); };
  assert.equal((await explainRehearsal('r1')).mode, 'demo');
  assert.deepEqual(calls, ['/rehearsals/r1/explanation']);
});

test('an answer reused from the cache says it spends no quota', () => {
  assert.equal(sourceText({ mode: 'llm', provider: 'gemini', model: 'gemini-3.8-flash', cached: true }),
    'Redactada con IA (gemini · gemini-3.8-flash) solo a partir del análisis de ScoreLint. Puede contener imprecisiones: '
    + 'contrástala con la partitura. Respuesta guardada: no gasta cupo.');
});
