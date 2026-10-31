import assert from 'node:assert/strict';
import test from 'node:test';
import { addInstrumentName, createInstrument, createOwnInstrument, deleteInstrumentName, filterInstruments, instrumentKeys, loadAdminInstruments,
  loadInstrumentSuggestions, loadLearnedNames, newInstrumentBody, OTHER_INSTRUMENT, ownInstrumentBody, ownInstrumentForm,
  aiConfidence, proposeInstruments, withAiProposals, withSuggestions } from '../../../frontend/src/instrumentCatalog.js';

// The instrument catalog in the database (2026-10-28): the administration adds the names an instrument is written
// with and new common instruments from Configuración.
function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', body: options.body });
    const [status, body] = routes[(options.method || 'GET') + ' ' + url] || [404, { detail: 'El instrumento no existe.' }];
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

const catalog = [
  { canonical_id: 'flugelhorn.bb', label_es: 'Fliscorno', label_en: 'Flugelhorn', section: 'brass',
    names: [{ id: 1, name: 'fliscorno' }, { id: 2, name: 'fiscorn' }] },
  { canonical_id: 'english_horn', label_es: 'Corno inglés', label_en: 'English Horn', section: 'woodwinds',
    names: [{ id: 3, name: 'cor anglais' }] },
];

test('the search finds an instrument by its labels or any of its names, without accents or case', () => {
  assert.deepEqual(filterInstruments(catalog, 'FISCORN').map(item => item.canonical_id), ['flugelhorn.bb']);
  assert.deepEqual(filterInstruments(catalog, 'INGLES').map(item => item.canonical_id), ['english_horn']);
  assert.deepEqual(filterInstruments(catalog, 'anglais').map(item => item.canonical_id), ['english_horn']);
  assert.equal(filterInstruments(catalog, '  ').length, 2, 'an empty search shows everything');
});

test('a new instrument takes its key and its names one per line', () => {
  assert.deepEqual(instrumentKeys.map(([value]) => value), ['', 'Bb', 'Eb', 'F', 'A', 'G', 'D']);
  assert.deepEqual(newInstrumentBody({ label_es: ' Dulzaina ', label_en: 'Dulzaina', section: 'woodwinds',
    family: 'Gaita castellana', transposition: '', sound: '', rehearsal_group: 'double_reeds',
    names: 'Dulzaina\n\n Gaita castellana \nDulzaina' }), {
    label_es: 'Dulzaina', label_en: 'Dulzaina', section: 'woodwinds', family: 'gaita_castellana', transposition: null,
    sound: null, rehearsal_group: 'double_reeds', names: ['Dulzaina', 'Gaita castellana'] });
});

test('the administration reads and changes the catalog through the API', async () => {
  const calls = fakeServer({
    'GET /admin/instruments': [200, { instruments: catalog, version: 'instrument-catalog-v5', sounds: ['oboe'] }],
    'POST /admin/instruments/flugelhorn.bb/names': [201, { id: 4, name: 'Fiscornio' }],
    'DELETE /admin/instruments/names/4': [204, null],
    'POST /admin/instruments': [201, { canonical_id: 'dulzaina' }],
  });
  assert.equal((await loadAdminInstruments()).instruments.length, 2);
  assert.deepEqual(await addInstrumentName('flugelhorn.bb', 'Fiscornio'), { id: 4, name: 'Fiscornio' });
  assert.equal(JSON.parse(calls[1].body).name, 'Fiscornio');
  assert.equal(await deleteInstrumentName(4), null);
  assert.equal((await createInstrument({ label_es: 'Dulzaina' })).canonical_id, 'dulzaina');
  fakeServer({ 'POST /admin/instruments/flugelhorn.bb/names': [409, { detail: 'Ese nombre ya corresponde a Trompeta.' }] });
  await assert.rejects(addInstrumentName('flugelhorn.bb', 'Trompeta'), /ya corresponde a Trompeta/);
});

