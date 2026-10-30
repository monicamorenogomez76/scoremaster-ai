// Bands of the director (decided 2026-10-06): several fixed templates, one active, each
// with its locality, rehearsal days, full instrumentation and a level per section.
import { apiJson } from './api.js';
import { displayFamilyName, gradeLabelsEs, instrumentLabel, rehearsalGroupName } from './labels.js';
import { t } from './i18n.js';

const send = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
const path = id => '/bands/' + encodeURIComponent(id);

export const listBands = async () => (await apiJson('/bands', {}, t('No se pudieron cargar las bandas.'))).bands;
export const createBand = band => apiJson('/bands', send('POST', band), t('No se pudo guardar la banda.'));
export const updateBand = (id, band) => apiJson(path(id), send('PUT', band), t('No se pudo guardar la banda.'));
export const deleteBand = id => apiJson(path(id), { method: 'DELETE' }, t('No se pudo eliminar la banda.'));
// The active band is the template of the analyses and BandFit.
export const activateBand = id => apiJson(path(id) + '/activate', { method: 'POST' }, t('No se pudo cambiar la banda activa.'));
export const loadCatalog = async () => (await apiJson('/instruments/catalog', {}, t('No se pudo cargar el catálogo.'))).instruments;

// Every catalog instrument by family; the percussion counts its percussionists in total, as BandFit.
export function templateGroups(catalog) {
  const groups = new Map();
  for (const entry of catalog) {
    const family = displayFamilyName(entry.section);
    const row = entry.section === 'percussion' ? { key: 'percussion', label: t('Percusionistas') } : { key: entry.canonical_id, label: instrumentLabel(entry) };
    const rows = groups.get(family) || [];
    if (!rows.some(item => item.key === row.key)) rows.push(row);
    groups.set(family, rows);
  }
  return [...groups];
}

const SECTIONS = ['flutes', 'double_reeds', 'clarinets', 'saxophones', 'high_brass', 'low_voices', 'percussion', 'strings_rhythm'];
export const sectionLevelRows = () => SECTIONS.map(key => [key, rehearsalGroupName(key)]);
export const levelOptions = [['', 'Sin indicar'], ...[1, 2, 3, 4, 5, 6].map(level => [String(level), level + ' · ' + gradeLabelsEs[level]])];
export const levelChoices = () => [['', t('Sin indicar')], ...[1, 2, 3, 4, 5, 6].map(level => [String(level), level + ' · ' + t(gradeLabelsEs[level])])];

const asText = values => Object.fromEntries(Object.entries(values || {}).map(([key, value]) => [key, String(value)]));

export function bandDraft(band) {
  return {
    name: band?.name || '', locality: band?.locality || '', place: band?.place || '',
    rehearsal_weekdays: band?.rehearsal_weekdays || [], rehearsal_time: band?.rehearsal_time || '20:00',
    rehearsal_minutes: String(band?.rehearsal_minutes || 120), profile: asText(band?.profile), section_levels: asText(band?.section_levels),
  };
}

// What the API stores: numbers, and no instrument or level left empty.
export function bandBody(draft) {
  const numbers = values => Object.fromEntries(Object.entries(values).filter(([, value]) => String(value).trim() !== '')
    .map(([key, value]) => [key, Number(value)]));
  return {
    name: draft.name.trim(), locality: draft.locality.trim() || null, place: draft.place.trim() || null,
    rehearsal_weekdays: draft.rehearsal_weekdays, rehearsal_time: draft.rehearsal_time || null,
    rehearsal_minutes: Number(draft.rehearsal_minutes) || null, profile: numbers(draft.profile), section_levels: numbers(draft.section_levels),
  };
}
