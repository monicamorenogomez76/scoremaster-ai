import assert from 'node:assert/strict';
import test from 'node:test';
import {
  analysisStatusText, deleteWork, durationText, groupPrioritiesBySection, listPriorities, listWorks, loadWork, preparationLabelsEs,
  saveBand, updatePreparation, workSummaryText,
} from '../../../frontend/src/library.js';

function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body, headers: new Headers(options.headers) });
    const [status, body, headers] = routes[(options.method || 'GET') + ' ' + url] || [404, { detail: 'La obra no existe.' }];
    if (body instanceof Uint8Array) return new Response(body, { status, headers });
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

test('a work summary reads as a musician would say it', () => {
  assert.equal(workSummaryText({ summary: { grade: 4, grade_max: 6, critical_passages: 12, compatibility_percent: 82 } }),
    'Grado 4 · Intermedio avanzado · 12 pasajes críticos · 82 % de la plantilla');
  assert.equal(workSummaryText({ summary: { grade: 1, grade_max: 6, critical_passages: 1, compatibility_percent: 100 } }),
    'Grado 1 · Muy fácil · 1 pasaje crítico · 100 % de la plantilla');
  assert.equal(workSummaryText({ summary: { grade: 3, grade_max: 5, critical_passages: 2, compatibility_percent: 90 } }),
    'Grado 3 de 5 (escala anterior) · 2 pasajes críticos · 90 % de la plantilla');
  assert.equal(workSummaryText({ summary: {} }), 'Sin análisis');
});

test('durations are shown in minutes and seconds, marked when the tempo is assumed', () => {
  assert.equal(durationText({ seconds: 245, assumed_tempo: false }), '4:05');
  assert.equal(durationText({ seconds: 60, assumed_tempo: true }), '1:00 (tempo supuesto)');
  assert.equal(durationText(undefined), '');
});

test('the library lists, reopens and deletes works', async () => {
  const calls = fakeServer({
    'GET /works': [200, { works: [{ id: 'w1', title: 'Persis' }] }],
    'GET /works/w1': [200, { title: 'Persis', work_id: 'w1' }],
    'GET /works/w1/file': [200, new Uint8Array([60, 115, 47, 62]), { 'Content-Disposition': 'attachment; filename="persis.musicxml"' }],
    'DELETE /works/w1': [204, null],
  });
  assert.deepEqual(await listWorks(), [{ id: 'w1', title: 'Persis' }]);
  const { data, file } = await loadWork('w1');
  assert.equal(data.work_id, 'w1');
  assert.equal(file.name, 'persis.musicxml');
  assert.equal(await file.text(), '<s/>');
  await deleteWork('w1');
  assert.equal(calls.at(-1).method, 'DELETE');
  await assert.rejects(loadWork('ajena'), { message: 'La obra no existe.' });
});

test('saving the band sends only the changed instruments', async () => {
  const calls = fakeServer({ 'PATCH /band': [200, { profile: { flute: 3, 'clarinet.bb': 11 } }] });
  assert.deepEqual(await saveBand({ flute: 3 }), { flute: 3, 'clarinet.bb': 11 });
  assert.deepEqual(JSON.parse(calls[0].body), { profile: { flute: 3 } });
  assert.equal(calls[0].headers.get('Content-Type'), 'application/json');
});

test('the director sets how far the band is with a work, apart from its difficulty', async () => {
  assert.deepEqual(preparationLabelsEs, { review: 'Por revisar', preparing: 'En preparación', ready: 'Lista para programa', archived: 'Archivada' });
  const calls = fakeServer({ 'PATCH /works/w1': [200, { id: 'w1', preparation_status: 'preparing' }] });
  assert.equal((await updatePreparation('w1', 'preparing')).preparation_status, 'preparing');
  assert.deepEqual(JSON.parse(calls[0].body), { preparation_status: 'preparing' });
  assert.equal(calls[0].headers.get('Content-Type'), 'application/json');
});

test('a work says whether its analysis is available', () => {
  assert.equal(analysisStatusText({ summary: { grade: 4 } }), 'Disponible');
  assert.equal(analysisStatusText({ summary: {} }), 'Sin analizar');
  assert.equal(analysisStatusText({}), 'Sin analizar');
});

test('priorities come from the works in preparation, grouped by section in their order', async () => {
  const priorities = [
    { work_id: 'w1', title: 'Persis', family: 'woodwinds', family_label_es: 'Viento madera', measure_range: '35-48', origin: 'analysis' },
    { work_id: 'w1', title: 'Persis', family: 'brass', family_label_es: 'Viento metal', measure_range: '72-84', origin: 'analysis' },
    { work_id: 'w2', title: 'Spania', family: 'woodwinds', family_label_es: 'Viento madera', measure_range: '9-16', origin: 'analysis' },
  ];
  fakeServer({ 'GET /works/priorities': [200, { priorities }] });
  assert.deepEqual(await listPriorities(), priorities);
  assert.deepEqual(groupPrioritiesBySection(priorities).map(([section, items]) => [section, items.map(item => item.measure_range)]),
    [['Viento madera', ['35-48', '9-16']], ['Viento metal', ['72-84']]]);
});
