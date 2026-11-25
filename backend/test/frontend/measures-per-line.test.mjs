import test from 'node:test';
import assert from 'node:assert/strict';
import { keepMeasures, keptMeasures, MEASURE_CHOICES } from '../../../frontend/src/score/measures-per-line.js';

const memory = () => { const kept = {}; return { getItem: key => kept[key] ?? null, setItem(key, value) { kept[key] = String(value); }, removeItem(key) { delete kept[key]; } }; };

test('the measures chosen for a line are kept in the browser', () => {
  const storage = memory();
  assert.equal(keptMeasures(storage), null, 'automatic at first');
  keepMeasures(6, storage);
  assert.equal(keptMeasures(storage), 6);
  keepMeasures(null, storage);
  assert.equal(keptMeasures(storage), null);
});

test('only the choices offered are used, and a browser without storage is automatic', () => {
  for (const value of ['44', 'x', '-1', '']) assert.equal(keptMeasures({ getItem: () => value }), null);
  const closed = { getItem() { throw new Error('closed'); }, setItem() { throw new Error('closed'); }, removeItem() { throw new Error('closed'); } };
  assert.equal(keptMeasures(closed), null);
  keepMeasures(4, closed);
  assert.ok(Math.max(...MEASURE_CHOICES) <= 16, 'a longer line of a whole band stops the browser');
});
