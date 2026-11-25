// Why the AI did not answer, as the server tells it (backend/application/ai.py).
import { t } from './i18n.js';

const reasons = () => ({
  timeout: t('La IA no respondió a tiempo'),
  rate_limit: t('La IA ha alcanzado su límite de uso'),
  invalid: t('La IA dio una respuesta que no coincidía con los datos'),
  model: t('Google no encuentra el modelo de IA configurado (GEMINI_MODEL)'),
  key: t('Google no acepta la clave de IA configurada (GEMINI_API_KEY)'),
  overloaded: t('El servicio de IA está saturado; prueba dentro de unos minutos'),
  error: t('La IA no está disponible'),
});

// An explanation is checked against the analysis; an answer, against the data it read.
export const aiFailure = (reason, checked = 'data') => (reason === 'invalid' && checked === 'analysis'
  ? t('La IA dio una respuesta que no coincidía con el análisis') : reasons()[reason] || reasons().error);
