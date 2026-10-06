import assert from 'node:assert/strict';
import test from 'node:test';
import { activateBand, bandBody, bandDraft, createBand, levelOptions, listBands, sectionLevelRows, templateGroups } from '../../../frontend/src/bands.js';

function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body });
    const [status, body] = routes[(options.method || 'GET') + ' ' + url] || [404, { detail: 'La banda no existe.' }];
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

const catalog = [
  { canonical_id: 'flute', label_es: 'Flauta', section: 'woodwinds' },
  { canonical_id: 'clarinet.bb', label_es: 'Clarinete en Si bemol', section: 'woodwinds' },
  { canonical_id: 'trumpet.bb', label_es: 'Trompeta en Si bemol', section: 'brass' },
  { canonical_id: 'snare_drum', label_es: 'Caja', section: 'percussion' },
  { canonical_id: 'timpani', label_es: 'Timbales', section: 'percussion' },
];

test('the full template lists every instrument by family and the percussionists as one total', () => {
  assert.deepEqual(templateGroups(catalog).map(([family, rows]) => [family, rows.map(row => row.key)]), [
    ['Viento madera', ['flute', 'clarinet.bb']], ['Viento metal', ['trumpet.bb']], ['Percusión', ['percussion']]]);
  assert.equal(templateGroups(catalog)[2][1][0].label, 'Percusionistas');
});

test('each section of the band has a level on the grade rubric, or none', () => {
  assert.deepEqual(levelOptions[0], ['', 'Sin indicar']);
  assert.deepEqual(levelOptions[4], ['4', '4 · Intermedio']);
  assert.deepEqual(sectionLevelRows().map(([key]) => key).slice(0, 3), ['flutes', 'double_reeds', 'clarinets']);
  assert.equal(sectionLevelRows()[2][1], 'Clarinetes');
});

test('the form of a band becomes what the API stores, without empty instruments or levels', () => {
  const draft = bandDraft({ name: 'Unió Musical', rehearsal_weekdays: [1, 3], profile: { flute: 3 }, section_levels: { clarinets: 4 } });
  assert.deepEqual([draft.name, draft.rehearsal_weekdays, draft.profile.flute, draft.section_levels.clarinets], ['Unió Musical', [1, 3], '3', '4']);
  const body = bandBody({ ...draft, locality: ' Albalat ', profile: { flute: '3', 'clarinet.bb': '', percussion: '0' },
    section_levels: { clarinets: '4', flutes: '' }, rehearsal_time: '20:00', rehearsal_minutes: '120' });
  assert.deepEqual(body, { name: 'Unió Musical', locality: 'Albalat', place: null, rehearsal_weekdays: [1, 3], rehearsal_time: '20:00',
    rehearsal_minutes: 120, profile: { flute: 3, percussion: 0 }, section_levels: { clarinets: 4 } });
  assert.equal(bandDraft(null).name, '', 'a new band starts empty');
});

test('bands are listed, created and one of them activated', async () => {
  const calls = fakeServer({ 'GET /bands': [200, { bands: [{ id: 'b1' }] }], 'POST /bands': [201, { id: 'b1' }],
    'POST /bands/b1/activate': [200, { id: 'b1', active: true }] });
  assert.deepEqual(await listBands(), [{ id: 'b1' }]);
  assert.equal((await createBand({ name: 'Unió' })).id, 'b1');
  assert.equal((await activateBand('b1')).active, true);
  assert.equal(calls[2].method, 'POST');
});
