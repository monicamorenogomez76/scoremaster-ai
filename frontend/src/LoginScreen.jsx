import React, { useEffect, useState } from 'react';
import { authConfig, register, requestPasswordReset, resetPassword, resetTokenFrom, signIn } from './api.js';

const TITLES = {
  login: ['Acceso', 'Bienvenida'], register: ['Nueva cuenta', 'Crea tu cuenta'],
  forgot: ['Recuperar el acceso', '¿Has olvidado la contraseña?'], reset: ['Recuperar el acceso', 'Elige una contraseña nueva'],
};
const SUBMIT = { login: 'Entrar', register: 'Crear cuenta', forgot: 'Enviar el enlace', reset: 'Guardar y entrar' };

export function LoginScreen({ hidden, onSignedIn }) {
  // A recovery link opens /#reset=<token>: the token is kept and taken out of the address bar and the history.
  const [token] = useState(() => resetTokenFrom(window.location.hash));
  const [mode, setMode] = useState(token ? 'reset' : 'login');
  const [config, setConfig] = useState({});
  const [form, setForm] = useState({ email: '', password: '', name: '' });
  const [state, setState] = useState({ busy: false, error: '', notice: '' });
  useEffect(() => { let current = true; authConfig().then(value => { if (current) setConfig(value); }); return () => { current = false; }; }, []);
  useEffect(() => { if (token) window.history.replaceState(null, '', window.location.pathname + window.location.search); }, [token]);
  const creating = mode === 'register';
  const newPassword = creating || mode === 'reset';
  const update = field => event => setForm(previous => ({ ...previous, [field]: event.target.value }));
  const switchTo = next => { setMode(next); setState({ busy: false, error: '', notice: '' }); };

  const submit = async event => {
    event.preventDefault();
    setState({ busy: true, error: '', notice: '' });
    try {
      if (mode === 'forgot') {
        const notice = await requestPasswordReset(form.email);
        setState({ busy: false, error: '', notice });
        return;
      }
      const user = mode === 'reset' ? await resetPassword(token, form.password)
        : creating ? await register(form.email, form.password, form.name) : await signIn(form.email, form.password);
      setForm(previous => ({ ...previous, password: '' }));
      setState({ busy: false, error: '', notice: '' });
      onSignedIn(user);
    } catch (error) {
      setState({ busy: false, error: error.message, notice: '' });
    }
  };

  return <section id="login-screen" className="login-screen" hidden={hidden}>
    <div className="login-brand">
      <div className="login-brand-mark"><img className="brand-logo" src="/static/brand.svg?v=2" alt="" width="52" height="52" /><span>ScoreMaster</span></div>
      {/* The band seen from the podium, as on the dashboard (identity of 2026-10-26); only decoration. */}
      <svg className="login-brand-arcs" viewBox="0 0 440 236" aria-hidden="true" focusable="false">
        <path d="M40 220 A180 180 0 0 1 400 220" className="login-arc login-arc--percussion" />
        <path d="M82 220 A138 138 0 0 1 358 220" className="login-arc login-arc--brass" />
        <path d="M126 220 A94 94 0 0 1 314 220" className="login-arc login-arc--woodwinds" />
        <path d="M168 220 A52 52 0 0 1 220 168" className="login-arc login-arc--strings" />
      </svg>
      <div className="login-brand-copy">
        <p className="eyebrow">Análisis de repertorio</p>
        <h1>Un espacio de trabajo para tu banda.</h1>
        <p>Evalúa partituras, encuentra los pasajes que requieren atención y organiza el ensayo desde una sola aplicación.</p>
      </div>
      <div className="login-brand-meta"><span>ScoreLint</span><span>BandFit</span><span>RehearsalAI</span></div>
    </div>
    <div className="login-panel">
      <form className="login-card" onSubmit={submit} noValidate>
        <p className="eyebrow">{TITLES[mode][0]}</p>
        <h2>{TITLES[mode][1]}</h2>
        {mode === 'forgot' && <p className="result-supporting">Escribe el email de tu cuenta y te enviaremos un enlace para elegir una contraseña nueva.</p>}
        {creating && <label className="login-field">Nombre
          <input id="login-name" autoComplete="name" maxLength={100} value={form.name} onChange={update('name')} /></label>}
        {mode !== 'reset' && <label className="login-field">Email
          <input id="login-email" type="email" autoComplete="email" required maxLength={254} value={form.email} onChange={update('email')} /></label>}
        {mode !== 'forgot' && <label className="login-field">{mode === 'reset' ? 'Contraseña nueva' : 'Contraseña'}
          <input id="login-password" type="password" required minLength={newPassword ? 10 : undefined} maxLength={256}
            autoComplete={newPassword ? 'new-password' : 'current-password'} value={form.password} onChange={update('password')} /></label>}
        {newPassword && <p className="result-supporting">Al menos 10 caracteres.</p>}
        {state.error && <p id="login-error" className="login-error" role="alert">{state.error}</p>}
        <div role="status">{state.notice && <p id="login-notice" className="login-note">{state.notice}</p>}</div>
        <button id="login-submit" className="login-demo-button" type="submit" disabled={state.busy}>
          {state.busy ? 'Un momento…' : SUBMIT[mode]}</button>
        {mode === 'login' && config.google_enabled && <a id="login-google" className="login-google" href="/auth/google/start">Entrar con Google</a>}
        {mode === 'login' && config.password_reset_enabled && <button id="login-forgot" className="login-switch" type="button"
          onClick={() => switchTo('forgot')}>¿Has olvidado la contraseña?</button>}
        <button id="login-mode" className="login-switch" type="button"
          onClick={() => switchTo(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Crear una cuenta' : creating ? 'Ya tengo cuenta' : 'Volver a entrar'}</button>
        {mode === 'login' && config.demo_email && <div className="login-note">Usuario de prueba: <strong>{config.demo_email}</strong>. La contraseña está en el README.</div>}
      </form>
    </div>
  </section>;
}
