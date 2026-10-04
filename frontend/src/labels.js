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
const bandProfileNames = {
  'Flautín': 'Piccolo', 'Flauta': 'Flute', 'Oboe': 'Oboe',
  'Clarinete': 'Clarinet', 'Clarinete en Si bemol': 'B♭ Clarinet',
  'Clarinete alto': 'Alto Clarinet', 'Clarinete bajo': 'Bass Clarinet',
  'Fagot': 'Bassoon', 'Saxofón alto': 'Alto Saxophone',
  'Saxofón tenor': 'Tenor Saxophone', 'Saxofón barítono': 'Baritone Saxophone',
  'Trompeta en Si bemol': 'B♭ Trumpet', 'Trompa en Fa': 'Horn in F',
  'Trombón': 'Trombone', 'Bombardino': 'Euphonium', 'Tuba': 'Tuba',
  'Contrabajo': 'Double Bass', 'Timbales': 'Timpani', 'Xilófono': 'Xylophone',
  'Glockenspiel': 'Glockenspiel', 'Campanas tubulares': 'Chimes',
  'Bombo': 'Concert Bass Drum', 'Caja': 'Concert Snare Drum',
  'Plato suspendido': 'Suspended Cymbal', 'Platos': 'Crash Cymbal',
  'Pandereta': 'Tambourine', 'Triángulo': 'Triangle', 'Marimba': 'Marimba'
};
export const dimensionLabelsEs = {
  range: 'Tesitura', register: 'Registro extremo', intervals: 'Saltos',
  density: 'Densidad de ataques', endurance: 'Continuidad', tempo: 'Tempo'
};
const sharedLabels = { unison: 'Unísono', octave: 'Octavas', rhythm: 'Mismo ritmo' };

function splitPartNumber(instrument) {
  const match = instrument.match(/^(.*)\s+(\d+)$/);
  return match ? [match[1], ' ' + match[2]] : [instrument, ''];
}

export function displayInstrumentName(instrument, details = {}) {
  if (details.instrument_label_es) return details.instrument_label_es;
  const [base, number] = splitPartNumber(instrument);
  return (instrumentLabelsEs[base] || base) + number;
}

export function apiInstrumentName(instrument) {
  const [base, number] = splitPartNumber(instrument);
  return (bandProfileNames[base] || base) + number;
}

export function displayFamilyName(family, details = {}) {
  return details.label_es || familyLabelsEs[family] || family;
}

export const findingLabel = code => findingLabels[code] || code;
export const gradeOf = details => Math.max(1, Math.min(5, Number(details?.grade) || 1));

// Highest grade first; the technical index breaks ties.
export function byDifficulty(entries, scoreKey) {
  return entries.slice().sort((left, right) =>
    gradeOf(right[1]) - gradeOf(left[1]) || (right[1][scoreKey] || 0) - (left[1][scoreKey] || 0));
}

export function bandIssueText(issue) {
  const instrument = displayInstrumentName(issue.instrument);
  if (issue.available === 0) return instrument + ': falta en la plantilla; se necesita ' + issue.required + '.';
  return instrument + ': hay ' + issue.available + ' músicos y se necesitan ' + issue.required + '.';
}

const measures = (...ranges) => 'c. ' + ranges.map(range => String(range).replace('-', '–')).join(', ');
const partList = parts => (parts || []).map(part => displayInstrumentName(part)).join(', ');

// Ensemble rehearsal: sectional blocks per common passage, then a tutti to join them.
export function rehearsalBlockTitle(block) {
  if (block.type === 'tutti') return 'Tutti para juntar · ' + measures(...(block.measure_ranges || []));
  return 'Seccional · ' + displayFamilyName(block.section) + ' · ' + measures(block.measure_range);
}

export function rehearsalBlockDetail(block) {
  const pieces = [block.type === 'tutti' ? 'Toda la banda' : partList(block.parts)];
  if (block.findings?.length) pieces.push(block.findings.map(findingLabel).join(', '));
  for (const item of block.shared || []) {
    pieces.push((sharedLabels[item.kind] || item.kind) + ': ' + item.parts.map(part => displayInstrumentName(part)).join(' y ')
      + (item.measure_range ? ' (' + measures(item.measure_range) + ')' : ''));
  }
  return pieces.join(' · ');
}

export function omittedBlockText(block) {
  return displayFamilyName(block.section) + ' · ' + measures(block.measure_range) + ' · ' + partList(block.parts);
}

export const uniqueParts = parts => Array.from(new Set(parts || []));

// Editable band template: one entry per score part, keyed by the API instrument name.
export function initialBandDraft(parts, profile = {}) {
  return Object.fromEntries(uniqueParts(parts).map(part => {
    const key = apiInstrumentName(part);
    return [key, String(profile[key] ?? 1)];
  }));
}

export function readBandProfile(parts, draft) {
  return Object.fromEntries(uniqueParts(parts).map(part => {
    const key = apiInstrumentName(part);
    return [key, Math.max(0, Number.parseInt(draft[key] || '0', 10) || 0)];
  }));
}
