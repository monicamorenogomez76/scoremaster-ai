import test from 'node:test';
import assert from 'node:assert/strict';
import { initialVideoQuery, parseYouTubeVideoId, safeSearchUrl, searchStatus } from '../../../frontend/src/videos/youtube.js';
import { createScoreSession } from '../../../frontend/src/score/score-session.js';

test('only YouTube links become embeddable video ids', () => {
  assert.equal(parseYouTubeVideoId('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10'), 'dQw4w9WgXcQ');
  assert.equal(parseYouTubeVideoId(' https://youtu.be/dQw4w9WgXcQ '), 'dQw4w9WgXcQ');
  assert.equal(parseYouTubeVideoId('https://youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ');
  assert.equal(parseYouTubeVideoId('https://evil.example/watch?v=dQw4w9WgXcQ'), null);
  assert.equal(parseYouTubeVideoId('javascript:alert(1)'), null);
  assert.equal(parseYouTubeVideoId('https://www.youtube.com/watch?v=short'), null);
});

test('fallback search links are restricted to YouTube results', () => {
  assert.equal(safeSearchUrl('https://www.youtube.com/results?search_query=Persis'), 'https://www.youtube.com/results?search_query=Persis');
  assert.equal(safeSearchUrl('javascript:alert(1)'), '');
  assert.equal(safeSearchUrl(undefined), '');
});

test('video query prefers score metadata and completes it from the file name', () => {
  assert.equal(initialVideoQuery('Persis', 'James L. Hosay', 'x.mxl'), 'Persis James L. Hosay');
  assert.equal(initialVideoQuery('Untitled score', '', 'spania-david_shaffer.mxl'), 'spania david shaffer');
  assert.equal(initialVideoQuery('Spania', '', 'spania-david-shaffer.mxl'), 'Spania david shaffer');
});

test('score source is fetched once per file and retried after a failure', async () => {
  const calls = [];
  let fail = true;
  const session = createScoreSession(async url => {
    calls.push(url);
    if (fail) { fail = false; return { ok: false }; }
    return { ok: true, text: async () => '<score/>' };
  });
  await assert.rejects(session.loadSource(), /Vuelve a subir/);
  const version = session.getVersion();
  session.setFile({ name: 'a.musicxml' });
  assert.notEqual(session.getVersion(), version);
  await assert.rejects(session.loadSource(), /No se pudo recuperar/);
  assert.equal(await session.loadSource(), '<score/>');
  assert.equal(await session.loadSource(), '<score/>');
  assert.equal(calls.length, 2);
  session.setFile(session.getFile());
  assert.equal(await session.loadSource(), '<score/>');
  assert.equal(calls.length, 2, 'analysing the same file reuses its source');
  session.setFile({ name: 'b.musicxml' }, '<known/>');
  assert.equal(await session.loadSource(), '<known/>');
  assert.equal(calls.length, 2, 'a locally mapped score is not downloaded again');
  session.clear();
  assert.equal(session.getFile(), null);
});

test('without integrated results the musician is told why', () => {
  // 2026-10-07: on Render the search "did not work" and the page only said there were no matches.
  assert.equal(searchStatus({ mode: 'api', reason: null }, 2), 'Reproduciendo la mejor coincidencia. Elige otra versión para cambiarla.');
  assert.equal(searchStatus({ mode: 'api', reason: null }, 0), 'No hay coincidencias integradas. Busca en YouTube o pega aquí un enlace.');
  assert.match(searchStatus({ mode: 'link', reason: 'no_key' }, 0), /^La búsqueda integrada de YouTube no está configurada en este servidor/);
  assert.match(searchStatus({ mode: 'link', reason: 'rejected' }, 0), /^YouTube ha rechazado la búsqueda integrada/);
  assert.match(searchStatus({ mode: 'link', reason: 'unavailable' }, 0), /^No se pudo contactar con YouTube/);
});

// 2026-10-28: on Render's free plan the request for the notation waited behind the audio preparation, and the score
// only showed about when play could start. An uncompressed MusicXML is read in the browser; only .mxl goes to the server.
test('an uncompressed MusicXML is read in the browser, a compressed one by the server', async () => {
  const calls = [];
  const session = createScoreSession(async url => { calls.push(url); return { ok: true, text: async () => '<from-server/>' }; });
  session.setFile(new File(['<?xml version="1.0"?><score-partwise/>'], 'obra.musicxml'));
  assert.equal(await session.loadSource(), '<?xml version="1.0"?><score-partwise/>');
  assert.equal(calls.length, 0, 'no request for a plain MusicXML');
  session.setFile(new File(['PK\u0003\u0004 zipped'], 'obra.mxl'));
  assert.equal(await session.loadSource(), '<from-server/>');
  assert.deepEqual(calls, ['/notation-source']);
});
