import assert from 'node:assert/strict';
import test from 'node:test';
import { addExternalGrade, comparisonText, deleteExternalGrade, listExternalGrades, valueOptions } from '../../../frontend/src/externalGrades.js';

test('each scale offers the values publishers use', () => {
  const grades = valueOptions('grade');
  assert.deepEqual(grades.slice(0, 3), [['0.5', 'Grade 0.5'], ['1', 'Grade 1'], ['1.5', 'Grade 1.5']]);
  assert.deepEqual(grades.at(-1), ['6', 'Grade 6']);
  assert.deepEqual(valueOptions('pepper').map(([value]) => value), ['VE', 'E', 'ME', 'M', 'MA', 'A']);
  assert.equal(valueOptions('pepper')[0][1], 'VE · muy fácil');
});

test('the comparison says what ScoreLint and the publishers give', () => {
  assert.equal(comparisonText(4, []), 'ScoreLint: grado 4. Añade el grado que publica una editorial para compararlo.');
  assert.equal(comparisonText(4, [{ grade: 3.5 }]), 'ScoreLint: grado 4 · editoriales: 3,5 · ScoreLint puntúa 0,5 más difícil.');
  assert.equal(comparisonText(3, [{ grade: 3 }, { grade: 4 }]), 'ScoreLint: grado 3 · editoriales: 3,5 (media de 2) · ScoreLint puntúa 0,5 más fácil.');
  assert.equal(comparisonText(2, [{ grade: 2 }]), 'ScoreLint: grado 2 · editoriales: 2 · coinciden.');
});

test('published grades are listed, added and deleted through the API', async () => {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push([url, options.method || 'GET', options.body ? JSON.parse(options.body) : null]);
    if (options.method === 'DELETE') return new Response(null, { status: 204 });
    return new Response(JSON.stringify(options.method === 'POST' ? { id: 'g1' } : { grades: [{ id: 'g1' }] }), { status: options.method === 'POST' ? 201 : 200 });
  };
  assert.deepEqual(await listExternalGrades('w 1'), [{ id: 'g1' }]);
  assert.deepEqual(await addExternalGrade('w 1', { scale: 'grade', value: '3', source: ' Hal Leonard ', url: '', consulted_on: '' }), { id: 'g1' });
  await deleteExternalGrade('w 1', 'g1');
  assert.deepEqual(calls, [
    ['/works/w%201/external-grades', 'GET', null],
    ['/works/w%201/external-grades', 'POST', { scale: 'grade', value: '3', source: 'Hal Leonard', url: null, consulted_on: null }],
    ['/works/w%201/external-grades/g1', 'DELETE', null],
  ]);
});

test('a refused grade shows the server message', async () => {
  // FastAPI answers a failed validation with a list of errors; the musician reads the first one.
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ msg: 'Value error, El enlace debe empezar por http:// o https://.' }] }), { status: 422 });
  await assert.rejects(addExternalGrade('w', { scale: 'grade', value: '3', source: 'x', url: 'javascript:x' }),
    { message: 'El enlace debe empezar por http:// o https://.' });
});

test('an average between half grades keeps its two decimals', () => {
  assert.equal(comparisonText(4, [{ grade: 3.5 }, { grade: 4 }]), 'ScoreLint: grado 4 · editoriales: 3,75 (media de 2) · ScoreLint puntúa 0,25 más difícil.');
});
