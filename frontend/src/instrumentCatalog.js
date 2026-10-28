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
