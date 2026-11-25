import { highlightMeasure } from './playback-guide.js';
import { applyEdits, figureOf, keyChange, mergeEdits } from './note-edits.js';
import { pitchLabel } from '../noteCorrections.js';
import { t } from '../i18n.js';

export const MEASURES_PER_PAGE = 4;
const CURSOR = [{ type: 3, color: '#6366f1', alpha: .25, follow: false }];

// Width fit with a legible minimum; tall ensembles scroll vertically instead of shrinking.
export function fitScale(widestPage, containerWidth, zoom, minimum = .75) {
  return Math.max(minimum, (containerWidth - 32) / widestPage) * zoom;
}

// What one line of the score holds at most, to be read: a longer page of the PDF is shown in several (2026-11-25).
export const MAX_MEASURES_PER_LINE = 8;

// The first measure of each line: those of the pages, and within a long page those of its even pieces.
export function splitPages(pages, last, most = MAX_MEASURES_PER_LINE) {
  return pages.flatMap((start, at) => {
    const count = (pages[at + 1] ?? last + 1) - start;
    const lines = Math.max(1, Math.ceil(count / most));
    return Array.from({ length: lines }, (_, line) => start + Math.ceil(line * count / lines));
  });
}

// Where each line starts: by the pages of the PDF, or by the measures the director chose (2026-11-25). None when neither
// is known: pages of up to four measures, the ones that fit.
function linesOf({ pages, first, last }, measures) {
  if (pages?.length) return splitPages(pages, last, measures || MAX_MEASURES_PER_LINE);
  if (!measures) return null;
  return Array.from({ length: Math.ceil((last - first + 1) / measures) }, (_, line) => first + line * measures);
}

// Such a line is this wide a measure to begin with, wider while the engraver breaks it.
// 400: wide enough for most pages to fit at the first drawing; each drawing of 30 staves stops the page a while.
const PDF_MEASURE_PIXELS = 400;
const PDF_LINE_ATTEMPTS = 4;

const ZOOM_STEP = 1.15;
// From six tenths of the fit to twice the engraver's size, however small the fit is.
const MIN_ZOOM = .6, MAX_SCALE = 2;

// The page of the PDF a measure is on: the index of the last start not after it (pages: the first measure of each).
export const pdfPageOf = (pages, measure) => Math.max(0, pages.findLastIndex(start => start <= measure));

export function pdfPageLabel(pages, index, first, last) {
  return t('Página {page} de {pages} · compases {first}–{last}', { page: index + 1, pages: pages.length, first, last });
}

// Pages hold up to four measures, fewer when they do not fit in one line, so they are told by their measures.
export function pageLabel(first, last, pageStart, pageEnd = Math.min(pageStart + MEASURES_PER_PAGE - 1, last)) {
  return t('Compases {first}–{last} de {total}', { first: pageStart, last: pageEnd, total: last - first + 1 });
}

// How many measures the engraver put in the first line, when it needed more than one (2026-11-01: «Paco el barba»,
// with its dense snare drum, could not fit four measures in the width of the page).
function measuresInFirstLine(display) {
  const systems = display?.GraphicSheet?.MusicPages?.[0]?.MusicSystems;
  return systems?.length > 1 ? systems[0].GraphicalMeasures?.length || null : null;
}

// OpenSheetMusicDisplay measures in units of ten pixels.
const UNIT = 10;

