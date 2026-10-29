// Spanish presentation of ScoreLint, BandFit and rehearsal results. Pure functions only.
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

export const rehearsalGroupName = group => (rehearsalGroups[group] || rehearsalGroups.other)[0];

function splitPartNumber(instrument) {
  const match = instrument.match(/^(.*)\s+(\d+)$/);
  return match ? [match[1], ' ' + match[2]] : [instrument, ''];
}

export function displayInstrumentName(instrument, details = {}) {
  if (details.instrument_label_es) return details.instrument_label_es;
  const [base, number] = splitPartNumber(instrument);
  return (instrumentLabelsEs[base] || base) + number;
}

export function displayFamilyName(family, details = {}) {
  return details.label_es || familyLabelsEs[family] || family;
}

export const findingLabel = code => findingLabels[code] || code;
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
  return scale.legacy ? 'Grado ' + grade + ' de ' + scale.grades + ' (escala anterior)' : 'Grado ' + grade + ' · ' + gradeLabelsEs[grade];
}

// Highest grade first; the technical index breaks ties.
export function byDifficulty(entries, scoreKey) {
  return entries.slice().sort((left, right) =>
    gradeOf(right[1]) - gradeOf(left[1]) || (right[1][scoreKey] || 0) - (left[1][scoreKey] || 0));
}

export function bandIssueText(issue) {
  const instrument = issue.label_es;
  if (issue.available === 0) return instrument + ': falta en la plantilla; se necesita ' + issue.required + '.';
  return instrument + ': hay ' + issue.available + ' músicos y se necesitan ' + issue.required + '.';
}

const unconfirmedStatuses = {
  unknown: 'Sin identificar',
  review: 'Propuesta por los datos del archivo',
  conflict: 'El nombre y los datos del archivo no coinciden',
  shared: 'Propuesto: otras cuentas lo confirmaron con este instrumento',
};
export const unconfirmedStatusText = item => unconfirmedStatuses[item.status] || unconfirmedStatuses.unknown;

// Catalog options for a part to confirm: the proposal and the candidates first, then the rest.
export function confirmationOptions(item, catalog) {
  const first = [item.proposal, ...(item.candidates || [])].filter(Boolean);
  const byId = new Map((catalog || []).map(entry => [entry.canonical_id, entry]));
  const preferred = first.map(id => byId.get(id)).filter(Boolean);
  return [...preferred, ...(catalog || []).filter(entry => !first.includes(entry.canonical_id))];
}

const measures = (...ranges) => 'c. ' + ranges.map(range => String(range).replace('-', '–')).join(', ');
const partList = parts => (parts || []).map(part => displayInstrumentName(part)).join(', ');

// Ensemble rehearsal: who plays the same thing, then subsections, then a tutti to join them.
export function rehearsalBlockTitle(block) {
  if (block.type === 'tutti') return 'Tutti para juntar · ' + measures(...(block.measure_ranges || []));
  if (block.type === 'common') return (commonKinds[block.kind] || commonKinds.rhythm) + ' · ' + measures(block.measure_range);
  return 'Seccional · ' + rehearsalGroupName(block.group) + ' · ' + measures(block.measure_range);
}

export function rehearsalBlockDetail(block) {
  const pieces = [block.type === 'tutti' ? 'Toda la banda' : partList(block.parts)];
  if (block.findings?.length) pieces.push(block.findings.map(findingLabel).join(', '));
  return pieces.join(' · ');
}

// Label of the block in the score viewer title.
export function blockScoreLabel(block) {
  if (block.type === 'tutti') return 'Toda la banda';
  if (block.type === 'common') return commonKinds[block.kind] || commonKinds.rhythm;
  return rehearsalGroupName(block.group);
}

// Short name that fits a narrow calendar slot; the full description stays in the aria-label.
export function calendarLabel(block) {
  if (block.type === 'tutti') return 'Tutti';
  if (block.type === 'common') return block.kind === 'line' ? 'Línea' : 'Ritmo';
  return (rehearsalGroups[block.group] || rehearsalGroups.other)[1];
}

export function omittedBlockText(block) {
  return (block.type === 'common' ? 'Común' : rehearsalGroupName(block.group)) + ' · ' + measures(block.measure_range) + ' · ' + partList(block.parts);
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
  ? 'Según las guías de grados de las editoriales · viento y cuerda; la percusión se muestra aparte'
  : difficulty?.algorithm_version
    ? 'Estimación provisional · viento y cuerda; la percusión y la sección rítmica se muestran aparte'
    : 'Estimación provisional · percentil 80 por familia';

export const gradeReasons = difficulty => difficulty?.rubric?.reasons_es || [];
