import assert from 'node:assert/strict';
import test from 'node:test';
import { setLanguage } from '../../../frontend/src/i18n.js';
import {
  correctionLabel, doubtTarget, measureNotes, noteLabel, pitchLabel, saveCorrection, undoLastCorrection,
} from '../../../frontend/src/noteCorrections.js';

test('a pitch is named as a musician reads it, in each language', () => {
  setLanguage('es');
  assert.equal(pitchLabel(['B', -1, 4]), 'si♭4');
  assert.equal(pitchLabel(['F', 1, 5]), 'fa♯5');
  assert.equal(pitchLabel(['C', 0, 5]), 'do5');
  assert.equal(pitchLabel(null), 'silencio');
  setLanguage('en');
  assert.equal(pitchLabel(['B', -1, 4]), 'B♭4');
  assert.equal(pitchLabel(null), 'rest');
  setLanguage('es');
});

test('each note of the measure says where it is and what it is', () => {
  assert.equal(noteLabel({ offset: 0, pitch: ['C', 0, 5], type: 'eighth' }, 0), '1.ª · tiempo 1 · do5 (corchea)');
  assert.equal(noteLabel({ offset: 1 / 3, pitch: null, type: 'eighth' }, 1), '2.ª · tiempo 1⅓ · silencio (corchea)');
  assert.equal(noteLabel({ offset: 1, pitch: ['E', 0, 5], type: 'quarter', chord: true }, 2), '3.ª · tiempo 2 · mi5 (negra, en acorde)');
  assert.equal(correctionLabel({ part: 'Fl. 1', measure: '82', old: null, new: ['D', 0, 5] }), 'Fl. 1 · compás 82 · silencio → re5');
});

test('a doubt opens the form on its part and the first measure of its passage', () => {
  const parts = [{ id: 'P1', name: 'Fl. 1' }, { id: 'P2', name: 'Fl. 2' }];
  assert.deepEqual(doubtTarget(parts, 'Fl. 2', '81-83'), { partId: 'P2', measure: '81' });
  assert.equal(doubtTarget(parts, 'Oboe', '5'), null);
});

test('the notes of a measure are asked for, and a correction is sent and undone', async () => {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body && JSON.parse(options.body) });
    return new Response(JSON.stringify({ corrections: [], notes: [] }), { status: 200 });
  };
  await measureNotes('w1', 'P 1', '82');
  const note = { offset: 0.5, pitch: null, staff: 2, voice: '5' };
  await saveCorrection('w1', 'P1', 3, note, ['D', 0, 5]);
  await undoLastCorrection('w1');
  assert.deepEqual(calls, [
    { url: '/works/w1/notes?part_id=P+1&measure=82', method: 'GET', body: undefined },
    { url: '/works/w1/corrections', method: 'POST',
      body: { part_id: 'P1', measure: 3, offset: 0.5, old: null, new: ['D', 0, 5], staff: 2, voice: '5' } },
    { url: '/works/w1/corrections/last', method: 'DELETE', body: undefined },
  ]);
});
