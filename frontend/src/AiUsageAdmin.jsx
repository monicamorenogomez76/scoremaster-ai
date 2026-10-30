import React, { useEffect, useState } from 'react';
import { loadAiUsage, outcomeLabel, purposeLabel, usageRows } from './aiUsage.js';
import { t } from './i18n.js';

const PERIODS = [7, 30, 90];

// Configuración › Uso de la IA (M5, 2026-10-30), only for the administration: what the AI layer spent over the last days.
export function AiUsageAdmin() {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let current = true;
    setSummary(null); setError('');
    loadAiUsage(days).then(found => { if (current) setSummary(found); }).catch(failure => { if (current) setError(failure.message); });
    return () => { current = false; };
  }, [days]);
  const rows = usageRows(summary);
  const counts = entries => Object.entries(entries || {});

  return <section className="surface settings-card ai-usage" aria-labelledby="settings-ai-usage-title">
    <h2 id="settings-ai-usage-title">{t('Uso de la IA')}</h2>
    <p className="result-supporting">{t('Llamadas reales al modelo, respuestas de la caché y respuestas descartadas. Solo se guardan cifras, tiempos y motivos: nunca un texto ni quién lo pidió.')}</p>
    <label htmlFor="ai-usage-days">{t('Periodo')}
      <select id="ai-usage-days" value={days} onChange={event => setDays(Number(event.target.value))}>
        {PERIODS.map(value => <option key={value} value={value}>{t('Últimos {count} días', { count: value })}</option>)}
      </select></label>
    {error && <p className="result-supporting" role="alert">{error}</p>}
    {!summary && !error && <p className="result-supporting" role="status">{t('Cargando el uso de la IA…')}</p>}
    {summary && rows.length === 0 && <p className="result-supporting">{t('Ninguna llamada a la IA en este periodo.')}</p>}
    {rows.length > 0 && <div className="table-scroll">
      <table className="summary-table">
        <caption className="visually-hidden">{t('Uso por modelo')}</caption>
        <thead><tr><th scope="col">{t('Modelo')}</th><th scope="col">{t('Llamadas')}</th><th scope="col">{t('Fallidas')}</th>
          <th scope="col">{t('Tokens (entrada / salida)')}</th><th scope="col">{t('Latencia (media · p95)')}</th>
          <th scope="col">{t('Coste estimado')}</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.model}><th scope="row">{row.model}</th><td>{row.calls}</td><td>{row.failed}</td>
          <td>{row.tokens}</td><td>{row.latency}</td><td>{row.cost}</td></tr>)}</tbody>
      </table>
    </div>}
    {summary && (rows.length > 0 || summary.cache_hits > 0) && <dl className="ai-usage-facts">
      <dt>{t('Llamadas por uso')}</dt>
      <dd>{summary.purposes.map(item => purposeLabel(item.purpose) + ': ' + item.calls).join(' · ') || '—'}</dd>
      <dt>{t('Respuestas de la caché')}</dt><dd>{summary.cache_hits}</dd>
      <dt>{t('Fallos por motivo')}</dt>
      <dd>{counts(summary.failures).map(([reason, total]) => outcomeLabel(reason) + ': ' + total).join(' · ') || '—'}</dd>
      <dt>{t('Descartadas')}</dt>
      <dd>{counts(summary.rejected).map(([reason, total]) => outcomeLabel(reason) + ': ' + total).join(' · ') || '—'}</dd>
    </dl>}
    {summary && !summary.priced && <p className="table-supporting">{t('Sin precio configurado: el plan gratuito no cuesta. Con un plan de pago, define GEMINI_PRICE_INPUT_PER_MTOK y GEMINI_PRICE_OUTPUT_PER_MTOK (dólares por millón de tokens).')}</p>}
  </section>;
}
