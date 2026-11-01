import assert from 'node:assert/strict';
import test from 'node:test';
import { setLanguage } from '../../../frontend/src/i18n.js';
import { loadSubstitutes, needsSubstitutes, transpositionText } from '../../../frontend/src/substitutes.js';

// Substitutes for the instruments the band lacks (2026-10-31): ScoreLint's candidates, chosen by the AI or the demo.
test('the substitutes of a work are asked for its parts without a musician', async () => {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET' });
    return new Response(JSON.stringify({ mode: 'demo', summary: 'Una parte sin músico.', substitutes: [] }), { status: 200 });
  };
  assert.equal((await loadSubstitutes('w 1')).summary, 'Una parte sin músico.');
  assert.deepEqual(calls, [{ url: '/works/w%201/substitutes', method: 'GET' }]);
  assert.equal(needsSubstitutes({ issues: [{ key: 'oboe' }] }), true);
  assert.equal(needsSubstitutes({ issues: [{ key: 'percussion' }] }), false, 'the percussionists already share their parts');
  assert.equal(needsSubstitutes({}), false);
});

test('how much a substitute transposes the part, as an interval', () => {
  setLanguage('es');
  assert.deepEqual([0, 2, -2, 9, 14, -12, null].map(transpositionText), [
    'Lee la parte tal como está escrita.', 'Transporta la parte una 2ª mayor arriba.', 'Transporta la parte una 2ª mayor abajo.',
    'Transporta la parte una 6ª mayor arriba.', 'Transporta la parte una 2ª mayor y una octava arriba.',
    'Transporta la parte una octava abajo.', '']);
  setLanguage('en');
  assert.equal(transpositionText(2), 'Transpose the part a major 2nd up.');
  setLanguage('es');
});
