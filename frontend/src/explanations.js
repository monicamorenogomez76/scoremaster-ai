// Explanations written from ScoreLint's analysis (step 20): by a real AI provider or by the demo,
// which is never presented as AI (original brief).
import { apiJson } from './api.js';

export const explainWork = id => apiJson('/works/' + encodeURIComponent(id) + '/explanation', {},
  'No se pudo explicar la dificultad de la obra.');

const FALLBACKS = {
  timeout: 'La IA no respondió a tiempo',
  rate_limit: 'La IA ha alcanzado su límite de uso',
  invalid: 'La IA dio una respuesta que no coincidía con el análisis',
  error: 'La IA no está disponible',
};

export function sourceText(result) {
  if (result.mode === 'llm') {
    return 'Redactada con IA (' + result.provider + (result.model ? ' · ' + result.model : '') + ') solo a partir del '
      + 'análisis de ScoreLint. Puede contener imprecisiones: contrástala con la partitura.';
  }
  if (result.fallback_reason) return (FALLBACKS[result.fallback_reason] || FALLBACKS.error) + ': se muestra el modo demo, redactado con reglas, sin IA.';
  return 'Modo demo · explicación redactada con reglas a partir del análisis de ScoreLint, sin IA.';
}
