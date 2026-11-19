// The musical analysis of a work as in a conservatory (2026-11-18): calculated by the server, said here in a musician's
// words. API helpers and pure functions only.
import { apiJson } from './api.js';
import { currentLanguage, t } from './i18n.js';

export const loadMusicalAnalysis = workId => apiJson('/works/' + encodeURIComponent(workId) + '/musical-analysis', {},
  t('No se pudo cargar el análisis musical.'));

// The commentary written about the analysis (2026-11-19): by the AI, or by the demo when it fails.
export const loadAnalysisCommentary = workId => apiJson('/works/' + encodeURIComponent(workId) + '/musical-analysis/commentary', {},
  t('No se pudo redactar el comentario del análisis.'));

const SOLFEGE = { C: 'Do', D: 'Re', E: 'Mi', F: 'Fa', G: 'Sol', A: 'La', B: 'Si' };
const ACCIDENTALS = { b: '♭', '#': '♯' };

// «Mi♭ mayor», «B♭ major».
export function keyName(key) {
  if (!key) return '';
  const letter = key.tonic[0], accidental = ACCIDENTALS[key.tonic.slice(1)] || '';
  const note = (currentLanguage() === 'en' ? letter : SOLFEGE[letter]) + accidental;
  return t(key.mode === 'minor' ? '{note} menor' : '{note} mayor', { note });
}

const RELATIONS = () => ({
  tonic: t('tonalidad principal'), parallel: t('homónimo'), relative: t('relativo'), dominant: t('dominante'),
  subdominant: t('subdominante'), supertonic: t('supertónica'), mediant: t('mediante'), submediant: t('superdominante'),
  subtonic: t('subtónica'), distant: t('tono lejano'),
});
export const relationText = code => RELATIONS()[code] || code;

const TEXTURES = () => ({ tutti: t('tutti'), reduced: t('plantilla reducida'), solo: t('solo') });
export const textureText = code => TEXTURES()[code] || code;

const CADENCES = () => ({ authentic: t('cadencia auténtica'), half: t('semicadencia'), plagal: t('cadencia plagal'),
  deceptive: t('cadencia rota') });
export const cadenceText = kind => CADENCES()[kind] || kind;

// The server names each mark in English words with its value after them: «rehearsal B», «words Trio».
export function markText(mark) {
  const [kind, value] = [mark.split(' ')[0], mark.split(' ').slice(1).join(' ')];
  if (kind === 'rehearsal') return t('letra de ensayo {mark}', { mark: value });
  if (kind === 'words') return '«' + value + '»';
  if (kind === 'ending') return t('casilla {number}', { number: value });
  return {
    'repeat start': t('inicio de repetición'), 'repeat end': t('final de repetición'), 'double barline': t('doble barra'),
    'final barline': t('barra final'), segno: t('segno'), coda: t('coda'),
  }[mark] || mark;
}

// Width of each section on the timeline, in percent of the measures of the work.
export function sectionShares(sections) {
  const lengths = sections.map(section => section.last - section.first + 1);
  const total = lengths.reduce((sum, length) => sum + length, 0);
  return lengths.map(length => Math.round(length * 10000 / total) / 100);
}

// «7 min 47 s».
export function durationText(seconds) {
  const minutes = Math.floor(seconds / 60), rest = seconds % 60;
  return minutes ? t('{minutes} min {seconds} s', { minutes, seconds: rest }) : t('{seconds} s', { seconds: rest });
}

// «c. 1: ♩ = 120 · Allegro»: the tempo written at a measure, with its words.
export const tempoText = entry => t('c. {measure}: {tempo}', { measure: entry.measure,
  tempo: [entry.bpm ? '♩ = ' + entry.bpm : '', ...entry.words].filter(Boolean).join(' · ') });

// The first items of a long list and how many more there are.
export const listText = (items, shown) => items.length > shown
  ? t('{items} y {count} más', { items: items.slice(0, shown).join(', '), count: items.length - shown }) : items.join(', ');

const ENDINGS = () => ({ conclusive: t('conclusiva'), suspensive: t('suspensiva'), open: t('abierta') });

// «4 + 4 (suspensiva, conclusiva)»: the phrases of the tune of a section and how each ends.
export const phrasesText = section => (section.phrases.length
  ? section.structure + ' (' + section.phrases.map(phrase => ENDINGS()[phrase.ending] || phrase.ending).join(', ') + ')' : '—');

// «periodo simétrico, cc. 1–8».
export function periodText(period) {
  const kind = period.kind === 'period' ? (period.symmetric ? t('periodo simétrico') : t('periodo'))
    : (period.symmetric ? t('frase repetida') : t('frase repetida'));
  return t('{kind}, cc. {first}–{last}', { kind, first: period.first, last: period.last });
}

const TEXTURE_KINDS = () => ({ unison: t('unísono'), homorhythmic: t('homorrítmica'),
  melody_and_accompaniment: t('melodía acompañada'), polyphonic: t('polifónica') });
export const textureKindText = kind => (kind ? TEXTURE_KINDS()[kind] || kind : '');

// Below this share of syncopated attacks the rhythm is not called syncopated.
const SYNCOPATED = 0.15;

