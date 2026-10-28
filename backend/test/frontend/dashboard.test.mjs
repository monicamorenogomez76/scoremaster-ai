import assert from 'node:assert/strict';
import test from 'node:test';
import { concertCoverage, familyOfSection, planCounts, workHeadline } from '../../../frontend/src/dashboard.js';
import { summaryPriorityRows } from '../../../frontend/src/rehearsals.js';

// Director's dashboard (2026-10-26): «Dónde trabajar» shows which sections need work, from the priorities.
test('each section of a priority belongs to a family of the band', () => {
  for (const label of ['Flautas', 'Dobles cañas', 'Clarinetes', 'Saxofones', 'Viento madera']) assert.equal(familyOfSection(label), 'woodwinds', label);
  for (const label of ['Metales agudos', 'Graves', 'Viento metal']) assert.equal(familyOfSection(label), 'brass', label);
  assert.equal(familyOfSection('Percusión'), 'percussion');
  assert.equal(familyOfSection('Cuerda y rítmica'), 'strings');
  assert.equal(familyOfSection('Cuerda'), 'strings');
  assert.equal(familyOfSection('Toda la banda'), null, 'the whole band is no single section');
  assert.equal(familyOfSection('Clarinetes, Saxofones'), 'woodwinds', 'a review of several sections takes the first');
});

test('the priorities say their family, from the analysis or from the reviewed section', () => {
  const rows = summaryPriorityRows(
    [{ work_id: 'w1', title: 'Persis', sections: ['Metales agudos'], parts: [], measure_range: '', status: 'pending', note: '' },
     { work_id: 'w1', title: 'Persis', sections: [], parts: [], measure_range: '', status: 'improve', note: '' }],
    [{ work_id: 'w2', title: 'Spania', family: 'percussion', family_label_es: 'Percusión', measure_range: '9', findings: [] }]);
  assert.deepEqual(rows.map(row => row.family), ['brass', null, 'percussion']);
});

test('the plan counts the priorities of each family, every family shown even without any', () => {
  assert.deepEqual(planCounts([{ family: 'woodwinds' }, { family: 'woodwinds' }, { family: 'brass' }, { family: null }, { family: 'keyboard' }]),
    { woodwinds: 2, brass: 1, percussion: 0, strings: 0 });
});

test('the summary says in one sentence which section needs most work', () => {
  assert.equal(workHeadline({ woodwinds: 2, brass: 1, percussion: 0, strings: 0 }), 'Más trabajo en viento madera: 2 pasajes.');
  assert.equal(workHeadline({ woodwinds: 1, brass: 1, percussion: 0, strings: 0 }), 'Más trabajo en viento madera y viento metal: 1 pasaje cada una.');
  assert.equal(workHeadline({ woodwinds: 0, brass: 0, percussion: 0, strings: 0 }), 'Sin prioridades por ahora.');
});

// «Cobertura hasta el concierto» (requested 2026-10-26): rehearsals held, minutes rehearsed per work and
// passages resolved per work, over the series of the next concert.
const block = (work_id, minutes, measures, status) => ({ work_id, minutes, measures, review: status ? { status, note: '' } : null });
const coverageConcert = { id: 'c1', date: '2026-11-20', works: [{ id: 'w1', title: 'Persis' }, { id: 'w2', title: 'Spania' }] };
const series = [
  { concert_id: 'c1', date: '2026-10-05', reviewed_at: '2026-10-05T21:00:00Z',
    blocks: [block(null, 10), block('w1', 30, '1-20', 'improve'), block('w2', 20, '5-9', 'not_done')] },
  { concert_id: 'c1', date: '2026-10-12', reviewed_at: '2026-10-12T21:00:00Z',
    blocks: [block('w1', 30, '1-20', 'resolved'), block('w1', 20, '40-48', 'pending')] },
  { concert_id: 'c1', date: '2026-10-19', reviewed_at: null, blocks: [block('w1', 40, '1-60'), block('w2', 20, '5-9')] },
  { concert_id: 'c1', date: '2026-11-02', reviewed_at: null, blocks: [block('w1', 40, '1-60'), block('w2', 40, '1-80')] },
  { concert_id: 'other', date: '2026-10-05', reviewed_at: '2026-10-05T21:00:00Z', blocks: [block('w1', 90, '1-90', 'resolved')] },
];

test('the coverage counts the rehearsals of the series held before today or already reviewed', () => {
  assert.deepEqual(concertCoverage(coverageConcert, series, '2026-10-26').rehearsals, { done: 3, total: 4, percent: 75 });
  assert.deepEqual(concertCoverage(coverageConcert, series, '2026-10-15').rehearsals, { done: 2, total: 4, percent: 50 });
});

test('the coverage of a work is its minutes rehearsed over its minutes planned, without the blocks not done', () => {
  const [persis, spania] = concertCoverage(coverageConcert, series, '2026-10-26').works;
  assert.deepEqual(persis.minutes, { done: 120, total: 160, percent: 75 });
  assert.deepEqual(spania.minutes, { done: 20, total: 80, percent: 25 }, 'the block not done does not count as rehearsed');
});

test('each passage reviewed counts once with its latest status', () => {
  const [persis, spania] = concertCoverage(coverageConcert, series, '2026-10-26').works;
  assert.deepEqual(persis.passages, { resolved: 1, improve: 0, pending: 1, total: 2, percent: 50 });
  assert.deepEqual(spania.passages, { resolved: 0, improve: 0, pending: 0, total: 0, percent: null }, 'a block not done is no review');
});

test('without a concert or its series there is no coverage to show', () => {
  assert.equal(concertCoverage(null, series, '2026-10-26'), null);
  const empty = concertCoverage({ ...coverageConcert, id: 'c9' }, series, '2026-10-26');
  assert.deepEqual(empty.rehearsals, { done: 0, total: 0, percent: null });
  assert.deepEqual(empty.works[0].minutes, { done: 0, total: 0, percent: null });
});
