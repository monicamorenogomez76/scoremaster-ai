// Language of the interface (2026-10-30): Spanish, the language it is written in, or English. The Spanish text is
// the key of its translation, so a text not translated yet still reads in Spanish. A preference of this device,
// like the theme; without one, the browser's language.
import { en } from './locales/en.js';

export const languages = [['es', 'Español'], ['en', 'English']];
const KEY = 'scoremaster.language';
// The catalog's instruments join the English dictionary: the server names them in Spanish in every analysis.
const dictionaries = { en: { ...en } };
const listeners = new Set();
let language = 'es';
const deviceStorage = () => { try { return globalThis.localStorage; } catch { return undefined; } };
const browserLanguages = () => globalThis.navigator?.languages || [globalThis.navigator?.language].filter(Boolean);

export function detectLanguage(preferred = browserLanguages()) {
  const first = (preferred[0] || '').toLowerCase();
  return first.startsWith('en') ? 'en' : 'es';
}

export function loadLanguage(storage = deviceStorage(), preferred = browserLanguages()) {
  try {
    const saved = storage?.getItem(KEY);
    if (languages.some(([code]) => code === saved)) return saved;
  } catch { /* falls back to the browser's language */ }
  return detectLanguage(preferred);
}

export function saveLanguage(code, storage = deviceStorage()) {
  try { storage?.setItem(KEY, code); } catch { /* the language still applies to this visit */ }
}

export const currentLanguage = () => language;

// Locale for dates and numbers in the current language.
export const dateLocale = () => (language === 'en' ? 'en-GB' : 'es-ES');

export function setLanguage(code) {
  language = languages.some(([known]) => known === code) ? code : 'es';
}

// The page declares its language (WCAG 3.1.1) and the app renders again in it.
export function applyLanguage(code, root = globalThis.document?.documentElement) {
  setLanguage(code);
  if (root) root.lang = language;
  listeners.forEach(listener => listener(language));
}

export function addTranslations(instruments) {
  for (const { label_es: spanish, label_en: english } of instruments || []) {
    if (spanish && english && !(spanish in en)) dictionaries.en[spanish] = english;
  }
}

export function onLanguageChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// The text in the current language, with its {placeholders} filled from values.
export function t(text, values = {}) {
  const translated = dictionaries[language]?.[text] ?? text;
  return translated.replace(/\{(\w+)\}/g, (whole, name) => (name in values ? String(values[name]) : whole));
}
