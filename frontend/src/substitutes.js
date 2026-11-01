// Who plays the parts the band has no musician for (2026-10-31): ScoreLint lists the instruments of the band with
// musicians to spare that reach each part, and the AI (or, without it, the demo) chooses and explains. API helpers and
// pure functions only.
import { apiJson } from './api.js';
import { t } from './i18n.js';

export const loadSubstitutes = workId => apiJson('/works/' + encodeURIComponent(workId) + '/substitutes', {},
  t('No se pudieron proponer sustitutos.'));

// Percussion is left out: its players already share the parts.
export const needsSubstitutes = bandFit => (bandFit?.issues || []).some(issue => issue.key !== 'percussion');

const intervals = () => [t('octava'), t('2ª menor'), t('2ª mayor'), t('3ª menor'), t('3ª mayor'), t('4ª justa'),
  t('4ª aumentada'), t('5ª justa'), t('6ª menor'), t('6ª mayor'), t('7ª menor'), t('7ª mayor')];

export function transpositionText(semitones) {
  if (semitones === null || semitones === undefined) return '';
  if (semitones === 0) return t('Lee la parte tal como está escrita.');
  const size = Math.abs(semitones), octaves = Math.floor(size / 12), rest = size % 12;
  const interval = rest === 0 ? t('una octava') + (octaves > 1 ? ' ×' + octaves : '')
    : t('una {interval}', { interval: intervals()[rest] }) + (octaves ? t(' y una octava') : '');
  return t(semitones > 0 ? 'Transporta la parte {interval} arriba.' : 'Transporta la parte {interval} abajo.', { interval });
}
