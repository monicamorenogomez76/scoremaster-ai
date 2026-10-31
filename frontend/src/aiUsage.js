// The AI usage panel (M5, 2026-10-30), only for the administration: calls per model, tokens, estimated cost, cache hits,
// latency and rejections by reason. The server keeps only counts, times and reasons, never a text.
import { apiJson } from './api.js';
import { currentLanguage, dateLocale, t } from './i18n.js';

export const loadAiUsage = days => apiJson('/admin/ai-usage?days=' + encodeURIComponent(days), {},
  t('No se pudo cargar el uso de la IA.'));

const number = (value, digits = 0) => Number(value || 0).toLocaleString(dateLocale(), { maximumFractionDigits: digits });
const seconds = ms => number(ms / 1000, 1) + ' s';

export const latencyText = latency => (latency?.average == null ? '—'
  : seconds(latency.average) + ' · p95 ' + seconds(latency.p95));

// Dollars, as the providers price their tokens; without prices (the free tier) there is no cost to show.
export function costText(cost, priced) {
  if (!priced || cost == null) return t('Sin precio');
  const amount = number(cost, 4);
  return currentLanguage() === 'en' ? '$' + amount : amount + ' $';
}

export const usageRows = summary => (summary?.models || []).map(item => ({
  model: item.model, calls: number(item.calls), failed: number(item.failed),
  tokens: number(item.input_tokens) + ' / ' + number(item.output_tokens),
  latency: latencyText(item.latency_ms), cost: costText(item.estimated_cost, summary.priced),
}));

const purposes = () => ({ difficulty: t('Explicación de la dificultad'), rehearsal: t('Explicación del ensayo'),
  passage_review: t('Valoración con IA (método B)'), instrument_proposal: t('Propuesta de instrumentos') });
export const purposeLabel = purpose => purposes()[purpose] || purpose;

const outcomes = () => ({ timeout: t('Sin respuesta a tiempo'), rate_limit: t('Límite de uso alcanzado'),
  error: t('Error del proveedor'), invalid: t('Respuesta descartada por la validación') });
export const outcomeLabel = outcome => outcomes()[outcome] || outcome;
