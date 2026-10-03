import React from 'react';

export function LoginScreen({ hidden, onEnter }) {
  return <section id="login-screen" className="login-screen" hidden={hidden}>
    <div className="login-brand">
      <div className="login-brand-mark"><img className="brand-logo" src="/static/brand.svg" alt="" width="44" height="44" /><span>ScoreMaster</span></div>
      <div className="login-brand-copy">
        <p className="eyebrow">Análisis de repertorio</p>
        <h1>Un espacio de trabajo para tu banda.</h1>
        <p>Evalúa partituras, encuentra los pasajes que requieren atención y organiza el ensayo desde una sola aplicación.</p>
      </div>
      <div className="login-brand-meta"><span>ScoreLint</span><span>BandFit</span><span>RehearsalAI</span></div>
    </div>
    <div className="login-panel">
      <div className="login-card">
        <p className="eyebrow">Acceso de demostración</p>
        <h2>Bienvenida</h2>
        <p>Explora el análisis musical determinista y sus herramientas de ensayo.</p>
        <button id="enter-demo" className="login-demo-button" type="button" onClick={onEnter}>Entrar en modo demo</button>
        <div className="login-note">Esta demo no usa cuentas reales. La plantilla solo se conserva mientras dure la sesión.</div>
      </div>
    </div>
  </section>;
}
