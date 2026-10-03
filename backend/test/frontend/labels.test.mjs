import assert from 'node:assert/strict';
import test from 'node:test';
import {
  apiInstrumentName, bandIssueText, byDifficulty, displayFamilyName, displayInstrumentName,
  gradeOf, initialBandDraft, readBandProfile, rehearsalSegmentText,
} from '../../../frontend/src/labels.js';

test('instrument names keep the part number in both directions', () => {
  assert.equal(displayInstrumentName('Horn in F 2'), 'Trompa en Fa 2');
  assert.equal(apiInstrumentName('Trompa en Fa 2'), 'Horn in F 2');
  assert.equal(displayInstrumentName('Ondes Martenot'), 'Ondes Martenot');
  assert.equal(displayInstrumentName('Flute', { instrument_label_es: 'Flauta 1ª' }), 'Flauta 1ª');
  assert.equal(displayFamilyName('brass'), 'Viento metal');
  assert.equal(displayFamilyName('brass', { label_es: 'Metales' }), 'Metales');
});

test('grades are bounded to the visible 1-5 scale', () => {
  assert.equal(gradeOf({}), 1);
  assert.equal(gradeOf({ grade: 9 }), 5);
  assert.equal(gradeOf(undefined), 1);
});

test('difficulty ordering uses grade first and the index to break ties', () => {
  const ordered = byDifficulty([
    ['a', { grade: 2, score: 9 }], ['b', { grade: 4, score: 1 }], ['c', { grade: 4, score: 3 }],
  ], 'score');
  assert.deepEqual(ordered.map(([name]) => name), ['c', 'b', 'a']);
});

test('band template starts with one player per part and never goes negative', () => {
  const parts = ['Flute', 'Flute', 'Horn in F 2'];
  const draft = initialBandDraft(parts, { 'Horn in F 2': 0 });
  assert.deepEqual(draft, { Flute: '1', 'Horn in F 2': '0' });
  assert.deepEqual(readBandProfile(parts, { ...draft, Flute: '-3' }), { Flute: 0, 'Horn in F 2': 0 });
  assert.deepEqual(readBandProfile(parts, { Flute: '', 'Horn in F 2': '2' }), { Flute: 0, 'Horn in F 2': 2 });
  assert.deepEqual(readBandProfile(undefined, {}), {});
});

test('band issues and rehearsal blocks read as musician-facing Spanish', () => {
  assert.equal(bandIssueText({ instrument: 'Oboe', available: 0, required: 1 }), 'Oboe: falta en la plantilla; se necesita 1.');
  assert.equal(bandIssueText({ instrument: 'Horn in F', available: 2, required: 4 }), 'Trompa en Fa: hay 2 músicos y se necesitan 4.');
  assert.equal(rehearsalSegmentText({ instrument: 'Flute', measure_range: '1-4', minutes: 5, reason: 'Default rehearsal block.' }),
    'Flauta · compás 1-4 · 5 min · Bloque general de ensayo.');
});