// The map over the score (2026-11-20): above the staves, the lanes of the map of the work cut to the measures of the
// page. The cells of the measures are given in percent of the page, so the lanes follow the zoom; overlay.lanes(cells)
// says what goes in them (pageLanes in musicalAnalysis.js).
function drawOverlay(staging, display, overlay) {
  if (!overlay) return null;
  const svg = Array.from(staging.querySelectorAll('svg')).find(item => Number.parseFloat(item.getAttribute('width')));
  const pageWidth = svg && Number.parseFloat(svg.getAttribute('width'));
  const measures = (display?.GraphicSheet?.MeasureList || []).map(staves => staves.find(Boolean)).filter(Boolean);
  if (!pageWidth || !measures.length) return null;
  const share = value => Math.round(value * UNIT * 10000 / pageWidth) / 100;
  const cells = measures.map((measure, at) => {
    const box = measure.PositionAndShape, next = measures[at + 1]?.PositionAndShape;
    return { measure: Number(measure.parentSourceMeasure?.MeasureNumberXML ?? measure.MeasureNumber),
      left: share(box.AbsolutePosition.x), width: share(next ? next.AbsolutePosition.x - box.AbsolutePosition.x : box.Size.width) };
  });
  const page = overlay.lanes(cells);
  if (!page) return null;
  const document = staging.ownerDocument;
  const element = (className, text) => { const item = document.createElement(text === undefined ? 'div' : 'span'); item.className = className; if (text !== undefined) item.textContent = text; return item; };
  const strip = element('score-map');
  strip.setAttribute('role', 'group');
  strip.setAttribute('aria-label', overlay.label);
  for (const lane of page.lanes) {
    const row = element('score-map-lane score-map-lane--' + lane.name);
    const label = element('score-map-label', lane.label);
    label.style.width = page.labelWidth + '%';
    row.append(label);
    for (const item of lane.items) {
      const mark = element(item.className, item.text ?? '');
      mark.style.left = item.left + '%';
      if (item.width !== undefined) mark.style.width = item.width + '%';
      if (item.height !== undefined) { mark.style.height = Math.round(item.height * 100) + '%'; mark.setAttribute('aria-hidden', 'true'); }
      if (item.title) mark.setAttribute('title', item.title);
      row.append(mark);
    }
    strip.append(row);
  }
  staging.prepend(strip);
  return strip;
}


// --- Notes edited on the score (2026-11-23) ------------------------------------------------------------------------

const STEP_AT = { 0: 'C', 2: 'D', 4: 'E', 5: 'F', 7: 'G', 9: 'A', 11: 'B' };
const ALTER_OF = { 0: 1, 1: -1, 2: 0, 3: 0, 4: 2, 5: -2 };          // OpenSheetMusicDisplay's AccidentalEnum
const ACCIDENTAL_OF = { '-2': 5, '-1': 1, 0: 2, 1: 0, 2: 4 };
const samePitch = (one, other) => JSON.stringify(one ?? null) === JSON.stringify(other ?? null);
const samePlace = (one, other) => one.partId === other.partId && one.number === other.number && Math.abs(one.offset - other.offset) < 1e-4;

// The notes drawn on the page, each with what a correction names it by: part, printed measure, place in quarters, pitch.
function notesOf(display) {
  const found = [];
  (display?.GraphicSheet?.MeasureList || []).forEach((staves, measureIndex) => staves.forEach((measure, staff) => {
    if (!measure) return;
    const number = String(measure.parentSourceMeasure?.MeasureNumberXML ?? measure.MeasureNumber);
    for (const entry of measure.staffEntries || []) for (const voice of entry.graphicalVoiceEntries || []) for (const graphical of voice.notes || []) {
      const note = graphical.sourceNote;
      if (!note || note.ParentVoiceEntry?.IsGrace) continue;
      const pitch = note.isRest() ? null : note.Pitch && STEP_AT[note.Pitch.FundamentalNote]
        ? [STEP_AT[note.Pitch.FundamentalNote], ALTER_OF[note.Pitch.Accidental] ?? 0, note.Pitch.Octave + 3] : undefined;
      if (pitch === undefined) continue;
      found.push({ graphical, note, staff, measureIndex, number, pitch, partId: note.ParentStaff?.ParentInstrument?.IdString,
        partName: note.ParentStaff?.ParentInstrument?.Name, offset: (entry.relInMeasureTimestamp?.RealValue || 0) * 4,
        chord: (note.ParentVoiceEntry?.Notes?.length || 1) > 1, element: graphical.getSVGGElement?.() || null,
        length: (note.Length?.RealValue || 0) * 4, tuplet: Boolean(note.NoteTuplet) });
    }
  }));
  return found;
}

export const pageStartFor = (first, measure) => first + Math.floor((measure - first) / MEASURES_PER_PAGE) * MEASURES_PER_PAGE;

const idle = { visible: false, status: '', busy: false, page: '', canPrevious: false, canNext: false, zoomLabel: 'Auto', loaded: false };

