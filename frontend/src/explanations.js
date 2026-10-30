// Explanations written from ScoreLint's analysis (step 20): by a real AI provider or by the demo,
// which is never presented as AI (original brief).
import { apiJson } from './api.js';
import { t } from './i18n.js';

export const explainWork = id => apiJson('/works/' + encodeURIComponent(id) + '/explanation', {},
  t('No se pudo explicar la dificultad de la obra.'));

const fallbacks = () => ({
  timeout: t('La IA no respondió a tiempo'),
  rate_limit: t('La IA ha alcanzado su límite de uso'),
  invalid: t('La IA dio una respuesta que no coincidía con el análisis'),
  error: t('La IA no está disponible'),
});

export function sourceText(result) {
  if (result.mode === 'llm') {
    return t('Redactada con IA ({provider}) solo a partir del análisis de ScoreLint. Puede contener imprecisiones: contrástala con la partitura.',
      { provider: result.provider + (result.model ? ' · ' + result.model : '') })
      + (result.cached ? ' ' + t('Respuesta guardada: no gasta cupo.') : '');
  }
  const reasons = fallbacks();
  if (result.fallback_reason) return t('{reason}: se muestra el modo demo, redactado con reglas, sin IA.', { reason: reasons[result.fallback_reason] || reasons.error });
  return t('Modo demo · explicación redactada con reglas a partir del análisis de ScoreLint, sin IA.');
}

export const explainRehearsal = id => apiJson('/rehearsals/' + encodeURIComponent(id) + '/explanation', {},
  t('No se pudo explicar el ensayo.'));
