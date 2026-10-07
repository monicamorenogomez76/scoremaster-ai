import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createCampaign, exportFileName, invitationProgress, listCampaigns, parseEmails, predictionText, removePassage,
  setCampaignStatus, setInvitations, shortfallText, statusLabel, campaignSummary,
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
