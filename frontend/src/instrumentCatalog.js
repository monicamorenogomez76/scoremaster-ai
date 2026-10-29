// The instrument catalog in the database (2026-10-28): the administration adds the names an instrument is written
// with and new common instruments from Configuración. API helpers and pure functions only.
import { apiJson } from './api.js';

export const instrumentSections = [['woodwinds', 'Viento madera'], ['brass', 'Viento metal'], ['percussion', 'Percusión'],
  ['strings', 'Cuerda'], ['keyboard', 'Teclas'], ['rhythm', 'Sección rítmica']];
export const instrumentKeys = [['', 'Do (no transpositor)'], ['Bb', 'Si♭'], ['Eb', 'Mi♭'], ['F', 'Fa'], ['A', 'La'],
  ['G', 'Sol'], ['D', 'Re']];
export const instrumentGroups = [['flutes', 'Flautas'], ['double_reeds', 'Dobles cañas'], ['clarinets', 'Clarinetes'],
  ['saxophones', 'Saxofones'], ['high_brass', 'Metales agudos'], ['low_voices', 'Graves'], ['percussion', 'Percusión'],
  ['strings_rhythm', 'Cuerda y rítmica']];

const plain = text => String(text || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

export function filterInstruments(instruments, query) {
  const wanted = plain(query);
  if (!wanted) return instruments;
  return instruments.filter(item => [item.label_es, item.label_en, ...item.names.map(name => name.name)]
    .some(text => plain(text).includes(wanted)));
}

export function newInstrumentBody(form) {
  const names = [];
  for (const line of String(form.names || '').split('\n')) {
    const name = line.trim();
    if (name && !names.includes(name)) names.push(name);
  }
  return {
    label_es: form.label_es.trim(), label_en: form.label_en.trim(), section: form.section,
    family: plain(form.family).replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40),
    transposition: form.transposition || null, sound: form.sound || null, rehearsal_group: form.rehearsal_group, names,
  };
}

const json = body => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const loadAdminInstruments = () => apiJson('/admin/instruments', {}, 'No se pudo cargar el catálogo de instrumentos.');

export const addInstrumentName = (instrumentId, name) => apiJson(
  '/admin/instruments/' + encodeURIComponent(instrumentId) + '/names', { method: 'POST', ...json({ name }) },
  'No se pudo añadir el nombre.');

export const deleteInstrumentName = nameId => apiJson('/admin/instruments/names/' + nameId, { method: 'DELETE' },
  'No se pudo quitar el nombre.');

export const createInstrument = body => apiJson('/admin/instruments', { method: 'POST', ...json(body) },
  'No se pudo crear el instrumento.');

// «Otro instrumento…» when a part to confirm is not in the catalog (2026-10-28): it is created for this account
// with its name, family and key, and the part name is learnt for the next works.
export const OTHER_INSTRUMENT = '__other__';

export const ownInstrumentForm = part => ({ label_es: String(part || '').replace(/\s+\d+(\s*(y|&|\/|-)\s*\d+)*$/, '').trim(),
  section: 'woodwinds', transposition: '', sound: '', rehearsal_group: 'flutes' });

export const ownInstrumentBody = (part, form) => ({
  name: part, label_es: form.label_es.trim(),
  family: plain(form.label_es).replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'other',
  section: form.section, transposition: form.transposition || null, sound: form.sound || null,
  rehearsal_group: form.rehearsal_group,
});

export const createOwnInstrument = body => apiJson('/instruments', { method: 'POST', ...json(body) },
  'No se pudo crear el instrumento.');

// Shared between accounts (2026-10-29): for parts without a proposal, the instrument other accounts confirmed for the
// same name. It comes chosen in the list but counts only once the part is confirmed; without an answer, nothing changes.
export async function loadInstrumentSuggestions(items) {
  const parts = (items || []).filter(item => !item.proposal).map(item => item.part);
  if (parts.length === 0) return {};
  try {
    const body = await apiJson('/instruments/suggestions?' + new URLSearchParams(parts.map(part => ['part', part])), {}, '');
    return body.suggestions || {};
  } catch {
    return {};
  }
}

export const withSuggestions = (items, suggestions) => (items || []).map(item =>
  !item.proposal && suggestions[item.part] ? { ...item, status: 'shared', proposal: suggestions[item.part] } : item);

export const loadLearnedNames = () => apiJson('/admin/instruments/learned', {},
  'No se pudieron cargar los nombres confirmados por las cuentas.');
