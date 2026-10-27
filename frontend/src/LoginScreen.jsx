import React, { useEffect, useState } from 'react';
import { authConfig, register, signIn } from './api.js';

export function LoginScreen({ hidden, onSignedIn }) {
  const [mode, setMode] = useState('login');
  const [config, setConfig] = useState({});
  const [form, setForm] = useState({ email: '', password: '', name: '' });
  const [state, setState] = useState({ busy: false, error: '' });
  useEffect(() => { let current = true; authConfig().then(value => { if (current) setConfig(value); }); return () => { current = false; }; }, []);
  const creating = mode === 'register';
  const update = field => event => setForm(previous => ({ ...previous, [field]: event.target.value }));

  const submit = async event => {
    event.preventDefault();
    setState({ busy: true, error: '' });
    try {
      const user = creating ? await register(form.email, form.password, form.name) : await signIn(form.email, form.password);
      setForm(previous => ({ ...previous, password: '' }));
      setState({ busy: false, error: '' });
      onSignedIn(user);
    } catch (error) {
      setState({ busy: false, error: error.message });
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
        <p className="eyebrow">{creating ? 'Nueva cuenta' : 'Acceso'}</p>
        <h2>{creating ? 'Crea tu cuenta' : 'Bienvenida'}</h2>
        {creating && <label className="login-field">Nombre
          <input id="login-name" autoComplete="name" maxLength={100} value={form.name} onChange={update('name')} /></label>}
        <label className="login-field">Email
          <input id="login-email" type="email" autoComplete="email" required maxLength={254} value={form.email} onChange={update('email')} /></label>
        <label className="login-field">Contraseña
          <input id="login-password" type="password" required minLength={creating ? 10 : undefined} maxLength={256}
            autoComplete={creating ? 'new-password' : 'current-password'} value={form.password} onChange={update('password')} /></label>
        {creating && <p className="result-supporting">Al menos 10 caracteres.</p>}
        {state.error && <p id="login-error" className="login-error" role="alert">{state.error}</p>}
        <button id="login-submit" className="login-demo-button" type="submit" disabled={state.busy}>
          {state.busy ? 'Un momento…' : creating ? 'Crear cuenta' : 'Entrar'}</button>
        {config.google_enabled && <a id="login-google" className="login-google" href="/auth/google/start">Entrar con Google</a>}
        <button id="login-mode" className="login-switch" type="button"
          onClick={() => { setMode(creating ? 'login' : 'register'); setState({ busy: false, error: '' }); }}>
          {creating ? 'Ya tengo cuenta' : 'Crear una cuenta'}</button>
        {config.demo_email && <div className="login-note">Usuario de prueba: <strong>{config.demo_email}</strong>. La contraseña está en el README.</div>}
      </form>
    </div>
  </section>;
}
