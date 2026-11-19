import assert from 'node:assert/strict';
import test from 'node:test';
import { setLanguage } from '../../../frontend/src/i18n.js';
import { cadenceText, keyName, markText, relationText, sectionShares, textureText } from '../../../frontend/src/musicalAnalysis.js';

// The musical analysis of a work (2026-11-18) in a musician's words.
test('a key is named as a musician says it, in each language', () => {
  setLanguage('es');
  assert.equal(keyName({ tonic: 'Eb', mode: 'major' }), 'Mi♭ mayor');
  assert.equal(keyName({ tonic: 'F#', mode: 'minor' }), 'Fa♯ menor');
  setLanguage('en');
  assert.equal(keyName({ tonic: 'Bb', mode: 'major' }), 'B♭ major');
  setLanguage('es');
  assert.equal(keyName(null), '');
});

test('relations, textures, cadences and marks read as words', () => {
  setLanguage('es');
  assert.equal(relationText('dominant'), 'dominante');
  assert.equal(relationText('distant'), 'tono lejano');
  assert.equal(textureText('reduced'), 'plantilla reducida');
  assert.equal(cadenceText('authentic'), 'cadencia auténtica');
  assert.equal(markText('rehearsal B'), 'letra de ensayo B');
  assert.equal(markText('words D.C. al Fine'), '«D.C. al Fine»');
  assert.equal(markText('ending 1'), 'casilla 1');
  assert.equal(markText('double barline'), 'doble barra');
});

test('the timeline gives each section its share of the measures', () => {
  assert.deepEqual(sectionShares([{ first: 1, last: 8 }, { first: 9, last: 24 }]), [33.33, 66.67]);
  assert.deepEqual(sectionShares([]), []);
});

test('duration, tempos and meters read as a musician writes them', async () => {
  const { durationText, tempoText, listText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(durationText(467), '7 min 47 s');
  assert.equal(durationText(45), '45 s');
  assert.equal(tempoText({ measure: 1, bpm: 120, words: ['Allegro'] }), 'c. 1: ♩ = 120 · Allegro');
  assert.equal(tempoText({ measure: 16, bpm: null, words: ['rit.'] }), 'c. 16: rit.');
  assert.equal(listText(['a', 'b', 'c', 'd'], 2), 'a, b y 2 más');
  assert.equal(listText(['a', 'b'], 3), 'a, b');
});
