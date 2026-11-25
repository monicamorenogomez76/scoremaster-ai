import test from 'node:test';
import assert from 'node:assert/strict';
import { createFullScoreRenderer, fitScale, MAX_MEASURES_PER_LINE, pageLabel, pageStartFor, splitPages } from '../../../frontend/src/score/full-score-renderer.js';

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

// 2026-11-25: pages of 44 measures of the whole band in one line stopped the browser.
test('a long page of the PDF is cut in even lines of eight measures at most', () => {
  assert.equal(MAX_MEASURES_PER_LINE, 8);
  assert.deepEqual(splitPages([1, 9, 15], 20), [1, 9, 15], 'the pages that fit are whole');
  assert.deepEqual(splitPages([1, 10], 14), [1, 6, 10], 'nine measures: five and four');
  assert.deepEqual(splitPages([1], 44), [1, 9, 16, 23, 31, 38], 'forty-four: 8, 7, 7, 8, 7 and 7');
  assert.deepEqual(splitPages([0, 5], 14), [0, 5, 10], 'an upbeat is measure 0');
});

test('the pieces of a page keep its number, and playback follows them', async () => {
  const pages = [], container = new Element();
  let view;
  const renderer = createFullScoreRenderer({ container, nextFrame: async () => {},
    session: { getVersion: () => 0, loadSource: async () => '<score/>' },
    filter: (_, instrument, range) => { pages.push(range); return '<page/>'; },
    bounds: () => ({ first: 1, last: 18, pages: [1, 13] }),
    createDisplay: target => ({ async load() {}, render() { const svg = new Element(); svg.attributes = { width: '4000', height: '500' }; target.append(svg); } }),
    onChange: snapshot => { view = snapshot; } });
  const settle = () => new Promise(resolve => setTimeout(resolve, 0));
  await renderer.load();
  assert.equal(view.page, 'Página 1 de 2 · compases 1–6');
  renderer.next(); await settle();
  assert.equal(view.page, 'Página 1 de 2 · compases 7–12');
  renderer.next(); await settle();
  assert.equal(view.page, 'Página 2 de 2 · compases 13–18');
  assert.equal(view.canNext, false);
  renderer.follow(8, true); await settle();
  assert.equal(view.page, 'Página 1 de 2 · compases 7–12');
  assert.deepEqual(pages, ['1-6', '7-12', '13-18', '7-12']);
});

test('a page shrunk to its width can be enlarged until it is read', async () => {
  const state = setup();
  await state.renderer.load();
  for (let i = 0; i < 40; i++) state.renderer.zoomIn();
  assert.equal(state.view().zoomLabel, '200 %');
  for (let i = 0; i < 40; i++) state.renderer.zoomOut();
  assert.equal(state.view().zoomLabel, '46 %', 'no smaller than 60 % of the fit');
  state.renderer.resetZoom();
  assert.equal(state.view().zoomLabel, '77 %');
});

test('zooming keeps under the pointer what was under it', async () => {
  const state = setup();
  await state.renderer.load();
  const staging = state.container.children[0];
  state.container.scrollLeft = 0; state.container.scrollTop = 0;
  // The browser's layout: the page starts at the container's corner, moved by its scroll.
  const size = name => Number.parseFloat(staging.children[0].style[name]);
  staging.getBoundingClientRect = () => ({ left: -state.container.scrollLeft, top: -state.container.scrollTop, width: size('width'), height: size('height') });
  state.renderer.zoomAt(2, { x: 384, y: 100 });
  assert.equal(Math.round(state.container.scrollLeft), 384);
  assert.equal(Math.round(state.container.scrollTop), 100);
});

// 2026-11-25: the director chooses how many measures a line shows; «Automático» is what the score showed before.
function choosing({ pages, last, measures }) {
  const asked = [], container = new Element();
  let view;
  const renderer = createFullScoreRenderer({ container, nextFrame: async () => {}, measures,
    session: { getVersion: () => 0, loadSource: async () => '<score/>' },
    filter: (_, instrument, range) => { asked.push(range); return '<page/>'; },
    bounds: () => ({ first: 1, last, pages }),
    // The engraver breaks any line wider than its 500 pixels a measure.
    createDisplay: target => {
      const [from, to] = asked.at(-1).split('-').map(Number), count = to - from + 1;
      const fit = Math.max(1, Math.floor(Number.parseFloat(target.style.width) / 500));
      const lines = count > fit ? [fit, count - fit] : [count];
      return { async load() {}, GraphicSheet: { MusicPages: [{ MusicSystems: lines.map(n => ({ GraphicalMeasures: Array(n) })) }] },
        render() { const svg = new Element(); svg.attributes = { width: String(count * 500), height: '500' }; target.append(svg); } };
    },
    onChange: snapshot => { view = snapshot; } });
  return { renderer, container, asked, view: () => view };
}
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

