import React, { useEffect, useState } from 'react';
import { authConfig, resendVerification } from './api.js';
import { t } from './i18n.js';

// The email of the account still to confirm (2026-10-30), or what the confirmation link said. Only when the server can
// send the link; the administration and the invitations wait for it in production.
export function EmailNotice({ user, notice }) {
  const [canSend, setCanSend] = useState(false);
  const [state, setState] = useState({ busy: false, message: '' });
  useEffect(() => {
    let current = true;
    authConfig().then(config => { if (current) setCanSend(Boolean(config.password_reset_enabled)); });
    return () => { current = false; };
  }, []);
  const resend = async () => {
    setState({ busy: true, message: '' });
    try { setState({ busy: false, message: await resendVerification() }); }
    catch (failure) { setState({ busy: false, message: failure.message }); }
  };
  const pending = user && !user.email_verified && canSend;
  return <div role="status" className="email-notice-region">
    {notice && <p className="email-notice">{notice}</p>}
    {!notice && pending && <p className="email-notice">
      {t('Confirma tu email con el enlace que te enviamos a {email}. Hasta entonces no puedes administrar ni valorar campañas.', { email: user.email })}
      {' '}<button type="button" className="link-action" disabled={state.busy} onClick={resend}>{t('Enviar otro enlace')}</button>
      {state.message && <span className="email-notice-result"> {state.message}</span>}
    </p>}
  </div>;
}
