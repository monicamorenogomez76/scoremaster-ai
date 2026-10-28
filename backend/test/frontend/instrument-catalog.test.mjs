import assert from 'node:assert/strict';
import test from 'node:test';
import { addInstrumentName, createInstrument, deleteInstrumentName, filterInstruments, instrumentKeys, loadAdminInstruments,
  newInstrumentBody } from '../../../frontend/src/instrumentCatalog.js';

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
