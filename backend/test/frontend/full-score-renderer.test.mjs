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
  assert.equal(state.view().page, 'Compases 1–4 de 5');
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
  assert.equal(state.view().page, 'Compases 21–24 de 48');
});

test('page arithmetic keeps four-measure pages aligned to the first measure', () => {
  assert.equal(pageStartFor(70, 80), 78);
  assert.equal(pageLabel(70, 114, 78), 'Compases 78–81 de 45');
  assert.equal(pageLabel(70, 114, 78, 80), 'Compases 78–80 de 45');
  assert.equal(fitScale(1000, 432, 1), .75);
  assert.equal(fitScale(1000, 1032, 1.2), 1.2);
});

// «Paco el barba» (2026-11-01): its dense snare drum could not fit four measures in the width of the page, so the fourth
// went down to a second line and the page was twice as tall. A page shows the measures that fit in one line.
test('a page shows only the measures that fit in one line, and the next one starts after them', async () => {
  const pages = [];
  const container = new Element();
  let view;
  const renderer = createFullScoreRenderer({
    container, session: { getVersion: () => 0, loadSource: async () => '<score/>' }, nextFrame: async () => {},
    filter: (_, instrument, range) => { pages.push(range); return '<page/>'; }, bounds: () => ({ first: 1, last: 9 }),
    createDisplay: target => {
      const asked = pages[pages.length - 1].split('-').map(Number);
      const count = asked[1] - asked[0] + 1;
      // Three measures fit in a line.
      const lines = count > 3 ? [3, count - 3] : [count];
      return { async load() {}, GraphicSheet: { MusicPages: [{ MusicSystems: lines.map(n => ({ GraphicalMeasures: Array(n) })) }] },
        render() { const svg = new Element(); svg.attributes = { width: '1000', height: '500' }; target.append(svg); } };
    },
    onChange: snapshot => { view = snapshot; },
  });
  const settle = () => new Promise(resolve => setTimeout(resolve, 0));
  await renderer.load();
  assert.deepEqual(pages, ['1-4', '1-3'], 'drawn again with the three that fit');
  assert.equal(view.page, 'Compases 1–3 de 9');
  renderer.next(); await settle();
  assert.deepEqual(pages.slice(2), ['4-7', '4-6'], 'the next page starts after the last measure shown');
  renderer.next(); await settle();
  assert.equal(view.page, 'Compases 7–9 de 9');
  assert.equal(view.canNext, false);
  renderer.previous(); await settle();
  assert.equal(view.page, 'Compases 4–6 de 9', 'back to where it was');
});
