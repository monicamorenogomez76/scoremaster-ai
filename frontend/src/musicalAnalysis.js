// The musical analysis of a work as in a conservatory (2026-11-18): calculated by the server, said here in a musician's
// words. API helpers and pure functions only.
import { apiJson } from './api.js';
import { currentLanguage, t } from './i18n.js';

export const loadMusicalAnalysis = workId => apiJson('/works/' + encodeURIComponent(workId) + '/musical-analysis', {},
  t('No se pudo cargar el análisis musical.'));

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

const CADENCES = () => ({ authentic: t('cadencia auténtica'), half: t('semicadencia') });
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
