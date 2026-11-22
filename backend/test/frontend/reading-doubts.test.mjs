import assert from 'node:assert/strict';
import test from 'node:test';
import { doubtsSummary, markDoubtsReviewed } from '../../../frontend/src/readingDoubts.js';

test('the doubts of the reader say how many parts are still to review', () => {
  const doubts = [{ part: 'Fl. 1', measures: 4, reviewed: false, passages: ['81-83', '95'] },
    { part: 'Tpt. 2', measures: 1, reviewed: true, passages: ['5'] }];
  assert.equal(doubtsSummary(doubts), '1 de 2 partes por revisar · 5 compases dudosos');
  assert.equal(doubtsSummary(doubts.map(doubt => ({ ...doubt, reviewed: true }))), 'Todas las partes revisadas · 5 compases dudosos');
  assert.equal(doubtsSummary([]), '');
});

test('a part is marked reviewed with its name in the body', async () => {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method, body: JSON.parse(options.body) });
    return new Response(JSON.stringify({ reading_doubts: [{ part: 'Fl. 1', measures: 1, reviewed: true, passages: ['1'] }] }), { status: 200 });
  };
  const doubts = await markDoubtsReviewed('w 1', 'Fl. 1', true);
  assert.deepEqual(calls, [{ url: '/works/w%201/reading-doubts/review', method: 'PUT', body: { part: 'Fl. 1', reviewed: true } }]);
  assert.equal(doubts[0].reviewed, true);
});
