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
    // t(count === 1 ? 'one' : 'many', …): both texts.
    for (const [, , one, , many] of text.matchAll(/\bt\([^'"()?]*\?\s*(['"])([^'"]*)\1\s*:\s*(['"])([^'"]*)\3/g)) {
      keys.set(one, name); keys.set(many, name);
    }
  }
  assert.ok(keys.size > 50, 'the interface is marked');
  const missing = [...keys].filter(([key]) => !(key in en)).map(([key, name]) => `${name}: ${key}`);
  assert.deepEqual(missing, []);
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort().join();
  const mismatched = Object.entries(en).filter(([key, value]) => placeholders(key) !== placeholders(value));
  assert.deepEqual(mismatched, []);
});

test('no Spanish text is translated twice', () => {
  const source = readFileSync(new URL('../../../frontend/src/locales/en.js', import.meta.url), 'utf8');
  const keys = [...source.matchAll(/^ {2}(['"])((?:(?!\1).)+)\1:/gm)].map(match => match[2]);
  assert.equal(keys.length, Object.keys(en).length);
});

// Tables of options and labels keep their Spanish texts and are translated where they are shown, so the scan above
// does not see them: each of their texts needs its English one too.
test('the tables of options and labels are translated', async () => {
  const src = '../../../frontend/src/';
  const [ev, lb, ic, lib, rh, st, ex] = await Promise.all(['evaluations', 'labels', 'instrumentCatalog', 'library', 'rehearsals',
    'settings', 'externalGrades'].map(name => import(src + name + '.js')));
  const texts = [
    ...ev.GRADE_RUBRIC.flatMap(item => [item.label, item.description]), ...ev.EXPERIENCE_OPTIONS.map(([, label]) => label),
    ...Object.values(ev.PRIORITY_LABELS), ...['draft', 'open', 'closed'].map(ev.statusLabel),
    ...Object.values(lb.findingLabels), ...Object.values(lb.gradeLabelsEs), ...Object.values(lb.bandStatusLabels),
    ...Object.values(lb.dimensionLabelsEs), ...[ic.instrumentSections, ic.instrumentKeys, ic.instrumentGroups].flat().map(([, label]) => label),
    ...Object.values(lib.preparationLabelsEs), ...rh.reviewStatusOptions.map(([, label]) => label),
    ...[st.textSizes, st.themes, ex.scales].flat().map(([, label]) => label),
  ];
  assert.deepEqual(texts.filter(text => !(text in en)), []);
});

test('the instrument catalog adds the English name of each instrument the server names in Spanish', async () => {
  const { addTranslations } = await import('../../../frontend/src/i18n.js');
  const { displayInstrumentName } = await import('../../../frontend/src/labels.js');
  addTranslations([{ label_es: 'Clarinete en Si bemol', label_en: 'B♭ Clarinet' }, { label_es: 'Gaita', label_en: '' }]);
  setLanguage('en');
  assert.equal(t('Clarinete en Si bemol'), 'B♭ Clarinet');
  assert.equal(t('Gaita'), 'Gaita', 'an instrument without its English name keeps the Spanish one');
  assert.equal(displayInstrumentName('Clarinet 1', { instrument_label_es: 'Clarinete en Si bemol' }), 'B♭ Clarinet');
  assert.equal(displayInstrumentName('Clarinet 1'), 'Clarinet 1', 'in English the name in the file is kept');
  assert.equal(displayInstrumentName('Clarinet', { instrument_label_es: 'Clarinete' }), 'Clarinet', 'also when the catalog has no English name');
  setLanguage('es');
  assert.equal(displayInstrumentName('Clarinet 1'), 'Clarinete 1');
});