test('the chosen measures fill each line of a work without pages, drawn wider rather than cut', async () => {
  const { renderer, container, asked, view } = choosing({ pages: [], last: 20, measures: 6 });
  await renderer.load();
  assert.equal(view().page, 'Compases 1–6 de 20');
  assert.ok(asked.every(range => range === '1-6'), 'never cut');
  assert.equal(container.children[0].children.find(child => child.attributes.width).style.width, '768px', 'shrunk to the screen');
  renderer.next(); await settle();
  assert.equal(view().page, 'Compases 7–12 de 20');
  renderer.follow(19, true); await settle();
  assert.equal(view().page, 'Compases 19–20 de 20');
  renderer.previous(); await settle();
  assert.equal(view().page, 'Compases 13–18 de 20');
});

test('the chosen measures cut the pages of the PDF, or leave them whole', async () => {
  const { renderer, view } = choosing({ pages: [1, 11], last: 20, measures: 16 });
  await renderer.load();
  assert.equal(view().page, 'Página 1 de 2 · compases 1–10');
  await renderer.setMeasures(4);
  assert.equal(view().page, 'Página 1 de 2 · compases 1–4');
  await renderer.setMeasures(null);
  assert.equal(view().page, 'Página 1 de 2 · compases 1–5', 'automatic: eight at most');
});

test('changing the measures of a line keeps the place, and is kept for the next work', async () => {
  const { renderer, view } = choosing({ pages: [], last: 20 });
  await renderer.setMeasures(2);
  await renderer.load();
  assert.equal(view().page, 'Compases 1–2 de 20');
  renderer.follow(14, true); await settle();
  assert.equal(view().page, 'Compases 13–14 de 20');
  await renderer.setMeasures(5);
  assert.equal(view().page, 'Compases 11–15 de 20');
  await renderer.setMeasures(null);
  assert.match(view().page, /^Compases 9–/, 'the page of four measures it is in, cut to what fits');
});

// Going to a measure (2026-11-25).
test('going to a measure opens the line that holds it', async () => {
  const { renderer, view, asked } = choosing({ pages: [1, 11], last: 20 });
  await renderer.load();
  assert.equal(await renderer.goTo(18), true);
  assert.equal(view().page, 'Página 2 de 2 · compases 16–20');
  const drawn = asked.length;
  assert.equal(await renderer.goTo(17), true);
  assert.equal(asked.length, drawn, 'already in view: not drawn again');
});

test('going to a measure that its page of four could not fit opens the next one', async () => {
  const { renderer, view } = choosing({ pages: [], last: 20 });
  await renderer.load();
  assert.equal(view().page, 'Compases 1–1 de 20', 'one fits in the width of this screen');
  await renderer.goTo(8);
  assert.equal(view().page, 'Compases 8–8 de 20');
});

test('a measure the work does not have says which it has, and moves nothing', async () => {
  const { renderer, view } = choosing({ pages: [], last: 20, measures: 4 });
  assert.equal(await renderer.goTo(3), false, 'nothing loaded');
  await renderer.load();
  for (const measure of [0, 21, NaN, 2.5]) {
    assert.equal(await renderer.goTo(measure), false);
    assert.equal(view().status, 'La obra va del compás 1 al 20.');
  }
  assert.equal(view().page, 'Compases 1–4 de 20');
});

test('an enlarged line of fewer measures does not go past the largest zoom', async () => {
  const { renderer, view } = choosing({ pages: [], last: 20, measures: 6 });
  await renderer.load();
  for (let i = 0; i < 40; i++) renderer.zoomIn();
  assert.equal(view().zoomLabel, '200 %');
  await renderer.setMeasures(2);
  assert.equal(view().zoomLabel, '200 %');
});

test('a work whose parts have other measures says so while it is open', async () => {
  const uneven = { least: 9, most: 14, parts: [] };
  const container = new Element();
  let view;
  const renderer = createFullScoreRenderer({ container, nextFrame: async () => {}, filter: () => '<page/>',
    session: { getVersion: () => 0, loadSource: async () => '<score/>' }, bounds: () => ({ first: 1, last: 4, pages: [], uneven }),
    createDisplay: target => ({ async load() {}, render() { const svg = new Element(); svg.attributes = { width: '900', height: '500' }; target.append(svg); } }),
    onChange: snapshot => { view = snapshot; } });
  await renderer.load();
  assert.equal(view.uneven, uneven);
  renderer.clear();
  assert.equal(view.uneven, null);
});
