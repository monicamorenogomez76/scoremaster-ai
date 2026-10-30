import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';
import {
  applyLanguage, currentLanguage, detectLanguage, languages, loadLanguage, onLanguageChange, saveLanguage, setLanguage, t,
} from '../../../frontend/src/i18n.js';
import { en } from '../../../frontend/src/locales/en.js';

function storage(values = {}) {
  return { getItem: key => (key in values ? values[key] : null), setItem: (key, value) => { values[key] = String(value); }, values };
}

test('the interface speaks Spanish or English, and each language names itself in its own language', () => {
  assert.deepEqual(languages, [['es', 'Español'], ['en', 'English']]);
});

test('the Spanish text is the key: English translates it, and what is not translated stays in Spanish', () => {
  setLanguage('es');
  assert.equal(t('Resumen'), 'Resumen');
  assert.equal(t('Hola, {name}', { name: 'Mónica' }), 'Hola, Mónica');
  setLanguage('en');
  assert.equal(t('Resumen'), 'Overview');
  assert.equal(t('Un texto que aún no tiene traducción'), 'Un texto que aún no tiene traducción');
  setLanguage('es');
});

test('the language comes from this device, else from the browser, else Spanish', () => {
  assert.equal(detectLanguage(['en-GB', 'es']), 'en');
  assert.equal(detectLanguage(['gl-ES', 'es-ES']), 'es');
  assert.equal(detectLanguage(['fr-FR']), 'es');
  assert.equal(detectLanguage([]), 'es');
  const local = storage();
  assert.equal(loadLanguage(local, ['en-US']), 'en');
  saveLanguage('es', local);
  assert.equal(local.values['scoremaster.language'], 'es');
  assert.equal(loadLanguage(local, ['en-US']), 'es');
  assert.equal(loadLanguage(storage({ 'scoremaster.language': 'xx' }), ['es']), 'es');
  const blocked = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(loadLanguage(blocked, ['en']), 'en');
  assert.doesNotThrow(() => saveLanguage('en', blocked));
});

test('changing the language sets the page language and tells the app to render again', () => {
  const root = { lang: 'es' };
  const seen = [];
  const stop = onLanguageChange(language => seen.push(language));
  applyLanguage('en', root);
  assert.equal(root.lang, 'en');
  assert.equal(currentLanguage(), 'en');
  applyLanguage('es', root);
  stop();
  applyLanguage('en', root);
  assert.deepEqual(seen, ['en', 'es']);
  applyLanguage('es', root);
});

// Every t('…') of the interface has its English text, with the same {placeholders}.
function sources(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = new URL(entry.name + (entry.isDirectory() ? '/' : ''), directory);
    if (entry.isDirectory()) return entry.name === 'locales' ? [] : sources(path);
    return /\.jsx?$/.test(entry.name) ? [[entry.name, readFileSync(path, 'utf8')]] : [];
  });
}

test('every text of the interface marked for translation is translated', () => {
  const keys = new Map();
  for (const [name, text] of sources(new URL('../../../frontend/src/', import.meta.url))) {
    for (const [, , key] of text.matchAll(/\bt\((['"])((?:(?!\1)[^\\]|\\.)*)\1/g)) keys.set(key.replace(/\\(.)/g, '$1'), name);
  }
  assert.ok(keys.size > 50, 'the interface is marked');
  const missing = [...keys].filter(([key]) => !(key in en)).map(([key, name]) => `${name}: ${key}`);
  assert.deepEqual(missing, []);
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort().join();
  const mismatched = Object.entries(en).filter(([key, value]) => placeholders(key) !== placeholders(value));
  assert.deepEqual(mismatched, []);
});
