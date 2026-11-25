// Asking the work (M6, 2026-11-20): the AI chooses which read-only data of ScoreMaster to read and answers from them;
// the suggested questions, and every question without the AI, are answered by rules, never presented as AI.
import { apiJson } from './api.js';
import { aiFailure } from './aiFailures.js';
import { currentLanguage, t } from './i18n.js';

export const MAX_QUESTION = 300;

export const askWork = (id, body) => apiJson('/works/' + encodeURIComponent(id) + '/questions', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
}, t('No se pudo responder la pregunta.'));

export const askRepertoire = body => apiJson('/repertoire/questions', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
}, t('No se pudo responder la pregunta.'));

export const repertoireSuggestions = () => [
  ['ready', t('¿Qué obras puede tocar ya mi banda?')],
  ['easiest', t('¿Cuáles son las obras más fáciles?')],
  ['hardest', t('¿Cuáles son las obras más difíciles?')],
  ['preparing', t('¿Qué obras estamos preparando?')],
  ['concerts', t('¿Qué tocamos en los próximos conciertos?')],
];

export const suggestions = () => [
  ['grade', t('¿Por qué tiene este grado?')],
  ['passages', t('¿Qué pasajes son los más difíciles?')],
  ['band', t('¿Mi banda la puede tocar?')],
  ['form', t('¿Qué forma tiene?')],
  ['schedule', t('¿Cuándo la ensayamos?')],
];

const toolNames = () => ({ difficulty: t('dificultad'), band: t('banda'), analysis: t('análisis musical'),
  schedule: t('ensayos y conciertos'), find_works: t('tus obras'), work_details: t('detalle de obras'),
  repertoire_schedule: t('conciertos y ensayos'), repertoire_band: t('plantilla de la banda') });

// The repertoire's schedule and band read other data than the work's, under the same names.
const listed = (tools, scope) => {
  const names = toolNames();
  const items = (tools || []).map(tool => names[(scope === 'repertoire' && (tool === 'schedule' || tool === 'band') ? 'repertoire_' : '') + tool] || tool);
  return new Intl.ListFormat(currentLanguage(), { type: 'conjunction' }).format(items);
};

export function answerSource(result, scope = 'work') {
  const read = listed(result.tools, scope);
  if (result.mode === 'llm') {
    const provider = result.provider + (result.model ? ' · ' + result.model : '');
    if (!read) return t('Respondida con IA ({provider}) sin leer datos de la obra.', { provider });
    return t('Respondida con IA ({provider}) a partir de estos datos de ScoreMaster: {data}. Puede contener imprecisiones: contrástala con la partitura.',
      { provider, data: read }) + (result.cached ? ' ' + t('Respuesta guardada: no gasta cupo.') : '');
  }
  const rules = read ? t('se responde con reglas, sin IA, a partir de: {data}.', { data: read }) : t('se responde con reglas, sin IA.');
  if (result.fallback_reason) return aiFailure(result.fallback_reason) + ': ' + rules;
  return read ? t('Respondida con reglas a partir de estos datos de ScoreMaster, sin IA: {data}.', { data: read })
    : t('Respondida con reglas, sin IA.');
}
