import assert from 'node:assert/strict';
import test from 'node:test';
import { familyOfSection, planCounts, workHeadline } from '../../../frontend/src/dashboard.js';
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
