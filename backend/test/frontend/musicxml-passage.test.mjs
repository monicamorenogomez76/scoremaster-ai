import assert from 'node:assert/strict';
import test from 'node:test';
import { writtenPart } from '../../../frontend/src/score/musicxml-passage.js';

// A part that changes instrument (2026-11-17) is analysed as «Mallet Percussion (Bells)», «Mallet Percussion (Tambourine)»…
test('an instrument of a part that changes instrument names its written part', () => {
  assert.equal(writtenPart('Mallet Percussion (Bells)'), 'Mallet Percussion');
  assert.equal(writtenPart('Xylophone (Wood Blocks)'), 'Xylophone');
  assert.equal(writtenPart('B♭ Trumpet 2'), null);
});
