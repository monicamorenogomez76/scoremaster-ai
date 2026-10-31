// Spanish presentation of ScoreLint, BandFit and rehearsal results. Pure functions only.
import { currentLanguage, t } from './i18n.js';
export const bandStatusLabels = {
  ok: 'Compatible',
  warning: 'Requiere revisar la plantilla',
  critical: 'Incompatibilidad importante'
};
export const findingLabels = {
  SL003: 'Alta densidad rítmica',
  SL004: 'Intervalos amplios',
  SL002: 'Registro agudo',
  SL005: 'Pasaje prolongado sin descanso'
};
const familyLabelsEs = {
  woodwinds: 'Viento madera',
  brass: 'Viento metal',
  strings: 'Cuerda',
  percussion: 'Percusión',
  keyboard: 'Teclas',
  rhythm: 'Sección rítmica',
  other: 'Otros'
};
const instrumentLabelsEs = {
  'Piccolo': 'Flautín', 'Flute': 'Flauta', 'Oboe': 'Oboe',
  'Clarinet': 'Clarinete', 'B♭ Clarinet': 'Clarinete en Si bemol',
  'Bb Clarinet': 'Clarinete en Si bemol', 'Alto Clarinet': 'Clarinete alto',
  'Bass Clarinet': 'Clarinete bajo', 'Bassoon': 'Fagot',
  'Alto Saxophone': 'Saxofón alto', 'Tenor Saxophone': 'Saxofón tenor',
  'Baritone Saxophone': 'Saxofón barítono', 'B♭ Trumpet': 'Trompeta en Si bemol',
  'Bb Trumpet': 'Trompeta en Si bemol', 'Horn in F': 'Trompa en Fa',
  'Trumpet': 'Trompeta', 'Trombone': 'Trombón', 'Euphonium': 'Bombardino',
  'Tuba': 'Tuba', 'Double Bass': 'Contrabajo', 'Timpani': 'Timbales',
  'Xylophone': 'Xilófono', 'Glockenspiel': 'Glockenspiel', 'Chimes': 'Campanas tubulares',
  'Concert Bass Drum': 'Bombo', 'Bass Drum': 'Bombo',
  'Concert Snare Drum': 'Caja', 'Snare Drum': 'Caja',
  'Crash Cymbal': 'Platos', 'Suspended Cymbal': 'Plato suspendido',
  'Tambourine': 'Pandereta', 'Triangle': 'Triángulo', 'Marimba': 'Marimba'
};
export const dimensionLabelsEs = {
  range: 'Tesitura', register: 'Registro extremo', intervals: 'Saltos',
  density: 'Densidad de ataques', endurance: 'Continuidad', tempo: 'Tempo'
};
const rehearsalGroups = {
  flutes: ['Flautas', 'Flautas'], double_reeds: ['Dobles cañas', 'D. cañas'], clarinets: ['Clarinetes', 'Clarinetes'],
  saxophones: ['Saxofones', 'Saxos'], high_brass: ['Metales agudos', 'M. agudos'], low_voices: ['Graves', 'Graves'],
  percussion: ['Percusión', 'Perc.'], strings_rhythm: ['Cuerda y rítmica', 'Cuerda'], other: ['Otros', 'Otros'],
};
const commonKinds = { line: 'Línea común', rhythm: 'Ritmo común' };

export const rehearsalGroupName = group => t((rehearsalGroups[group] || rehearsalGroups.other)[0]);

function splitPartNumber(instrument) {
  const match = instrument.match(/^(.*)\s+(\d+)$/);
  return match ? [match[1], ' ' + match[2]] : [instrument, ''];
}

export function displayInstrumentName(instrument, details = {}) {
  // In English, the catalog's English name or else the name the file gives the part (usually English already).
  if (currentLanguage() === 'en') {
    const translated = details.instrument_label_es && t(details.instrument_label_es);
    return translated && translated !== details.instrument_label_es ? translated : instrument;
  }
  if (details.instrument_label_es) return details.instrument_label_es;
  const [base, number] = splitPartNumber(instrument);
  return (instrumentLabelsEs[base] || base) + number;
}

// A catalog instrument in the language of the interface.
export const instrumentLabel = entry => (currentLanguage() === 'en' && entry?.label_en) || entry?.label_es || '';

export function displayFamilyName(family, details = {}) {
  // The server names the family in Spanish; the same names translate into the language of the interface.
  return t(details.label_es || familyLabelsEs[family] || family);
}

export const findingLabel = code => (findingLabels[code] ? t(findingLabels[code]) : code);
// Step 13: grades 1-6 and index 0-10. An analysis without a declared scale was graded 1-5.
const CURRENT_SCALE = { grades: 6, indexMax: 10, legacy: false };
const LEGACY_SCALE = { grades: 5, indexMax: 5, legacy: true };
export const gradeScaleOf = difficulty => (difficulty?.scale?.grades === 6 ? CURRENT_SCALE : LEGACY_SCALE);

// Aligned with the Grade 1-6 scale of band publishers (decided 2026-10-13): an orientative
// equivalence, not an official certification; the grade calculation itself did not change.
export const gradeLabelsEs = { 1: 'Muy fácil', 2: 'Fácil', 3: 'Intermedio', 4: 'Intermedio avanzado', 5: 'Avanzado', 6: 'Profesional' };

