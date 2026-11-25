// The mouse over the score (2026-11-25): the wheel with Ctrl or Cmd zooms where the pointer is (a trackpad's pinch comes
// as that), and dragging moves the score in any direction. The scroll bars, the zoom buttons and the keyboard do the same
// without dragging, and touch keeps the browser's own gestures.

// Less than this many pixels is a click, which selects a note when editing.
const DRAG_PIXELS = 4;
// A wheel's notch is about a hundred pixels, a pinch comes in steps of a few.
const PIXELS_PER_E = 400, MAX_WHEEL_STEP = 100;

export function attachPanZoom(container, onZoom) {
  let from = null, dragged = false;

  const wheel = event => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const step = Math.max(-MAX_WHEEL_STEP, Math.min(MAX_WHEEL_STEP, event.deltaY));
    onZoom(Math.exp(-step / PIXELS_PER_E), { x: event.clientX, y: event.clientY });
  };
  const onScrollBar = event => {
    const box = container.getBoundingClientRect();
    return event.clientX - box.left - container.clientLeft >= container.clientWidth
      || event.clientY - box.top - container.clientTop >= container.clientHeight;
  };
  const down = event => {
    dragged = false;
    if (event.button !== 0 || event.pointerType !== 'mouse' || onScrollBar(event)) return;
    from = { x: event.clientX, y: event.clientY, left: container.scrollLeft, top: container.scrollTop };
  };
  const move = event => {
    if (!from) return;
    const x = event.clientX - from.x, y = event.clientY - from.y;
    if (!dragged) {
      if (Math.hypot(x, y) < DRAG_PIXELS) return;
      dragged = true;
      container.setPointerCapture?.(event.pointerId);
      container.setAttribute('data-panning', '');
    }
    container.scrollLeft = from.left - x;
    container.scrollTop = from.top - y;
  };
  const end = () => { from = null; container.removeAttribute('data-panning'); };
  const click = event => {
    if (!dragged) return;
    dragged = false;
    event.stopImmediatePropagation();
  };

  const listeners = [['wheel', wheel, { passive: false }], ['pointerdown', down], ['pointermove', move], ['pointerup', end],
    ['pointercancel', end], ['lostpointercapture', end], ['click', click, { capture: true }]];
  for (const [type, handler, options] of listeners) container.addEventListener(type, handler, options);
  return () => { for (const [type, handler, options] of listeners) container.removeEventListener(type, handler, options); };
}
