import { preparePlayback, stopPlayback } from './playback.js';

export function createScoreView({ getSource, getFile, filter }) {
  const el = (id) => document.getElementById(id);
  const status = el('full-score-status'), audioStatus = el('ensemble-status');
  const play = el('ensemble-play'), stop = el('ensemble-stop'), seek = el('ensemble-seek');
  let score, transport, playing = false, generation = 0, rendering = 0;
  const clock = (seconds) => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
  function busy(target, message, loading) {
    target.textContent = message; target.setAttribute('aria-busy', String(loading));
  }
  function resetTransport() {
    generation++; stopPlayback(); transport = null; playing = false;
    play.textContent = '▶ Reproducir'; play.disabled = !score;
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
    el('score-page').textContent = 'Compases ' + state.pageStart + '–' + end + ' de ' + state.first + '–' + state.last;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (token !== rendering || state !== score) return;
    const container = el('full-score-rendering'), staging = document.createElement('div');
    staging.style.width = Math.max(900, container.clientWidth - 24) + 'px';
    staging.style.position = 'absolute'; staging.style.visibility = 'hidden';
    container.append(staging);
    try {
      const xml = filter(state.source, null, state.pageStart + '-' + end);
      const OSMD = window.opensheetmusicdisplay?.OpenSheetMusicDisplay;
      if (!OSMD) throw new Error('No se pudo cargar el visor. Comprueba la conexión a Internet.');
      const display = new OSMD(staging, { autoResize: false, backend: 'svg', drawTitle: false,
        drawPartNames: true, drawMeasureNumbers: true });
      await display.load(xml);
      if (token !== rendering || state !== score) return;
      display.render();
      staging.style.position = ''; staging.style.visibility = '';
      staging.style.width = Math.max(900, container.clientWidth - 24) * state.zoom + 'px';
      for (const svg of staging.querySelectorAll('svg')) {
        const width = Number.parseFloat(svg.getAttribute('width'));
        const height = Number.parseFloat(svg.getAttribute('height'));
        if (width && height) { svg.style.width = width * state.zoom + 'px'; svg.style.height = height * state.zoom + 'px'; }
      }
      container.replaceChildren(staging); container.scrollTop = 0;
      busy(status, 'Todas las voces · notación original · compases ' + state.pageStart + '–' + end, false);
      el('score-zoom-label').textContent = Math.round(state.zoom * 100) + ' %';
    } catch (error) {
      if (token === rendering) busy(status, 'No se pudo mostrar esta página: ' + error.message, false);
    } finally { if (staging.style.visibility === 'hidden') staging.remove(); }
  }
  async function load() {
    resetTransport(); score = null; rendering++;
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
        playing = state.playing; play.textContent = playing ? '❚❚ Pausar' : '▶ Reproducir';
        seek.value = state.position;
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
  function zoom(delta) { if (score) { score.zoom = Math.max(.6, Math.min(2, score.zoom + delta)); renderPage(); } }
  el('score-zoom-out').addEventListener('click', () => zoom(-.1)); el('score-zoom-in').addEventListener('click', () => zoom(.1));
  el('score-fullscreen').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen(); else await el('embedded-score').requestFullscreen();
      await renderPage();
    } catch (_) { busy(status, 'La pantalla completa no está disponible en este navegador.', false); }
  });
  return { load, stop: resetTransport };
}
