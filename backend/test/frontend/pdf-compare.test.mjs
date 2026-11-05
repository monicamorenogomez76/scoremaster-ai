import assert from 'node:assert/strict';
import test from 'node:test';
import { localPdf } from '../../../frontend/src/score/pdf-compare.js';

// The director's own PDF beside the score (2026-11-05): it is read in the browser and never sent to the server.
const file = (content, name = 'obra.pdf') => new File([content], name);
const urls = { made: [], createObjectURL(blob) { this.made.push(blob); return 'blob:local'; } };

test('a PDF opens from the computer as a PDF, whatever the browser said it was', async () => {
  urls.made = [];
  assert.equal(await localPdf(new File(['%PDF-1.7 page'], 'obra.pdf', { type: 'text/html' }), urls), 'blob:local');
  assert.equal(urls.made[0].type, 'application/pdf', 'never run as the type a file claims');
  assert.equal(await urls.made[0].text(), '%PDF-1.7 page');
});

test('what is not a PDF by its content is refused, whatever its name', async () => {
  urls.made = [];
  await assert.rejects(localPdf(file('<script>alert(1)</script>'), urls), /no es un PDF/);
  await assert.rejects(localPdf(file(''), urls), /no es un PDF/);
  assert.equal(urls.made.length, 0);
});

test('nothing goes to the server', async () => {
  const fetched = [];
  const original = globalThis.fetch;
  globalThis.fetch = async url => { fetched.push(url); return new Response('{}'); };
  try { await localPdf(file('%PDF-1.7 page'), urls); } finally { globalThis.fetch = original; }
  assert.deepEqual(fetched, []);
});
