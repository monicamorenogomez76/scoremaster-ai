import test from 'node:test';
import assert from 'node:assert/strict';
import { createFullScoreRenderer, fitScale, pageLabel, pageStartFor } from '../../../frontend/src/score/full-score-renderer.js';

class Element {
  constructor() { this.style = {}; this.children = []; this.attributes = {}; this.clientWidth = 800; this.clientHeight = 600; this.ownerDocument = { createElement: () => new Element() }; }
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return this.attributes[key]; }
  append(node) { this.children.push(node); }
  replaceChildren(...children) { this.children = children; }
  querySelectorAll() { return this.children; }
  remove() { this.removed = true; }
}

function setup({ source = async () => '<score/>', last = 5 } = {}) {
  const container = new Element(), pages = [];
  let version = 0, view;
  const session = { getVersion: () => version, loadSource: source, change() { version++; } };
  const renderer = createFullScoreRenderer({
    container, session, nextFrame: async () => {},
    filter: (_, instrument, range) => { pages.push(range); return '<page/>'; },
    bounds: () => ({ first: 1, last }),
    createDisplay: target => ({
      async load() {},
      render() { const svg = new Element(); svg.attributes = { width: '1000', height: '2000' }; target.append(svg); },
    }),
    onChange: snapshot => { view = snapshot; },
  });
  return { container, session, renderer, pages, view: () => view };
}

test('fits ensemble width without shrinking all staves to viewport height', async () => {
  const state = setup();
  await state.renderer.load();
  const svg = state.container.children[0].children[0];
  assert.equal(svg.style.height, '1536px'); assert.equal(svg.style.width, '768px');
  assert.equal(state.view().page, 'Página 1/2 · compases 1–4');
  assert.equal(state.view().busy, false);
  assert.equal(state.view().canNext, true);
  state.container.clientHeight = 400; state.renderer.fit();
  assert.equal(svg.style.height, '1536px', 'height changes must not shrink notation');
  state.container.clientWidth = 390; state.renderer.fit();
  assert.equal(svg.style.width, '750px', 'small screens retain readable notation with internal scroll');
  state.renderer.clear();
  assert.equal(state.view().visible, false);
  assert.equal(state.view().loaded, false);
  assert.equal(state.container.children.length, 0);
});

test('changing score during asynchronous source load discards the old score', async () => {
  let resolve;
  const state = setup({ source: () => new Promise(done => { resolve = done; }) });
  const pending = state.renderer.load();
  state.session.change(); state.renderer.clear(); resolve('<old/>'); await pending;
  assert.equal(state.view().visible, false);
  assert.equal(state.view().loaded, false);
  assert.equal(state.container.children.length, 0);
  assert.deepEqual(state.pages, []);
});

test('playback turns to the page that contains the sounding measure', async () => {
  const state = setup({ last: 48 });
  await state.renderer.load();
  state.renderer.follow(2, true);
  assert.deepEqual(state.pages, ['1-4'], 'a measure on the current page does not re-render');
  state.renderer.follow(22, true);
  await new Promise(done => setImmediate(done));
  assert.deepEqual(state.pages, ['1-4', '21-24']);
  assert.equal(state.view().page, 'Página 6/12 · compases 21–24');
});

test('page arithmetic keeps four-measure pages aligned to the first measure', () => {
  assert.equal(pageStartFor(70, 80), 78);
  assert.equal(pageLabel(70, 114, 78), 'Página 3/12 · compases 78–81');
  assert.equal(fitScale(1000, 432, 1), .75);
  assert.equal(fitScale(1000, 1032, 1.2), 1.2);
});
