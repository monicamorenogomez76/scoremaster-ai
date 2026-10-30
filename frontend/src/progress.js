// What a slow action is doing and for how long (2026-10-07: on Render's free plan analysing or
// planning took minutes behind a fixed message, and it looked as if nothing was happening).
// The server does not report how far it is, so there is no percentage: only the step and the time.
import { t } from './i18n.js';
export const slowNotice = () => t('La primera vez con una obra grande, el servidor puede tardar unos minutos.');
const COUNT_AFTER = 5, EXPLAIN_AFTER = 15;

function elapsedText(seconds) {
  if (seconds < 60) return seconds + ' s';
  const minutes = Math.floor(seconds / 60), rest = seconds % 60;
  return minutes + ' min' + (rest ? ' ' + rest + ' s' : '');
}

export function activityText(label, seconds) {
  if (!label) return '';
  if (seconds < COUNT_AFTER) return label + '…';
  const text = label + '… ' + elapsedText(seconds);
  return seconds < EXPLAIN_AFTER ? text : text + '. ' + slowNotice();
}

const works = count => t(count === 1 ? '{count} obra' : '{count} obras', { count });

// Proposals read the analysis of every work: the more works, the longer the wait.
export function proposalActivity(kind, count) {
  return kind === 'concert' ? t('Calculando la planificación del concierto con el análisis de {works}', { works: works(count) })
    : t('Calculando la agenda con el análisis de {works}', { works: works(count) });
}
