import assert from 'node:assert/strict';
import test from 'node:test';
import { keyChange, mergeEdits } from '../../../frontend/src/score/note-edits.js';

const key = (name, modifiers = {}) => keyChange(['B', 0, 4], { key: name, ...modifiers });

test('the arrows move a note by a step, a semitone with shift and an octave with the command key', () => {
  assert.deepEqual(key('ArrowUp'), { pitch: ['C', 0, 5] });
  assert.deepEqual(key('ArrowDown'), { pitch: ['A', 0, 4] });
  assert.deepEqual(keyChange(['B', -1, 4], { key: 'ArrowUp' }), { pitch: ['C', 0, 5] }, 'a step up from B flat is C');
  assert.deepEqual(key('ArrowUp', { shiftKey: true }), { pitch: ['C', 0, 5] });
  assert.deepEqual(keyChange(['B', -1, 4], { key: 'ArrowUp', shiftKey: true }), { pitch: ['B', 0, 4] });
  assert.deepEqual(keyChange(['C', 0, 5], { key: 'ArrowDown', shiftKey: true }), { pitch: ['B', 0, 4] });
  assert.deepEqual(keyChange(['D', 0, 5], { key: 'ArrowDown', shiftKey: true }), { pitch: ['D', -1, 5] });
  assert.deepEqual(keyChange(['F', 1, 5], { key: 'ArrowUp', shiftKey: true }), { pitch: ['G', 0, 5] });
  assert.deepEqual(key('ArrowUp', { metaKey: true }), { pitch: ['B', 0, 5] });
  assert.deepEqual(key('ArrowDown', { ctrlKey: true }), { pitch: ['B', 0, 3] });
});

test('a letter names the note in the nearest octave, and the signs change its accidental', () => {
  assert.deepEqual(key('c'), { pitch: ['C', 0, 5] });
  assert.deepEqual(key('A'), { pitch: ['A', 0, 4] });
  assert.deepEqual(keyChange(['C', 0, 5], { key: 'g' }), { pitch: ['G', 0, 4] });
  assert.deepEqual(key('-'), { pitch: ['B', -1, 4] });
  assert.deepEqual(keyChange(['B', -1, 4], { key: '+' }), { pitch: ['B', 0, 4] });
  assert.deepEqual(keyChange(['F', 1, 4], { key: '=' }), { pitch: ['F', 0, 4] });
  assert.equal(keyChange(['F', 2, 4], { key: '+' }), null, 'no further than a double sharp');
});

test('a rest takes a letter near the note before it; delete makes a rest; arrows move the selection', () => {
  assert.deepEqual(keyChange(null, { key: 'd' }, ['C', 0, 5]), { pitch: ['D', 0, 5] });
  assert.equal(keyChange(null, { key: 'ArrowUp' }), null);
  assert.deepEqual(key('Delete'), { rest: true });
  assert.deepEqual(key('Backspace'), { rest: true });
  assert.deepEqual(key('ArrowRight'), { move: 'next' });
  assert.deepEqual(key('ArrowLeft'), { move: 'previous' });
  assert.deepEqual(key('ArrowUp', { altKey: true }), { move: 'up' });
  assert.deepEqual(key('ArrowDown', { altKey: true }), { move: 'down' });
  assert.equal(key('x'), null);
});

test('the changes of one note become one change from what was read to what it is now', () => {
  const at = { partId: 'P1', number: '82', offset: 1 / 3 };
  let edits = mergeEdits([], { ...at, old: null, new: ['C', 0, 5] });
  edits = mergeEdits(edits, { ...at, old: ['C', 0, 5], new: ['D', 0, 5] });
  assert.deepEqual(edits, [{ ...at, old: null, new: ['D', 0, 5] }]);
  edits = mergeEdits(edits, { partId: 'P2', number: '82', offset: 0, old: ['E', 0, 4], new: ['F', 0, 4] });
  assert.equal(edits.length, 2);
  assert.deepEqual(mergeEdits(edits, { ...at, old: ['D', 0, 5], new: null }), edits.slice(1), 'back to what was read');
});
