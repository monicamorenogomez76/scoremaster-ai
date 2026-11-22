import test from 'node:test';
import assert from 'node:assert/strict';
import { createFullScoreRenderer, fitScale, pageLabel, pageStartFor } from '../../../frontend/src/score/full-score-renderer.js';

class Element {
  constructor() { this.style = {}; this.children = []; this.attributes = {}; this.clientWidth = 800; this.clientHeight = 600; this.ownerDocument = { createElement: () => new Element() }; }
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return this.attributes[key]; }
  append(node) { node.parent = this; this.children.push(node); }
  prepend(node) { node.parent = this; this.children.unshift(node); }
  replaceChildren(...children) { this.children = children; }
  querySelectorAll() { return this.children; }
  remove() { this.removed = true; if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
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

// The map over the score (2026-11-20): the lanes of the map above the staves, placed on the cells of the measures of the page.
test('the map is drawn above the measures of the page, and removed when hidden', async () => {
  const container = new Element();
  const measure = (number, x, width) => [{ parentSourceMeasure: { MeasureNumberXML: number },
    PositionAndShape: { AbsolutePosition: { x }, Size: { width } } }];
  const renderer = createFullScoreRenderer({
    container, session: { getVersion: () => 0, loadSource: async () => '<score/>' }, nextFrame: async () => {},
    filter: () => '<page/>', bounds: () => ({ first: 1, last: 2 }),
    createDisplay: target => ({ async load() {},
      GraphicSheet: { MeasureList: [measure(1, 10, 40), measure(2, 50, 40)] },
      render() { const svg = new Element(); svg.attributes = { width: '1000', height: '500' }; target.append(svg); } }),
    onChange: () => {},
  });
  const seen = [];
  renderer.setOverlay(cells => {
    seen.push(cells);
    return { labelWidth: cells[0].left, lanes: [
      { name: 'cadence', label: 'Cadencia', items: [{ className: 'work-map-cadence', left: 70, text: '◐', title: 'semicadencia (c. 2)' }] },
      { name: 'dynamics', label: 'Dinámica', items: [{ className: 'work-map-bar', left: 10, width: 40, height: 0.5 }] }] };
  }, 'Análisis de estos compases');
  await renderer.load();
  assert.deepEqual(seen[0], [{ measure: 1, left: 10, width: 40 }, { measure: 2, left: 50, width: 40 }]);
  const staging = container.children[0];
  const strip = staging.children[0];
  assert.equal(strip.className, 'score-map');
  assert.equal(strip.attributes['aria-label'], 'Análisis de estos compases');
  const [cadences, dynamics] = strip.children;
  assert.equal(cadences.className, 'score-map-lane score-map-lane--cadence');
  const [label, mark] = cadences.children;
  assert.equal(label.textContent, 'Cadencia');
  assert.equal(label.style.width, '10%', 'in the room of the part names');
  assert.equal(mark.className, 'work-map-cadence');
  assert.deepEqual([mark.style.left, mark.textContent, mark.attributes.title], ['70%', '◐', 'semicadencia (c. 2)']);
  const bar = dynamics.children[1];
  assert.deepEqual([bar.style.left, bar.style.width, bar.style.height], ['10%', '40%', '50%']);
  assert.equal(bar.attributes['aria-hidden'], 'true');
  assert.equal(staging.children[1].attributes.width, '1000', 'the staves follow the map');
  renderer.setOverlay(null);
  assert.equal(staging.children.length, 1);
});


// The pages of the PDF (2026-11-22, «1812»): a work that marks where each page of its PDF starts is shown page by page,
// as the PDF, each page whole in one line, smaller when it is wide (the zoom enlarges it); the director compares them.
test('a work with the pages of its PDF turns them where the PDF does, each page whole in one line', async () => {
  const pages = [], widths = [], options = [];
  const container = new Element();
  let view;
  const renderer = createFullScoreRenderer({
    container, session: { getVersion: () => 0, loadSource: async () => '<score/>' }, nextFrame: async () => {},
    filter: (_, instrument, range) => { pages.push(range); return '<page/>'; },
    bounds: () => ({ first: 1, last: 9, pages: [1, 4, 6] }),
    createDisplay: (target, given) => {
      options.push(given);
      const asked = pages[pages.length - 1].split('-').map(Number);
      const count = asked[1] - asked[0] + 1;
      const width = Number.parseFloat(target.style.width);
      widths.push(width);
      // 450 px a measure: a narrower line breaks.
      const fit = Math.floor(width / 450);
      const lines = count > fit ? [fit, count - fit] : [count];
      return { async load() {}, GraphicSheet: { MusicPages: [{ MusicSystems: lines.map(n => ({ GraphicalMeasures: Array(n) })) }] },
        render() { const svg = new Element(); svg.attributes = { width: String(count * 450), height: '500' }; target.append(svg); } };
    },
    onChange: snapshot => { view = snapshot; },
  });
  const settle = () => new Promise(resolve => setTimeout(resolve, 0));
  await renderer.load();
  assert.ok(pages.length && pages.every(range => range === '1-3'), 'the first page of the PDF, never cut');
  assert.equal(view.page, 'Página 1 de 3 · compases 1–3');
  // Its one line is the last of the score, which OpenSheetMusicDisplay leaves at its natural width: half the page was blank.
  assert.ok(options.every(given => given.stretchLastSystemLine), 'the line is stretched to the whole width');
  renderer.next(); await settle();
  assert.equal(view.page, 'Página 2 de 3 · compases 4–5');
  renderer.follow(7, true); await settle();
  assert.equal(view.page, 'Página 3 de 3 · compases 6–9');
  assert.ok(pages.slice(-2).every(range => range === '6-9'), 'drawn wider until its four measures fit in one line');
  assert.ok(widths.at(-1) >= 1800);
  const svg = container.children[0].children.find(child => child.attributes.width);
  assert.equal(svg.style.width, '768px', 'its 1800 px shrunk to the width of the screen');
  assert.equal(view.canNext, false);
  renderer.previous(); await settle();
  assert.equal(view.page, 'Página 2 de 3 · compases 4–5');
});

