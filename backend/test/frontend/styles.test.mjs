import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';

// One stylesheet with one set of tokens (2026-10-14): the first lines still held the dark theme of the
// pre-React page, overridden rule by rule further down.
const SOURCE = new URL('../../../frontend/src/', import.meta.url);
const css = readFileSync(new URL('styles.css', SOURCE), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

// Selector lists of the top-level rules (outside @media and @keyframes).
function topLevelSelectors(text) {
  const selectors = [];
  let depth = 0, start = 0;
  for (let index = 0; index < text.length; index++) {
    if (text[index] === '{') {
      if (depth === 0) selectors.push(text.slice(start, index).trim());
      depth++;
    } else if (text[index] === '}') {
      depth--;
      if (depth === 0) start = index + 1;
    }
  }
  return selectors.filter(selector => !selector.startsWith('@'));
}

function sourceTokens(directory) {
  const tokens = new Set();
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = new URL(entry.name + (entry.isDirectory() ? '/' : ''), directory);
    if (entry.isDirectory()) { sourceTokens(path).forEach(token => tokens.add(token)); continue; }
    if (!/\.(jsx?|mjs)$/.test(entry.name)) continue;
    for (const [, single, double, template] of readFileSync(path, 'utf8').matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)) {
      for (const token of (single ?? double ?? template).match(/[A-Za-z][\w-]*/g) || []) tokens.add(token);
    }
  }
  return tokens;
}

test('the stylesheet has a single set of light tokens', () => {
  const roots = topLevelSelectors(css).filter(selector => selector === ':root');
  assert.equal(roots.length, 1);
  assert.doesNotMatch(css, /color-scheme:\s*light dark/);
});

test('each top-level selector is declared once', () => {
  const seen = new Map();
  for (const list of topLevelSelectors(css)) seen.set(list, (seen.get(list) || 0) + 1);
  assert.deepEqual([...seen].filter(([, count]) => count > 1).map(([list]) => list), []);
});

test('every class of the stylesheet is used by a component', () => {
  const tokens = sourceTokens(SOURCE);
  // Classes built by concatenation ('calendar-slot--' + group) are covered by their prefix.
  const prefixes = [...tokens].filter(token => token.endsWith('-'));
  const classes = new Set([...css.replace(/\d*\.\d+/g, '').matchAll(/(?<![\w-])\.([A-Za-z][\w-]*)/g)].map(match => match[1]));
  const unused = [...classes].filter(name => !tokens.has(name) && !prefixes.some(prefix => name.startsWith(prefix)));
  assert.deepEqual(unused, []);
});

function declarationsOf(selector) {
  const rule = css.match(new RegExp('(?:^|\\})\\s*' + selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\{([^}]*)\\}'));
  return rule ? rule[1] : '';
}

test('the interface uses the Inter font that main.jsx loads, form controls included', () => {
  // @fontsource-variable/inter registers the family as «Inter Variable»: «Inter» fell back to the system font.
  assert.match(declarationsOf('body'), /font-family:\s*"Inter Variable"/);
  // Selects and textareas kept the browser's own font (Arial) unless a rule of their view set it.
  assert.match(declarationsOf('button, input, select, textarea'), /font:\s*inherit/);
});