export const gradeOf = (details, scale = CURRENT_SCALE) => Math.max(1, Math.min(scale.grades, Number(details?.grade) || 1));

export function gradeText(details, scale = CURRENT_SCALE) {
  const grade = gradeOf(details, scale);
  return scale.legacy ? t('Grado {grade} de {grades} (escala anterior)', { grade, grades: scale.grades })
    : t('Grado {grade} · {label}', { grade, label: t(gradeLabelsEs[grade]) });
}

// Highest grade first; the technical index breaks ties.
export function byDifficulty(entries, scoreKey) {
  return entries.slice().sort((left, right) =>
    gradeOf(right[1]) - gradeOf(left[1]) || (right[1][scoreKey] || 0) - (left[1][scoreKey] || 0));
}

export function bandIssueText(issue) {
  const instrument = t(issue.label_es);
  if (issue.available === 0) return t('{instrument}: falta en la plantilla; se necesita {required}.', { instrument, required: issue.required });
  return t('{instrument}: hay {available} músicos y se necesitan {required}.', { instrument, available: issue.available, required: issue.required });
}

const unconfirmedStatuses = {
  unknown: 'Sin identificar',
  review: 'Propuesta por los datos del archivo',
  conflict: 'El nombre y los datos del archivo no coinciden',
  shared: 'Propuesto: otras cuentas lo confirmaron con este instrumento',
  ai: 'Propuesto por la IA: revísalo antes de confirmar',
};
export const unconfirmedStatusText = item => t(unconfirmedStatuses[item.status] || unconfirmedStatuses.unknown);

// Catalog options for a part to confirm: the proposal and the candidates first, then the rest.
export function confirmationOptions(item, catalog) {
  const first = [item.proposal, ...(item.candidates || [])].filter(Boolean);
  const byId = new Map((catalog || []).map(entry => [entry.canonical_id, entry]));
  const preferred = first.map(id => byId.get(id)).filter(Boolean);
  return [...preferred, ...(catalog || []).filter(entry => !first.includes(entry.canonical_id))];
}

const measures = (...ranges) => t('c. {range}', { range: ranges.map(range => String(range).replace('-', '–')).join(', ') });
const partList = parts => (parts || []).map(part => displayInstrumentName(part)).join(', ');

// Ensemble rehearsal: who plays the same thing, then subsections, then a tutti to join them.
export function rehearsalBlockTitle(block) {
  if (block.type === 'tutti') return t('Tutti para juntar') + ' · ' + measures(...(block.measure_ranges || []));
  if (block.type === 'common') return t(commonKinds[block.kind] || commonKinds.rhythm) + ' · ' + measures(block.measure_range);
  return t('Seccional · {section}', { section: rehearsalGroupName(block.group) }) + ' · ' + measures(block.measure_range);
}

export function rehearsalBlockDetail(block) {
  const pieces = [block.type === 'tutti' ? t('Toda la banda') : partList(block.parts)];
  if (block.findings?.length) pieces.push(block.findings.map(findingLabel).join(', '));
  return pieces.join(' · ');
}

// Label of the block in the score viewer title.
export function blockScoreLabel(block) {
  if (block.type === 'tutti') return t('Toda la banda');
  if (block.type === 'common') return t(commonKinds[block.kind] || commonKinds.rhythm);
  return rehearsalGroupName(block.group);
}

// Short name that fits a narrow calendar slot; the full description stays in the aria-label.
export function calendarLabel(block) {
  if (block.type === 'tutti') return t('Tutti');
  if (block.type === 'common') return block.kind === 'line' ? t('Línea') : t('Ritmo');
  return t((rehearsalGroups[block.group] || rehearsalGroups.other)[1]);
}

export function omittedBlockText(block) {
  return (block.type === 'common' ? t('Común') : rehearsalGroupName(block.group)) + ' · ' + measures(block.measure_range) + ' · ' + partList(block.parts);
}

// Editable band template: one entry per instrument (or percussionists), keyed as BandFit reports it.
export function initialBandDraft(requirements, profile = {}) {
  return Object.fromEntries((requirements || []).map(item => [item.key, String(profile[item.key] ?? item.required)]));
}

export function readBandProfile(requirements, draft) {
  return Object.fromEntries((requirements || []).map(item =>
    [item.key, Math.max(0, Number.parseInt(draft[item.key] || '0', 10) || 0)]));
}

// difficulty-v2 (2026-10-14): the work's grade comes from its winds and strings; percussion, the rhythm
// section, keyboards and unidentified parts keep their own grade, shown apart.
export const familyCountsForWork = details => details?.counts_for_work !== false;

// difficulty-v3 (2026-10-25): the grade follows the publishers' grading guides, and the analysis says which of
// their criteria sets it.
export const workGradeDetail = difficulty => difficulty?.rubric
  ? t('Según las guías de grados de las editoriales · viento y cuerda; la percusión se muestra aparte')
  : difficulty?.algorithm_version
    ? t('Estimación provisional · viento y cuerda; la percusión y la sección rítmica se muestran aparte')
    : t('Estimación provisional · percentil 80 por familia');

export const gradeReasons = difficulty => (currentLanguage() === 'en' && difficulty?.rubric?.reasons_en) || difficulty?.rubric?.reasons_es || [];
