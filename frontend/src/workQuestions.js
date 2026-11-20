// Asking the work (M6, 2026-11-20): the AI chooses which read-only data of ScoreMaster to read and answers from them;
// the suggested questions, and every question without the AI, are answered by rules, never presented as AI.
import { apiJson } from './api.js';
import { currentLanguage, t } from './i18n.js';

export const MAX_QUESTION = 300;

export const askWork = (id, body) => apiJson('/works/' + encodeURIComponent(id) + '/questions', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
}, t('No se pudo responder la pregunta.'));

export const suggestions = () => [
  ['grade', t('¿Por qué tiene este grado?')],
  ['passages', t('¿Qué pasajes son los más difíciles?')],
  ['band', t('¿Mi banda la puede tocar?')],
  ['form', t('¿Qué forma tiene?')],
  ['schedule', t('¿Cuándo la ensayamos?')],
];

const toolNames = () => ({ difficulty: t('dificultad'), band: t('banda'), analysis: t('análisis musical'),
  schedule: t('ensayos y conciertos') });

const fallbacks = () => ({
  timeout: t('La IA no respondió a tiempo'),
  rate_limit: t('La IA ha alcanzado su límite de uso'),
  invalid: t('La IA dio una respuesta que no coincidía con los datos'),
  error: t('La IA no está disponible'),
});

const listed = tools => {
  const names = toolNames();
  const items = (tools || []).map(tool => names[tool] || tool);
  return new Intl.ListFormat(currentLanguage(), { type: 'conjunction' }).format(items);
};

export function answerSource(result) {
  const read = listed(result.tools);
  if (result.mode === 'llm') {
    const provider = result.provider + (result.model ? ' · ' + result.model : '');
    if (!read) return t('Respondida con IA ({provider}) sin leer datos de la obra.', { provider });
    return t('Respondida con IA ({provider}) a partir de estos datos de ScoreMaster: {data}. Puede contener imprecisiones: contrástala con la partitura.',
      { provider, data: read }) + (result.cached ? ' ' + t('Respuesta guardada: no gasta cupo.') : '');
  }
  const rules = read ? t('se responde con reglas, sin IA, a partir de: {data}.', { data: read }) : t('se responde con reglas, sin IA.');
  if (result.fallback_reason) {
    const reasons = fallbacks();
    return (reasons[result.fallback_reason] || reasons.error) + ': ' + rules;
  }
  return read ? t('Respondida con reglas a partir de estos datos de ScoreMaster, sin IA: {data}.', { data: read })
    : t('Respondida con reglas, sin IA.');
}
