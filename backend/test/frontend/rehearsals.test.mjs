import assert from 'node:assert/strict';
import test from 'node:test';
import {
  agendaTime, blockWorkText, createRehearsal, deleteRehearsal, duplicateBlock, listRehearsals, moveBlock,
  nextRehearsal, proposalBlocks, proposeRehearsal, rehearsalDateText, splitRehearsals, updateRehearsal,
} from '../../../frontend/src/rehearsals.js';

function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body });
    const [status, body] = routes[(options.method || 'GET') + ' ' + url] || [404, { detail: 'El ensayo no existe.' }];
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

const rehearsals = [
  { id: 'a', date: '2026-10-01', time: '19:00' },
  { id: 'b', date: '2026-10-05', time: '20:00' },
  { id: 'c', date: '2026-10-12', time: '19:00' },
];

test('rehearsals from today on are upcoming; earlier ones were held, latest first', () => {
  const { upcoming, past } = splitRehearsals(rehearsals, '2026-10-05');
  assert.deepEqual(upcoming.map(item => item.id), ['b', 'c']);
  assert.deepEqual(past.map(item => item.id), ['a']);
  assert.equal(nextRehearsal(rehearsals, '2026-10-05').id, 'b');
  assert.equal(nextRehearsal(rehearsals, '2026-10-13'), null);
});

test('a rehearsal date reads as today or as a full date', () => {
  assert.equal(rehearsalDateText({ date: '2026-10-05', time: '19:00' }, '2026-10-05'), 'Hoy · 19:00');
  assert.match(rehearsalDateText({ date: '2026-10-12', time: null }, '2026-10-05'), /^lunes, 12 de octubre de 2026$/);
});

test('the agenda shows the time assigned and what is left or exceeded', () => {
  assert.deepEqual(agendaTime([{ minutes: 15 }, { minutes: 25 }], 60), { assigned: 40, remaining: 20, exceeded: 0 });
  assert.deepEqual(agendaTime([{ minutes: 45 }, { minutes: 25 }], 60), { assigned: 70, remaining: 0, exceeded: 10 });
  assert.deepEqual(agendaTime([{ minutes: '' }], 60), { assigned: 0, remaining: 60, exceeded: 0 });
});

test('blocks move up and down and can be duplicated', () => {
  const blocks = [{ title: 'A' }, { title: 'B' }, { title: 'C' }];
  assert.deepEqual(moveBlock(blocks, 2, -1).map(block => block.title), ['A', 'C', 'B']);
  assert.deepEqual(moveBlock(blocks, 0, -1).map(block => block.title), ['A', 'B', 'C']);
  assert.deepEqual(duplicateBlock(blocks, 1).map(block => block.title), ['A', 'B', 'B', 'C']);
  assert.notEqual(duplicateBlock(blocks, 1)[2], blocks[1]);
});

test('each block says which work is rehearsed in it', () => {
  assert.equal(blockWorkText({ work_title: 'Persis', measures: '35-48' }), 'Persis · cc. 35–48');
  assert.equal(blockWorkText({ work_title: 'Persis', measures: '' }), 'Persis');
  assert.equal(blockWorkText({ work_title: 'Persis', measures: '1-4, 9-16' }), 'Persis · cc. 1–4, 9–16');
  assert.equal(blockWorkText({ work_title: null }), 'Toda la banda · sin obra concreta');
});

test('rehearsals are listed, created, replaced and deleted', async () => {
  const saved = { id: 'r1', date: '2026-10-20', blocks: [] };
  const calls = fakeServer({
    'GET /rehearsals': [200, { rehearsals: [saved] }],
    'POST /rehearsals': [201, saved],
    'PUT /rehearsals/r1': [200, saved],
    'DELETE /rehearsals/r1': [204, null],
  });
  assert.deepEqual(await listRehearsals(), [saved]);
  assert.equal((await createRehearsal({ date: '2026-10-20' })).id, 'r1');
  assert.deepEqual(JSON.parse(calls[1].body), { date: '2026-10-20' });
  assert.equal((await updateRehearsal('r1', { date: '2026-10-20' })).id, 'r1');
  assert.equal(calls[2].method, 'PUT');
  await deleteRehearsal('r1');
  assert.equal(calls[3].method, 'DELETE');
  await assert.rejects(updateRehearsal('ajeno', {}), { message: 'El ensayo no existe.' });
});

test('the proposed agenda becomes editable blocks, each with its work', async () => {
  const proposal = { blocks: [
    { type: 'warmup', minutes: 9, parts: [], findings: [], work_id: null, work_title: null },
    { type: 'sectional', group: 'clarinets', parts: ['Clarinet'], measure_range: '1-4', minutes: 20, findings: ['SL002'], work_id: 'w1', work_title: 'Persis' },
    { type: 'common', kind: 'line', parts: ['Trombone', 'Euphonium'], groups: ['low'], measure_range: '9', minutes: 15, findings: [], work_id: 'w1', work_title: 'Persis' },
    { type: 'tutti', parts: ['Clarinet', 'Trombone'], measure_ranges: ['1-4', '9-16'], minutes: 16, findings: [], work_id: 'w1', work_title: 'Persis' },
  ] };
  const blocks = proposalBlocks(proposal);
  assert.deepEqual(blocks.map(block => [block.title, block.minutes, block.work_id, block.measures]), [
    ['Calentamiento', 9, null, ''],
    ['Seccional · Clarinetes', 20, 'w1', '1-4'],
    ['Línea común', 15, 'w1', '9'],
    ['Tutti para juntar', 16, 'w1', '1-4, 9-16'],
  ]);
  assert.deepEqual(blocks[1].sections, ['Clarinetes']);
  assert.deepEqual(blocks[3].sections, ['Toda la banda']);
  assert.match(blocks[1].objective, /Registro agudo/);
  assert.ok(blocks.every(block => block.objective.length <= 500 && block.measures.length <= 40));

  const calls = fakeServer({ 'POST /rehearsals/proposal': [200, proposal] });
  assert.equal((await proposeRehearsal(['w1'], 60)).blocks.length, 4);
  assert.deepEqual(JSON.parse(calls[0].body), { work_ids: ['w1'], duration_minutes: 60 });
});