// «síncopas (50 %) · ostinato: Tuba (cc. 1–4) · imitación: Clarinet (c. 2)».
export function rhythmText(section) {
  const items = [];
  if (section.syncopation >= SYNCOPATED) items.push(t('síncopas ({share} %)', { share: Math.round(section.syncopation * 100) }));
  if (section.ostinatos.length) items.push(t('ostinato: {parts}', { parts: section.ostinatos.map(item =>
    t('{part} (cc. {first}–{last})', item)).join(', ') }));
  if (section.imitations.length) items.push(t('imitación: {parts}', { parts: section.imitations.map(item =>
    t('{part} (c. {measure})', item)).join(', ') }));
  return items.join(' · ') || '—';
}

const STATEMENTS = () => ({ exposition: t('exposición'), return: t('vuelve'), transposed: t('vuelve en otro tono'),
  varied: t('vuelve variado') });

// «T2 (vuelve) · cabeza de T1: Tuba (c. 9)»: the theme of a section and the heads of earlier themes heard in it.
export function themeText(section) {
  const items = [];
  if (section.theme) items.push(section.theme.id + ' (' + (STATEMENTS()[section.theme.statement] || section.theme.statement) + ')');
  for (const motif of section.motifs) items.push(t('cabeza de {theme}: {part} (c. {measure})', motif));
  return items.join(' · ') || '—';
}

const ROLES = () => ({ continuous: t('continua'), punctual: t('puntual') });

// «solo: Flute (c. 9) · percusión: Caja (continua) · agudo extremo: Oboe (c. 22)».
export function orchestrationText(section) {
  const items = [];
  for (const kind of ['solo', 'soli']) {
    const solos = section.solos.filter(item => item.kind === kind);
    const parts = solos.map(item => t('{part} (c. {measure})', item)).join(', ');
    if (solos.length) items.push(kind === 'solo' ? t('solo: {parts}', { parts }) : t('soli: {parts}', { parts }));
  }
  if (section.percussion.length) items.push(t('percusión: {parts}', { parts: section.percussion.map(item =>
    item.part + ' (' + (ROLES()[item.role] || item.role) + ')').join(', ') }));
  if (section.registers.length) items.push(t('agudo extremo: {parts}', { parts: section.registers.map(item =>
    t('{part} (c. {measure})', item)).join(', ') }));
  return items.join(' · ') || '—';
}

// «modula a Sol mayor (dominante, c. 7)»: a key a section moves to, related to the section's own.
export const modulationText = modulation => t('modula a {key} ({relation}, c. {measure})', { key: keyName(modulation.key),
  relation: relationText(modulation.relation), measure: modulation.measure });

// «Si♭», «B♭»: a note as a musician names it.
const noteName = note => (currentLanguage() === 'en' ? note[0] : SOLFEGE[note[0]]) + (ACCIDENTALS[note.slice(1)] || '');

const PEDALS = values => ({ tonic: () => t('pedal de tónica en {note} ({measures})', values),
  dominant: () => t('pedal de dominante en {note} ({measures})', values),
  subdominant: () => t('pedal de subdominante en {note} ({measures})', values), other: () => t('pedal en {note} ({measures})', values) });

// «1,5 acordes por compás · V/V (c. 2) · pedal de tónica en Si♭ (cc. 1–4)».
export function harmonyDetailsText(section) {
  const items = [];
  if (section.harmonic_rhythm) items.push(t('{count} acordes por compás', {
    count: section.harmonic_rhythm.toLocaleString(currentLanguage() === 'en' ? 'en' : 'es') }));
  for (const item of section.secondary_dominants) items.push(t('V/{degree} (c. {measure})', { degree: item.of, measure: item.measure }));
  for (const item of section.pedals) {
    const pedals = PEDALS({ note: noteName(item.note), measures: t('cc. {first}–{last}', item) });
    items.push((pedals[item.degree] || pedals.other)());
  }
  return items.join(' · ');
}

// «hemiolia (cc. 3, 11) · acentos a contratiempo (cc. 17, 18…)»: where the meter is regrouped or contradicted.
export function meterText(section) {
  const items = [];
  if (section.hemiolas.length) items.push(t('hemiolia (cc. {measures})', { measures: listText(section.hemiolas.map(String), 5) }));
  if (section.displaced_accents.length) items.push(t('acentos a contratiempo (cc. {measures})', {
    measures: listText(section.displaced_accents.map(String), 5) }));
  return items.join(' · ');
}

const CONTOURS = () => ({ arch: t('en arco'), inverted_arch: t('en arco invertido'), ascending: t('ascendente'),
  descending: t('descendente'), level: t('plano') });
const MOTIONS = () => ({ conjunct: t('por grados'), disjunct: t('por saltos') });

// «Si♭4–La5 (11 semitonos), en arco, por grados»: the range of a theme (sounding) and its shape.
export function themeShapeText(theme) {
  const pitch = name => noteName(name.replace(/-?\d+$/, '')) + name.match(/-?\d+$/)[0];
  return t('{lowest}–{highest} ({range} semitonos)', { lowest: pitch(theme.lowest), highest: pitch(theme.highest), range: theme.range })
    + ', ' + (CONTOURS()[theme.contour] || theme.contour) + ', ' + (MOTIONS()[theme.motion] || theme.motion);
}
