import assert from 'node:assert/strict';
import test from 'node:test';
import { writtenPart } from '../../../frontend/src/score/musicxml-passage.js';

// A part that changes instrument (2026-11-17) is analysed as «Mallet Percussion (Bells)», «Mallet Percussion (Tambourine)»…
test('an instrument of a part that changes instrument names its written part', () => {
  assert.equal(writtenPart('Mallet Percussion (Bells)'), 'Mallet Percussion');
  assert.equal(writtenPart('Xylophone (Wood Blocks)'), 'Xylophone');
  assert.equal(writtenPart('B♭ Trumpet 2'), null);
});

// The pages of the PDF (2026-11-22): the measures of the first part that start a page, after the first page.
test('the pages of a work start where its first part marks a new page', async () => {
  const { pageStarts } = await import('../../../frontend/src/score/musicxml-passage.js');
  const bar = (number, page) => `<measure number="${number}">${page ? '<print new-page="yes"/>' : ''}<note/></measure>`;
  const xml = `<score-partwise><part id="P1">${bar(1)}${bar(2)}${bar(3, true)}${bar(4)}${bar(5, true)}</part>`
    + `<part id="P2">${bar(1)}${bar(2, true)}</part></score-partwise>`;
  assert.deepEqual(pageStarts(xml), [1, 3, 5]);
  assert.deepEqual(pageStarts(`<score-partwise><part id="P1">${bar(1)}${bar(2)}</part></score-partwise>`), [],
    'a work without pages is shown four measures at a time');
  assert.deepEqual(pageStarts(`<part id="P1">${bar(1)}<measure number="2"><print new-system="yes"/></measure></part>`), [],
    'a new system is no new page');
});
