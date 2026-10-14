// Configuración: the visible name lives in the account; the text size and the theme are preferences of this device.
import { apiJson } from './api.js';

export const textSizes = [['normal', 'Normal', '100%'], ['large', 'Grande', '112.5%'], ['xlarge', 'Muy grande', '125%']];
const KEY = 'scoremaster.text-size';
const deviceStorage = () => { try { return globalThis.localStorage; } catch { return undefined; } };

// Storage may be missing or blocked (private window, cleared data): the app always works without it.
export function loadTextSize(storage = deviceStorage()) {
  try {
    const saved = storage?.getItem(KEY);
    return textSizes.some(([size]) => size === saved) ? saved : 'normal';
  } catch { return 'normal'; }
}

export function saveTextSize(size, storage = deviceStorage()) {
  try { storage?.setItem(KEY, size); } catch { /* the size still applies to this visit */ }
}

// The whole interface is sized in rem, so the root font size scales it.
export function applyTextSize(size, root = globalThis.document?.documentElement) {
  if (root) root.style.fontSize = (textSizes.find(([key]) => key === size) || textSizes[0])[2];
}

// Theme of this device (2026-10-14): the system's choice unless the director picks light or dark.
export const themes = [['auto', 'Automático'], ['light', 'Claro'], ['dark', 'Oscuro']];
const THEME_KEY = 'scoremaster.theme';
let following = null;

export function loadTheme(storage = deviceStorage()) {
  try {
    const saved = storage?.getItem(THEME_KEY);
    return themes.some(([theme]) => theme === saved) ? saved : 'auto';
  } catch { return 'auto'; }
}

export function saveTheme(theme, storage = deviceStorage()) {
  try { storage?.setItem(THEME_KEY, theme); } catch { /* the theme still applies to this visit */ }
}

// Sets data-theme on the root, the attribute the stylesheet reads; in automatic mode it follows the
// system while it changes. Returns the function that stops following it.
export function applyTheme(theme, root = globalThis.document?.documentElement, media = globalThis.matchMedia?.('(prefers-color-scheme: dark)')) {
  following?.();
  following = null;
  if (!root) return () => {};
  if (theme !== 'auto' || !media) {
    root.dataset.theme = theme === 'dark' ? 'dark' : 'light';
    return () => {};
  }
  const follow = () => { root.dataset.theme = media.matches ? 'dark' : 'light'; };
  follow();
  media.addEventListener('change', follow);
  following = () => media.removeEventListener('change', follow);
  return following;
}

export const updateProfile = async displayName => (await apiJson('/auth/me', {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ display_name: displayName }),
}, 'No se pudo guardar el nombre.')).user;