// Renders the whole ensemble with OpenSheetMusicDisplay, in pages of up to four measures in a single line.
// React owns the controls; this object owns only the notation inside `container`.
export function createFullScoreRenderer({ container, session, filter, bounds, createDisplay, onChange, nextFrame, onSave, onDuration, measures = null }) {
  let score = null, rendering = 0, snapshot = idle, overlay = null;
  // Editing on the score: the pending changes, and the note selected by its place and pitch (2026-11-23).
  let editing = false, edits = [], selection = null, selectAfter = null;
  // After saving, the work opens again on the same page with the same note selected.
  let resume = null;
  const publish = changes => { snapshot = { ...snapshot, ...changes }; onChange(snapshot); };
  const frame = nextFrame || (() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

  // The lines of the work, when its PDF or the director says them: each shown whole, as small as its width needs.
  const linesOfWork = () => score?.lines || null;

  const pageWidth = () => Math.max(...score.sizes.map(item => item.width));
  const scaleAt = zoom => fitScale(pageWidth(), container.clientWidth, zoom, linesOfWork() ? 0 : .75);
  const mostZoom = () => Math.max(1, MAX_SCALE / scaleAt(1));

  function fit() {
    if (!score?.sizes?.length || container.clientWidth <= 32 || container.clientHeight <= 32) return;
    score.zoom = Math.min(score.zoom, mostZoom());   // a line of fewer measures starts larger
    const width = pageWidth(), scale = scaleAt(score.zoom);
    for (const item of score.sizes) {
      item.svg.style.display = 'block';
      item.svg.style.width = item.width * scale + 'px';
      item.svg.style.height = item.height * scale + 'px';
    }
    score.staging.style.width = width * scale + 'px';
    if (score.display) score.display.playbackScale = scale;
    publish({ zoomLabel: Math.round(scale * 100) + ' %' });
  }

  async function renderPage() {
    if (!score) return;
    const state = score, token = ++rendering, lines = linesOfWork();
    const index = lines ? pdfPageOf(lines, state.pageStart) : 0;
    let end = lines ? (index + 1 < lines.length ? lines[index + 1] - 1 : state.last)
      : Math.min(state.pageStart + MEASURES_PER_PAGE - 1, state.last);
    const label = () => (state.pages?.length ? pdfPageLabel(state.pages, pdfPageOf(state.pages, state.pageStart), state.pageStart, end) : pageLabel(state.first, state.last, state.pageStart, end));
    publish({ status: t('Cargando partitura · compases {first}–{last}…', { first: state.pageStart, last: end }), busy: true,
      canPrevious: state.pageStart > state.first, canNext: end < state.last, page: label() });
    await frame();
    if (token !== rendering || state !== score) return;
    let staging;
    try {
      let display;
      const count = end - state.pageStart + 1;
      let width = Math.max(900, container.clientWidth - 24, lines ? count * PDF_MEASURE_PIXELS : 0);
      // Drawn once with up to four measures; again with the ones that fit when they need a second line. A line of
      // the PDF or of the director is never cut: it is drawn wider until it fits, and shrunk to the screen.
      for (let attempt = 0; attempt < (lines ? PDF_LINE_ATTEMPTS : 2); attempt++) {
        staging?.remove();
        staging = container.ownerDocument.createElement('div');
        staging.style.width = width + 'px';
        staging.style.position = 'absolute'; staging.style.visibility = 'hidden';
        container.append(staging);
        const pageXml = applyEdits(filter(state.source, null, state.pageStart + '-' + end), edits);
        const xml = pageXml.trimStart().startsWith('<?xml') ? pageXml : '<?xml version="1.0" encoding="UTF-8"?>\n' + pageXml;
        // Such a line is the last of what is drawn: stretched to the width, or half of it stayed blank.
        display = createDisplay(staging, { autoResize: false, backend: 'svg', drawTitle: false,
          drawPartNames: true, drawMeasureNumbers: true, cursorsOptions: CURSOR, ...(lines ? { stretchLastSystemLine: true } : {}) });
        await display.load(xml);
        if (token !== rendering || state !== score) return;
        display.render();
        const fitting = measuresInFirstLine(display);
        if (!fitting || fitting >= end - state.pageStart + 1) break;
        if (lines) width = Math.ceil(width * count / fitting * 1.1);
        else end = state.pageStart + fitting - 1;
      }
      state.pageEnd = end;
      publish({ canNext: end < state.last, page: label() });
      staging.style.position = ''; staging.style.visibility = '';
      state.staging = staging; state.display = display;
      container.replaceChildren(staging); container.scrollTop = 0; container.scrollLeft = 0;
      publish({ status: t('Todas las voces · notación original · compases {first}–{last}', { first: state.pageStart, last: end }), busy: false });
      drawn(state);
      if (editing && (selectAfter || !selection)) selectOnPage(selectAfter);
      else if (editing) tell();
      selectAfter = null;
    } catch (error) {
      if (token === rendering) publish({ status: t('No se pudo mostrar esta página: {error}', { error: error.message }), busy: false });
    } finally { if (staging?.style.visibility === 'hidden') staging.remove(); }
  }

  // What follows each drawing of the page, also after a note changed in place.
  function drawn(state) {
    const { staging, display } = state;
    state.sizes = Array.from(staging.querySelectorAll('svg'))
      .map(svg => ({ svg, width: Number.parseFloat(svg.getAttribute('width')), height: Number.parseFloat(svg.getAttribute('height')) }))
      .filter(item => item.width && item.height);
    state.strip?.remove();
    state.strip = drawOverlay(staging, display, overlay);
    state.notes = notesOf(display);
    mark();
    fit();
    if (state.currentMeasure !== undefined) highlightMeasure(display, state.currentMeasure, container);
  }

  const selected = () => (selection && score?.notes?.find(note => note.staff === selection.staff && samePlace(note, selection)
    && samePitch(note.pitch, selection.pitch))) || null;

  function mark() {
    const current = selected();
    for (const note of score?.notes || []) {
      if (!note.element) continue;
      note.element.classList.toggle('score-note', editing);
      note.element.classList.toggle('score-note-selected', editing && note === current);
      note.element.classList.toggle('score-note-edited', edits.some(edit => samePlace(edit, note) && samePitch(edit.new, note.pitch)));
    }
  }

  function tell() {
    const note = selected();
    publish({ edits: edits.length, status: note ? t('{part} · compás {measure} · {pitch}', { part: note.partName || note.partId,
      measure: note.number, pitch: pitchLabel(note.pitch) }) : snapshot.status });
  }

  function select(note) {
    selection = note ? { partId: note.partId, number: note.number, offset: note.offset, staff: note.staff, pitch: note.pitch } : null;
    mark(); tell();
    note?.element?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
  }

  // After a page is drawn: the first or last note of a staff (moving past the page), else the first note of the page.
  function selectOnPage(wanted) {
    const notes = score?.notes || [];
    const staff = wanted ? notes.filter(note => note.staff === wanted.staff) : notes;
    select(wanted?.last ? staff[staff.length - 1] : staff[0] || notes[0] || null);
  }

  function inOrder(staff) {
    return (score?.notes || []).filter(note => note.staff === staff)
      .sort((one, other) => one.measureIndex - other.measureIndex || one.offset - other.offset);
  }

  function move(direction) {
    const current = selected();
    if (!current) return;
    if (direction === 'up' || direction === 'down') {
      const staff = current.staff + (direction === 'up' ? -1 : 1);
      const options = inOrder(staff).filter(note => note.measureIndex === current.measureIndex);
      const nearest = options.sort((one, other) => Math.abs(one.offset - current.offset) - Math.abs(other.offset - current.offset))[0];
      if (nearest) select(nearest);
      return;
    }
    const line = inOrder(current.staff);
    const at = line.indexOf(current) + (direction === 'next' ? 1 : -1);
    if (line[at]) return select(line[at]);
    if (direction === 'next' && snapshot.canNext) { selectAfter = { staff: current.staff }; turn(1); }
    if (direction === 'previous' && snapshot.canPrevious) { selectAfter = { staff: current.staff, last: true }; turn(-1); }
  }

  function change(pitch) {
    const note = selected();
    if (!note) return;
    if (!pitch && note.chord) { publish({ status: t('Una nota de un acorde no puede ser un silencio: corrige su altura.') }); return; }
    edits = mergeEdits(edits, { partId: note.partId, number: note.number, offset: note.offset, old: note.pitch, new: pitch });
    selection = { ...selection, pitch };
    const Pitch = globalThis.opensheetmusicdisplay?.Pitch;
    if (note.pitch && pitch && Pitch) {
      // A pitch for a pitch is drawn again in place, at once; a rest needs the page drawn from its MusicXML.
      const semitone = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }[pitch[0]];
      note.note.pitch = new Pitch(semitone, pitch[2] - 3, ACCIDENTAL_OF[pitch[1]]);
      score.display.updateGraphic();
      score.display.render();
      drawn(score);
      tell();
    } else renderPage();
  }

  // A figure is saved at once with the changes waiting (2026-11-23): it moves the notes after it.
  function changeDuration(result) {
    const note = selected();
    if (!note) return;
    const current = figureOf(note.length);
    if (note.tuplet || !current) { publish({ status: t('Una nota de un tresillo no cambia de duración aquí.') }); return; }
    const type = result.duration || current.type;
    const dots = result.dot ? (current.dots ? 0 : 1) : 0;
    if (type === current.type && dots === current.dots) return;
    onDuration?.({ partId: note.partId, number: note.number, offset: note.offset, old: note.pitch, new: note.pitch, newType: type, newDots: dots });
  }

  container.addEventListener?.('click', event => {
    if (!editing || !score?.notes) return;
    const hit = score.notes.find(note => note.element?.contains(event.target));
    if (hit) { select(hit); container.focus(); }
  });
  container.addEventListener?.('keydown', event => {
    if (!editing) return;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); onSave?.(); return; }
    if (event.key === 'Escape') { selection = null; mark(); tell(); return; }
    const note = selected();
    if (!note) return;
    const before = inOrder(note.staff).filter(item => item.pitch && (item.measureIndex < note.measureIndex
      || (item.measureIndex === note.measureIndex && item.offset < note.offset))).pop();
    const result = keyChange(note.pitch, event, before?.pitch || ['C', 0, 5]);
    if (!result) return;
    event.preventDefault();
    if (result.move) move(result.move);
    else if (result.duration || result.dot) changeDuration(result);
    else change(result.rest ? null : result.pitch);
  });

  function clear() {
    edits = []; selection = null;
    score = null; rendering++;
    container.replaceChildren();
    publish({ ...idle, editing, edits: 0 });
  }

  async function load() {
    clear();
    const version = session.getVersion();
    publish({ visible: true, status: t('Cargando partitura…'), busy: true });
    try {
      const source = await session.loadSource();
      if (version !== session.getVersion()) return;
      score = { source, ...bounds(source), zoom: 1, starts: [] };
      score.lines = linesOf(score, measures);
      score.pageStart = score.first;
      if (resume) {
        if (resume.pageStart >= score.first && resume.pageStart <= score.last) score.pageStart = resume.pageStart;
        selection = resume.selection;
        resume = null;
      }
      publish({ loaded: true });
      await renderPage();
    } catch (error) {
      if (version === session.getVersion()) publish({ status: error.message, busy: false });
    }
  }

  // The next page starts after the last measure shown; the previous one goes back to where it was.
  const turn = delta => {
    if (!score) return;
    const lines = linesOfWork();
    if (lines) {
      const index = pdfPageOf(lines, score.pageStart) + delta;
      if (index < 0 || index >= lines.length) return;
      score.pageStart = lines[index];
    } else if (delta > 0) {
      if (score.pageEnd >= score.last) return;
      score.starts.push(score.pageStart);
      score.pageStart = score.pageEnd + 1;
    } else {
      if (score.pageStart <= score.first) return;
      score.pageStart = score.starts.pop() ?? Math.max(score.first, score.pageStart - MEASURES_PER_PAGE);
    }
    renderPage();
  };
  // Zooms keeping in its place what is under the point (the pointer, or the middle of what is seen).
  function zoomAt(factor, point) {
    if (!score?.sizes?.length) return;
    const box = () => score.staging.getBoundingClientRect?.();
    const before = box(), view = container.getBoundingClientRect?.();
    const at = point || (view && { x: view.left + container.clientWidth / 2, y: view.top + container.clientHeight / 2 });
    score.zoom = Math.max(MIN_ZOOM, Math.min(mostZoom(), score.zoom * factor));
    fit();
    const after = box();
    if (!before?.width || !before.height || !at) return;
    container.scrollLeft += after.left + (at.x - before.left) / before.width * after.width - at.x;
    container.scrollTop += after.top + (at.y - before.top) / before.height * after.height - at.y;
  }

  return {
    load, clear, fit, renderPage,
    previous: () => turn(-1),
    next: () => turn(1),
    zoomIn: () => zoomAt(ZOOM_STEP),
    zoomOut: () => zoomAt(1 / ZOOM_STEP),
    zoomAt,
    // Opens the line of a measure and marks it; editing, its first note is selected. False when the work has no such measure.
    async goTo(measure) {
      if (!score) return false;
      if (!Number.isInteger(measure) || measure < score.first || measure > score.last) {
        publish({ status: t('La obra va del compás {first} al {last}.', { first: score.first, last: score.last }) });
        return false;
      }
      const state = score;
      state.currentMeasure = measure;
      if (measure >= state.pageStart && measure <= (state.pageEnd ?? -Infinity)) highlightMeasure(state.display, measure, container);
      else {
        state.starts = [];
        state.pageStart = state.lines ? state.lines[pdfPageOf(state.lines, measure)] : pageStartFor(state.first, measure);
        await renderPage();
        // The engraver may fit fewer measures than its page: the line after them.
        while (state === score && state.currentMeasure === measure && state.pageEnd < measure && state.pageEnd >= state.pageStart) {
          state.starts.push(state.pageStart);
          state.pageStart = state.pageEnd + 1;
          await renderPage();
        }
      }
      if (editing && state === score) {
        const note = inOrder(selection?.staff ?? 0).find(item => item.number === String(measure));
        if (note) select(note);
      }
      return true;
    },
    // How many measures a line shows (null: automatic), from the line the measure in view is in.
    setMeasures(count) {
      measures = count;
      if (!score) return;
      score.lines = linesOf(score, measures);
      score.starts = [];
      score.pageStart = score.lines ? score.lines[pdfPageOf(score.lines, score.pageStart)] : pageStartFor(score.first, score.pageStart);
      return renderPage();
    },
    resetZoom() { if (score) { score.zoom = 1; fit(); } },
    // Follow playback: turn the page when the sounding measure leaves it, otherwise move the marker.
    follow(measure, playing) {
      if (!score || measure === undefined) return;
      const pageEnd = score.pageEnd ?? score.pageStart + MEASURES_PER_PAGE - 1;
      const outside = measure < score.pageStart || measure > pageEnd;
      if (score.currentMeasure === measure && !(playing && outside)) return;
      score.currentMeasure = measure;
      if (playing && outside) {
        // Playing on, the next page starts with the measure that sounds; a jump goes to the page of four it is in.
        const lines = linesOfWork();
        if (lines) score.pageStart = lines[pdfPageOf(lines, measure)];
        else {
          if (measure === pageEnd + 1) score.starts.push(score.pageStart);
          else score.starts = [];
          score.pageStart = measure === pageEnd + 1 ? measure : pageStartFor(score.first, measure);
        }
        renderPage();
      }
      else highlightMeasure(score.display, measure, container);
    },
    hideMarker() {
      if (!score) return;
      score.display?.cursor?.hide(); score.currentMeasure = undefined;
    },
    setStatus: status => publish({ status, busy: false }),
    // Editing on the score: on, the notes can be selected and changed; the changes wait to be saved together.
    setEditing(on) {
      editing = on;
      if (!on) selection = null;
      else if (!selection) selectOnPage(null);
      mark();
      if (on) container.focus();
      publish({ editing: on, edits: edits.length });
    },
    getEdits: () => edits,
    discardEdits() { edits = []; selection = null; publish({ edits: 0 }); return renderPage(); },
    saved() { resume = score ? { pageStart: score.pageStart, selection } : null; edits = []; publish({ edits: 0 }); },
    // lanes: cells → what to draw (pageLanes), or null to hide the map; label names it.
    setOverlay(lanes, label = '') {
      overlay = lanes ? { lanes, label } : null;
      if (!score?.staging) return;
      score.strip?.remove();
      score.strip = drawOverlay(score.staging, score.display, overlay);
    },
  };
}
