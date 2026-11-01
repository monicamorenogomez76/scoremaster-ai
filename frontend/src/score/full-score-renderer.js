import { highlightMeasure } from './playback-guide.js';
import { t } from '../i18n.js';

export const MEASURES_PER_PAGE = 4;
const CURSOR = [{ type: 3, color: '#6366f1', alpha: .25, follow: false }];

// Width fit with a legible minimum; tall ensembles scroll vertically instead of shrinking.
export function fitScale(widestPage, containerWidth, zoom) {
  return Math.max(.75, (containerWidth - 32) / widestPage) * zoom;
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

export const pageStartFor = (first, measure) => first + Math.floor((measure - first) / MEASURES_PER_PAGE) * MEASURES_PER_PAGE;

const idle = { visible: false, status: '', busy: false, page: '', canPrevious: false, canNext: false, zoomLabel: 'Auto', loaded: false };

// Renders the whole ensemble with OpenSheetMusicDisplay, in pages of up to four measures in a single line.
// React owns the controls; this object owns only the notation inside `container`.
export function createFullScoreRenderer({ container, session, filter, bounds, createDisplay, onChange, nextFrame }) {
  let score = null, rendering = 0, snapshot = idle;
  const publish = changes => { snapshot = { ...snapshot, ...changes }; onChange(snapshot); };
  const frame = nextFrame || (() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

  function fit() {
    if (!score?.sizes?.length || container.clientWidth <= 32 || container.clientHeight <= 32) return;
    const width = Math.max(...score.sizes.map(item => item.width));
    const scale = fitScale(width, container.clientWidth, score.zoom);
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
    const state = score, token = ++rendering;
    let end = Math.min(state.pageStart + MEASURES_PER_PAGE - 1, state.last);
    publish({ status: t('Cargando partitura · compases {first}–{last}…', { first: state.pageStart, last: end }), busy: true,
      canPrevious: state.pageStart > state.first, canNext: end < state.last, page: pageLabel(state.first, state.last, state.pageStart, end) });
    await frame();
    if (token !== rendering || state !== score) return;
    let staging;
    try {
      let display;
      // Drawn once with up to four measures; again with the ones that fit when they need a second line.
      for (let attempt = 0; attempt < 2; attempt++) {
        staging?.remove();
        staging = container.ownerDocument.createElement('div');
        staging.style.width = Math.max(900, container.clientWidth - 24) + 'px';
        staging.style.position = 'absolute'; staging.style.visibility = 'hidden';
        container.append(staging);
        const pageXml = filter(state.source, null, state.pageStart + '-' + end);
        const xml = pageXml.trimStart().startsWith('<?xml') ? pageXml : '<?xml version="1.0" encoding="UTF-8"?>\n' + pageXml;
        display = createDisplay(staging, { autoResize: false, backend: 'svg', drawTitle: false,
          drawPartNames: true, drawMeasureNumbers: true, cursorsOptions: CURSOR });
        await display.load(xml);
        if (token !== rendering || state !== score) return;
        display.render();
        const fitting = measuresInFirstLine(display);
        if (!fitting || fitting >= end - state.pageStart + 1) break;
        end = state.pageStart + fitting - 1;
      }
      state.pageEnd = end;
      publish({ canNext: end < state.last, page: pageLabel(state.first, state.last, state.pageStart, end) });
      staging.style.position = ''; staging.style.visibility = '';
      state.staging = staging; state.display = display;
      state.sizes = Array.from(staging.querySelectorAll('svg'))
        .map(svg => ({ svg, width: Number.parseFloat(svg.getAttribute('width')), height: Number.parseFloat(svg.getAttribute('height')) }))
        .filter(item => item.width && item.height);
      container.replaceChildren(staging); container.scrollTop = 0;
      publish({ status: t('Todas las voces · notación original · compases {first}–{last}', { first: state.pageStart, last: end }), busy: false });
      fit();
      if (state.currentMeasure !== undefined) highlightMeasure(display, state.currentMeasure, container);
    } catch (error) {
      if (token === rendering) publish({ status: t('No se pudo mostrar esta página: {error}', { error: error.message }), busy: false });
    } finally { if (staging?.style.visibility === 'hidden') staging.remove(); }
  }

  function clear() {
    score = null; rendering++;
    container.replaceChildren();
    publish(idle);
  }

  async function load() {
    clear();
    const version = session.getVersion();
    publish({ visible: true, status: t('Cargando partitura…'), busy: true });
    try {
      const source = await session.loadSource();
      if (version !== session.getVersion()) return;
      score = { source, ...bounds(source), zoom: 1, starts: [] };
      score.pageStart = score.first;
      publish({ loaded: true });
      await renderPage();
    } catch (error) {
      if (version === session.getVersion()) publish({ status: error.message, busy: false });
    }
  }

  // The next page starts after the last measure shown; the previous one goes back to where it was.
  const turn = delta => {
    if (!score) return;
    if (delta > 0) {
      if (score.pageEnd >= score.last) return;
      score.starts.push(score.pageStart);
      score.pageStart = score.pageEnd + 1;
    } else {
      if (score.pageStart <= score.first) return;
      score.pageStart = score.starts.pop() ?? Math.max(score.first, score.pageStart - MEASURES_PER_PAGE);
    }
    renderPage();
  };
  const zoom = delta => { if (score) { score.zoom = Math.max(.6, Math.min(2, score.zoom + delta)); fit(); } };

  return {
    load, clear, fit, renderPage,
    previous: () => turn(-1),
    next: () => turn(1),
    zoomIn: () => zoom(.1),
    zoomOut: () => zoom(-.1),
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
        if (measure === pageEnd + 1) score.starts.push(score.pageStart);
        else score.starts = [];
        score.pageStart = measure === pageEnd + 1 ? measure : pageStartFor(score.first, measure);
        renderPage();
      }
      else highlightMeasure(score.display, measure, container);
    },
    hideMarker() {
      if (!score) return;
      score.display?.cursor?.hide(); score.currentMeasure = undefined;
    },
    setStatus: status => publish({ status, busy: false }),
  };
}
