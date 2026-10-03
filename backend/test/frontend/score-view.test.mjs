import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function setup() {
  const nodes = new Map();
  class Element {
    constructor() { this.style = {}; this.children = []; this.handlers = {}; this.attributes = {}; this.clientWidth = 800; this.clientHeight = 600; }
    setAttribute(key, value) { this.attributes[key] = value; }
    getAttribute(key) { return this.attributes[key]; }
    addEventListener(key, fn) { this.handlers[key] = fn; }
    append(node) { this.children.push(node); }
    replaceChildren(...children) { this.children = children; }
    querySelectorAll() { return this.children; }
    remove() { this.removed = true; }
  }
  const el = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  let stopped = 0, resize;
  const context = vm.createContext({
    document: { getElementById: el, createElement: () => new Element() },
    stopPlayback: () => stopped++, preparePlayback: async () => {},
    ResizeObserver: class { constructor(fn) { resize = fn; } observe() {} },
    DOMParser: class { parseFromString() { return { getElementsByTagName: () => [1, 2, 3, 4, 5].map(n => ({ localName: 'measure', getAttribute: () => n })) }; } },
    requestAnimationFrame: fn => fn(),
    window: { opensheetmusicdisplay: { OpenSheetMusicDisplay: class {
      constructor(target) { this.target = target; }
      async load() {}
      render() { const svg = new Element(); svg.attributes = { width: '1000', height: '2000' }; this.target.append(svg); }
    } } },
  });
  const source = fs.readFileSync(new URL('../../app/static/score-view.js', import.meta.url), 'utf8').replace(/^import .*\n/, '').replace('export function', 'function');
  vm.runInContext(source + '\nglobalThis.create = createScoreView;', context);
  return { el, context, stopped: () => stopped, resize: () => resize() };
}

test('fits tall ensemble page in both dimensions and refits after resize', async () => {
  const state = setup(); const file = {};
  const view = state.context.create({ getFile: () => file, getSource: async () => '<score/>', filter: () => '<page/>' });
  await view.load();
  const svg = state.el('full-score-rendering').children[0].children[0];
  assert.equal(svg.style.height, '568px'); assert.equal(svg.style.width, '284px');
  state.el('full-score-rendering').clientHeight = 400; state.resize();
  assert.equal(svg.style.height, '368px');
  view.clear();
  assert.equal(state.el('embedded-score').hidden, true);
  assert.equal(state.el('full-score-rendering').children.length, 0);
  assert.equal(state.el('ensemble-play').disabled, true);
});

test('reset during asynchronous source load discards old score', async () => {
  const state = setup(); let file = {}; let resolve;
  const view = state.context.create({ getFile: () => file, getSource: () => new Promise(r => resolve = r), filter: () => '<page/>' });
  const pending = view.load();
  file = null; view.clear(); resolve('<old/>'); await pending;
  assert.equal(state.el('embedded-score').hidden, true);
  assert.equal(state.el('full-score-rendering').children.length, 0);
  assert.equal(state.el('ensemble-play').disabled, true);
  assert.ok(state.stopped() >= 2);
});
