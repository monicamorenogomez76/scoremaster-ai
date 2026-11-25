import test from 'node:test';
import assert from 'node:assert/strict';
import { attachPanZoom } from '../../../frontend/src/score/pan-zoom.js';

function setup() {
  const listeners = {}, zooms = [], attributes = {};
  const container = { scrollLeft: 300, scrollTop: 200, clientWidth: 800, clientHeight: 600, clientLeft: 1, clientTop: 1,
    addEventListener(type, handler, options) { listeners[type] = { handler, options }; },
    removeEventListener(type) { delete listeners[type]; },
    getBoundingClientRect: () => ({ left: 0, top: 0 }), setPointerCapture() {},
    setAttribute(name, value) { attributes[name] = value; }, removeAttribute(name) { delete attributes[name]; } };
  const detach = attachPanZoom(container, (factor, point) => zooms.push([factor, point]));
  const fire = (type, event = {}) => {
    const state = { prevented: false, stopped: false };
    listeners[type].handler({ preventDefault() { state.prevented = true; }, stopImmediatePropagation() { state.stopped = true; },
      button: 0, buttons: 1, pointerType: 'mouse', pointerId: 1, clientX: 0, clientY: 0, ...event });
    return state;
  };
  return { container, listeners, zooms, attributes, detach, fire };
}

test('the wheel zooms with Ctrl or Cmd, at the pointer, and scrolls without them', () => {
  const { fire, zooms, listeners } = setup();
  assert.equal(listeners.wheel.options.passive, false, 'or the browser would zoom the whole page');
  assert.equal(fire('wheel', { deltaY: -100 }).prevented, false);
  assert.equal(zooms.length, 0);
  assert.equal(fire('wheel', { deltaY: -100, ctrlKey: true, clientX: 40, clientY: 50 }).prevented, true);
  assert.ok(zooms[0][0] > 1); assert.deepEqual(zooms[0][1], { x: 40, y: 50 });
  fire('wheel', { deltaY: 100, metaKey: true });
  assert.ok(zooms[1][0] < 1);
  assert.ok(Math.abs(zooms[0][0] * zooms[1][0] - 1) < 1e-9, 'in and out are symmetrical');
});

test('dragging with the mouse moves the score in both directions', () => {
  const { container, fire, attributes } = setup();
  fire('pointerdown', { clientX: 100, clientY: 100 });
  fire('pointermove', { clientX: 60, clientY: 130 });
  assert.deepEqual([container.scrollLeft, container.scrollTop], [340, 170]);
  assert.equal(attributes['data-panning'], '');
  fire('pointerup');
  assert.equal('data-panning' in attributes, false);
  fire('pointermove', { clientX: 0, clientY: 0, buttons: 0 });
  assert.equal(container.scrollLeft, 340, 'released');
  assert.equal(fire('click').stopped, true, 'the end of a drag selects no note');
});

test('a click that hardly moves still selects a note', () => {
  const { container, fire } = setup();
  fire('pointerdown', { clientX: 100, clientY: 100 });
  fire('pointermove', { clientX: 102, clientY: 101 });
  fire('pointerup');
  assert.equal(container.scrollLeft, 300);
  assert.equal(fire('click').stopped, false);
});

test('touch, other buttons and the scroll bars keep their own gestures', () => {
  const { container, fire } = setup();
  for (const event of [{ pointerType: 'touch' }, { button: 2 }, { clientX: 805 }, { clientY: 605 }]) {
    fire('pointerdown', { clientX: 100, clientY: 100, ...event });
    fire('pointermove', { clientX: 0, clientY: 0 });
    fire('pointerup');
  }
  assert.deepEqual([container.scrollLeft, container.scrollTop], [300, 200]);
});

test('nothing is left listening after the viewer closes', () => {
  const { detach, listeners } = setup();
  detach();
  assert.deepEqual(Object.keys(listeners), []);
});
