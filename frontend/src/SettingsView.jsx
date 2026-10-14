import React, { useEffect, useState } from 'react';
import { applyTextSize, applyTheme, loadTextSize, loadTheme, saveTextSize, saveTheme, textSizes, themes, updateProfile } from './settings.js';
import { View } from './View.jsx';

// Configuración (author's mock-up): the account's visible name and the text size and theme of this device.
export function SettingsView({ active, user, onUserChanged }) {
  const [name, setName] = useState(user?.display_name || '');
  const [size, setSize] = useState(loadTextSize);
  const [theme, setTheme] = useState(loadTheme);
  const [status, setStatus] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => { setName(user?.display_name || ''); }, [user?.email, user?.display_name]);

  const saveName = async event => {
    event.preventDefault();
    setSaving(true); setStatus('');
    try { onUserChanged({ ...user, ...(await updateProfile(name.trim())) }); setStatus('Nombre guardado.'); }
    catch (failure) { setStatus(failure.message); } finally { setSaving(false); }
  };
  const chooseSize = value => { setSize(value); saveTextSize(value); applyTextSize(value); };
  const chooseTheme = value => { setTheme(value); saveTheme(value); applyTheme(value); };

  return <View name="settings" active={active} eyebrow="Configuración" title="Configuración"
    description="Tu cuenta y las preferencias de la aplicación.">
    <div className="settings-grid">
      <form className="surface settings-card" onSubmit={saveName} aria-labelledby="settings-account-title">
        <h2 id="settings-account-title">Tu cuenta</h2>
        <label>Nombre visible<input type="text" required maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
        <p className="result-supporting">Email: {user?.email || '—'}</p>
        <button type="submit" className="primary-action" disabled={saving || !name.trim()}>{saving ? 'Guardando…' : 'Guardar nombre'}</button>
        {status && <p className="result-supporting" role="status">{status}</p>}
      </form>
      <section className="surface settings-card" aria-labelledby="settings-display-title">
        <h2 id="settings-display-title">Pantalla</h2>
        <fieldset className="text-size-options">
          <legend>Tamaño del texto</legend>
          {textSizes.map(([value, label]) => <label key={value} className="weekday-option">
            <input type="radio" name="text-size" value={value} checked={size === value} onChange={() => chooseSize(value)} />{label}
          </label>)}
        </fieldset>
        <fieldset className="text-size-options">
          <legend>Tema</legend>
          {themes.map(([value, label]) => <label key={value} className="weekday-option">
            <input type="radio" name="theme" value={value} checked={theme === value} onChange={() => chooseTheme(value)} />{label}
          </label>)}
        </fieldset>
        <p className="result-supporting">Se guardan en este dispositivo. Automático sigue el modo claro u oscuro del sistema.</p>
      </section>
    </div>
  </View>;
}
