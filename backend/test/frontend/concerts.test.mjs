import assert from 'node:assert/strict';
import test from 'node:test';
import {
  assistantStep, concertProgress, createConcert, daysUntil, nextConcert, listConcerts, monthGrid, patternDates, phaseLabel, planItemsToSave,
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

test('the next concert and the rehearsals still to do before it', () => {
  const concerts = [
    { id: 'old', date: '2026-10-01', rehearsals: [] },
    { id: 'next', date: '2026-10-29', rehearsals: [{ date: '2026-10-13', reviewed: true }, { date: '2026-10-20', reviewed: false }, { date: '2026-10-27', reviewed: false }] },
    { id: 'later', date: '2026-12-20', rehearsals: [] },
  ];
  assert.deepEqual(nextConcert(concerts, '2026-10-14'), { concert: concerts[1], remaining: 2, days: 15 });
  assert.equal(nextConcert(concerts, '2026-12-21'), null);
});

test('the assistant suggests the next step of the next concert', () => {
  const concert = { id: 'c1', date: '2026-10-29', rehearsals: [] };
  const held = { id: 'r1', concert_id: 'c1', date: '2026-10-13', reviewed_at: null, fixed: false, updated_at: '2026-10-10T10:00:00Z' };
  const next = { id: 'r2', concert_id: 'c1', date: '2026-10-15', reviewed_at: null, fixed: false, updated_at: '2026-10-10T10:00:00Z' };
  const today = '2026-10-14';
  assert.deepEqual(assistantStep([], [], today), { step: 'free' }, 'without concerts, a single rehearsal is proposed');
  assert.deepEqual(assistantStep([concert], [], today), { step: 'plan', concert });
  assert.deepEqual(assistantStep([concert], [held, next], today), { step: 'review', concert, rehearsal: held });
  const reviewed = { ...held, reviewed_at: '2026-10-13T22:00:00Z' };
  assert.deepEqual(assistantStep([concert], [reviewed, next], today), { step: 'replan', concert, rehearsal: next },
    'a review after the next rehearsals were planned suggests replanning');
  const replanned = { ...next, updated_at: '2026-10-14T09:00:00Z' };
  assert.deepEqual(assistantStep([concert], [reviewed, replanned], today), { step: 'next', concert, rehearsal: replanned });
  assert.deepEqual(assistantStep([concert], [reviewed, { ...next, fixed: true }], today).step, 'next', 'a fixed rehearsal is not replanned');
});
