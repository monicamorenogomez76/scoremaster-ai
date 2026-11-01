import React, { useEffect, useState } from 'react';
import { sourceText } from './explanations.js';
import { loadSubstitutes, transpositionText } from './substitutes.js';
import { t } from './i18n.js';

// Who plays the parts the band has no musician for (2026-10-31). Asked on demand, so viewing spends no AI quota.
export function Substitutes({ workId }) {
  const [state, setState] = useState({ status: 'idle', result: null, error: '' });
  useEffect(() => { setState({ status: 'idle', result: null, error: '' }); }, [workId]);
  const ask = async () => {
    setState({ status: 'loading', result: null, error: '' });
    try {
      setState({ status: 'done', result: await loadSubstitutes(workId), error: '' });
    } catch (failure) {
      setState({ status: 'error', result: null, error: failure.message });
    }
  };
  const { result } = state;
  return <section id="band-substitutes" className="band-substitutes" aria-labelledby="band-substitutes-title">
    <h3 id="band-substitutes-title">{t('Sustitutos para lo que falta')}</h3>
    <button type="button" className="secondary-action" disabled={state.status === 'loading'} onClick={ask}>
      {state.status === 'loading' ? t('Buscando sustitutos…') : t('Proponer sustitutos')}
    </button>
    {state.error && <p className="result-supporting" role="alert">{state.error}</p>}
    <div aria-live="polite">{result && <>
      <p>{result.summary}</p>
      <ul className="result-list">{result.substitutes.map(item => <li key={item.part}>
        <strong>{t('{part} ({missing}): {substitute}', { part: item.part, missing: t(item.missing_label_es),
          substitute: item.instrument ? t(item.label_es) : t('sin sustituto en la plantilla') })}</strong>
        {item.instrument && <span> · {transpositionText(item.write_shift_semitones)}</span>}
        {item.reason && <span className="result-supporting substitute-reason">{item.reason}</span>}
      </li>)}</ul>
      <p className="result-supporting">{sourceText(result)}</p>
    </>}</div>
  </section>;
}
