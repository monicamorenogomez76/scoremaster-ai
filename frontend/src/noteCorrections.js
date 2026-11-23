// The notes the director corrects in a work (2026-11-22): a pitch, a rest that is a note, a note that is a rest. The
// server finds the note by its part, measure, place and what it is now, and never guesses.
import { apiJson } from './api.js';
import { currentLanguage, t } from './i18n.js';

const path = id => '/works/' + encodeURIComponent(id);
const SOLFEGE = { C: 'do', D: 're', E: 'mi', F: 'fa', G: 'sol', A: 'la', B: 'si' };
const SIGNS = { '-2': '𝄫', '-1': '♭', 0: '', 1: '♯', 2: '𝄪' };
export const STEPS = ['C', 'D', 'E', 'F', 'G', 'A', 'B'];
export const ALTERS = [-2, -1, 0, 1, 2];
const typesEs = { whole: 'redonda', half: 'blanca', quarter: 'negra', eighth: 'corchea', '16th': 'semicorchea',
  '32nd': 'fusa', '64th': 'semifusa', breve: 'cuadrada' };

export const stepLabel = step => (currentLanguage() === 'en' ? step : SOLFEGE[step]);
export const alterLabel = alter => ({ '-2': t('doble bemol'), '-1': t('bemol'), 0: t('natural'), 1: t('sostenido'),
  2: t('doble sostenido') })[alter];

export function pitchLabel(pitch) {
  if (!pitch) return t('silencio');
  const [step, alter, octave] = pitch;
  return stepLabel(step) + SIGNS[alter] + octave;
}

// The beat where the note starts, from 1, with thirds and halves as a musician says them.
function beatLabel(offset) {
  const whole = Math.floor(offset + 1e-6);
  const rest = offset - whole;
  const fraction = [[1 / 3, '⅓'], [2 / 3, '⅔'], [1 / 2, '½'], [1 / 4, '¼'], [3 / 4, '¾']]
    .find(([value]) => Math.abs(rest - value) < 1e-3)?.[1];
  if (rest < 1e-3) return String(whole + 1);
  return fraction ? String(whole + 1) + fraction : (offset + 1).toFixed(2);
}

export function noteLabel(note, index) {
  const kind = typesEs[note.type] ? t(typesEs[note.type]) : note.type;
  const details = [kind, note.chord ? t('en acorde') : null].filter(Boolean).join(', ');
  return t('{n}.ª · tiempo {beat} · {pitch}', { n: index + 1, beat: beatLabel(note.offset), pitch: pitchLabel(note.pitch) })
    + (details ? ' (' + details + ')' : '');
}

export const correctionLabel = item =>
  t('{part} · compás {measure} · {old} → {new}', { part: item.part, measure: item.measure, old: pitchLabel(item.old), new: pitchLabel(item.new) });

// The form opened from a reader's doubt: its part by name and the first measure of its passage.
export function doubtTarget(parts, partName, passage) {
  const part = parts.find(item => item.name === partName);
  return part ? { partId: part.id, measure: String(passage).split('-')[0] } : null;
}

export const workParts = async id => (await apiJson(path(id) + '/notes', {}, t('No se pudieron cargar las partes.'))).parts;
export const measureNotes = (id, partId, measure) =>
  apiJson(path(id) + '/notes?' + new URLSearchParams({ part_id: partId, measure }), {}, t('No se pudo cargar el compás.'));
export const listCorrections = async id => (await apiJson(path(id) + '/corrections', {}, t('No se pudieron cargar las correcciones.'))).corrections;
export const saveCorrection = async (id, partId, measure, note, pitch) => (await apiJson(path(id) + '/corrections', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ part_id: partId, measure, offset: note.offset, old: note.pitch, new: pitch, staff: note.staff ?? null,
    voice: note.voice ?? null }),
}, t('No se pudo guardar la corrección.'))).corrections;
export const undoLastCorrection = async id => (await apiJson(path(id) + '/corrections/last', { method: 'DELETE' },
  t('No se pudo deshacer la corrección.'))).corrections;

// The notes changed on the score (2026-11-23), saved together with one analysis; measures by their printed number.
export const saveEdits = async (id, edits) => (await apiJson(path(id) + '/corrections/batch', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ corrections: edits.map(edit => ({ part_id: edit.partId, number: edit.number, offset: edit.offset,
    old: edit.old, new: edit.new })) }),
}, t('No se pudieron guardar los cambios.'))).corrections;
