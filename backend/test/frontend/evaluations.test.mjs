import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createCampaign, exportFileName, invitationProgress, listCampaigns, parseEmails, predictionText, removePassage,
  setCampaignStatus, setInvitations, shortfallText, statusLabel, campaignSummary,
  GRADE_RUBRIC, EXPERIENCE_OPTIONS, PRIORITY_LABELS, nextToRate, ratedCount, ratingDraft, ratingToSend, saveProfile, saveRating,
} from '../../../frontend/src/evaluations.js';

function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body });
    const [status, body] = routes[(options.method || 'GET') + ' ' + url] || [404, { detail: 'La campaña no existe.' }];
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

test('the emails of the musicians are read one per line, or separated by commas', () => {
  assert.deepEqual(parseEmails(' ana@banda.org\nBerta@Banda.org, carla@banda.org;ana@banda.org\n\n'),
    ['ana@banda.org', 'berta@banda.org', 'carla@banda.org']);
  assert.deepEqual(parseEmails(''), []);
});

test('statuses and the prediction read as a director would say them', () => {
  assert.deepEqual(['draft', 'open', 'closed'].map(statusLabel), ['Borrador', 'Abierta', 'Cerrada']);
  assert.equal(predictionText({ grade: 4, critical: true }), 'Grado 4 · crítico');
  assert.equal(predictionText({ grade: 2, critical: false }), 'Grado 2');
});

test('the progress of each invited musician', () => {
  assert.equal(invitationProgress({ rated: 0, profile_done: false }, 20), 'Aún no ha empezado');
  assert.equal(invitationProgress({ rated: 7, profile_done: true }, 20), '7 de 20 pasajes');
  assert.equal(invitationProgress({ rated: 20, profile_done: true }, 20), 'Ha valorado todos los pasajes');
});

test('a campaign summary counts the passages ScoreLint finds critical', () => {
  const passages = [{ snapshot: { critical: true } }, { snapshot: { critical: false } }, { snapshot: { critical: true } }];
  assert.equal(campaignSummary({ passages, invitations: [{}, {}] }), '3 pasajes · 2 críticos según ScoreLint · 2 músicos invitados');
  assert.equal(campaignSummary({ passages: [passages[1]], invitations: [{}] }), '1 pasaje · 0 críticos según ScoreLint · 1 músico invitado');
});

test('the export is named after the campaign', () => {
  assert.equal(exportFileName({ title: 'Dificultad: banda / otoño' }), 'valoraciones-dificultad-banda-otono.json');
});

test('campaigns are listed, created, trimmed, shared and opened through the API', async () => {
  const calls = fakeServer({
    'GET /evaluations': [200, { owned: [{ id: 'c1' }], invited: [] }],
    'POST /evaluations': [201, { id: 'c1' }],
    'DELETE /evaluations/c1/passages/p1': [204, null],
    'PUT /evaluations/c1/invitations': [200, { id: 'c1' }],
    'POST /evaluations/c1/status': [200, { id: 'c1', status: 'open' }],
  });
  assert.deepEqual((await listCampaigns()).owned, [{ id: 'c1' }]);
  await createCampaign({ title: 'Prueba', work_ids: ['w1'], size: 20 });
  assert.deepEqual(JSON.parse(calls[1].body), { title: 'Prueba', work_ids: ['w1'], size: 20 });
  await removePassage('c1', 'p1');
  await setInvitations('c1', ['ana@banda.org']);
  assert.deepEqual(JSON.parse(calls[3].body), { emails: ['ana@banda.org'] });
  assert.equal((await setCampaignStatus('c1', 'open')).status, 'open');
});

test('the director is told when the works give fewer passages than asked', () => {
  assert.equal(shortfallText(20, 9), 'Se han propuesto 9 de los 20 pasajes pedidos: las obras elegidas no dan para más. Añade obras si necesitas más.');
  assert.equal(shortfallText(20, 20), '');
});

test('the musician rates with the same rubric as ScoreLint, grade by grade', () => {
  assert.deepEqual(GRADE_RUBRIC.map(item => item.grade), [1, 2, 3, 4, 5, 6]);
  assert.deepEqual(GRADE_RUBRIC[3], { grade: 4, label: 'Intermedio', band: 'Banda amateur media' });
  assert.deepEqual(EXPERIENCE_OPTIONS.map(([value]) => value), ['estudiante', 'amateur', 'profesional', 'docente']);
  assert.equal(PRIORITY_LABELS[1], 'Puede esperar');
  assert.equal(PRIORITY_LABELS[5], 'Ensayarlo cuanto antes');
});

test('a rating starts empty and is sent only when complete', () => {
  const draft = ratingDraft(null);
  assert.deepEqual(draft, { difficulty: '', critical: '', priority: '', comment: '' });
  assert.equal(ratingToSend(draft), null);
  assert.deepEqual(ratingToSend({ difficulty: '4', critical: 'yes', priority: '3', comment: '  Entradas  ' }),
    { difficulty: 4, critical: true, priority: 3, comment: 'Entradas' });
  assert.deepEqual(ratingDraft({ difficulty: 2, critical: false, priority: 1, comment: '' }),
    { difficulty: '2', critical: 'no', priority: '1', comment: '' });
});

test('after saving, the musician goes on to the next passage still to rate', () => {
  const passages = [{ rating: { difficulty: 1 } }, { rating: null }, { rating: { difficulty: 3 } }, { rating: null }];
  assert.equal(ratedCount({ passages }), 2);
  assert.equal(nextToRate(passages, 1), 3, 'the next one without a rating');
  assert.equal(nextToRate(passages, 3), 1, 'from the end, back to the first one left');
  assert.equal(nextToRate(passages.map(item => ({ rating: { difficulty: 2 } })), 1), 2, 'all rated: simply the next one');
  assert.equal(nextToRate([{ rating: { difficulty: 2 } }], 0), 0);
});

test('the profile and each rating are saved through the API', async () => {
  const calls = fakeServer({
    'PUT /evaluations/c1/profile': [200, { experience_level: 'amateur', main_instrument: 'Clarinete' }],
    'PUT /evaluations/c1/passages/p1/rating': [200, { difficulty: 4, critical: true, priority: 3, comment: '' }],
  });
  await saveProfile('c1', 'amateur', ' Clarinete ');
  assert.deepEqual(JSON.parse(calls[0].body), { experience_level: 'amateur', main_instrument: 'Clarinete' });
  await saveRating('c1', 'p1', { difficulty: 4, critical: true, priority: 3, comment: '' });
  assert.equal(calls[1].method, 'PUT');
});
