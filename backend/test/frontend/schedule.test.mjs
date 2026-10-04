import test from 'node:test';
import assert from 'node:assert/strict';
import { rehearsalSchedule } from '../../../frontend/src/schedule.js';

const blocks = [
  { type: 'sectional', section: 'brass', minutes: 6 },
  { type: 'sectional', section: 'woodwinds', minutes: 5 },
  { type: 'tutti', section: null, minutes: 22 },
];

test('blocks follow one another from the start time', () => {
  const schedule = rehearsalSchedule(blocks, '19:00');
  assert.deepEqual(schedule.map(item => [item.start, item.end]), [['19:00', '19:06'], ['19:06', '19:11'], ['19:11', '19:33']]);
});

test('each block knows its share of the rehearsal to be drawn on the timeline', () => {
  const schedule = rehearsalSchedule(blocks, '19:00');
  assert.deepEqual(schedule.map(item => [item.offset, item.share]), [[0, 6 / 33], [6 / 33, 5 / 33], [11 / 33, 22 / 33]]);
});

test('times wrap after midnight and an invalid start falls back to 19:00', () => {
  assert.equal(rehearsalSchedule(blocks, '23:55')[2].end, '00:28');
  assert.equal(rehearsalSchedule(blocks, 'tarde')[0].start, '19:00');
});

test('an empty plan has an empty schedule', () => {
  assert.deepEqual(rehearsalSchedule([], '19:00'), []);
});
