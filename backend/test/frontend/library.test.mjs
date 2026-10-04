import assert from 'node:assert/strict';
import test from 'node:test';
import { deleteWork, durationText, listWorks, loadWork, saveBand, workSummaryText } from '../../../frontend/src/library.js';

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
  assert.equal(workSummaryText({ summary: { grade: 3, critical_passages: 12, compatibility_percent: 82 } }),
    'Grado 3 · 12 pasajes críticos · 82 % de la plantilla');
  assert.equal(workSummaryText({ summary: { grade: 1, critical_passages: 1, compatibility_percent: 100 } }),
    'Grado 1 · 1 pasaje crítico · 100 % de la plantilla');
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
