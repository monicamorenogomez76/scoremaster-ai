import assert from 'node:assert/strict';
import test from 'node:test';
import { costText, latencyText, loadAiUsage, outcomeLabel, purposeLabel, usageRows } from '../../../frontend/src/aiUsage.js';
import { setLanguage } from '../../../frontend/src/i18n.js';

const SUMMARY = {
  days: 30, priced: true, cache_hits: 4, rejected: { invalid: 1 }, failures: { timeout: 2, rate_limit: 1 },
  purposes: [{ purpose: 'difficulty', calls: 9 }, { purpose: 'passage_review', calls: 3 }],
  models: [{ model: 'gemini-3.8-flash', calls: 12, failed: 3, input_tokens: 15000, output_tokens: 3200,
    latency_ms: { average: 8200, p95: 31000 }, estimated_cost: 0.0125 }],
};

test('the panel asks the server for the usage of the last days', async () => {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => { calls.push(url); return new Response(JSON.stringify(SUMMARY), { status: 200 }); };
  assert.equal((await loadAiUsage(7)).days, 30);
  assert.equal(calls[0], '/admin/ai-usage?days=7');
});

test('each model is a row with its calls, failures, tokens, latency and cost', () => {
  setLanguage('es');
  assert.deepEqual(usageRows(SUMMARY), [{ model: 'gemini-3.8-flash', calls: '12', failed: '3', tokens: '15.000 / 3200',
    latency: '8,2 s · p95 31 s', cost: '0,0125 $' }]);
});

test('latency and cost read well, also when they are missing', () => {
  setLanguage('es');
  assert.equal(latencyText({ average: null, p95: null }), '—');
  assert.equal(latencyText({ average: 450, p95: 900 }), '0,5 s · p95 0,9 s');
  assert.equal(costText(null, false), 'Sin precio');
  assert.equal(costText(0, true), '0 $');
  setLanguage('en');
  assert.equal(costText(0.0125, true), '$0.0125');
  assert.equal(latencyText({ average: 8200, p95: 31000 }), '8.2 s · p95 31 s');
  setLanguage('es');
});

test('purposes and outcomes are named in the language of the interface', () => {
  setLanguage('es');
  assert.deepEqual(['difficulty', 'rehearsal', 'passage_review', 'instrument_proposal', 'other'].map(purposeLabel),
    ['Explicación de la dificultad', 'Explicación del ensayo', 'Valoración con IA (método B)', 'Propuesta de instrumentos', 'other']);
  assert.deepEqual(['timeout', 'rate_limit', 'error', 'invalid'].map(outcomeLabel),
    ['Sin respuesta a tiempo', 'Límite de uso alcanzado', 'Error del proveedor', 'Respuesta descartada por la validación']);
  setLanguage('en');
  assert.equal(purposeLabel('difficulty'), 'Difficulty explanation');
  setLanguage('es');
});
