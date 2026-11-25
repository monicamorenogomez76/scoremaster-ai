import React, { useEffect, useRef, useState } from 'react';
import { authConfig } from './api.js';
import { VIEW, noticeSeen, policy, seeNotice } from './privacy.js';
import { t } from './i18n.js';

export const PrivacyLink = () => <a className="privacy-link" href={VIEW}>{t('Privacidad y cookies')}</a>;

// The policy opens over any screen, signed in or not, with its own address: #privacidad.
export function PrivacyPolicy() {
  const dialog = useRef(null);
  const [privacy, setPrivacy] = useState(null);
  useEffect(() => {
    const show = () => {
      if (window.location.hash !== VIEW || dialog.current.open) return;
      dialog.current.showModal();
      dialog.current.scrollTop = 0;
      authConfig().then(config => setPrivacy(config.privacy || {}));
    };
    show();
    window.addEventListener('hashchange', show);
    return () => window.removeEventListener('hashchange', show);
  }, []);
  const closed = () => {
    if (window.location.hash === VIEW) window.history.replaceState(null, '', window.location.pathname + window.location.search);
  };
  return <dialog id="privacy-policy" ref={dialog} className="privacy-dialog" aria-labelledby="privacy-title" onClose={closed}>
    <h2 id="privacy-title">{t('Privacidad y cookies')}</h2>
    {privacy === null ? <p role="status">{t('Cargando…')}</p> : policy(privacy).map(([heading, blocks]) => <section key={heading}>
      <h3>{heading}</h3>
      {blocks.map(block => (Array.isArray(block)
        ? <ul key={block[0]}>{block.map(item => <li key={item}>{item}</li>)}</ul>
        : <p key={block}>{block}</p>))}
    </section>)}
    <button id="privacy-close" className="primary-action" type="button" onClick={() => dialog.current.close()}>{t('Cerrar')}</button>
  </dialog>;
}

export function CookieNotice() {
  const [seen, setSeen] = useState(noticeSeen);
  if (seen) return null;
  return <aside id="cookie-notice" className="cookie-notice" aria-label={t('Aviso de cookies')}>
    <p>{t('Esta aplicación solo usa cookies técnicas, necesarias para mantener tu sesión. No hay cookies de analítica ni de publicidad. YouTube solo se carga si lo permites.')} <PrivacyLink /></p>
    <button id="cookie-accept" className="primary-action" type="button" onClick={() => { seeNotice(); setSeen(true); }}>{t('Entendido')}</button>
  </aside>;
}
