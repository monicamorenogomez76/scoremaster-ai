import React, { useState } from 'react';
import { deleteAccount } from './api.js';
import { t } from './i18n.js';

// The rights of access, portability and erasure (2026-11-25), in Configuración › Privacidad.
export function AccountData({ user, onDeleted }) {
  const [asking, setAsking] = useState(false);
  const [confirmation, setConfirmation] = useState('');
  const [state, setState] = useState({ busy: false, error: '' });
  const withPassword = user?.has_password !== false;
  const close = () => { setAsking(false); setConfirmation(''); setState({ busy: false, error: '' }); };
  const submit = async event => {
    event.preventDefault();
    setState({ busy: true, error: '' });
    try {
      await deleteAccount(withPassword ? { password: confirmation } : { email: confirmation });
      close();
      onDeleted();
    } catch (failure) { setState({ busy: false, error: failure.message }); }
  };
  return <>
    <p><a id="account-download" className="secondary-action" href="/auth/me/data" download>{t('Descargar mis datos')}</a></p>
    <p className="result-supporting">{t('Un archivo zip con tus datos y tus partituras.')}</p>
    {!asking && <button id="account-delete" className="secondary-action" type="button" onClick={() => setAsking(true)}>{t('Borrar mi cuenta')}</button>}
    {asking && <form className="account-delete" onSubmit={submit}>
      <p>{t('Se borran para siempre tu cuenta, tus obras, bandas, conciertos, ensayos, campañas y valoraciones. No se puede deshacer.')}</p>
      <label className="login-field">{withPassword ? t('Escribe tu contraseña para confirmarlo') : t('Escribe el email de tu cuenta para confirmarlo')}
        <input id="account-confirmation" type={withPassword ? 'password' : 'email'} autoComplete={withPassword ? 'current-password' : 'email'} required
          maxLength={254} value={confirmation} aria-describedby={state.error ? 'account-error' : undefined} aria-invalid={Boolean(state.error)}
          onChange={event => setConfirmation(event.target.value)} /></label>
      {state.error && <p id="account-error" className="login-error" role="alert">{state.error}</p>}
      <div className="score-edit-actions">
        <button id="account-delete-confirm" className="primary-action" type="submit" disabled={state.busy || !confirmation}>
          {state.busy ? t('Un momento…') : t('Borrar mi cuenta para siempre')}</button>
        <button className="secondary-action" type="button" disabled={state.busy} onClick={close}>{t('Cancelar')}</button>
      </div>
    </form>}
  </>;
}
