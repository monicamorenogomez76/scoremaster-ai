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

test('phrases and periods read as a musician says them', async () => {
  const { phrasesText, periodText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(phrasesText({ structure: '4 + 4', phrases: [{ ending: 'suspensive' }, { ending: 'conclusive' }] }),
    '4 + 4 (suspensiva, conclusiva)');
  assert.equal(phrasesText({ structure: '', phrases: [] }), '—');
  assert.equal(periodText({ first: 1, last: 8, kind: 'period', symmetric: true }), 'periodo simétrico, cc. 1–8');
  assert.equal(periodText({ first: 9, last: 20, kind: 'repetition', symmetric: false }), 'frase repetida, cc. 9–20');
});

test('texture and rhythm read as a musician says them', async () => {
  const { textureKindText, rhythmText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(textureKindText('melody_and_accompaniment'), 'melodía acompañada');
  assert.equal(textureKindText('polyphonic'), 'polifónica');
  assert.equal(textureKindText(null), '');
  assert.equal(rhythmText({ syncopation: 0.5, ostinatos: [{ part: 'Tuba', first: 1, last: 4 }],
    imitations: [{ part: 'Clarinet', imitates: 'Flute', measure: 2 }] }),
    'síncopas (50 %) · ostinato: Tuba (cc. 1–4) · imitación: Clarinet (c. 2)');
  assert.equal(rhythmText({ syncopation: 0.05, ostinatos: [], imitations: [] }), '—');
});

test('the theme of a section and the themes it develops read as words', async () => {
  const { themeText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(themeText({ theme: { id: 'T1', statement: 'exposition' }, motifs: [] }), 'T1 (exposición)');
  assert.equal(themeText({ theme: { id: 'T1', statement: 'transposed' }, motifs: [] }), 'T1 (vuelve en otro tono)');
  assert.equal(themeText({ theme: { id: 'T2', statement: 'return' }, motifs: [{ theme: 'T1', part: 'Tuba', measure: 9 }] }),
    'T2 (vuelve) · cabeza de T1: Tuba (c. 9)');
  assert.equal(themeText({ theme: null, motifs: [] }), '—');
});
