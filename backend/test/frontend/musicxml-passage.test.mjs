import assert from 'node:assert/strict';
import test from 'node:test';
import { writtenPart } from '../../../frontend/src/score/musicxml-passage.js';

// A part that changes instrument (2026-11-17) is analysed as «Mallet Percussion (Bells)», «Mallet Percussion (Tambourine)»…
test('an instrument of a part that changes instrument names its written part', () => {
  assert.equal(writtenPart('Mallet Percussion (Bells)'), 'Mallet Percussion');
  assert.equal(writtenPart('Xylophone (Wood Blocks)'), 'Xylophone');
  assert.equal(writtenPart('B♭ Trumpet 2'), null);
});

// The pages of the PDF (2026-11-22): the measures that start a page, after the first page.
const bar = (number, page) => `<measure number="${number}">${page ? '<print new-page="yes"/>' : ''}<note/></measure>`;
const part = (id, last, starts) => `<part id="${id}">${Array.from({ length: last }, (_, at) => bar(at + 1, starts.includes(at + 1))).join('')}</part>`;
const work = (...parts) => `<score-partwise>${parts.join('')}</score-partwise>`;

test('the pages of a work start where its parts mark a new page', async () => {
  const { pageStarts } = await import('../../../frontend/src/score/musicxml-passage.js');
  assert.deepEqual(pageStarts(work(part('P1', 5, [3, 5]), part('P2', 5, [3, 5]))), [1, 3, 5]);
  assert.deepEqual(pageStarts(work(part('P1', 2, []))), [], 'a work without pages is shown four measures at a time');
  assert.deepEqual(pageStarts(`<part id="P1">${bar(1)}<measure number="2"><print new-system="yes"/></measure></part>`), [],
    'a new system is no new page');
  assert.deepEqual(pageStarts(work(part('P1', 6, [4]), part('P2', 6, [3, 5]), part('P3', 6, [3, 5]))), [1, 3, 5],
    'a part completed from its own sheet does not move the pages of the score');
});

// 2026-11-25: a work joined from its parts carried the pages of each part's sheet, 44 measures each; drawn in one line
// for the whole band they were unreadable (3 %) and stopped the browser.
test('the pages of the sheets of the parts are not pages of the work', async () => {
  const { pageStarts } = await import('../../../frontend/src/score/musicxml-passage.js');
  assert.deepEqual(pageStarts(work(part('P1', 12, [5, 9]), part('P2', 12, [7]), part('P3', 12, [6, 11]))), [], 'each sheet turns elsewhere');
});
