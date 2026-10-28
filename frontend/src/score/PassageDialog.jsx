import React, { useEffect, useImperativeHandle, useRef, useState } from 'react';
import { displayInstrumentName } from '../labels.js';
import { filterMusicXmlPassage, parseMeasureRange } from './musicxml-passage.js';
import { nextFrame, openSheetMusicDisplay, toggleFullscreen } from './notation.js';
import { highlightMeasure } from './playback-guide.js';
import { passageTimeline, preparePlayback } from './playback.js';
import { createScoreSession } from './score-session.js';
import { Icon, TransportBar } from './TransportBar.jsx';
import { useTransport } from './useTransport.js';

const ZOOM = { min: .75, max: 1.5, step: .1 };
// Beyond the last measure of any band work: the range of a whole part.
const WHOLE_WORK = 99999;

// One instrument over a measure range: the whole passage is drawn and scrolls inside the dialog.
export function PassageDialog({ ref, session }) {
  const dialog = useRef(null), frame = useRef(null), container = useRef(null), passage = useRef(null);
  const [info, setInfo] = useState({ title: 'Partitura del pasaje', status: 'Selecciona un pasaje para abrir la partitura.', range: '', zoom: '100%', position: '' });
  const show = changes => setInfo(previous => ({ ...previous, ...changes }));
  const sessionOf = state => state?.session || session;
  const transport = useTransport({
    prepare: onStatus => preparePlayback(sessionOf(passage.current).getFile(), passage.current, onStatus),
    onPosition: measure => {
      const state = passage.current;
      if (!state || measure === state.currentMeasure) return;
      state.currentMeasure = measure;
      show({ position: 'Compás ' + measure + (state.wholePart ? '' : ' de ' + state.firstMeasure + '–' + state.lastMeasure) });
      highlightMeasure(state.renderer, measure, container.current);
    },
    stoppedMessage: '',
  });

  function stop() {
    transport.reset();
    const state = passage.current;
    state?.renderer?.cursor?.hide();
    if (state) state.currentMeasure = undefined;
    show({ position: '' });
  }

  async function render() {
    const state = passage.current;
    const { firstMeasure: first, lastMeasure: last } = state;
    show({ range: state.wholePart ? 'Parte completa · toda la obra · desplázate para revisarla'
      : 'Pasaje completo · compases ' + first + '–' + last + ' · ' + (last - first + 1) + ' compases · desplázate para revisarlos',
      status: 'Cargando el pasaje completo…' });
    await nextFrame();
    const stale = () => state !== passage.current || !dialog.current.open;
    if (stale()) return;
    const target = container.current;
    target.replaceChildren();
    const xml = filterMusicXmlPassage(state.source, state.instruments || state.instrument, first + '-' + last);
    const renderer = openSheetMusicDisplay(target, { autoResize: true, backend: 'svg', drawTitle: false,
      drawPartNames: true, drawMeasureNumbers: true, cursorsOptions: [{ type: 3, color: '#6366f1', alpha: .25, follow: false }] });
    await renderer.load(xml);
    if (stale()) return;
    renderer.render();
    state.renderer = renderer;
    const svg = target.querySelector('svg');
    if (svg) {
      svg.style.width = (state.zoom * 100) + '%';
      svg.style.maxWidth = 'none';
      renderer.playbackScale = svg.getBoundingClientRect().width / Number.parseFloat(svg.getAttribute('width'));
    }
    target.scrollTop = 0; target.scrollLeft = 0;
    if (state.currentMeasure !== undefined) highlightMeasure(renderer, state.currentMeasure, target);
    show({ zoom: Math.round(state.zoom * 100) + '%',
      status: 'Notación original · tonalidad escrita del MusicXML · ' + state.label + ' · audio en sonido real (instrumentos transpositores)' });
  }
  const rerender = () => render().catch(error => show({ status: error.message || 'No se pudo representar este pasaje.' }));

  useImperativeHandle(ref, () => ({
    // One instrument (a critical passage) or several (a rehearsal block, labelled by its section).
    // A file of its own (a passage rated by an invited musician) leaves the open work untouched;
    // wholePart shows those parts through the whole work.
    async open(selection, measureRange, label, { file = null, wholePart = false } = {}) {
      stop();
      const [firstMeasure, lastMeasure] = wholePart ? [1, WHOLE_WORK] : parseMeasureRange(measureRange);
      const instruments = Array.isArray(selection) ? selection : null;
      const instrument = instruments ? null : selection;
      const own = file ? createScoreSession() : null;
      own?.setFile(file);
      const state = { instrument, instruments, label: label || displayInstrumentName(instrument), firstMeasure, lastMeasure, zoom: 1,
        session: own, wholePart };
      passage.current = state;
      // Never show the previous passage while the new one loads.
      container.current.replaceChildren();
      show({ title: state.label + (wholePart ? ' · toda la obra' : ' · compases ' + measureRange), status: 'Cargando el pasaje completo…', range: '' });
      if (!dialog.current.open) dialog.current.showModal();
      try {
        state.source = await sessionOf(state).loadSource();
      } catch (error) {
        show({ status: error.message || 'No se pudo representar este pasaje.' });
        return;
      }
      // The score first, then the audio (2026-10-28): on Render's free plan, preparing the audio kept the server busy
      // and the score only showed about when play could start. The audio still starts before play is pressed.
      passageTimeline(sessionOf(state).getFile(), state).catch(() => {});
      try {
        if (state === passage.current) await render();
      } catch (error) {
        show({ status: error.message || 'No se pudo representar este pasaje.' });
      }
    },
    // A passage of another work: the dialog answers at once while the work loads.
    loading(label) {
      stop();
      passage.current = null;
      container.current.replaceChildren();
      show({ title: label, status: 'Cargando la obra…', range: '' });
      if (!dialog.current.open) dialog.current.showModal();
    },
    failed: message => show({ status: message }),
    getPassage: () => passage.current,
    highlight: measure => highlightMeasure(passage.current?.renderer, measure, container.current),
    stop,
  }));

  // Closing by button, Escape or code always stops the passage audio.
  useEffect(() => {
    const node = dialog.current;
    const closed = async () => {
      stop();
      if (document.fullscreenElement === frame.current) await document.exitFullscreen();
    };
    node.addEventListener('close', closed);
    return () => node.removeEventListener('close', closed);
  });

  const zoomTo = value => {
    const state = passage.current;
    if (!state) return;
    state.zoom = Math.max(ZOOM.min, Math.min(ZOOM.max, value));
    rerender();
  };
  const fullscreen = async () => {
    try { await toggleFullscreen(frame.current); await render(); }
    catch { transport.reset('La pantalla completa no está disponible en este navegador.'); }
  };

  return <dialog id="notation-dialog" ref={dialog} className="score-dialog" aria-labelledby="notation-title">
    <div id="passage-view" ref={frame} className="passage-view">
      <div className="score-dialog-head">
        <div>
          <h2 id="notation-title">{info.title}</h2>
          <p id="notation-status" className="score-dialog-status">{info.status}</p>
        </div>
        <button id="notation-close" className="score-tool score-close" type="button" aria-label="Cerrar partitura" title="Cerrar partitura"
          onClick={() => dialog.current.close()}><Icon path="m6 4 6 6 6-6 2 2-6 6 6 6-2 2-6-6-6 6-2-2 6-6-6-6z" /></button>
      </div>
      <TransportBar prefix="passage" group label="Reproducción del pasaje" volumeLabel="Volumen del pasaje" seekLabel="Posición del pasaje"
        fullscreenId="passage-fullscreen" transport={transport} onStop={stop} onFullscreen={fullscreen} />
      <div className="passage-progress">
        <output id="passage-position" className="score-page-label" aria-live="polite">{info.position}</output>
        <span id="playback-status" className="loading-status" role="status" aria-live="polite" aria-busy={transport.loading}>{transport.status}</span>
      </div>
      <div id="notation-score" ref={container} className="score-rendering" />
      <div className="score-toolbar" aria-label="Controles de partitura">
        <span id="notation-page-label" className="score-page-label">{info.range}</span>
        <button id="notation-zoom-out" className="score-tool" type="button" aria-label="Reducir zoom" title="Reducir zoom"
          onClick={() => zoomTo((passage.current?.zoom ?? 1) - ZOOM.step)}>−</button>
        <button id="notation-fit" className="score-tool" type="button" aria-label="Ajustar al ancho" title="Ajustar al ancho"
          onClick={() => zoomTo(1)}><Icon path="M5 2h14v20H5zm2 2v16h10V4zM9 7h6v2H9zm0 4h6v2H9z" /></button>
        <output id="notation-zoom-label">{info.zoom}</output>
        <button id="notation-zoom-in" className="score-tool" type="button" aria-label="Ampliar zoom" title="Ampliar zoom"
          onClick={() => zoomTo((passage.current?.zoom ?? 1) + ZOOM.step)}>+</button>
      </div>
    </div>
  </dialog>;
}
