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

// Colours that mean something by themselves keep their value in both themes: the sections of the
// rehearsal calendar, the concert/rehearsal events, the sign-in illustration and the video frame.
const FIXED_COLOURS = /calendar-slot--|\.event-|\.login-brand|\.video-player/;

test('the interface colours come from the tokens, so the dark theme reaches every component', () => {
  const literal = /#[0-9a-f]{3,8}\b|rgba?\(|\b(white|black)\b/i;
  const offenders = [];
  const body = css.replace(/:root(\[[^\]]*\])?\s*\{[^}]*\}/g, '');
  for (const [, selector, declarations] of body.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (FIXED_COLOURS.test(selector)) continue;
    for (const declaration of declarations.split(';')) {
      const [property, value = ''] = declaration.split(/:(.*)/s).map(part => part.trim());
      if (/^(color|background(-color)?|border(-[a-z]+)*|outline(-color)?)$/.test(property) && literal.test(value)) {
        offenders.push(selector.trim() + ' { ' + property + ': ' + value + ' }');
      }
    }
  }
  assert.deepEqual(offenders, []);
});

test('the dark theme redefines every colour token of the light one', () => {
  const tokens = block => new Set([...block.matchAll(/--([\w-]+):/g)].map(match => match[1]));
  const light = tokens(css.match(/:root\s*\{([^}]*)\}/)[1]);
  const darkBlock = css.match(/:root\[data-theme="dark"\]\s*\{([^}]*)\}/);
  assert.ok(darkBlock, 'a :root[data-theme="dark"] block');
  const dark = tokens(darkBlock[1]);
  assert.deepEqual([...light].filter(token => !dark.has(token) && !token.startsWith('radius') && !token.startsWith('ease') && !token.startsWith('duration')), []);
  assert.match(darkBlock[1], /color-scheme:\s*dark/);
});

// Visual language of 2026-10-14: one easing curve for every movement, layered shadows from the tokens
// (one set per theme) and a pressed state on the actions.
function declarations(property) {
  const body = css.replace(/:root(\[[^\]]*\])?\s*\{[^}]*\}/g, '');
  return [...body.matchAll(/([^{}]+)\{([^{}]*)\}/g)].flatMap(([, selector, block]) => block.split(';')
    .map(declaration => declaration.split(/:(.*)/s).map(part => part.trim()))
    .filter(([name]) => name === property).map(([, value]) => [selector.trim(), value]));
}

test('every movement uses the shared easing curve, never transition: all', () => {
  assert.match(css.match(/:root\s*\{([^}]*)\}/)[1], /--ease-out:\s*cubic-bezier\(0\.16, 1, 0\.3, 1\)/);
  const transitions = declarations('transition');
  assert.ok(transitions.length > 0);
  // «none» is the reduced-motion preference, which removes them all.
  assert.deepEqual(transitions.filter(([, value]) => !value.startsWith('none') && (/\ball\b/.test(value) || !value.includes('var(--ease-out)'))), []);
});

test('shadows come from the tokens, so each theme has its own', () => {
  const literal = declarations('box-shadow').filter(([, value]) => /#[0-9a-f]{3,8}\b|rgba?\(/i.test(value));
  assert.deepEqual(literal, []);
  for (const token of ['--shadow-1', '--shadow-2', '--shadow-3']) {
    assert.match(css.match(/:root\s*\{([^}]*)\}/)[1], new RegExp(token + ':'));
    assert.match(css.match(/:root\[data-theme="dark"\]\s*\{([^}]*)\}/)[1], new RegExp(token + ':'));
  }
});

test('actions answer to the pointer: hover, keyboard focus and a pressed state', () => {
  for (const action of ['.primary-action', '.secondary-action', '.danger-action', '.link-action', '.nav-item']) {
    assert.ok(new RegExp('\\' + action + '[^{,]*:active').test(css), action + ':active');
  }
});
