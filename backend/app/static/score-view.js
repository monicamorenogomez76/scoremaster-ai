import { preparePlayback, stopPlayback } from './playback.js?v=5';
import { highlightMeasure } from './playback-guide.js';

export function createScoreView({ getSource, getFile, filter }) {
  const el = (id) => document.getElementById(id);
  const status = el('full-score-status'), audioStatus = el('ensemble-status');
  const play = el('ensemble-play'), stop = el('ensemble-stop'), seek = el('ensemble-seek');
  let score, transport, playing = false, generation = 0, rendering = 0;
  const clock = (seconds) => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
  function busy(target, message, loading) {
    target.textContent = message; target.setAttribute('aria-busy', String(loading));
  }
  function setPlayIcon(paused) {
    play.innerHTML = paused ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h4v14H7zm6 0h4v14h-4z"/></svg>' : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4v16l13-8z"/></svg>';
    play.setAttribute('aria-label', paused ? 'Pausar' : 'Reproducir');
    play.title = paused ? 'Pausar' : 'Reproducir';
  }
  function clear() {
    score = null; rendering++; resetTransport();
    busy(status, '', false);
    el('score-prev').disabled = true; el('score-next').disabled = true;
    el('score-page').textContent = '';
    el('score-zoom-label').textContent = 'Auto';
    el('full-score-rendering').replaceChildren();
    el('embedded-score').hidden = true;
  }
  function fit() {
    if (!score?.sizes?.length) return;
    const container = el('full-score-rendering');
    if (container.clientWidth <= 32 || container.clientHeight <= 32) return;
    const width = Math.max(...score.sizes.map(item => item.width));
    // Keep notation legible: fit width, and scroll vertically through the ensemble.
    const scale = Math.max(.75, (container.clientWidth - 32) / width) * score.zoom;
    for (const item of score.sizes) { item.svg.style.display = 'block'; item.svg.style.width = item.width * scale + 'px'; item.svg.style.height = item.height * scale + 'px'; }
    score.staging.style.width = width * scale + 'px';
    if (score.display) score.display.playbackScale = scale;
    el('score-zoom-label').textContent = Math.round(scale * 100) + ' %';
  }
  new ResizeObserver(fit).observe(el('full-score-rendering'));
  function resetTransport() {
    generation++; stopPlayback(); transport = null; playing = false;
    if (score) { score.display?.cursor?.hide(); score.currentMeasure = undefined; }
    setPlayIcon(false); play.disabled = !score;
    stop.disabled = !score; seek.disabled = true; seek.value = 0;
    el('ensemble-time').textContent = '0:00 / 0:00';
    busy(audioStatus, 'Detenido.', false);
  }
  async function renderPage() {
    if (!score) return;
    const state = score, token = ++rendering;
    const end = Math.min(state.pageStart + 3, state.last);
    busy(status, 'Cargando partitura · compases ' + state.pageStart + '–' + end + '…', true);
    el('score-prev').disabled = state.pageStart <= state.first;
    el('score-next').disabled = end >= state.last;
    el('score-page').textContent = 'Página ' + (Math.floor((state.pageStart - state.first) / 4) + 1) + '/' + Math.ceil((state.last - state.first + 1) / 4) + ' · compases ' + state.pageStart + '–' + end;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (token !== rendering || state !== score) return;
    const container = el('full-score-rendering'), staging = document.createElement('div');
    staging.style.width = Math.max(900, container.clientWidth - 24) + 'px';
    staging.style.position = 'absolute'; staging.style.visibility = 'hidden';
    container.append(staging);
    try {
      const pageXml = filter(state.source, null, state.pageStart + '-' + end);
      const xml = pageXml.trimStart().startsWith('<?xml') ? pageXml : '<?xml version="1.0" encoding="UTF-8"?>\n' + pageXml;
      const OSMD = window.opensheetmusicdisplay?.OpenSheetMusicDisplay;
      if (!OSMD) throw new Error('No se pudo cargar el visor. Comprueba la conexión a Internet.');
      const display = new OSMD(staging, { autoResize: false, backend: 'svg', drawTitle: false,
        drawPartNames: true, drawMeasureNumbers: true, cursorsOptions: [{ type: 3, color: '#6366f1', alpha: .25, follow: false }] });
      await display.load(xml);
      if (token !== rendering || state !== score) return;
      display.render();
      staging.style.position = ''; staging.style.visibility = '';
      state.staging = staging; state.display = display;
      state.sizes = Array.from(staging.querySelectorAll('svg')).map(svg => ({ svg, width: Number.parseFloat(svg.getAttribute('width')), height: Number.parseFloat(svg.getAttribute('height')) })).filter(item => item.width && item.height);
      container.replaceChildren(staging); container.scrollTop = 0;
      busy(status, 'Todas las voces · notación original · compases ' + state.pageStart + '–' + end, false);
      fit();
      if (state.currentMeasure !== undefined) highlightMeasure(display, state.currentMeasure, container);
    } catch (error) {
      if (token === rendering) busy(status, 'No se pudo mostrar esta página: ' + error.message, false);
    } finally { if (staging.style.visibility === 'hidden') staging.remove(); }
  }
  async function load() {
    clear(); el('embedded-score').hidden = false;
    const file = getFile(); play.disabled = true; stop.disabled = true;
    el('full-score-rendering').replaceChildren();
    busy(status, 'Cargando partitura…', true);
    try {
      const source = await getSource();
      if (file !== getFile()) return;
      const xml = new DOMParser().parseFromString(source, 'application/xml');
      const numbers = Array.from(xml.getElementsByTagName('*')).filter((item) => item.localName === 'measure')
        .map((item) => Number.parseInt(item.getAttribute('number'), 10)).filter(Number.isFinite);
      if (!numbers.length) throw new Error('La partitura no contiene compases.');
      const first = numbers.reduce((a, b) => Math.min(a, b)), last = numbers.reduce((a, b) => Math.max(a, b));
      score = { source, first, last, pageStart: first, zoom: 1 };
      play.disabled = false; stop.disabled = false;
      busy(audioStatus, 'Todas las voces · pulsa Reproducir para cargar los sonidos.', false);
      await renderPage();
    } catch (error) { if (file === getFile()) busy(status, error.message, false); }
  }
  play.addEventListener('click', async () => {
    if (!score) return;
    if (transport) { if (playing) transport.pause(); else await transport.play(); return; }
    const token = ++generation; play.disabled = true;
    busy(audioStatus, 'Cargando sonidos…', true);
    try {
      const ready = await preparePlayback(getFile(), null, (message) => {
        if (token === generation) busy(audioStatus, message, !transport);
      });
      if (token !== generation || !ready) return;
      transport = ready;
      ready.setSpeed(Number(el('ensemble-speed').value));
      ready.setVolume(Number(el('ensemble-volume').value) / 100);
      seek.max = ready.duration; seek.disabled = false;
      ready.subscribe((state) => {
        playing = state.playing; setPlayIcon(playing);
        seek.value = state.position;
        if (score && state.currentMeasure !== undefined && (score.currentMeasure !== state.currentMeasure || (state.playing && (state.currentMeasure < score.pageStart || state.currentMeasure > score.pageStart + 3)))) {
          score.currentMeasure = state.currentMeasure;
          if (state.playing && (state.currentMeasure < score.pageStart || state.currentMeasure > score.pageStart + 3)) {
            score.pageStart = score.first + Math.floor((state.currentMeasure - score.first) / 4) * 4;
            renderPage();
          } else highlightMeasure(score.display, state.currentMeasure, el('full-score-rendering'));
        }
        el('ensemble-time').textContent = clock(state.position) + ' / ' + clock(state.duration);
      });
      busy(audioStatus, 'Sonidos cargados.', false);
      await ready.play();
    } catch (error) {
      if (token === generation) {
        resetTransport();
        busy(audioStatus, error.name === 'AbortError' ? 'Carga cancelada o demasiado lenta. Puedes volver a intentarlo.' : error.message, false);
      }
    } finally { if (token === generation) play.disabled = false; }
  });
  stop.addEventListener('click', resetTransport);
  seek.addEventListener('change', () => transport?.seek(Number(seek.value)));
  el('ensemble-speed').addEventListener('change', (event) => transport?.setSpeed(Number(event.target.value)));
  el('ensemble-volume').addEventListener('input', (event) => transport?.setVolume(Number(event.target.value) / 100));
  el('score-prev').addEventListener('click', () => { if (score) { score.pageStart = Math.max(score.first, score.pageStart - 4); renderPage(); } });
  el('score-next').addEventListener('click', () => { if (score) { score.pageStart = Math.min(score.last, score.pageStart + 4); renderPage(); } });
  function zoom(delta) { if (score) { score.zoom = Math.max(.6, Math.min(2, score.zoom + delta)); fit(); } }
  el('score-zoom-out').addEventListener('click', () => zoom(-.1)); el('score-zoom-in').addEventListener('click', () => zoom(.1));
  el('score-fullscreen').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen(); else await el('embedded-score').requestFullscreen();
      await renderPage();
    } catch (_) { busy(status, 'La pantalla completa no está disponible en este navegador.', false); }
  });
  el('score-fit').addEventListener('click', () => { if (score) { score.zoom = 1; fit(); } });
  return { load, clear, stop: resetTransport };
}