test('an instrument the catalog does not have is created for the account from the part to confirm', async () => {
  assert.equal(OTHER_INSTRUMENT, '__other__');
  assert.deepEqual(ownInstrumentBody('Dulzaina 1', { label_es: ' Dulzaina ', section: 'woodwinds', transposition: 'Eb',
    sound: 'oboe', rehearsal_group: 'double_reeds' }), {
    name: 'Dulzaina 1', label_es: 'Dulzaina', family: 'dulzaina', section: 'woodwinds', transposition: 'Eb', sound: 'oboe',
    rehearsal_group: 'double_reeds' });
  assert.equal(ownInstrumentBody('X', { label_es: 'Gaita gallega', section: 'woodwinds', transposition: '', sound: '',
    rehearsal_group: 'flutes' }).transposition, null);
  assert.equal(ownInstrumentForm('Dulzaina 1').label_es, 'Dulzaina', 'the part name without its number');
  const calls = fakeServer({ 'POST /instruments': [201, { canonical_id: 'own.1', label_es: 'Dulzaina', section: 'woodwinds', own: true }] });
  assert.equal((await createOwnInstrument({ name: 'Dulzaina 1' })).canonical_id, 'own.1');
  assert.equal(JSON.parse(calls[0].body).name, 'Dulzaina 1');
});

// Shared between accounts (2026-10-29): a name other accounts confirmed comes proposed and is counted once confirmed.
test('a name other accounts confirmed comes proposed for the parts without a proposal', async () => {
  const calls = fakeServer({ 'GET /instruments/suggestions?part=Fiscornio+2&part=Dulzaina':
    [200, { suggestions: { 'Fiscornio 2': 'flugelhorn.bb' } }] });
  const items = [{ part: 'Fiscornio 2', status: 'unknown' }, { part: 'Dulzaina', status: 'unknown' },
    { part: 'Clarinete', status: 'review', proposal: 'clarinet.bb' }];
  const suggestions = await loadInstrumentSuggestions(items);
  assert.equal(calls.length, 1, 'only the parts without a proposal are asked');
  assert.deepEqual(withSuggestions(items, suggestions), [
    { part: 'Fiscornio 2', status: 'shared', proposal: 'flugelhorn.bb' }, { part: 'Dulzaina', status: 'unknown' },
    { part: 'Clarinete', status: 'review', proposal: 'clarinet.bb' }]);
  assert.deepEqual(await loadInstrumentSuggestions([items[2]]), {}, 'nothing to ask');
  fakeServer({});
  assert.deepEqual(await loadInstrumentSuggestions(items), {}, 'without suggestions the parts are asked as before');
});

test('the administration reads the names the accounts confirmed', async () => {
  fakeServer({ 'GET /admin/instruments/learned': [200, { names: [{ name: 'Fiscornio', canonical_id: 'flugelhorn.bb',
    label_es: 'Fliscorno', accounts: 2 }] }] });
  assert.equal((await loadLearnedNames()).names[0].accounts, 2);
});

// The AI proposes the instrument of the parts the catalog does not know (2026-10-31): it comes chosen with its reason
// where nothing was chosen yet, and the part counts only once it is confirmed.
test('the AI proposals fill the parts nothing was chosen for and say why', async () => {
  const calls = fakeServer({ 'POST /works/w%201/instrument-proposals': [200, { proposals: {
    'Fiscorn 1': { instrument: 'flugelhorn.bb', confidence: 0.9, reason: 'Fiscorn es el fliscorno en catalán.' },
    'Clarinete': { instrument: 'clarinet.eb', confidence: 0.4, reason: 'Quizá el requinto.' } }, rejected: 1 }] });
  const answer = await proposeInstruments('w 1');
  assert.equal(calls[0].method, 'POST');
  const items = [{ part: 'Fiscorn 1', status: 'unknown' }, { part: 'Clarinete', status: 'review', proposal: 'clarinet.bb' },
    { part: 'Dulzaina', status: 'unknown' }];
  assert.deepEqual(withAiProposals(items, answer.proposals), [
    { part: 'Fiscorn 1', status: 'ai', proposal: 'flugelhorn.bb', ai: answer.proposals['Fiscorn 1'] },
    { part: 'Clarinete', status: 'review', proposal: 'clarinet.bb', ai: answer.proposals.Clarinete },
    { part: 'Dulzaina', status: 'unknown' }]);
  assert.deepEqual([aiConfidence(0.9), aiConfidence(0.6), aiConfidence(0.2)], ['alta', 'media', 'baja']);
  fakeServer({ 'POST /works/w/instrument-proposals': [409, { detail: 'La propuesta de instrumentos necesita la IA.' }] });
  await assert.rejects(proposeInstruments('w'), { message: 'La propuesta de instrumentos necesita la IA.' });
});
