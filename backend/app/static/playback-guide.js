// Follow the source measure, without expanding repeats or changing the audio.
export function highlightMeasure(display, number, container) {
  const cursor = display?.cursor;
  const measures = display?.Sheet?.SourceMeasures || [];
  const index = measures.findIndex(m => Number(m.MeasureNumberXML ?? m.MeasureNumber) === number);
  if (!cursor || index < 0) return;
  if (cursor.Iterator.CurrentMeasureIndex > index || cursor.Iterator.EndReached) cursor.reset();
  cursor.Iterator.SkipRepetitions = true;
  let guard = 0;
  while (!cursor.Iterator.EndReached && cursor.Iterator.CurrentMeasureIndex < index && guard++ < 10000) cursor.next();
  cursor.show();
  cursor.update();
  const marker = cursor.cursorElement;
  if (!marker) return;
  marker.style.zIndex = '1';
  marker.style.pointerEvents = 'none';
  const scale = display.playbackScale || 1;
  marker.style.left = parseFloat(marker.style.left) * scale + 'px';
  marker.style.top = parseFloat(marker.style.top) * scale + 'px';
  marker.style.transformOrigin = 'top left';
  marker.style.transform = `scale(${scale})`;
  const box = marker.getBoundingClientRect(), viewport = container.getBoundingClientRect();
  if (box.top < viewport.top || box.bottom > viewport.bottom) container.scrollTop += box.top - viewport.top - 40;
  if (box.left < viewport.left || box.right > viewport.right) container.scrollLeft += box.left - viewport.left - 40;
}
