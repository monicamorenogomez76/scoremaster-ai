// Configuración: the visible name lives in the account; the text size is a preference of this device.
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

export const updateProfile = async displayName => (await apiJson('/auth/me', {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ display_name: displayName }),
}, 'No se pudo guardar el nombre.')).user;
