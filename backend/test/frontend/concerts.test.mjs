import assert from 'node:assert/strict';
import test from 'node:test';
import {
  concertProgress, createConcert, daysUntil, listConcerts, monthGrid, patternDates, phaseLabel, planItemsToSave,
  proposeConcertPlan, saveConcertPlan, weekdayOptions,
} from '../../../frontend/src/concerts.js';

function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body });
    const [status, body] = routes[(options.method || 'GET') + ' ' + url] || [404, { detail: 'El concierto no existe.' }];
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

test('phases and weekdays read as a musician would say them', () => {
  assert.deepEqual(['reading', 'passages', 'integration', 'general'].map(phaseLabel),
    ['Lectura y pasajes', 'Pasajes e integración', 'Integración', 'Ensayo general']);
  assert.deepEqual(weekdayOptions.map(([day, label]) => [day, label]).slice(0, 2), [[0, 'L'], [1, 'M']]);
});

test('the days left until a concert and the rehearsals already reviewed', () => {
  assert.equal(daysUntil('2026-10-29', '2026-10-13'), 16);
  assert.equal(daysUntil('2026-10-13', '2026-10-13'), 0);
  assert.deepEqual(concertProgress({ rehearsals: [{ reviewed: true }, { reviewed: false }, { reviewed: false }] }), { reviewed: 1, total: 3 });
});

test('the preview of the weekly pattern lists the rehearsal dates before the concert', () => {
  const schedule = { weekdays: [1, 3], start_date: '2026-10-13' };
  assert.deepEqual(patternDates(schedule, '2026-10-29', '2026-10-12'),
    ['2026-10-13', '2026-10-15', '2026-10-20', '2026-10-22', '2026-10-27']);
  assert.deepEqual(patternDates(schedule, '2026-10-29', '2026-10-21'), ['2026-10-22', '2026-10-27'], 'from today on');
});

test('a month grid starts on Monday and places concerts and rehearsals on their days', () => {
  const weeks = monthGrid(2026, 10, [{ date: '2026-10-13', kind: 'rehearsal' }, { date: '2026-10-29', kind: 'concert' }]);
  assert.equal(weeks[0].length, 7);
  assert.deepEqual(weeks[0].map(day => day && day.day), [null, null, null, 1, 2, 3, 4], 'October 2026 starts on Thursday');
  const day13 = weeks.flat().find(day => day && day.day === 13);
  assert.deepEqual(day13.events.map(event => event.kind), ['rehearsal']);
  assert.equal(weeks.flat().filter(Boolean).length, 31);
});

test('a planned series becomes the rehearsals to save, with its blocks ready for the editor', () => {
  const plan = [{ id: null, date: '2026-10-27', time: '20:00', duration_minutes: 90, phase: 'general', work_ids: ['w1'],
    blocks: [{ type: 'warmup', minutes: 14, work_id: null, work_title: null, parts: [], findings: [] },
      { type: 'runthrough', minutes: 76, work_id: 'w1', work_title: 'Persis', parts: [], findings: [] }] }];
  const [item] = planItemsToSave(plan);
  assert.deepEqual([item.id, item.date, item.phase, item.work_ids], [null, '2026-10-27', 'general', ['w1']]);
  assert.deepEqual(item.blocks.map(block => [block.title, block.minutes, block.group, block.work_id]),
    [['Calentamiento', 14, 'warmup', null], ['Pasada completa', 76, 'tutti', 'w1']]);
  assert.ok(item.blocks.every(block => !('work_title' in block)), 'only what the API stores');
});

test('concerts are listed, created, planned and their series saved', async () => {
  const calls = fakeServer({
    'GET /concerts': [200, { concerts: [{ id: 'c1' }] }],
    'POST /concerts': [201, { id: 'c1' }],
    'POST /concerts/c1/plan': [200, { rehearsals: [], kept: [] }],
    'PUT /concerts/c1/rehearsals': [200, { rehearsals: [] }],
  });
  assert.deepEqual(await listConcerts(), [{ id: 'c1' }]);
  assert.equal((await createConcert({ title: 'Santa Cecilia' })).id, 'c1');
  assert.deepEqual(await proposeConcertPlan('c1', '2026-10-12'), { rehearsals: [], kept: [] });
  assert.deepEqual(JSON.parse(calls[2].body), { today: '2026-10-12' });
  await saveConcertPlan('c1', '2026-10-12', []);
  assert.deepEqual(JSON.parse(calls[3].body), { today: '2026-10-12', rehearsals: [] });
});
